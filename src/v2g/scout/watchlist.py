"""Watchlist Monitor + Draft Agent.

按固定 X 账号名单做小时级监控，筛出新信号后生成中文发推草稿。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tomllib
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from xml.sax.saxutils import escape

import click

from v2g.scout.store import ScoutStore
from v2g.scout.twitter_monitor import _normalize_tweet, _search_one_query, rule_filter
from v2g.scout.x_publisher import TweetDraft, run_draft_publish, validate_draft

WATCHLIST_TWEET_SOURCE = "watchlist_tweet"
WATCHLIST_TOPIC_SOURCE = "watchlist_topic"
WATCHLIST_PLIST_LABEL = "com.v2g.watchlist"
WATCHLIST_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{WATCHLIST_PLIST_LABEL}.plist"
WATCHLIST_LOG_DIR = Path.home() / ".v2g"

_GROUP_LABELS = {
    "daily": "每天必看",
    "trigger": "事件触发",
    "context": "叙事补充",
    "manual": "手动覆盖",
}

_DEFAULT_CONFIG_PATH = Path("config/watchlist.toml")
_DEFAULT_WATCHLIST = {
    "since_hours": 1,
    "min_likes": 0,
    "max_tweets": 120,
    "drafts_per_run": 3,
    "publish_count": 1,
    "keywords": [
        "AI",
        "agent",
        "semiconductor",
        "inference",
        "datacenter",
        "compute",
    ],
    "editorial_principle": (
        "Karpathy / SemiAnalysis / Serenity 给你选题，"
        "Musk / Trump / Sacks 给你催化剂，财报和行业报告给你事实验证。"
    ),
    "groups": {},
    "few_shots": [],
}

WATCHLIST_SOURCE_TYPES = {
    "person",
    "company",
    "research_firm",
    "news",
    "policy",
    "market_signal",
}
WATCHLIST_ACTIONS = {"write", "watch", "skip"}
WATCHLIST_CONFIDENCE = {"high", "medium", "low"}

WATCHLIST_CANDIDATE_FIELDS = [
    "source_account",
    "source_url",
    "source_type",
    "raw_event",
    "one_line_summary",
    "why_now",
    "industry_chain_mapping",
    "related_tickers",
    "bottleneck_logic",
    "market_mispricing_angle",
    "what_to_verify",
    "counter_argument",
    "confidence",
    "recommended_action",
    "tweet_hooks",
    "draft_short",
    "draft_thread",
]

_GENERIC_DRAFT_PATTERNS = (
    "AI 基建是一张供应链网络",
    "基础设施越来越重要",
    "模型竞争转向工程化",
    "AI 行业正在发展",
    "值得关注",
    "可能产生影响",
)

_CONCRETE_TECH_TERMS = (
    "SKC",
    "Absolics",
    "TrendForce",
    "AMAT",
    "AMD",
    "AWS",
    "CoWoS",
    "HBM",
    "CPO",
    "GPU",
    "ASIC",
    "NVLink",
    "TSMC",
    "Nvidia",
    "Broadcom",
    "Marvell",
    "glass substrate",
    "玻璃基板",
    "先进封装",
    "封装",
    "基板",
    "光通信",
    "电力",
    "数据中心",
    "grep timeout",
    "runtime",
)


def _resolve_vault(cfg) -> Path:
    p = getattr(cfg, "obsidian_vault_path", Path(""))
    if p and str(p) not in ("", "."):
        return Path(p)
    return Path("output")


def _config_path(cfg, explicit_path: str | None = None) -> Path:
    if explicit_path:
        return Path(explicit_path)
    return Path(getattr(cfg, "watchlist_config_path", _DEFAULT_CONFIG_PATH))


def load_watchlist_config(path: Path) -> dict:
    """读取 TOML 配置；文件不存在时返回安全默认值。"""
    data = dict(_DEFAULT_WATCHLIST)
    data["keywords"] = list(_DEFAULT_WATCHLIST["keywords"])
    data["groups"] = {}
    data["few_shots"] = []

    if not path.exists():
        return data

    with path.open("rb") as f:
        raw = tomllib.load(f)

    for key in ("since_hours", "min_likes", "max_tweets", "drafts_per_run", "publish_count"):
        if key in raw:
            data[key] = raw[key]
    if "editorial_principle" in raw:
        data["editorial_principle"] = str(raw["editorial_principle"])
    if "keywords" in raw:
        data["keywords"] = raw["keywords"]
    if isinstance(raw.get("groups"), dict):
        data["groups"] = raw["groups"]
    if isinstance(raw.get("few_shots"), list):
        data["few_shots"] = raw["few_shots"]
    return data


def _normalize_author(raw: str) -> str:
    token = raw.strip().strip(",;")
    if not token:
        return ""
    if "://" in token or token.startswith(("x.com/", "twitter.com/")):
        parsed = urlparse(token if "://" in token else f"https://{token}")
        path = parsed.path.strip("/")
        token = path.split("/", 1)[0] if path else ""
    token = token.strip().lstrip("@")
    return re.sub(r"[^A-Za-z0-9_]", "", token)


def _split_handles(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        parts = [str(item) for item in value]
    else:
        parts = re.split(r"[,;\s]+", str(value))
    seen: set[str] = set()
    handles: list[str] = []
    for part in parts:
        handle = _normalize_author(part)
        key = handle.lower()
        if handle and key not in seen:
            seen.add(key)
            handles.append(handle)
    return handles


def build_author_groups(
    cfg,
    authors_override: str | None = None,
    watchlist_config: dict | None = None,
) -> dict[str, list[str]]:
    """从配置构建账号分组；命令行 --authors 会覆盖三组默认名单。"""
    if authors_override:
        return {"manual": _split_handles(authors_override)}

    watchlist_config = watchlist_config or load_watchlist_config(_config_path(cfg))
    groups = {
        name: _split_handles(authors)
        for name, authors in (watchlist_config.get("groups") or {}).items()
    }
    return {name: authors for name, authors in groups.items() if authors}


def _parse_tweet_time(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        ts = float(value)
        if ts > 10_000_000_000:
            ts /= 1000
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    else:
        text = str(value).strip()
        dt = None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            pass
        if dt is None:
            try:
                dt = parsedate_to_datetime(text)
            except (TypeError, ValueError, IndexError):
                return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def filter_since(tweets: list[dict], since_hours: int, now: datetime | None = None) -> list[dict]:
    """只保留最近 N 小时的推文；无法解析时间的推文保留。"""
    if since_hours <= 0:
        return tweets
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = now.astimezone(timezone.utc) - timedelta(hours=since_hours)
    result = []
    for tweet in tweets:
        dt = _parse_tweet_time(tweet.get("created_at"))
        if dt is None or dt >= cutoff:
            result.append(tweet)
    return result


def watchlist_rule_filter(tweets: list[dict], min_likes: int = 0) -> list[dict]:
    """Watchlist 专用粗筛：保留低互动但高信息密度账号的内容。"""
    filtered = rule_filter(tweets, min_likes=min_likes)
    result = []
    for tweet in filtered:
        text = (tweet.get("text") or "").strip()
        if text.startswith("@") and len(text) < 80:
            continue
        if re.fullmatch(r"https?://\S+", text):
            continue
        result.append(tweet)
    return result


def fetch_watchlist_tweets(
    api_key: str,
    groups: dict[str, list[str]],
    max_tweets: int = 120,
    max_pages: int = 1,
) -> list[dict]:
    """按账号 Latest 抓取推文并归一化。"""
    if not api_key:
        raise click.ClickException("TWITTER_API_IO_KEY 未设置")

    authors = [(group, author) for group, values in groups.items() for author in values]
    if not authors:
        raise click.ClickException("Watchlist 账号为空，请配置 WATCHLIST_*_AUTHORS 或传 --authors")

    per_author = max(5, min(30, max_tweets // max(len(authors), 1)))
    all_tweets: dict[str, dict] = {}

    for group, author in authors:
        click.echo(f"   🔎 [{_GROUP_LABELS.get(group, group)}] @{author}")
        raw_tweets = _search_one_query(
            api_key,
            f"from:{author}",
            query_type="Latest",
            max_items=per_author,
            max_pages=max_pages,
        )
        for raw in raw_tweets:
            tweet = _normalize_tweet(raw)
            tweet_id = tweet.get("tweet_id")
            if not tweet_id:
                continue
            tweet["watch_group"] = group
            tweet["watch_author"] = author
            all_tweets.setdefault(tweet_id, tweet)

    tweets = list(all_tweets.values())
    tweets.sort(
        key=lambda t: _parse_tweet_time(t.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return tweets[:max_tweets]


def _build_user_message(
    tweets: list[dict],
    max_drafts: int,
    principle: str,
    keywords: str | list[str],
    few_shots: list[dict] | None = None,
) -> str:
    keyword_text = ", ".join(str(k) for k in keywords) if isinstance(keywords, list) else str(keywords)
    lines = [
        f"最多生成 {max_drafts} 条可发布草稿。",
        f"编辑原则: {principle}",
    ]
    if keyword_text:
        lines.append(f"关注关键词: {keyword_text}")
    lines.append("")

    if few_shots:
        lines.append("## Few-shot 风格样例")
        lines.append("下面是风格参考：模仿结构和判断密度，不要复制具体事实。")
        lines.append("")
        for idx, shot in enumerate(few_shots[:6], start=1):
            lines.append(f"### 样例 {idx}: {shot.get('name', 'unnamed')}")
            if shot.get("signal"):
                lines.append(f"信号: {str(shot['signal']).strip()}")
            if shot.get("bad"):
                lines.append(f"不要这样: {str(shot['bad']).strip()}")
            if shot.get("good"):
                lines.append(f"参考写法: {str(shot['good']).strip()}")
            lines.append("")

    lines.append("## Watchlist 推文")

    for idx, tweet in enumerate(tweets[:40], start=1):
        group = tweet.get("watch_group", "")
        author = tweet.get("author") or tweet.get("watch_author", "")
        text = re.sub(r"\s+", " ", tweet.get("text", "")).strip()
        lines.extend([
            f"[{idx}] id={tweet.get('tweet_id', '')} group={group} @{author}",
            f"created_at={tweet.get('created_at', '')} likes={tweet.get('likes', 0)} retweets={tweet.get('retweets', 0)} replies={tweet.get('replies', 0)}",
            f"url={tweet.get('url', '')}",
            text[:700],
            "",
        ])
    return "\n".join(lines)


def _as_str(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _as_list(value: Any) -> list:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _normalize_related_tickers(value: Any) -> dict[str, list[str]]:
    value = value if isinstance(value, dict) else {}
    result: dict[str, list[str]] = {}
    for key in ("direct", "indirect", "sentiment"):
        seen: set[str] = set()
        items: list[str] = []
        for item in _as_list(value.get(key)):
            token = _as_str(item)
            if not token:
                continue
            token = token if token.startswith("$") else token
            norm = token.upper().lstrip("$")
            if norm not in seen:
                seen.add(norm)
                items.append(token)
        result[key] = items
    return result


def _normalize_candidate(candidate: dict) -> dict:
    """把 LLM 输出整理成稳定 schema，缺字段补空值。"""
    out = {field: candidate.get(field) for field in WATCHLIST_CANDIDATE_FIELDS}
    out["source_account"] = _as_str(out["source_account"])
    out["source_url"] = _as_str(out["source_url"])
    out["source_type"] = _as_str(out["source_type"]) or "market_signal"
    if out["source_type"] not in WATCHLIST_SOURCE_TYPES:
        out["source_type"] = "market_signal"

    for field in (
        "raw_event",
        "one_line_summary",
        "why_now",
        "industry_chain_mapping",
        "bottleneck_logic",
        "market_mispricing_angle",
        "counter_argument",
        "draft_short",
    ):
        out[field] = _as_str(out[field])

    out["related_tickers"] = _normalize_related_tickers(out["related_tickers"])
    out["what_to_verify"] = [_as_str(x) for x in _as_list(out["what_to_verify"]) if _as_str(x)]
    out["tweet_hooks"] = [_as_str(x) for x in _as_list(out["tweet_hooks"]) if _as_str(x)]
    out["draft_thread"] = [_as_str(x) for x in _as_list(out["draft_thread"]) if _as_str(x)]

    out["confidence"] = _as_str(out["confidence"]).lower() or "medium"
    if out["confidence"] not in WATCHLIST_CONFIDENCE:
        out["confidence"] = "medium"
    out["recommended_action"] = _as_str(out["recommended_action"]).lower() or "watch"
    if out["recommended_action"] not in WATCHLIST_ACTIONS:
        out["recommended_action"] = "watch"
    return out


def _legacy_topic_to_candidate(topic: dict) -> dict:
    """兼容旧 topics/drafts 结构，避免已有测试/产物完全不可读。"""
    drafts = topic.get("drafts") if isinstance(topic.get("drafts"), list) else []
    first = drafts[0] if drafts and isinstance(drafts[0], dict) else {}
    return _normalize_candidate({
        "source_account": "",
        "source_url": first.get("source_url", ""),
        "source_type": "market_signal",
        "raw_event": topic.get("summary") or topic.get("reason") or topic.get("title") or "",
        "one_line_summary": topic.get("summary") or topic.get("title") or "",
        "why_now": "",
        "industry_chain_mapping": "",
        "related_tickers": {"direct": [], "indirect": [], "sentiment": []},
        "bottleneck_logic": "",
        "market_mispricing_angle": "",
        "what_to_verify": [],
        "counter_argument": "",
        "confidence": "low",
        "recommended_action": "watch",
        "tweet_hooks": [],
        "draft_short": first.get("text", ""),
        "draft_thread": [],
    })


def _normalize_plan(data: dict) -> dict:
    if not isinstance(data, dict):
        return {"candidates": []}
    raw_candidates = data.get("candidates")
    if isinstance(raw_candidates, list):
        candidates = [
            _normalize_candidate(c)
            for c in raw_candidates
            if isinstance(c, dict)
        ]
    elif isinstance(data.get("topics"), list):
        candidates = [
            _legacy_topic_to_candidate(t)
            for t in data["topics"]
            if isinstance(t, dict)
        ]
    else:
        candidates = []
    return {"candidates": candidates}


def _validate_plan(data: dict) -> bool:
    data = _normalize_plan(data)
    if not isinstance(data, dict):
        return False
    candidates = data.get("candidates")
    if not isinstance(candidates, list):
        return False
    for candidate in candidates:
        if not isinstance(candidate, dict):
            return False
        for field in WATCHLIST_CANDIDATE_FIELDS:
            if field not in candidate:
                return False
        if not isinstance(candidate.get("related_tickers"), dict):
            return False
        if not isinstance(candidate.get("what_to_verify"), list):
            return False
        if not isinstance(candidate.get("tweet_hooks"), list):
            return False
        if not isinstance(candidate.get("draft_thread"), list):
            return False
    return True


def _candidate_text(candidate: dict) -> str:
    parts = [
        candidate.get("source_account", ""),
        candidate.get("raw_event", ""),
        candidate.get("one_line_summary", ""),
        candidate.get("why_now", ""),
        candidate.get("industry_chain_mapping", ""),
        candidate.get("bottleneck_logic", ""),
        candidate.get("market_mispricing_angle", ""),
        candidate.get("counter_argument", ""),
        candidate.get("draft_short", ""),
        "\n".join(candidate.get("tweet_hooks") or []),
        "\n".join(candidate.get("draft_thread") or []),
    ]
    tickers = candidate.get("related_tickers") or {}
    for group in ("direct", "indirect", "sentiment"):
        parts.extend(tickers.get(group) or [])
    parts.extend(candidate.get("what_to_verify") or [])
    return "\n".join(_as_str(p) for p in parts if _as_str(p))


def _count_concrete_terms(candidate: dict) -> int:
    text = _candidate_text(candidate)
    terms: set[str] = set()
    for term in _CONCRETE_TECH_TERMS:
        if term.lower() in text.lower():
            terms.add(term.lower())
    for token in re.findall(r"\$?[A-Z][A-Z0-9]{1,8}(?:\.[A-Z])?", text):
        cleaned = token.lstrip("$")
        if cleaned not in {"AI", "X", "CEO", "GPU"}:
            terms.add(cleaned)
    for token in re.findall(r"@[A-Za-z0-9_]{2,20}", text):
        terms.add(token.lower())
    return len(terms)


def _has_timeline_or_catalyst(candidate: dict) -> bool:
    text = "\n".join([
        candidate.get("raw_event", ""),
        candidate.get("why_now", ""),
        "\n".join(candidate.get("what_to_verify") or []),
    ])
    patterns = (
        r"\bH[12]\s*20\d{2}\b",
        r"\bQ[1-4]\s*20\d{2}\b",
        r"\b20\d{2}\b",
        r"\b\d+[月日]\b",
        r"量产|测试|验证|订单|财报|发布|监管|政策|capex|产能|爬坡|窗口|催化",
    )
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


def _has_related_tickers(candidate: dict) -> bool:
    tickers = candidate.get("related_tickers") or {}
    return any(tickers.get(group) for group in ("direct", "indirect", "sentiment"))


def _field_has_content(candidate: dict, field: str, min_len: int = 12) -> bool:
    return len(_as_str(candidate.get(field))) >= min_len


def _passes_min_signal_criteria(candidate: dict) -> tuple[int, list[str]]:
    """至少满足 3 个信号维度，否则不应生成正式 draft。"""
    checks = {
        "specific_entity": bool(candidate.get("source_account")) or _count_concrete_terms(candidate) >= 1,
        "timeline_or_catalyst": _has_timeline_or_catalyst(candidate),
        "industry_chain_position": _field_has_content(candidate, "industry_chain_mapping"),
        "ticker_or_beneficiary": _has_related_tickers(candidate),
        "mispricing_angle": _field_has_content(candidate, "market_mispricing_angle"),
        "risk_or_verification": bool(candidate.get("what_to_verify")) or _field_has_content(candidate, "counter_argument", 8),
    }
    passed = [name for name, ok in checks.items() if ok]
    failed = [name for name, ok in checks.items() if not ok]
    return len(passed), failed


def _has_generic_draft(candidate: dict) -> bool:
    text = "\n".join([
        candidate.get("draft_short", ""),
        "\n".join(candidate.get("draft_thread") or []),
    ])
    return any(pattern in text for pattern in _GENERIC_DRAFT_PATTERNS)


def quality_check_candidate(candidate: dict) -> list[str]:
    """Post-generation quality gate for write candidates."""
    issues: list[str] = []
    action = candidate.get("recommended_action")

    if action == "skip":
        return issues

    criteria_count, missing = _passes_min_signal_criteria(candidate)
    if action == "write" and criteria_count < 3:
        issues.append(
            "formal_draft_requires_three_signal_criteria:"
            + ",".join(missing)
        )

    if action == "write" and _count_concrete_terms(candidate) < 2:
        issues.append("missing_two_concrete_terms")

    if action == "write" and not _field_has_content(candidate, "industry_chain_mapping"):
        issues.append("missing_industry_chain_mapping")

    if action == "write" and not _field_has_content(candidate, "why_now"):
        issues.append("missing_why_now")

    if action == "write" and not (
        bool(candidate.get("what_to_verify"))
        or _field_has_content(candidate, "counter_argument", 8)
    ):
        issues.append("missing_counter_argument_or_verification")

    if action == "write" and _has_generic_draft(candidate):
        issues.append("generic_or_banned_draft_expression")

    if action == "write":
        short_len = len(_as_str(candidate.get("draft_short")))
        if not (280 <= short_len <= 500):
            issues.append("draft_short_must_be_280_to_500_chars")

    if action == "write":
        thread = candidate.get("draft_thread") or []
        if not (3 <= len(thread) <= 6):
            issues.append("draft_thread_must_have_3_to_6_tweets")
        if any(len(str(tweet)) > 280 for tweet in thread):
            issues.append("draft_thread_tweet_too_long")

    return issues


def _annotate_quality(plan: dict) -> dict:
    candidates = []
    for candidate in plan.get("candidates", []):
        c = dict(candidate)
        issues = quality_check_candidate(c)
        c["quality_issues"] = issues
        c["quality_passed"] = not issues
        candidates.append(c)
    return {"candidates": candidates}


def _downgrade_failed_candidates(plan: dict) -> dict:
    candidates = []
    for candidate in plan.get("candidates", []):
        c = dict(candidate)
        issues = quality_check_candidate(c)
        if c.get("recommended_action") == "write" and issues:
            criteria_count, _ = _passes_min_signal_criteria(c)
            c["recommended_action"] = "watch" if criteria_count >= 2 else "skip"
            if c["recommended_action"] == "skip":
                c["draft_short"] = ""
                c["draft_thread"] = []
        c["quality_issues"] = quality_check_candidate(c)
        c["quality_passed"] = not c["quality_issues"]
        candidates.append(c)
    return {"candidates": candidates}


def _build_rewrite_message(
    original_message: str,
    plan: dict,
    quality_issues: dict[int, list[str]],
) -> str:
    return (
        original_message
        + "\n\n## 初稿质量问题\n"
        + "下面是你上一版 JSON 中未通过质量门禁的 candidate index 和问题。"
        + "请只输出完整 JSON 对象，保留 schema，重写不合格候选；"
        + "如果信息不足，请把 recommended_action 改成 watch 或 skip，不要硬写。\n\n"
        + json.dumps(
            {
                "quality_issues": quality_issues,
                "previous_plan": plan,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _rewrite_watchlist_plan_once(
    cfg,
    original_message: str,
    plan: dict,
    quality_issues: dict[int, list[str]],
) -> dict | None:
    from v2g.llm import call_llm
    from v2g.scout import _load_prompt
    from v2g.scriptwriter import _extract_json

    click.echo("   🔁 质量门禁未通过，要求 LLM 重写一次...")
    raw = call_llm(
        _load_prompt("scout_watchlist.md"),
        _build_rewrite_message(original_message, plan, quality_issues),
        cfg.scout_model,
        temperature=0.35,
        max_tokens=6000,
    )
    return _normalize_plan(_extract_json(raw))


def generate_watchlist_plan(
    cfg,
    tweets: list[dict],
    max_drafts: int,
    principle: str,
    keywords: str | list[str],
    few_shots: list[dict] | None = None,
) -> dict | None:
    """调用 LLM 从 watchlist 推文生成话题和草稿。"""
    from v2g.llm import call_llm
    from v2g.scout import _load_prompt
    from v2g.scriptwriter import _extract_json

    if not tweets:
        return None

    user_message = _build_user_message(tweets, max_drafts, principle, keywords, few_shots)
    raw = call_llm(
        _load_prompt("scout_watchlist.md"),
        user_message,
        cfg.scout_model,
        temperature=0.55,
        max_tokens=7000,
    )
    data = _normalize_plan(_extract_json(raw))
    if not _validate_plan(data):
        click.echo("   ⚠️ Watchlist 草稿 JSON 结构校验未通过")
        return None

    checked = _annotate_quality(data)
    write_failures = {
        idx: c.get("quality_issues", [])
        for idx, c in enumerate(checked.get("candidates", []))
        if c.get("recommended_action") == "write" and c.get("quality_issues")
    }
    if write_failures:
        repaired = _rewrite_watchlist_plan_once(cfg, user_message, checked, write_failures)
        if repaired and _validate_plan(repaired):
            checked = _annotate_quality(repaired)

    checked = _downgrade_failed_candidates(checked)
    return checked


def _topic_item_id(topic: dict) -> str:
    tickers = topic.get("related_tickers") or {}
    ticker_key = ",".join(
        str(x)
        for group in ("direct", "indirect", "sentiment")
        for x in (tickers.get(group) or [])
    )
    key = str(
        topic.get("source_url")
        or topic.get("raw_event")
        or topic.get("one_line_summary")
        or ticker_key
    ).strip().lower()
    if not key:
        key = topic.get("source_account", "") + "|" + topic.get("industry_chain_mapping", "")
    key = re.sub(r"\s+", " ", key)
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _filter_new_topics(
    store: ScoutStore,
    topics: list[dict],
    force: bool = False,
) -> tuple[list[dict], list[dict]]:
    kept: list[dict] = []
    skipped: list[dict] = []
    for topic in topics:
        item_id = _topic_item_id(topic)
        topic["_topic_item_id"] = item_id
        if not force and store.is_seen(WATCHLIST_TOPIC_SOURCE, item_id):
            skipped.append(topic)
        else:
            kept.append(topic)
    return kept, skipped


def build_watchlist_drafts(
    candidates: list[dict],
    source_file: str,
    max_drafts: int,
) -> list[TweetDraft]:
    drafts: list[TweetDraft] = []
    for candidate in candidates:
        if candidate.get("recommended_action") != "write":
            continue
        if candidate.get("quality_issues"):
            continue

        thread = [
            str(t).strip()
            for t in (candidate.get("draft_thread") or [])
            if str(t).strip()
        ]
        short = str(candidate.get("draft_short") or "").strip()
        tweets = thread or ([short] if short else [])
        if not tweets:
            continue

        drafts.append(
            TweetDraft(
                source_type="watchlist",
                tweets=tweets,
                source_file=source_file,
                topic=str(candidate.get("one_line_summary") or candidate.get("raw_event") or ""),
                version="thread" if thread else "short",
                metadata={
                    "topic_item_id": candidate.get("_topic_item_id", ""),
                    "source_account": candidate.get("source_account", ""),
                    "source_url": candidate.get("source_url", ""),
                    "source_type": candidate.get("source_type", ""),
                    "related_tickers": candidate.get("related_tickers", {}),
                    "confidence": candidate.get("confidence", ""),
                    "candidate": candidate,
                },
            )
        )
        if len(drafts) >= max_drafts:
            return drafts
    return drafts


def _output_paths(vault: Path, now: datetime) -> tuple[Path, Path]:
    stamp = now.astimezone().strftime("%Y-%m-%d-%H%M")
    base = vault / "scout" / "watchlist"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{stamp}-watchlist.md", base / f"{stamp}-watchlist.json"


def _policy_records(drafts: list[TweetDraft]) -> list[dict]:
    records = []
    for draft in drafts:
        issues = validate_draft(draft)
        records.append({
            "topic": draft.topic,
            "version": draft.version,
            "tweets": draft.normalized_tweets(),
            "content_hash": draft.content_hash,
            "metadata": draft.metadata,
            "publishable": not any(issue.severity == "error" for issue in issues),
            "policy_issues": [issue.__dict__ for issue in issues],
        })
    return records


def render_watchlist_md(payload: dict) -> str:
    lines = [
        "---",
        f"generated_at: {payload.get('generated_at', '')}",
        "type: watchlist",
        "tags: [watchlist, twitter, draft]",
        "---",
        "",
        "# Watchlist Drafts",
        "",
        f"编辑原则: {payload.get('principle', '')}",
        "",
        "## Source Tweets",
        "",
    ]
    for tweet in payload.get("source_tweets", []):
        author = tweet.get("author") or tweet.get("watch_author", "")
        group = tweet.get("watch_group", "")
        url = tweet.get("url", "")
        text = re.sub(r"\s+", " ", tweet.get("text", "")).strip()
        lines.append(f"### [{_GROUP_LABELS.get(group, group)}] @{author}")
        lines.append(f"likes={tweet.get('likes', 0)} retweets={tweet.get('retweets', 0)} replies={tweet.get('replies', 0)}")
        lines.append(f"> {text[:500]}")
        if url:
            lines.append(f"[source]({url})")
        lines.append("")

    lines.extend(["## Candidates", ""])
    for idx, candidate in enumerate(payload.get("candidates", []), start=1):
        action = candidate.get("recommended_action", "")
        confidence = candidate.get("confidence", "")
        status = "passed" if candidate.get("quality_passed") else "needs-review"
        lines.append(f"### Candidate {idx}: {candidate.get('one_line_summary', '')}")
        lines.append(f"Action: `{action}` · Confidence: `{confidence}` · Quality: `{status}`")
        if candidate.get("source_account"):
            lines.append(f"Source: {candidate.get('source_account')} ({candidate.get('source_type', '')})")
        if candidate.get("source_url"):
            lines.append(f"[source]({candidate.get('source_url')})")
        if candidate.get("raw_event"):
            lines.append(f"Raw event: {candidate['raw_event']}")
        if candidate.get("why_now"):
            lines.append(f"Why now: {candidate['why_now']}")
        if candidate.get("industry_chain_mapping"):
            lines.append(f"Industry chain: {candidate['industry_chain_mapping']}")
        tickers = candidate.get("related_tickers") or {}
        ticker_parts = []
        for group in ("direct", "indirect", "sentiment"):
            values = tickers.get(group) or []
            if values:
                ticker_parts.append(f"{group}: {', '.join(values)}")
        if ticker_parts:
            lines.append("Tickers: " + " | ".join(ticker_parts))
        if candidate.get("bottleneck_logic"):
            lines.append(f"Bottleneck: {candidate['bottleneck_logic']}")
        if candidate.get("market_mispricing_angle"):
            lines.append(f"Mispricing: {candidate['market_mispricing_angle']}")
        if candidate.get("what_to_verify"):
            lines.append("Verify:")
            for item in candidate["what_to_verify"]:
                lines.append(f"- {item}")
        if candidate.get("counter_argument"):
            lines.append(f"Counter: {candidate['counter_argument']}")
        issues = candidate.get("quality_issues") or []
        if issues:
            lines.append("Quality issues:")
            for issue in issues:
                lines.append(f"- {issue}")
        hooks = candidate.get("tweet_hooks") or []
        if hooks:
            lines.append("Hooks:")
            for hook in hooks:
                lines.append(f"- {hook}")
        if candidate.get("draft_short"):
            lines.append("")
            lines.append("Draft short:")
            lines.append(f"> {candidate['draft_short']}")
        thread = candidate.get("draft_thread") or []
        if thread:
            lines.append("")
            lines.append("Draft thread:")
            for i, tweet in enumerate(thread, start=1):
                lines.append(f"{i}. {tweet}")
        lines.append("")

    skipped = payload.get("skipped_topics") or []
    if skipped:
        lines.extend(["## Skipped Duplicate Topics", ""])
        for topic in skipped:
            lines.append(f"- {topic.get('one_line_summary', '')} ({topic.get('source_url', '')})")
        lines.append("")

    lines.extend(["## Drafts", ""])
    for idx, draft in enumerate(payload.get("drafts", []), start=1):
        status = "publishable" if draft.get("publishable") else "blocked"
        lines.append(f"### Draft {idx}: {draft.get('topic', '')} ({status})")
        for tweet in draft.get("tweets", []):
            lines.append(f"> {tweet}")
        issues = draft.get("policy_issues") or []
        if issues:
            lines.append("")
            lines.append("Policy issues:")
            for issue in issues:
                lines.append(f"- {issue.get('code')}: {issue.get('message')}")
        lines.append("")
    return "\n".join(lines)


def _write_outputs(
    md_path: Path,
    json_path: Path,
    payload: dict,
) -> None:
    md_path.write_text(render_watchlist_md(payload), encoding="utf-8")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _mark_processed(
    store: ScoutStore,
    tweets: list[dict],
    topics: list[dict],
) -> None:
    if tweets:
        store.mark_seen_batch(WATCHLIST_TWEET_SOURCE, tweets, lambda t: t["tweet_id"])
    for topic in topics:
        store.mark_seen(
            WATCHLIST_TOPIC_SOURCE,
            topic["_topic_item_id"],
            {
                "one_line_summary": topic.get("one_line_summary", ""),
                "source_account": topic.get("source_account", ""),
                "source_url": topic.get("source_url", ""),
                "recommended_action": topic.get("recommended_action", ""),
                "related_tickers": topic.get("related_tickers", {}),
            },
        )


def run_watchlist(
    cfg,
    authors: str | None = None,
    config_path: str | None = None,
    since_hours: int | None = None,
    min_likes: int | None = None,
    max_tweets: int | None = None,
    max_drafts: int | None = None,
    dry_run: bool = True,
    force: bool = False,
    yes: bool = False,
    mark_seen: bool = True,
    publish_count: int | None = None,
) -> Path | None:
    """Watchlist 主流程。dry_run=True 表示只预览/写草稿，不真实发帖。"""
    click.echo("🛰️ Watchlist Monitor + Draft Agent")

    loaded_config = load_watchlist_config(_config_path(cfg, config_path))
    groups = build_author_groups(cfg, authors, loaded_config)
    author_count = sum(len(v) for v in groups.values())
    if author_count == 0:
        raise click.ClickException("Watchlist 账号为空")

    since_hours = since_hours if since_hours is not None else int(loaded_config.get("since_hours", 1))
    min_likes = min_likes if min_likes is not None else int(loaded_config.get("min_likes", 0))
    max_tweets = max_tweets if max_tweets is not None else int(loaded_config.get("max_tweets", 120))
    max_drafts = max_drafts if max_drafts is not None else int(loaded_config.get("drafts_per_run", 3))
    publish_count = publish_count if publish_count is not None else int(loaded_config.get("publish_count", 1))
    principle = str(loaded_config.get("editorial_principle", ""))
    keywords = loaded_config.get("keywords", [])
    few_shots = loaded_config.get("few_shots", [])

    click.echo(f"   账号: {author_count} 个，窗口: 最近 {since_hours} 小时，最多抓取: {max_tweets}")
    click.echo(f"   发布模式: {'dry-run' if dry_run else 'publish'}")

    api_key = os.environ.get("TWITTER_API_IO_KEY", "")
    fetched = fetch_watchlist_tweets(api_key, groups, max_tweets=max_tweets)
    recent = filter_since(fetched, since_hours)
    click.echo(f"   📥 抓取 {len(fetched)} 条，时间窗口内 {len(recent)} 条")

    with ScoutStore(cfg.scout_db_path) as store:
        new_tweets = recent if force else store.filter_new(
            WATCHLIST_TWEET_SOURCE,
            recent,
            lambda t: t["tweet_id"],
        )
        click.echo(f"   🆕 新推文: {len(new_tweets)} / {len(recent)}")
        if not new_tweets:
            return None

        filtered = watchlist_rule_filter(new_tweets, min_likes=min_likes)
        click.echo(f"   🎯 粗筛后: {len(filtered)}")
        if not filtered:
            if mark_seen:
                store.mark_seen_batch(WATCHLIST_TWEET_SOURCE, new_tweets, lambda t: t["tweet_id"])
            return None

        click.echo("   🤖 生成 watchlist 草稿...")
        plan = generate_watchlist_plan(cfg, filtered, max_drafts, principle, keywords, few_shots)
        if not plan:
            return None
        plan = _annotate_quality(_normalize_plan(plan))

        candidates, skipped = _filter_new_topics(store, plan.get("candidates", []), force=force)
        if skipped:
            click.echo(f"   ⏭️ 跳过重复候选: {len(skipped)}")
        if not candidates:
            if mark_seen:
                store.mark_seen_batch(WATCHLIST_TWEET_SOURCE, new_tweets, lambda t: t["tweet_id"])
            return None

        now = datetime.now().astimezone()
        md_path, json_path = _output_paths(_resolve_vault(cfg), now)
        drafts = build_watchlist_drafts(candidates, str(json_path), max_drafts=max_drafts)
        payload = {
            "generated_at": now.isoformat(),
            "principle": principle,
            "keywords": keywords,
            "few_shot_count": len(few_shots) if isinstance(few_shots, list) else 0,
            "config_path": str(_config_path(cfg, config_path)),
            "source_tweets": filtered,
            "candidates": candidates,
            "skipped_topics": skipped,
            "drafts": _policy_records(drafts),
        }
        _write_outputs(md_path, json_path, payload)
        click.echo(f"   📝 Markdown: {md_path}")
        click.echo(f"   📦 JSON:     {json_path}")

        if mark_seen:
            _mark_processed(store, new_tweets, candidates)
        else:
            click.echo("   ℹ️ --no-mark-seen 已启用，未写入去重记录")

    if not drafts:
        click.echo("   ⚠️ 未生成可发布草稿")
        return md_path

    to_publish = drafts if dry_run else drafts[:max(0, publish_count)]
    if not dry_run:
        click.echo(f"   🚀 准备发布前 {len(to_publish)} 条草稿")

    for draft in to_publish:
        run_draft_publish(cfg, draft, dry_run=dry_run, force=force, yes=yes)

    return md_path


def _plist_arg(value: str) -> str:
    return f"        <string>{escape(str(value))}</string>"


def _hours_for_interval(interval: int, start: int = 9, end: int = 21) -> list[int]:
    return list(range(start, end + 1, interval))


def _build_watchlist_plist(
    v2g_bin: str,
    project_dir: str,
    hours: list[int],
    *,
    config_path: str | None = None,
    publish: bool = False,
    publish_count: int | None = None,
) -> str:
    intervals = "\n".join(
        f"        <dict>\n"
        f"            <key>Hour</key><integer>{h}</integer>\n"
        f"            <key>Minute</key><integer>0</integer>\n"
        f"        </dict>"
        for h in hours
    )
    args = [v2g_bin]
    env_path = Path(project_dir) / ".env"
    if env_path.exists():
        args += ["--env", str(env_path)]
    args += ["scout", "watchlist"]
    if config_path:
        args += ["--config", config_path]
    if publish:
        args += ["--publish", "--yes"]
        if publish_count is not None:
            args += ["--publish-count", str(publish_count)]

    arg_lines = "\n".join(_plist_arg(a) for a in args)
    project_dir_xml = escape(project_dir)
    log_out_xml = escape(str(WATCHLIST_LOG_DIR / "watchlist.log"))
    log_err_xml = escape(str(WATCHLIST_LOG_DIR / "watchlist-error.log"))
    home_xml = escape(str(Path.home()))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{WATCHLIST_PLIST_LABEL}</string>

    <key>ProgramArguments</key>
    <array>
{arg_lines}
    </array>

    <key>WorkingDirectory</key>
    <string>{project_dir_xml}</string>

    <key>StartCalendarInterval</key>
    <array>
{intervals}
    </array>

    <key>StandardOutPath</key>
    <string>{log_out_xml}</string>
    <key>StandardErrorPath</key>
    <string>{log_err_xml}</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>HOME</key>
        <string>{home_xml}</string>
    </dict>

    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>"""


