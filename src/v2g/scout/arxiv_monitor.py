"""arXiv 论文监控：通过 arXiv Query API 抓取最新论文 + LLM 分析。

arXiv 提供免费 REST API（`export.arxiv.org/api/query`），返回 Atom XML，无需 token。
按分类 + 关键词混合查询，再合并去重。
"""

import time
from datetime import date, datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import click

ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"

# arXiv API 礼仪：建议每次请求间隔 ≥3s，且带可联系的 User-Agent。
# https://info.arxiv.org/help/api/tou.html
_ARXIV_UA = "v2g-scout/1.0 (https://github.com/; contact via repo issues)"
_ARXIV_DELAY = 3.0


def search_arxiv(
    categories: list[str],
    keywords: list[str],
    days: int = 2,
    max_per_query: int = 30,
) -> list[dict]:
    """通过 arXiv API 检索最近 N 天的论文。

    每个 (category, keyword) 组合单独查询，按提交时间倒序，再合并去重。
    无关键词时按分类纯时间倒序。
    """
    import httpx

    if not categories:
        categories = ["cs.AI", "cs.CL", "cs.LG"]

    queries: list[str] = []
    for cat in categories:
        if keywords:
            for kw in keywords:
                # arXiv 全文搜索：cat:cs.AI AND all:agent
                queries.append(f'cat:{cat} AND all:"{kw}"')
        else:
            queries.append(f"cat:{cat}")

    click.echo(
        f"   🔍 arXiv 搜索: {len(categories)} 分类 × "
        f"{len(keywords) or 1} 关键词 = {len(queries)} 查询, 最近 {days}d"
    )

    all_entries: list[dict] = []
    headers = {"User-Agent": _ARXIV_UA}
    for idx, q in enumerate(queries):
        if idx > 0:
            time.sleep(_ARXIV_DELAY)
        try:
            resp = httpx.get(
                "https://export.arxiv.org/api/query",
                params={
                    "search_query": q,
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                    "max_results": max_per_query,
                },
                headers=headers,
                timeout=30.0,
            )
            resp.raise_for_status()
            all_entries.extend(_parse_atom(resp.text))
        except Exception as e:
            click.echo(f"   ⚠️ arXiv [{q}] 请求失败: {e}")

    # 时间过滤
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    fresh = [e for e in all_entries if _parse_ts(e.get("published")) >= cutoff]

    # 按 arxiv_id 去重，引用次数无 API，按 published 倒序
    seen: set[str] = set()
    unique: list[dict] = []
    for e in fresh:
        aid = e.get("arxiv_id", "")
        if aid and aid not in seen:
            seen.add(aid)
            unique.append(e)
    unique.sort(key=lambda e: e.get("published", ""), reverse=True)

    click.echo(f"   ✅ 找到 {len(unique)} 篇论文 (合并去重 + {days}d 内)")
    return unique


def _parse_ts(iso: str | None) -> float:
    if not iso:
        return 0.0
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _parse_atom(xml_text: str) -> list[dict]:
    """解析 arXiv Atom feed → 论文 dict 列表。"""
    entries: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        click.echo(f"   ⚠️ arXiv XML 解析失败: {e}")
        return entries

    for entry in root.findall(f"{ATOM_NS}entry"):
        aid_full = (entry.findtext(f"{ATOM_NS}id") or "").strip()
        # id 形如 http://arxiv.org/abs/2401.12345v2，去掉 version
        arxiv_id = aid_full.rsplit("/", 1)[-1]
        arxiv_id_base = arxiv_id.split("v")[0] if "v" in arxiv_id else arxiv_id

        title = (entry.findtext(f"{ATOM_NS}title") or "").strip().replace("\n", " ")
        summary = (entry.findtext(f"{ATOM_NS}summary") or "").strip().replace("\n", " ")
        published = (entry.findtext(f"{ATOM_NS}published") or "").strip()

        authors = [
            (a.findtext(f"{ATOM_NS}name") or "").strip()
            for a in entry.findall(f"{ATOM_NS}author")
        ]

        primary_cat = ""
        pc = entry.find(f"{ARXIV_NS}primary_category")
        if pc is not None:
            primary_cat = pc.get("term", "")

        categories = [
            c.get("term", "")
            for c in entry.findall(f"{ATOM_NS}category")
            if c.get("term")
        ]

        pdf_url = ""
        abs_url = f"https://arxiv.org/abs/{arxiv_id_base}"
        for link in entry.findall(f"{ATOM_NS}link"):
            if link.get("title") == "pdf":
                pdf_url = link.get("href", "")
            elif link.get("rel") == "alternate":
                abs_url = link.get("href", abs_url)

        entries.append(
            {
                "arxiv_id": arxiv_id_base,
                "title": title,
                "summary": summary,
                "authors": authors,
                "primary_category": primary_cat,
                "categories": categories,
                "published": published,
                "abs_url": abs_url,
                "pdf_url": pdf_url,
            }
        )
    return entries


