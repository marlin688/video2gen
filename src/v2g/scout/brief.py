"""每日 X 发推简报：5 热点 + 评分 + 推文版本 + 长推 + 大号回复。

读取当日 scout 五源报告（github/hn/arxiv/twitter/articles），交给 LLM 熔炼成
可直接发推的 JSON 结构，同时落地为人类可读的 Markdown。

twitter 块如果当天有数据，会作为"大号回复"的真实目标池；否则降级为 LLM
自由生成（hypothetical）。
"""

import json
from datetime import date as date_cls
from pathlib import Path

import click

SOURCES = ("github", "hn", "arxiv", "twitter", "articles")

_SOURCE_FILES = {
    "github":   ("github",   "trending"),
    "hn":       ("hn",       "hn"),
    "arxiv":    ("arxiv",    "arxiv"),
    "twitter":  ("twitter",  "curated"),
    "articles": ("articles", "articles"),
}

_MAX_PER_SOURCE = 4000  # 单源最大字节，避免 prompt 过长


def _resolve_vault(cfg) -> Path:
    """与 scout all / auto_post 保持一致的 vault 解析策略。"""
    p = cfg.obsidian_vault_path
    if p and str(p) not in ("", "."):
        return Path(p)
    return Path("output")


def _read_source_reports(vault: Path, today: date_cls) -> dict[str, str]:
    """读取当日各源 Markdown 报告。缺失的源不报错，跳过。"""
    out: dict[str, str] = {}
    for src, (subdir, suffix) in _SOURCE_FILES.items():
        path = vault / "scout" / subdir / f"{today}-{suffix}.md"
        if path.exists():
            try:
                out[src] = path.read_text(encoding="utf-8")[:_MAX_PER_SOURCE]
            except Exception as e:
                click.echo(f"   ⚠️ 读取 {path.name} 失败: {e}")
    return out


def _build_user_message(today: date_cls, sources: dict[str, str]) -> str:
    """把各源报告拼成统一 prompt。"""
    if not sources:
        return f"今天 ({today}) 没有任何源报告。"
    blocks = [f"日期: {today}", ""]
    for name in SOURCES:
        if name in sources:
            blocks.append(f"## ===== source: {name} =====")
            blocks.append(sources[name])
            blocks.append("")
    return "\n".join(blocks)


def generate_brief(cfg, today: date_cls, sources: dict[str, str]) -> dict | None:
    """调用 LLM 生成简报 JSON。失败返回 None。"""
    from v2g.llm import call_llm
    from v2g.scout import _load_prompt
    from v2g.scriptwriter import _extract_json

    system_prompt = _load_prompt("scout_brief.md")
    user_message = _build_user_message(today, sources)

    click.echo("   🤖 LLM 熔炼今日简报...")
    raw = call_llm(
        system_prompt,
        user_message,
        cfg.scout_model,
        temperature=0.6,
        max_tokens=6000,
    )

    try:
        data = _extract_json(raw)
    except Exception as e:
        click.echo(f"   ⚠️ JSON 解析失败: {e}")
        return None

    if not _validate_brief(data):
        click.echo("   ⚠️ 简报结构校验未通过")
        return None
    return data


def _validate_brief(data: dict) -> bool:
    """最低限度的结构校验。"""
    if not isinstance(data, dict):
        return False
    if not isinstance(data.get("topics"), list) or not data["topics"]:
        return False
    for t in data["topics"]:
        if not isinstance(t, dict):
            return False
        if not t.get("title") or not t.get("scores"):
            return False
        tweets = t.get("tweets")
        if not isinstance(tweets, list) or len(tweets) < 2:
            return False
    if not isinstance(data.get("long_tweet"), dict):
        return False
    if not data["long_tweet"].get("text"):
        return False
    replies = data.get("replies")
    if not isinstance(replies, list):
        return False
    return True