def setup_watchlist_cron(
    interval: int,
    start: int,
    end: int,
    uninstall: bool,
    *,
    config_path: str | None = None,
    publish: bool = False,
    publish_count: int | None = None,
) -> None:
    """安装或卸载 watchlist launchd 定时任务。"""
    if uninstall:
        subprocess.run(["launchctl", "unload", str(WATCHLIST_PLIST_PATH)], capture_output=True)
        WATCHLIST_PLIST_PATH.unlink(missing_ok=True)
        click.echo(f"✅ 已卸载 {WATCHLIST_PLIST_LABEL}")
        return

    v2g_bin = shutil.which("v2g")
    if not v2g_bin:
        raise click.ClickException("找不到 v2g 命令，请先 pip install -e .")

    project_dir = str(Path(__file__).parents[3])
    hours = _hours_for_interval(interval, start, end)
    plist_content = _build_watchlist_plist(
        v2g_bin,
        project_dir,
        hours,
        config_path=config_path,
        publish=publish,
        publish_count=publish_count,
    )

    WATCHLIST_LOG_DIR.mkdir(parents=True, exist_ok=True)
    WATCHLIST_PLIST_PATH.write_text(plist_content, encoding="utf-8")

    subprocess.run(["launchctl", "unload", str(WATCHLIST_PLIST_PATH)], capture_output=True)
    result = subprocess.run(["launchctl", "load", str(WATCHLIST_PLIST_PATH)], capture_output=True, text=True)
    if result.returncode != 0:
        click.echo(f"⚠️ launchctl load 失败: {result.stderr}")
        return

    times_str = "、".join(f"{h}:00" for h in hours)
    mode = "发布" if publish else "dry-run 草稿"
    click.echo(f"✅ 已安装 Watchlist 定时任务 ({mode}，每天 {times_str})")
    click.echo(f"   plist: {WATCHLIST_PLIST_PATH}")
    click.echo(f"   日志:  {WATCHLIST_LOG_DIR}/watchlist.log")
    click.echo(f"\n   查看日志: tail -f {WATCHLIST_LOG_DIR}/watchlist.log")
    click.echo("   手动触发: v2g scout watchlist")
    click.echo("   卸载:     v2g scout watchlist-cron-setup --uninstall")