def analyze_papers_with_llm(papers: list[dict], model: str) -> str:
    """用 LLM 分析 arXiv 论文，返回 Markdown。"""
    from v2g.llm import call_llm
    from v2g.scout import _load_prompt

    if not papers:
        return "*今日无新论文*"

    lines = []
    for p in papers[:20]:
        authors = ", ".join(p["authors"][:3])
        if len(p["authors"]) > 3:
            authors += " 等"
        summary_short = p["summary"][:400]
        lines.append(
            f"- **{p['title']}** ({p['primary_category']})\n"
            f"  作者: {authors} | {p['abs_url']}\n"
            f"  摘要: {summary_short}"
        )

    system_prompt = _load_prompt("scout_arxiv.md")
    user_message = "以下是近期 arXiv 上的 AI 相关新论文：\n\n" + "\n\n".join(lines)

    try:
        return call_llm(system_prompt, user_message, model, temperature=0.3, max_tokens=2000)
    except Exception as e:
        click.echo(f"   ⚠️ LLM 分析失败: {e}")
        return ""


def run_arxiv_monitor(cfg, days: int = 2, max_per_query: int = 30) -> "Path | None":
    """arXiv 监控主流程。"""
    from v2g.scout.obsidian import ObsidianWriter
    from v2g.scout.store import ScoutStore
    from v2g.scout.telegram import send_telegram

    click.echo("🟦 arXiv 论文监控")

    categories = [c.strip() for c in cfg.arxiv_categories.split(",") if c.strip()]
    keywords = [k.strip() for k in cfg.arxiv_keywords.split(",") if k.strip()]

    papers = search_arxiv(categories, keywords, days=days, max_per_query=max_per_query)
    if not papers:
        click.echo("   ℹ️ 未找到新论文")
        return None

    with ScoutStore(cfg.scout_db_path) as store:
        new_papers = store.filter_new("arxiv", papers, lambda p: p["arxiv_id"])
        click.echo(f"   📊 新论文: {len(new_papers)} / {len(papers)}")

        if not new_papers:
            click.echo("   ℹ️ 无新论文")
            return None

        click.echo("   🤖 LLM 分析中...")
        analysis = analyze_papers_with_llm(new_papers, cfg.scout_model)

        store.mark_seen_batch("arxiv", new_papers, lambda p: p["arxiv_id"])

    writer = ObsidianWriter(cfg.obsidian_vault_path)
    today = date.today()
    path = _write_arxiv_report(writer, today, new_papers, analysis)
    click.echo(f"   📝 已写入: {path}")

    if new_papers and cfg.telegram_bot_token:
        msg = _format_arxiv_telegram(new_papers[:10])
        send_telegram(cfg.telegram_bot_token, cfg.telegram_chat_id, msg)
        click.echo("   📬 Telegram 已通知")

    return path


def _write_arxiv_report(writer, today: date, papers: list[dict], analysis: str) -> Path:
    """写入 arXiv 报告到 Obsidian。当日重复运行时追加新条目。"""
    path = writer.vault / "scout" / "arxiv" / f"{today}-arxiv.md"
    (writer.vault / "scout" / "arxiv").mkdir(parents=True, exist_ok=True)

    if path.exists():
        existing = path.read_text(encoding="utf-8")
        new_lines = ["\n## 新增论文\n"]
        if analysis:
            new_lines += [analysis, ""]
        appended = 0
        for p in papers:
            if p["abs_url"] in existing:
                continue
            new_lines.extend(_format_paper_md(p))
            appended += 1
        if appended:
            path.write_text(existing.rstrip() + "\n\n" + "\n".join(new_lines), encoding="utf-8")
        return path

    lines = [
        "---",
        f"date: {today}",
        "source: arxiv",
        "tags: [arxiv, ai-tech, papers]",
        "---",
        "",
        "# arXiv AI 新论文",
        "",
    ]
    if analysis:
        lines += [analysis, ""]

    lines.append("## 论文列表\n")
    for p in papers:
        lines.extend(_format_paper_md(p))

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _format_paper_md(p: dict) -> list[str]:
    authors = ", ".join(p["authors"][:5])
    if len(p["authors"]) > 5:
        authors += " 等"
    out = [
        f"### [{p['title']}]({p['abs_url']})",
        f"📅 {p['published'][:10]} | 🏷 {p['primary_category']} | 👤 {authors}",
    ]
    if p.get("pdf_url"):
        out.append(f"[PDF]({p['pdf_url']})")
    if p.get("summary"):
        out.append("")
        out.append(f"> {p['summary'][:500]}{'...' if len(p['summary']) > 500 else ''}")
    out.append("")
    return out


def _format_arxiv_telegram(papers: list[dict]) -> str:
    from v2g.scout.telegram import _escape_html

    lines = ["<b>🟦 arXiv AI 新论文</b>\n"]
    for i, p in enumerate(papers, 1):
        title = _escape_html(p["title"])
        cat = _escape_html(p.get("primary_category", ""))
        lines.append(
            f'<b>{i}. <a href="{p["abs_url"]}">{title}</a></b> '
            f'🏷 {cat}'
        )
        lines.append("")
    return "\n".join(lines)
