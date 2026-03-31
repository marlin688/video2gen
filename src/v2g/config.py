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
            tts_voice=os.environ.get("TTS_VOICE", defaults.tts_voice),
            tts_rate=os.environ.get("TTS_RATE", defaults.tts_rate),
            script_model=os.environ.get("SCRIPT_MODEL", defaults.script_model),
            video_width=int(w),
            video_height=int(h),
            video_crf=int(os.environ.get("VIDEO_CRF", str(defaults.video_crf))),
            api_platform=os.environ.get("API_PLATFORM", ""),
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
