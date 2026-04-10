"""脚本质量档位配置（通用可复用）。"""

from pathlib import Path


PROMPTS_DIR = Path(__file__).parent / "prompts" / "quality_profiles"


QUALITY_PROFILES = {
    "default": {
        "label": "默认平衡",
        "description": "规则优先，兼顾内容表达",
        "weights": {
            "objective": 0.7,
            "subjective": 0.3,
        },
    },
    "tutorial_general": {
        "label": "通用教程高质量",
        "description": "主观内容优先（适合 AI 教程/技巧分享）",
        "weights": {
            "objective": 0.3,
            "subjective": 0.7,
        },
    },
    "anthropic_brand": {
        "label": "Anthropic 品牌片",
        "description": "米白衬线品牌短片，专用 slide.anthropic-* 场景组件",
        "weights": {
            "objective": 0.4,
            "subjective": 0.6,
        },
        # 自动设置 checkpoint.theme 为这个值
        "theme": "anthropic-cream",
        # LLM 的 style catalog 只会看到 id 以此开头的组件
        "style_id_prefix": "slide.anthropic-",
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
    }


def load_profile_prompt(name: str | None) -> str:
    profile = resolve_quality_profile(name)
    if profile["name"] == "default":
        return ""

    path = PROMPTS_DIR / f"{profile['name']}.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()

