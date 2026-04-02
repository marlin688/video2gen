"""Hacker News 监控：Algolia API 搜索 + LLM 分析。

HN Algolia API 完全免费，无需 token，无速率限制。
对 AI Tech 内容创作者来说，HN 是最好的技术话题发现源之一。
"""

import os
from datetime import datetime, timezone

import click

# 清理非法 proxy 环境变量
for _k in list(os.environ):
    if "proxy" in _k.lower():
        _v = os.environ[_k]
        if _v and _v.rstrip("/").endswith("~"):
            os.environ[_k] = _v.rstrip("~")


def search_hn_stories(
    keywords: list[str],
    hours: int = 24,
    min_points: int = 20,
    per_keyword: int = 10,
) -> list[dict]:
    """通过 HN Algolia API 搜索近期热门帖子。

    每个关键词单独查询再合并去重（Algolia 默认是 AND 逻辑）。
    """
    import httpx

    cutoff = int((datetime.now(timezone.utc).timestamp()) - hours * 3600)
    if not keywords:
        keywords = ["AI", "LLM"]

    click.echo(f"   🔍 Hacker News 搜索: {len(keywords)} 个关键词, 最近 {hours}h, points>{min_points}")

    all_hits = []
    for kw in keywords:
        try:
            resp = httpx.get(
                "https://hn.algolia.com/api/v1/search",
                params={
                    "query": kw,
                    "tags": "story",
                    "numericFilters": f"created_at_i>{cutoff},points>{min_points}",
                    "hitsPerPage": per_keyword,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
            all_hits.extend(hits)
        except Exception as e:
            click.echo(f"   ⚠️ HN [{kw}] 请求失败: {e}")

    # 按 objectID 去重，按 points 降序
    seen = set()
    unique = []
    for h in all_hits:
        oid = h.get("objectID", "")
        if oid not in seen:
            seen.add(oid)
            unique.append(h)
    unique.sort(key=lambda h: h.get("points", 0), reverse=True)

    click.echo(f"   ✅ 找到 {len(unique)} 篇帖子 (合并去重)")
    return unique


def _normalize_story(hit: dict) -> dict:
    """统一 HN Algolia 返回的字段。"""
    return {
        "story_id": hit.get("objectID", ""),
        "title": hit.get("title", ""),
        "url": hit.get("url", ""),
        "author": hit.get("author", ""),
        "points": hit.get("points", 0),
        "num_comments": hit.get("num_comments", 0),
        "created_at": hit.get("created_at", ""),
        "hn_url": f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
    }


def analyze_stories_with_llm(stories: list[dict], model: str) -> str:
    """用 LLM 分析 HN 热帖，返回 Markdown。"""
    from v2g.llm import call_llm
    from v2g.knowledge import _load_prompt

    if not stories:
        return "*今日无新帖*"

    story_lines = []
    for s in stories[:20]:
        story_lines.append(
            f"- **{s['title']}** (⬆{s['points']} 💬{s['num_comments']})\n"
            f"  作者: {s['author']} | {s['hn_url']}\n"
            f"  链接: {s.get('url', 'N/A')}"
        )

    system_prompt = _load_prompt("knowledge_hn.md")
    user_message = "以下是近期 Hacker News 上的 AI 相关热门帖子：\n\n" + "\n\n".join(story_lines)

    try:
        return call_llm(system_prompt, user_message, model, temperature=0.3, max_tokens=2000)
    except Exception as e:
        click.echo(f"   ⚠️ LLM 分析失败: {e}")
        return ""


def run_hn_monitor(cfg, hours: int = 24, min_points: int = 20) -> "Path | None":
    """Hacker News 监控主流程。"""
    from datetime import date
    from v2g.knowledge.store import KnowledgeStore
    from v2g.knowledge.obsidian import ObsidianWriter
    from v2g.knowledge.telegram import send_telegram

    click.echo("🟧 Hacker News 监控")

    keywords = [k.strip() for k in cfg.github_topics.split(",") if k.strip()]

    # 搜索
    raw_stories = search_hn_stories(keywords, hours=hours, min_points=min_points)
    if not raw_stories:
        click.echo("   ℹ️ 未找到新帖子")
        return None

    stories = [_normalize_story(h) for h in raw_stories]

    # 去重
    store = KnowledgeStore(cfg.knowledge_db_path)
    new_stories = store.filter_new("hn", stories, lambda s: s["story_id"])
    click.echo(f"   📊 新帖子: {len(new_stories)} / {len(stories)}")

    if not new_stories:
        store.close()
        click.echo("   ℹ️ 无新帖子")
        return None

    # LLM 分析
    click.echo("   🤖 LLM 分析中...")
    analysis = analyze_stories_with_llm(new_stories, cfg.knowledge_model)

    # 标记已见
    store.mark_seen_batch("hn", new_stories, lambda s: s["story_id"])
    store.close()

    # 写入 Obsidian
    writer = ObsidianWriter(cfg.obsidian_vault_path)
    today = date.today()
    path = _write_hn_report(writer, today, new_stories, analysis)
    click.echo(f"   📝 已写入: {path}")

    # Telegram 通知
    if new_stories and cfg.telegram_bot_token:
        msg = _format_hn_telegram(new_stories[:10])
        send_telegram(cfg.telegram_bot_token, cfg.telegram_chat_id, msg)
        click.echo("   📬 Telegram 已通知")

    return path


def _write_hn_report(writer, today, stories: list[dict], analysis: str):
    """写入 HN 报告到 Obsidian。"""
    path = writer.vault / "knowledge" / "hn" / f"{today}-hn.md"
    (writer.vault / "knowledge" / "hn").mkdir(parents=True, exist_ok=True)

    lines = [
        "---",
        f"date: {today}",
        "source: hackernews",
        "tags: [hackernews, ai-tech]",
        "---",
        "",
        "# Hacker News AI 热帖",
        "",
    ]
    if analysis:
        lines += [analysis, ""]

    lines.append("## 帖子列表\n")
    for s in stories:
        lines.append(f"### [{s['title']}]({s['hn_url']})")
        lines.append(f"⬆ {s['points']} | 💬 {s['num_comments']} | @{s['author']}")
        if s.get("url"):
            lines.append(f"[原文链接]({s['url']})")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _format_hn_telegram(stories: list[dict]) -> str:
    """格式化 HN 帖子为 Telegram HTML。"""
    from v2g.knowledge.telegram import _escape_html

    lines = ["<b>🟧 Hacker News AI 热帖</b>\n"]
    for i, s in enumerate(stories, 1):
        title = _escape_html(s["title"])
        lines.append(
            f'<b>{i}. <a href="{s["hn_url"]}">{title}</a></b> '
            f'⬆{s["points"]} 💬{s["num_comments"]}'
        )
        lines.append("")
    return "\n".join(lines)
