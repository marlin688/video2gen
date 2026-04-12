"""配置加载模块。"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Config:
    """video2gen 全局配置。"""

    # 路径
    trending_csv: Path = field(default_factory=lambda: Path("../youtube-trending/data/latest.csv"))
    l2n_output_dir: Path = field(default_factory=lambda: Path("../lecture2note/output/subtitle"))
    sources_dir: Path = field(default_factory=lambda: Path("sources"))
    output_dir: Path = field(default_factory=lambda: Path("output"))

    # TTS
    tts_voice: str = "zh-CN-YunxiNeural"
    tts_rate: str = "+5%"

    # LLM
    script_model: str = "claude-sonnet-4-5-20250929"

    # 视频
    video_width: int = 1920
    video_height: int = 1080
    video_crf: int = 20
    video_fps: int = 30

    # API 平台
    api_platform: str = ""

    # Scout Sources
    obsidian_vault_path: Path = field(default_factory=lambda: Path(""))
    scout_model: str = "claude-sonnet-4-5-20250929"
    scout_fallback_model: str = ""
    github_topics: str = "ai,ml,llm,agent,rag"
    apify_token: str = ""
    twitter_keywords: str = ""
    twitter_authors: str = ""
    scout_db_path: Path = field(default_factory=lambda: Path("data/scout.db"))
    hn_keywords: str = "AI,LLM,Claude,GPT,agent,RAG"
    article_rss_urls: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    youtube_api_key: str = ""

    # Bilibili
    bilibili_sessdata: str = ""
    bilibili_bili_jct: str = ""
    bilibili_retention_api: str = ""  # 自定义留存曲线 API endpoint

    @classmethod
    def load(cls, env_path: str | None = None) -> "Config":
        """从 .env 文件加载配置。"""
        load_dotenv(env_path or ".env")

        resolution = os.environ.get("VIDEO_RESOLUTION", "1920x1080")
        w, h = resolution.split("x") if "x" in resolution else ("1920", "1080")

        defaults = cls()
        cfg = cls(
            trending_csv=Path(os.environ.get("TRENDING_CSV_PATH", str(defaults.trending_csv))),
            l2n_output_dir=Path(os.environ.get("L2N_OUTPUT_DIR", str(defaults.l2n_output_dir))),
            sources_dir=Path(os.environ.get("SOURCES_DIR", str(defaults.sources_dir))),
            tts_voice=os.environ.get("TTS_VOICE", defaults.tts_voice),
            tts_rate=os.environ.get("TTS_RATE", defaults.tts_rate),
            script_model=os.environ.get("SCRIPT_MODEL", defaults.script_model),
            video_width=int(w),
            video_height=int(h),
            video_crf=int(os.environ.get("VIDEO_CRF", str(defaults.video_crf))),
            api_platform=os.environ.get("API_PLATFORM", ""),
            obsidian_vault_path=Path(os.environ.get("OBSIDIAN_VAULT_PATH", "")),
            scout_model=os.environ.get("SCOUT_MODEL", defaults.scout_model),
            scout_fallback_model=os.environ.get("SCOUT_FALLBACK_MODEL", ""),
            github_topics=os.environ.get("GITHUB_TOPICS", defaults.github_topics),
            apify_token=os.environ.get("APIFY_TOKEN", ""),
            twitter_keywords=os.environ.get("TWITTER_KEYWORDS", ""),
            twitter_authors=os.environ.get("TWITTER_AUTHORS", ""),
            scout_db_path=Path(os.environ.get("SCOUT_DB_PATH", str(defaults.scout_db_path))),
            hn_keywords=os.environ.get("HN_KEYWORDS", defaults.hn_keywords),
            article_rss_urls=os.environ.get("ARTICLE_RSS_URLS", ""),
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
            youtube_api_key=os.environ.get("YOUTUBE_API_KEY", ""),
            bilibili_sessdata=os.environ.get("BILIBILI_SESSDATA", ""),
            bilibili_bili_jct=os.environ.get("BILIBILI_BILI_JCT", ""),
            bilibili_retention_api=os.environ.get("BILIBILI_RETENTION_API", ""),
        )

        # 应用平台切换（复用 lecture2note 的模式）
        if cfg.api_platform:
            _apply_platform(cfg.api_platform)

        return cfg


def _apply_platform(platform: str):
    """将平台前缀环境变量覆盖到标准 ANTHROPIC_* 变量。"""
    name = platform.strip().lower()
    if not name:
        return
    prefix = name.upper() + "_"
    mapping = {
        f"{prefix}API_KEY": "ANTHROPIC_API_KEY",
        f"{prefix}BASE_URL": "ANTHROPIC_BASE_URL",
        f"{prefix}MODEL": "ANTHROPIC_MODEL",
    }
    for src, dst in mapping.items():
        val = os.environ.get(src)
        if val:
            os.environ[dst] = val
