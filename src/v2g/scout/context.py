"""上下文加载工具：为 hook/title/outline 注入额外分析上下文。"""

from datetime import date
from pathlib import Path

import click

from v2g.scout.url_extractor import _topic_matches_report


def load_notebooklm_context(vault_path: Path, today: date, topic: str) -> str:
    """加载 NotebookLM 深度分析结果作为 LLM 上下文。

    匹配 scout/notebooklm/{date}-{slug}.md，截取前 3000 字符。
    无文件时返回空字符串（notebooklm 是可选步骤）。
    """
    nlm_dir = vault_path / "scout" / "notebooklm"
    if not nlm_dir.exists():
        return ""

    for f in nlm_dir.glob(f"{today}-*.md"):
        if _topic_matches_report(f, topic):
            content = f.read_text(encoding="utf-8")[:3000]
            click.echo(f"   📎 已加载 NotebookLM 分析: {f.name}")
            return f"\n\n## NotebookLM 深度分析参考\n\n{content}"

    return ""
