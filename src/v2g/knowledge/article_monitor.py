"""文章监控：RSS / 手动 URL / inbox 三种输入 + LLM 摘要。"""

from pathlib import Path

import click


def fetch_from_rss(rss_urls: list[str]) -> list[dict]:
    """从 RSS/Atom feeds 获取文章列表。"""
    if not rss_urls:
        return []

    try:
        import feedparser
    except ImportError:
        click.echo("   ⚠️ feedparser 未安装，跳过 RSS。运行: pip install feedparser")
        return []

    entries = []
    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:  # 每个 feed 最多 10 篇
                entries.append({
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "author": entry.get("author", ""),
                    "published": entry.get("published", ""),
                })
        except Exception as e:
            click.echo(f"   ⚠️ RSS 解析失败 {url[:50]}: {e}")
    return entries


def fetch_from_urls(urls: list[str]) -> list[dict]:
    """直接传入 URL 列表。"""
    return [{"url": u.strip(), "title": "", "author": ""} for u in urls if u.strip()]


def fetch_from_inbox(vault_path: Path) -> list[dict]:
    """读取 Obsidian vault 的 inbox/articles.md 中的 URL。

    文件格式：每行一个 URL，或 Markdown 链接 [title](url)。
    """
    inbox_path = vault_path / "inbox" / "articles.md"
    if not inbox_path.exists():
        return []

    import re
    entries = []
    content = inbox_path.read_text(encoding="utf-8")
    for line in content.strip().split("\n"):
        line = line.strip().lstrip("- ")
        if not line or line.startswith("#"):
            continue
        # Markdown 链接
        md_match = re.match(r"\[([^\]]*)\]\(([^)]+)\)", line)
        if md_match:
            entries.append({"title": md_match.group(1), "url": md_match.group(2), "author": ""})
        elif line.startswith("http"):
            entries.append({"url": line, "title": "", "author": ""})
    return entries


def extract_and_summarize(
    entries: list[dict], model: str
) -> list[dict]:
    """抓取文章正文 + LLM 摘要。"""
    from v2g.fetcher import fetch_article
    from v2g.llm import call_llm
    from v2g.knowledge import _load_prompt

    system_prompt = _load_prompt("knowledge_article.md")
    results = []

    for entry in entries:
        url = entry.get("url", "")
        if not url:
            continue

        # 抓取正文
        try:
            article = fetch_article(url)
        except Exception as e:
            click.echo(f"   ⚠️ 抓取失败 {url[:50]}: {e}")
            continue

        # LLM 摘要
        try:
            content_preview = article["content"][:3000]
            summary = call_llm(
                system_prompt,
                f"标题: {article['title']}\n作者: {article['author']}\n\n{content_preview}",
                model,
                temperature=0.3,
                max_tokens=800,
            )
        except Exception as e:
            click.echo(f"   ⚠️ LLM 摘要失败: {e}")
            summary = ""

        results.append({
            "title": article.get("title") or entry.get("title", ""),
            "author": article.get("author") or entry.get("author", ""),
            "source_url": url,
            "word_count": article.get("word_count", 0),
            "summary": summary,
        })

    return results


def run_article_monitor(cfg, urls: list[str] | None = None) -> "Path | None":
    """文章监控主流程。"""
    from datetime import date
    from v2g.knowledge.store import KnowledgeStore
    from v2g.knowledge.obsidian import ObsidianWriter

    click.echo("📰 文章监控")

    # 汇聚三种输入源
    all_entries = []

    # 1. 手动 URL
    if urls:
        manual = fetch_from_urls(urls)
        click.echo(f"   📎 手动 URL: {len(manual)} 篇")
        all_entries.extend(manual)

    # 2. RSS
    rss_urls = [u.strip() for u in cfg.article_rss_urls.split(",") if u.strip()]
    if rss_urls:
        rss_entries = fetch_from_rss(rss_urls)
        click.echo(f"   📡 RSS: {len(rss_entries)} 篇")
        all_entries.extend(rss_entries)

    # 3. Inbox
    if cfg.obsidian_vault_path and str(cfg.obsidian_vault_path) != ".":
        inbox_entries = fetch_from_inbox(cfg.obsidian_vault_path)
        if inbox_entries:
            click.echo(f"   📥 Inbox: {len(inbox_entries)} 篇")
            all_entries.extend(inbox_entries)

    if not all_entries:
        click.echo("   ℹ️ 无文章待处理")
        return None

    # 去重
    with KnowledgeStore(cfg.knowledge_db_path) as store:
        new_entries = store.filter_new("article", all_entries, lambda e: e.get("url", ""))
        click.echo(f"   📊 新文章: {len(new_entries)} / {len(all_entries)}")

        if not new_entries:
            click.echo("   ℹ️ 无新文章")
            return None

        # 抓取 + 摘要
        click.echo("   🤖 抓取 + LLM 摘要中...")
        articles = extract_and_summarize(new_entries, cfg.knowledge_model)

        # 标记已见
        store.mark_seen_batch("article", new_entries, lambda e: e.get("url", ""))

    # 写入 Obsidian
    writer = ObsidianWriter(cfg.obsidian_vault_path)
    today = date.today()
    path = writer.write_article_report(today, articles)
    click.echo(f"   📝 已写入: {path}")

    return path
