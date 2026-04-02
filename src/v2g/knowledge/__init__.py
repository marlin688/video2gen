"""知识源头自动化模块。

知识源：GitHub 趋势、Hacker News、Twitter/X、文章监控。
创作辅助：创意构思、钩子、标题、大纲。
分发辅助：内容瀑布（博客/Twitter/LinkedIn）、短视频再利用。
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


def _load_video_content(cfg, video_id: str | None = None,
                        url: str | None = None,
                        file_path: str | None = None) -> tuple[str, str]:
    """加载视频/文章内容。返回 (content, source_desc)。

    优先级: video_id > url > file_path。
    video_id 按 output/{id}/script.md > sources/{id}/subtitle_zh.srt > subtitle_en.srt 查找。
    内容截断到 8000 字符避免 token 超限。
    """
    MAX_CHARS = 8000
    content = ""
    source_desc = ""

    if video_id:
        # 尝试多个路径
        candidates = [
            cfg.output_dir / video_id / "script.md",
            cfg.l2n_output_dir / video_id / "subtitle_zh.srt",
            cfg.l2n_output_dir / video_id / "subtitle_en.srt",
            Path("sources") / video_id / "subtitle_zh.srt",
            Path("sources") / video_id / "subtitle_en.srt",
        ]
        for p in candidates:
            if p.exists():
                content = p.read_text(encoding="utf-8")
                source_desc = f"来源: {p.name} ({video_id})"
                break
        if not content:
            raise FileNotFoundError(
                f"找不到 video_id={video_id} 的内容文件，"
                f"已尝试: {', '.join(str(c) for c in candidates)}"
            )

    elif url:
        from v2g.fetcher import fetch_article
        content = fetch_article(url) or ""
        if not content:
            raise ValueError(f"无法抓取 URL: {url}")
        source_desc = f"来源: {url}"

    elif file_path:
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        content = p.read_text(encoding="utf-8")
        source_desc = f"来源: {p.name}"

    else:
        raise ValueError("请指定 --video-id、--url 或 --file 之一")

    return content[:MAX_CHARS], source_desc


from .github_trending import run_github_trending  # noqa: E402, F401
from .hn_monitor import run_hn_monitor  # noqa: E402, F401
from .twitter_monitor import run_twitter_monitor  # noqa: E402, F401
from .article_monitor import run_article_monitor  # noqa: E402, F401
from .ideation import run_ideation  # noqa: E402, F401
from .hook import run_hook  # noqa: E402, F401
from .title import run_title  # noqa: E402, F401
from .outline import run_outline  # noqa: E402, F401
from .notebooklm import run_notebooklm  # noqa: E402, F401
from .waterfall import run_waterfall  # noqa: E402, F401
from .shorts import run_shorts  # noqa: E402, F401
