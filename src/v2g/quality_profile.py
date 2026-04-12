"""脚本质量档位配置（通用可复用）。"""

from pathlib import Path


PROMPTS_DIR = Path(__file__).parent / "prompts" / "quality_profiles"


QUALITY_PROFILES = {
    "default": {
        "label": "默认平衡",
        "description": "规则优先，兼顾内容表达",
        "content_type": "auto",  # 自动检测（关键词猜测）
        "weights": {
            "objective": 0.7,
            "subjective": 0.3,
        },
    },
    "tutorial_general": {
        "label": "通用教程高质量",
        "description": "主观内容优先（适合 AI 教程/技巧分享）",
        "content_type": "tutorial",
        "weights": {
            "objective": 0.3,
            "subjective": 0.7,
        },
    },
    "news_briefing": {
        "label": "热点播报",
        "description": "每日/每周 AI 热点快报，配图丰富，信息密度高",
        "content_type": "news",
        "weights": {
            "objective": 0.6,
            "subjective": 0.4,
        },
    },
    "commentary": {
        "label": "深度评论/分析",
        "description": "观点驱动的深度分析，不要求教程闭环和可执行交付",
        "content_type": "commentary",
        "weights": {
            "objective": 0.6,
            "subjective": 0.4,
        },
    },
    "anthropic_brand": {
        "label": "Anthropic 品牌片",
        "description": "米白衬线品牌短片，专用 slide.anthropic-* 场景组件",
        "content_type": "brand",
        "weights": {
            "objective": 0.4,
            "subjective": 0.6,
        },
        # 自动设置 checkpoint.theme 为这个值
        "theme": "anthropic-cream",
        # LLM 的 style catalog 只会看到 id 以此开头的组件
        "style_id_prefix": "slide.anthropic-",
    },
    "tech_explainer": {
        "label": "技术解说片（Anthropic 风格）",
        "description": "米白衬线风格的通用技术视频：talking-head 穿插 screen-clip，硬切，无段数/时长约束",
        "content_type": "tutorial",
        "weights": {
            "objective": 0.5,
            "subjective": 0.5,
        },
        "theme": "anthropic-cream",
        # 复用 Anthropic 风格组件库（14 个含 screen-clip / section-title / callout）
        "style_id_prefix": "slide.anthropic-",
        # 关闭全局运镜（硬切风格不要额外 pan/zoom）
        "camera_rig": False,
        # 默认段间硬切
        "default_transition": "none",
    },
}


def list_quality_profiles() -> list[str]:
    return sorted(QUALITY_PROFILES.keys())


def resolve_quality_profile(name: str | None) -> dict:
    key = (name or "default").strip().lower().replace("-", "_")
    profile = QUALITY_PROFILES.get(key)
    if not profile:
        valid = ", ".join(list_quality_profiles())
        raise ValueError(f"未知 quality profile: {name} (可选: {valid})")

    return {
        "name": key,
        "label": profile["label"],
        "description": profile["description"],
        "weights": {
            "objective": float(profile["weights"]["objective"]),
            "subjective": float(profile["weights"]["subjective"]),
        },
        # 可选：视觉主题覆盖（会写进 checkpoint.theme）
        "theme": profile.get("theme", ""),
        # 可选：style catalog 注入的白名单前缀
        "style_id_prefix": profile.get("style_id_prefix", ""),
        # 可选：是否启用全局 CameraRig 运镜（None = 走默认）
        "camera_rig": profile.get("camera_rig"),
        # 可选：默认段间转场（"none" = 硬切）
        "default_transition": profile.get("default_transition", ""),
        # 内容类型：控制 eval 规则适用性
        "content_type": profile.get("content_type", "auto"),
    }


def load_profile_prompt(name: str | None) -> str:
    profile = resolve_quality_profile(name)
    if profile["name"] == "default":
        return ""

    path = PROMPTS_DIR / f"{profile['name']}.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()

