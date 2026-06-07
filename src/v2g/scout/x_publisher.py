"""X (Twitter) 发帖模块 - OAuth 1.0a，发单推或帖串。"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

MAX_TWEET_CHARS = 280
CHAIN_DISCLAIMER = "不喊单，只拆逻辑。"

_PLACEHOLDER_PATTERNS = (
    "[link]",
    "待补链接",
    "链接占位",
)

_INVESTMENT_ADVICE_PATTERNS = (
    "建议买入",
    "建议卖出",
    "无脑买",
    "闭眼买",
    "稳赚",
    "必涨",
    "目标价",
    "满仓",
    "梭哈",
)


@dataclass
class TweetDraft:
    """发布前的标准草稿对象。"""

    source_type: str
    tweets: list[str]
    source_file: str = ""
    topic: str = ""
    version: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def normalized_tweets(self) -> list[str]:
        return [t.strip() for t in self.tweets if t and t.strip()]

    @property
    def content_hash(self) -> str:
        return _content_hash(self.normalized_tweets())


@dataclass
class PolicyIssue:
    severity: str
    code: str
    message: str
    tweet_index: int | None = None


def validate_draft(draft: TweetDraft) -> list[PolicyIssue]:
    """发布前门禁。error 会阻断真实发布。"""
    issues: list[PolicyIssue] = []
    tweets = draft.normalized_tweets()

    if not tweets:
        return [
            PolicyIssue(
                severity="error",
                code="empty_draft",
                message="推文草稿为空",
            )
        ]

    seen: dict[str, int] = {}
    for idx, tweet in enumerate(tweets, start=1):
        if len(tweet) > MAX_TWEET_CHARS:
            issues.append(
                PolicyIssue(
                    severity="error",
                    code="tweet_too_long",
                    tweet_index=idx,
                    message=f"推文 {idx} 超过 {MAX_TWEET_CHARS} 字符: {len(tweet)}",
                )
            )

        lowered = tweet.lower()
        for marker in _PLACEHOLDER_PATTERNS:
            if marker.lower() in lowered:
                issues.append(
                    PolicyIssue(
                        severity="error",
                        code="placeholder",
                        tweet_index=idx,
                        message=f"推文 {idx} 含未替换占位符: {marker}",
                    )
                )

        for pat in _INVESTMENT_ADVICE_PATTERNS:
            if pat in tweet:
                issues.append(
                    PolicyIssue(
                        severity="error",
                        code="investment_advice",
                        tweet_index=idx,
                        message=f"推文 {idx} 含投资建议/喊单风险表达: {pat}",
                    )
                )

        if "$XXX" in tweet or "待核实" in tweet or (
            draft.source_type == "chain" and "⚠️" in tweet
        ):
            issues.append(
                PolicyIssue(
                    severity="error",
                    code="unverified_ticker",
                    tweet_index=idx,
                    message=f"推文 {idx} 含待核实 ticker，不允许自动发布",
                )
            )

        ticker_count = len(re.findall(r"\$[A-Z]{1,5}(?:\.[A-Z])?", tweet))
        if ticker_count > 8:
            issues.append(
                PolicyIssue(
                    severity="error",
                    code="too_many_tickers",
                    tweet_index=idx,
                    message=f"推文 {idx} ticker 数过多: {ticker_count}",
                )
            )

        normalized = re.sub(r"\s+", " ", tweet).strip().lower()
        if normalized in seen:
            issues.append(
                PolicyIssue(
                    severity="error",
                    code="duplicate_tweet",
                    tweet_index=idx,
                    message=f"推文 {idx} 与推文 {seen[normalized]} 内容重复",
                )
            )
        seen[normalized] = idx

    if draft.source_type == "chain":
        joined = "\n".join(tweets)
        if CHAIN_DISCLAIMER not in joined:
            issues.append(
                PolicyIssue(
                    severity="error",
                    code="missing_disclaimer",
                    message=f"产业链推文必须包含免责声明: {CHAIN_DISCLAIMER}",
                )
            )

    return issues


def _get_client():
    try:
        import tweepy
    except ImportError:
        raise ImportError("请先安装: pip install 'video2gen[x]'")

    missing = [k for k in ("X_CONSUMER_KEY", "X_CONSUMER_SECRET",
                            "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")
               if not os.environ.get(k)]
    if missing:
        raise ValueError(f"缺少环境变量: {', '.join(missing)}")

    return tweepy.Client(
        consumer_key=os.environ["X_CONSUMER_KEY"],
        consumer_secret=os.environ["X_CONSUMER_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )


def post_thread(
    tweets: list[str],
    dry_run: bool = False,
    after_post: Callable[[int, str, list[str]], None] | None = None,
) -> list[str]:
    """发布帖串，返回 tweet ID 列表。dry_run=True 只打印不发。"""
    if not tweets:
        raise ValueError("推文列表为空")

    if dry_run:
        for i, t in enumerate(tweets, 1):
            print(f"[DRY RUN] 推文 {i}/{len(tweets)}:\n{t}\n{'─'*40}")
        return [f"dry_run_{i}" for i in range(len(tweets))]

    client = _get_client()
    tweet_ids: list[str] = []
    reply_to: str | None = None

    for idx, tweet in enumerate(tweets, start=1):
        kwargs: dict = {"text": tweet}
        if reply_to:
            kwargs["in_reply_to_tweet_id"] = reply_to
        resp = client.create_tweet(**kwargs)
        tid = str(resp.data["id"])
        tweet_ids.append(tid)
        reply_to = tid
        if after_post:
            after_post(idx, tid, list(tweet_ids))

    return tweet_ids


def parse_waterfall_tweets(content: str, version: str = "short") -> list[str]:
    """从 waterfall markdown 提取推文。version: 'short' | 'long'"""
    if version == "short":
        pat = r"###\s*短版.*?(?=###\s*长版|^---|\Z)"
    else:
        pat = r"###\s*长版.*?(?=^---|\Z)"

    m = re.search(pat, content, re.DOTALL | re.MULTILINE)
    if not m:
        return []

    section = m.group(0)
    # 按 **推文 N** 行分割，每块提取 blockquote 内容
    chunks = re.split(r'\n(?=\*\*推文)', section)

    tweets = []
    for chunk in chunks:
        lines = [ln.strip()[1:].strip()
                 for ln in chunk.split('\n')
                 if ln.strip().startswith('>')]
        if lines:
            text = '\n'.join(lines).strip()
            if text and text != '...':
                tweets.append(text)

    return tweets


def _content_hash(tweets: list[str]) -> str:
    normalized = [t.strip() for t in tweets if t and t.strip()]
    return hashlib.md5("\n---\n".join(normalized).encode()).hexdigest()[:12]


def _frontmatter_value(content: str, key: str) -> str:
    m = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*$", content, flags=re.MULTILINE)
    if not m:
        return ""
    return m.group(1).strip().strip('"').strip("'")


def build_waterfall_draft(path: Path, version: str = "short") -> TweetDraft:
    content = path.read_text(encoding="utf-8")
    tweets = parse_waterfall_tweets(content, version)
    return TweetDraft(
        source_type="waterfall",
        tweets=tweets,
        source_file=str(path),
        topic=_frontmatter_value(content, "topic"),
        version=version,
        metadata={"source_name": path.name},
    )


def _split_text_to_tweets(text: str, max_chars: int = MAX_TWEET_CHARS) -> list[str]:
    """把长文按段落/句子拆成 X API 可发布的线程。"""
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if not text:
        return []

    result: list[str] = []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    sentence_re = re.compile(r"(?<=[。！？!?])\s*")

    for para in paragraphs:
        if len(para) <= max_chars:
            result.append(para)
            continue

        buf = ""
        sentences = [s.strip() for s in sentence_re.split(para) if s.strip()]
        for sentence in sentences:
            if len(sentence) > max_chars:
                if buf:
                    result.append(buf)
                    buf = ""
                for start in range(0, len(sentence), max_chars):
                    result.append(sentence[start:start + max_chars])
                continue
            candidate = sentence if not buf else f"{buf}\n{sentence}"
            if len(candidate) <= max_chars:
                buf = candidate
            else:
                result.append(buf)
                buf = sentence
        if buf:
            result.append(buf)

    return result


def build_chain_draft(path: Path, version: str = "short") -> TweetDraft:
    """从 scout/chain JSON 或同名 Markdown 加载发布草稿。"""
    json_path = path
    if path.suffix.lower() == ".md":
        candidate = path.with_suffix(".json")
        if candidate.exists():
            json_path = candidate

    data = json.loads(json_path.read_text(encoding="utf-8"))
    if version == "short":
        tweets = [str(data.get("short_tweet") or "").strip()]
        if CHAIN_DISCLAIMER not in tweets[0]:
            tweets[0] = (tweets[0].rstrip() + "\n\n" + CHAIN_DISCLAIMER).strip()
    elif version == "long":
        tweets = _split_text_to_tweets(str(data.get("long_tweet") or ""))
    else:
        raise ValueError(f"未知 chain 发布版本: {version}")

    return TweetDraft(
        source_type="chain",
        tweets=tweets,
        source_file=str(json_path),
        topic=str(data.get("topic") or ""),
        version=version,
        metadata={
            "source_name": json_path.name,
            "risk_level": "financial",
            "disclaimer": str(data.get("disclaimer") or ""),
        },
    )


def _resolve_vault(cfg) -> Path:
    p = cfg.obsidian_vault_path
    if p and str(p) not in ("", "."):
        return Path(p)
    return Path("output")


def _latest_file(base: Path, pattern: str) -> Path | None:
    if not base.exists():
        return None
    files = sorted(base.glob(pattern), reverse=True)
    return files[0] if files else None


def _load_seen_data(store, source: str, item_id: str) -> dict:
    cur = store._conn.execute(
        "SELECT data FROM seen_items WHERE source=? AND item_id=?",
        (source, item_id),
    )
    row = cur.fetchone()
    if not row:
        return {}
    try:
        return json.loads(row[0])
    except json.JSONDecodeError:
        return {}


def _print_draft(draft: TweetDraft) -> None:
    import click

    tweets = draft.normalized_tweets()
    click.echo(f"\n   📋 {draft.source_type}:{draft.version or '-'} 共 {len(tweets)} 条")
    if draft.topic:
        click.echo(f"   话题: {draft.topic}")
    if draft.source_file:
        click.echo(f"   来源: {draft.source_file}")
    click.echo()
    for i, tweet in enumerate(tweets, 1):
        preview = tweet[:120] + ("…" if len(tweet) > 120 else "")
        click.echo(f"   [{i}] ({len(tweet)}字) {preview}")


def _print_policy_issues(issues: list[PolicyIssue]) -> None:
    import click

    if not issues:
        click.echo("   ✅ 发布门禁通过")
        return
    click.echo("   ❌ 发布门禁未通过:")
    for issue in issues:
        where = f"推文 {issue.tweet_index}: " if issue.tweet_index else ""
        click.echo(f"      - [{issue.code}] {where}{issue.message}")


def run_draft_publish(cfg, draft: TweetDraft, dry_run: bool, force: bool, yes: bool = False) -> bool:
    import click
    from v2g.scout.store import ScoutStore

    draft.tweets = draft.normalized_tweets()
    item_id = draft.content_hash

    _print_draft(draft)
    issues = validate_draft(draft)
    _print_policy_issues(issues)
    if any(i.severity == "error" for i in issues):
        click.echo("   ⛔ 已阻断发布，请修复草稿后重试")
        return False

    if dry_run:
        post_thread(draft.tweets, dry_run=True)
        click.echo("\n   ✅ Dry run 完成，未实际发布")
        return True

    with ScoutStore(cfg.scout_db_path) as store:
        if store.is_seen("x_publish", item_id) and not force:
            click.echo(f"   ⏭️  已发布过（hash={item_id}），用 --force 强制重发")
            return False

        attempt = _load_seen_data(store, "x_publish_attempt", item_id)
        partial_ids = attempt.get("tweet_ids") or []
        if partial_ids and attempt.get("status") in {"publishing", "failed"} and not force:
            click.echo("   ⛔ 检测到未完成的发布尝试，已阻断避免重复发首推")
            click.echo(f"      hash={item_id}, status={attempt.get('status')}, tweet_ids={partial_ids}")
            click.echo("      请人工确认 X 端状态后，用 --force 重新发布或手动清理记录")
            return False

        if not yes and not click.confirm("\n   确认发布?"):
            click.echo("   ❌ 已取消")
            return False

        store.mark_seen("x_publish_attempt", item_id, {
            "status": "publishing",
            "tweet_ids": [],
            "source_type": draft.source_type,
            "version": draft.version,
            "source_file": Path(draft.source_file).name if draft.source_file else "",
            "first_tweet": draft.tweets[0][:100],
        })

        def _record_partial(idx: int, tid: str, tweet_ids: list[str]) -> None:
            store.mark_seen("x_publish_attempt", item_id, {
                "status": "publishing",
                "tweet_ids": tweet_ids,
                "last_index": idx,
                "last_tweet_id": tid,
                "source_type": draft.source_type,
                "version": draft.version,
                "source_file": Path(draft.source_file).name if draft.source_file else "",
                "first_tweet": draft.tweets[0][:100],
            })

        try:
            tweet_ids = post_thread(draft.tweets, dry_run=False, after_post=_record_partial)
        except Exception as e:
            attempt = _load_seen_data(store, "x_publish_attempt", item_id)
            attempt["status"] = "failed"
            attempt["error"] = str(e)
            store.mark_seen("x_publish_attempt", item_id, attempt)
            raise click.ClickException(f"X 发布失败，可能已有部分推文发出: {e}") from e

        data = {
            "tweet_ids": tweet_ids,
            "source_type": draft.source_type,
            "version": draft.version,
            "source_file": Path(draft.source_file).name if draft.source_file else "",
            "topic": draft.topic,
            "first_tweet": draft.tweets[0][:100],
        }
        store.mark_seen("x_publish", item_id, data)
        store.mark_seen("x_publish_attempt", item_id, {**data, "status": "published"})
        click.echo(f"\n   ✅ 发布成功！首推: https://x.com/i/web/status/{tweet_ids[0]}")
        return True


def run_publish(cfg, file_path: str | None, version: str,
                dry_run: bool, force: bool, yes: bool = False) -> None:
    import click
    from v2g.scout.obsidian import ObsidianWriter

    click.echo("🐦 X 发布")

    # 定位 waterfall 文件
    if file_path:
        target = Path(file_path)
    else:
        writer = ObsidianWriter(cfg.obsidian_vault_path)
        dist_dir = writer.vault / "scout" / "distribution"
        files = sorted(dist_dir.glob("*-waterfall-*.md"), reverse=True)
        if not files:
            click.echo("   ⚠️ 未找到 waterfall 文件，请先运行 v2g scout waterfall")
            return
        target = files[0]
        click.echo(f"   📄 使用最新文件: {target.name}")

    if not target.exists():
        click.echo(f"   ⚠️ 文件不存在: {target}")
        return

    draft = build_waterfall_draft(target, version)
    if not draft.tweets:
        click.echo(f"   ⚠️ 未解析到推文 (version={version})，请检查文件格式")
        return

    run_draft_publish(cfg, draft, dry_run=dry_run, force=force, yes=yes)


def run_publish_chain(cfg, file_path: str | None, version: str,
                      dry_run: bool, force: bool, yes: bool = False) -> None:
    import click

    click.echo("🐦 X 发布（产业链推文）")

    if file_path:
        target = Path(file_path)
    else:
        target = _latest_file(_resolve_vault(cfg) / "scout" / "chain", "*-chain.json")
        if not target:
            click.echo("   ⚠️ 未找到 chain JSON，请先运行 v2g scout chain")
            return
        click.echo(f"   📄 使用最新文件: {target.name}")

    if not target.exists():
        click.echo(f"   ⚠️ 文件不存在: {target}")
        return

    draft = build_chain_draft(target, version)
    run_draft_publish(cfg, draft, dry_run=dry_run, force=force, yes=yes)
