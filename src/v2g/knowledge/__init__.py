"""知识源头自动化模块。

知识源：GitHub 趋势、Hacker News、Twitter/X、文章监控。
创作辅助：创意构思、钩子、标题、大纲。
所有输出汇入 Obsidian 知识库。
"""

import os
from datetime import date
from pathlib import Path

# 清理系统中可能携带非法字符的 proxy 环境变量（如 all_proxy=socks5://127.0.0.1:7890~）
for _k in list(os.environ):
    if "proxy" in _k.lower():
        _v = os.environ[_k]
        if _v and _v.rstrip("/").endswith("~"):
            os.environ[_k] = _v.rstrip("~")

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    """加载 prompts/ 目录下的 prompt 模板。"""
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def _load_today_context(vault_path: Path, today: date | None = None) -> str:
    """加载今日 daily digest 作为 LLM 上下文参考。"""
    today = today or date.today()
    daily_file = vault_path / "daily" / f"{today}.md"
    if daily_file.exists():
        return daily_file.read_text(encoding="utf-8")[:1500]
    return ""


from .github_trending import run_github_trending  # noqa: E402, F401
from .hn_monitor import run_hn_monitor  # noqa: E402, F401
from .twitter_monitor import run_twitter_monitor  # noqa: E402, F401
from .article_monitor import run_article_monitor  # noqa: E402, F401
from .ideation import run_ideation  # noqa: E402, F401
from .hook import run_hook  # noqa: E402, F401
from .title import run_title  # noqa: E402, F401
from .outline import run_outline  # noqa: E402, F401
from .notebooklm import run_notebooklm  # noqa: E402, F401
