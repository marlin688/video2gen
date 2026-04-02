"""知识源头自动化模块。

三个信息源：GitHub 趋势、Twitter/X 监控、文章监控。
所有输出汇入 Obsidian 知识库。
"""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    """加载 prompts/ 目录下的 prompt 模板。"""
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


from .github_trending import run_github_trending  # noqa: E402, F401
from .hn_monitor import run_hn_monitor  # noqa: E402, F401
from .twitter_monitor import run_twitter_monitor  # noqa: E402, F401
from .article_monitor import run_article_monitor  # noqa: E402, F401
from .ideation import run_ideation  # noqa: E402, F401