def render_brief_md(today: date_cls, brief: dict) -> str:
    """JSON → 人类可读 Markdown。"""
    lines = [
        "---",
        f"date: {today}",
        "type: daily-brief",
        "tags: [daily, brief, twitter]",
        "---",
        "",
        f"# 今日 X 发推简报 {today}",
        "",
        "## 一、今日热点 Top 5",
        "",
    ]
    for t in brief.get("topics", []):
        rank = t.get("rank", "?")
        title = t.get("title", "(无标题)")
        source = t.get("source", "")
        source_url = t.get("source_url", "")
        summary = t.get("summary", "")
        scores = t.get("scores", {})
        overall = scores.get("overall", 0)
        reason = t.get("score_reason", "")

        lines.append(f"### {rank}. {title}")
        lines.append(
            f"**来源**: {source}"
            + (f" · [原文]({source_url})" if source_url else "")
        )
        lines.append(
            f"**综合**: {_fmt_num(overall)} / 10  "
            f"(时效 {_fmt_num(scores.get('timeliness'))} · "
            f"争议 {_fmt_num(scores.get('controversy'))} · "
            f"密度 {_fmt_num(scores.get('density'))} · "
            f"契合 {_fmt_num(scores.get('audience_fit'))})"
        )
        if reason:
            lines.append(f"**理由**: {reason}")
        if summary:
            lines.append(f"**核心**: {summary}")
        lines.append("")

    lines += ["## 二、推文版本（每热点 2 条）", ""]
    for t in brief.get("topics", []):
        rank = t.get("rank", "?")
        title = t.get("title", "")
        lines.append(f"### 热点 {rank}: {title}")
        for tw in t.get("tweets", []):
            angle = tw.get("angle", "")
            text = (tw.get("text") or "").strip()
            lines.append(f"**[{angle}]**")
            lines.append(f"> {text}")
            lines.append("")

    lt = brief.get("long_tweet", {})
    lt_text = (lt.get("text") or "").strip()
    lines += [
        "## 三、干货长推（500-800 字）",
        "",
        f"_围绕热点 #{lt.get('topic_rank', '?')}_",
        "",
        lt_text,
        "",
    ]

    lines += ["## 四、大号回复（3 条）", ""]
    for i, r in enumerate(brief.get("replies", []), 1):
        kind = r.get("kind", "")
        author = r.get("target_author", "")
        excerpt = r.get("target_excerpt", "")
        url = r.get("target_url", "")
        reply = (r.get("reply") or "").strip()
        kind_tag = "🟢 real" if kind == "real" else "⚪ hypothetical"
        lines.append(f"### 回复 {i} {kind_tag}")
        target_line = f"**目标**: {author}"
        if url:
            target_line += f" · [推文链接]({url})"
        lines.append(target_line)
        if excerpt:
            lines.append(f"> {excerpt}")
        lines.append("")
        lines.append(f"**回复**:")
        lines.append(f"> {reply}")
        lines.append("")

    return "\n".join(lines)


def _fmt_num(n) -> str:
    if n is None:
        return "—"
    if isinstance(n, float):
        return f"{n:.1f}"
    return str(n)


def _write_outputs(vault: Path, today: date_cls, brief: dict) -> tuple[Path, Path]:
    """写入 Markdown + JSON 两份产物。"""
    base = vault / "scout" / "brief"
    base.mkdir(parents=True, exist_ok=True)

    md_path = base / f"{today}-brief.md"
    json_path = base / f"{today}-brief.json"

    md_path.write_text(render_brief_md(today, brief), encoding="utf-8")
    json_path.write_text(
        json.dumps(brief, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return md_path, json_path


def _format_brief_telegram(today: date_cls, brief: dict) -> str:
    """精简 Telegram 推送：5 个热点标题 + 综合分。"""
    from v2g.scout.telegram import _escape_html

    lines = [f"<b>📰 今日 X 简报 {today}</b>\n"]
    for t in brief.get("topics", [])[:5]:
        title = _escape_html(t.get("title", ""))
        overall = t.get("scores", {}).get("overall", 0)
        url = t.get("source_url", "")
        rank = t.get("rank", "?")
        if url:
            lines.append(
                f'<b>{rank}. <a href="{url}">{title}</a></b> · {_fmt_num(overall)}/10'
            )
        else:
            lines.append(f"<b>{rank}. {title}</b> · {_fmt_num(overall)}/10")
    return "\n".join(lines)


def run_brief(cfg, today: date_cls | None = None) -> Path | None:
    """简报主流程。"""
    from v2g.scout.telegram import send_telegram

    today = today or date_cls.today()
    click.echo(f"📰 今日 X 发推简报 ({today})")

    vault = _resolve_vault(cfg)
    sources = _read_source_reports(vault, today)
    if not sources:
        click.echo("   ℹ️ 当日无任何源报告，跳过简报生成")
        return None
    click.echo(f"   📚 加载源: {', '.join(sources.keys())}")

    brief = generate_brief(cfg, today, sources)
    if brief is None:
        return None

    md_path, json_path = _write_outputs(vault, today, brief)
    click.echo(f"   📝 Markdown: {md_path}")
    click.echo(f"   📦 JSON:     {json_path}")

    if cfg.telegram_bot_token:
        try:
            send_telegram(
                cfg.telegram_bot_token,
                cfg.telegram_chat_id,
                _format_brief_telegram(today, brief),
            )
            click.echo("   📬 Telegram 已通知")
        except Exception as e:
            click.echo(f"   ⚠️ Telegram 推送失败: {e}")

    return md_path
