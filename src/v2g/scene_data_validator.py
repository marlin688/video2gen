"""scene_data 字段名校验与自动修复。

检查 script.json 中每个 segment 的 slide_content.scene_data 字段名
是否匹配对应 Remotion 组件的期望接口，自动修复已知错误映射。
"""

from __future__ import annotations

import difflib
from typing import Any

# ---------------------------------------------------------------------------
# 硬编码的已知错误映射（从生产经验中提取）
# ---------------------------------------------------------------------------

_KNOWN_FIXES: dict[str, dict[str, str]] = {
    "slide.anthropic-feature-checklist": {
        "completed": "done",
        "pending": "todo",
        "finished": "done",
        "remaining": "todo",
    },
    "slide.anthropic-agent-config": {
        "prompt": "userPrompt",
        "curl": "apiCall",
        "config_yaml": "yamlLines",
        "agent_id": "agentName",
        "lines": "terminalLines",
    },
    "slide.anthropic-prompt-write": {
        "userInput": "prompt",
        "actions": "quickActions",
        "options": "templates",
    },
    "slide.anthropic-session-timeline": {
        "log": "agentLog",
        "entries": "agentLog",
        "title": "panelTitle",
        "files": "panelFiles",
        "footer": "panelFooter",
    },
    "slide.anthropic-session-detail": {
        "log": "agentLog",
        "hover": "popover",
        "system": "systemPrompt",
        "tools": "mcpTools",
    },
    "slide.anthropic-template-picker": {
        "options": "templates",
        "categories": "tags",
        "name": "appName",
    },
    "slide.anthropic-stickies-intro": {
        "notes": "stickies",
        "items": "stickies",
    },
    "slide.anthropic-callout": {
        "type": "kind",
        "content": "body",
        "text": "body",
    },
    "slide.anthropic-section-title": {
        "prefix": "chapter",
        "label": "chapter",
    },
    "slide.anthropic-brand-title": {
        "titles": "words",
        "text": "words",
    },
    "slide.anthropic-brand-outro": {
        "brand": "wordmark",
        "logo": "showLogo",
    },
}

# 已知需要 string → string[] 包装的字段
_ARRAY_FIELDS: dict[str, set[str]] = {
    "slide.anthropic-agent-config": {"apiCall", "yamlLines"},
    "slide.anthropic-brand-title": {"words"},
    "slide.anthropic-session-detail": {"systemPrompt", "mcpTools"},
}


def _load_expected_fields() -> dict[str, set[str]]:
    """尝试从 style_catalog 加载各组件的期望字段名集合。"""
    try:
        from v2g.style_catalog import load_styles

        styles = load_styles()
        result: dict[str, set[str]] = {}
        for s in styles:
            sd = s.get("scene_data_fields")
            if sd:
                result[s["id"]] = set(sd.keys())
        return result
    except Exception:
        return {}


def validate_and_fix_scene_data(
    script_data: dict,
    auto_fix: bool = True,
) -> tuple[dict, list[str]]:
    """校验并可选修复 scene_data 字段名。

    Args:
        script_data: 完整的 script.json dict
        auto_fix: True 时自动修复已知错误映射

    Returns:
        (可能修复后的 script_data, 警告列表)
    """
    warnings: list[str] = []
    expected_map = _load_expected_fields()

    segments = script_data.get("segments", [])
    for seg in segments:
        seg_id = seg.get("id", "?")
        component = seg.get("component", "")
        if not component:
            continue

        # scene_data 可能在 slide_content 下，也可能在 segment 顶层
        scene_data = None
        scene_data_parent = None
        scene_data_key = None

        sc = seg.get("slide_content")
        if isinstance(sc, dict) and "scene_data" in sc:
            scene_data = sc["scene_data"]
            scene_data_parent = sc
            scene_data_key = "scene_data"
        elif "scene_data" in seg:
            scene_data = seg["scene_data"]
            scene_data_parent = seg
            scene_data_key = "scene_data"

        if not isinstance(scene_data, dict) or not scene_data:
            continue

        expected = expected_map.get(component, set())
        known_fixes = _KNOWN_FIXES.get(component, {})
        array_fields = _ARRAY_FIELDS.get(component, set())

        keys_to_fix: list[tuple[str, str]] = []

        for key in list(scene_data.keys()):
            # 跳过内部属性
            if key.startswith("__"):
                continue

            # 已经是正确字段名
            if expected and key in expected:
                continue

            # 硬编码已知修复
            if key in known_fixes:
                new_key = known_fixes[key]
                keys_to_fix.append((key, new_key))
                warnings.append(f"seg_{seg_id}: {key} → {new_key} ({component.split('.')[-1]})")
                continue

            # 如果有期望字段列表，用模糊匹配建议
            if expected:
                close = difflib.get_close_matches(key, list(expected), n=1, cutoff=0.6)
                if close:
                    new_key = close[0]
                    keys_to_fix.append((key, new_key))
                    warnings.append(
                        f"seg_{seg_id}: {key} → {new_key} (模糊匹配, {component.split('.')[-1]})"
                    )

        # 执行修复
        if auto_fix and keys_to_fix:
            new_scene_data = {}
            for k, v in scene_data.items():
                replaced = False
                for old_key, new_key in keys_to_fix:
                    if k == old_key:
                        # 类型包装: string → string[]
                        if new_key in array_fields and isinstance(v, str):
                            v = [v]
                        new_scene_data[new_key] = v
                        replaced = True
                        break
                if not replaced:
                    new_scene_data[k] = v
            scene_data_parent[scene_data_key] = new_scene_data

    return script_data, warnings
