"""Obsidian vault Markdown 输出。"""

from datetime import date
from pathlib import Path

import click


class ObsidianWriter:
    """将知识源输出写入 Obsidian vault 的 Markdown 文件。"""

    def __init__(self, vault_path: Path):
        if not vault_path or str(vault_path) == ".":
            vault_path = Path("output")
            click.echo(
                "   ℹ️  OBSIDIAN_VAULT_PATH 未设置，输出到 output/knowledge/\n"
                "   提示: 在 .env 中设置 OBSIDIAN_VAULT_PATH 可直接写入你的 Obsidian vault"
            )
        self.vault = vault_path
        self.ensure_dirs()

    def ensure_dirs(self):
        for sub in ("knowledge/github", "knowledge/twitter", "knowledge/articles",
                    "knowledge/distribution", "daily"):
            (self.vault / sub).mkdir(parents=True, exist_ok=True)

    # -- GitHub --

    def write_github_report(
        self, today: date, repos: list[dict], analysis: str
    ) -> Path:
        path = self.vault / "knowledge" / "github" / f"{today}-trending.md"
        lines = [
            "---",
            f"date: {today}",
            "source: github",
            "tags: [github, trending, ai]",
            "---",
            "",
            "# GitHub AI 趋势",
            "",
        ]
        if analysis:
            lines += [analysis, ""]

        lines.append("## 仓库列表\n")
        for r in repos:
            name = r.get("full_name", r.get("name", "unknown"))
            stars = r.get("stargazers_count", r.get("stars", 0))
            lang = r.get("language", "")
            desc = r.get("description", "") or ""
            url = r.get("html_url", r.get("url", ""))
            lines.append(f"### [{name}]({url})")
            lines.append(f"⭐ {stars} | {lang}")
            lines.append(f"> {desc}")
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    # -- Twitter --

    def write_twitter_report(
        self, today: date, tweets: list[dict], summary: str
    ) -> Path:
        path = self.vault / "knowledge" / "twitter" / f"{today}-curated.md"
        lines = [
            "---",
            f"date: {today}",
            "source: twitter",
            "tags: [twitter, ai-tech]",
            "---",
            "",
            "# Twitter AI 精选",
            "",
        ]
        if summary:
            lines += [summary, ""]

        lines.append("## 推文列表\n")
        for t in tweets:
            author = t.get("author", t.get("user", {}).get("screen_name", "unknown"))
            text = t.get("text", t.get("full_text", ""))
            likes = t.get("likes", t.get("favorite_count", 0))
            url = t.get("url", "")
            score = t.get("total_score", "")
            lines.append(f"### @{author}")
            if score:
                lines.append(f"Score: {score:.2f} | ❤️ {likes}")
            else:
                lines.append(f"❤️ {likes}")
            lines.append(f"> {text[:300]}")
            if url:
                lines.append(f"[链接]({url})")
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    # -- Articles --

    def write_article_report(
        self, today: date, articles: list[dict]
    ) -> Path:
        path = self.vault / "knowledge" / "articles" / f"{today}-articles.md"
        lines = [
            "---",
            f"date: {today}",
            "source: articles",
            "tags: [articles, ai-tech]",
            "---",
            "",
            "# 文章摘要",
            "",
        ]
        for a in articles:
            title = a.get("title", "未知标题")
            url = a.get("source_url", a.get("url", ""))
            summary = a.get("summary", "")
            author = a.get("author", "")
            lines.append(f"### [{title}]({url})")
            if author:
                lines.append(f"作者: {author}")
            if summary:
                lines.append(f"\n{summary}")
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    # -- Daily Digest --

    def write_daily_digest(
        self, today: date, sections: dict[str, str]
    ) -> Path:
        path = self.vault / "daily" / f"{today}.md"
        lines = [
            "---",
            f"date: {today}",
            "tags: [daily, digest]",
            "---",
            "",
            f"# 每日知识汇总 {today}",
            "",
            "## 来源",
            f"- [[knowledge/github/{today}-trending|GitHub 趋势]]",
            f"- [[knowledge/hn/{today}-hn|Hacker News 热帖]]",
            f"- [[knowledge/articles/{today}-articles|文章摘要]]",
            "",
        ]
        for section_name, content in sections.items():
            lines.append(f"## {section_name}\n")
            lines.append(content)
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        return path
