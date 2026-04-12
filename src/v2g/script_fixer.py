"""脚本结构自动修复：组件↔数据字段不匹配、字段名错误、缺图清理。

在 scene_data_validator 之后、eval 之前调用。修复策略：
1. 字段名纠正：diagram_data → diagram, filename → fileName 等
2. 字段位置纠正：scene_data 里的数据提升到正确的顶层字段
3. 组件降级：组件无对应数据时降级到有数据的备选组件
4. 缺图清理：引用不存在的图片文件时清理引用
"""

from __future__ import annotations

from pathlib import Path

import click


# ── 组件 → 必需数据字段的映射 ────────────────────────────

_COMPONENT_DATA_FIELD: dict[str, str] = {
    "browser": "browser_content",
    "diagram": "diagram",
    "hero-stat": "hero_stat",
    "code-block": "code_content",
    "social-card": "social_card",
    "image-overlay": "image_content",
    "web-video": "web_video",
}

# ── 常见字段名错误 → 正确名 ──────────────────────────────

_FIELD_RENAMES: dict[str, str] = {
    # diagram
    "diagram_data": "diagram",
    "diagram_content": "diagram",
    # code-block
    "code": "code_content",
    "code_block": "code_content",
    # hero-stat
    "hero_stats": "hero_stat",
    "herostat": "hero_stat",
    # social-card
    "social": "social_card",
    "socialcard": "social_card",
    # browser
    "browser": "browser_content",
}

# code_content 内部字段修正
_CODE_CONTENT_RENAMES: dict[str, str] = {
    "filename": "fileName",
    "file_name": "fileName",
    "lines": "code",
    "code_lines": "code",
    "highlight": "highlightLines",
    "highlight_lines": "highlightLines",
}


def fix_script(script: dict, project_dir: Path) -> tuple[dict, list[str]]:
    """自动修复脚本结构问题。

    Args:
        script: script.json 的 dict
        project_dir: 项目目录（用于检查文件是否存在）

    Returns:
        (修复后的 script, 修复日志列表)
    """
    fixes: list[str] = []
    segments = script.get("segments", [])

    for seg in segments:
        sid = seg.get("id", "?")
        comp = seg.get("component", "")
        schema = comp.split(".")[0] if comp else ""

        if not schema:
            continue

        required_field = _COMPONENT_DATA_FIELD.get(schema)
        if not required_field:
            continue

        # 已经有正确的数据字段 → 跳过
        if seg.get(required_field):
            # 但检查 code_content 内部字段名
            if schema == "code-block":
                _fix_code_content(seg, sid, fixes)
            continue

        # ── 策略 1: 顶层字段名纠正 ──
        for wrong, correct in _FIELD_RENAMES.items():
            if wrong in seg and correct == required_field:
                seg[required_field] = seg.pop(wrong)
                fixes.append(f"[{sid}] {wrong} → {required_field}")
                break

        if seg.get(required_field):
            if schema == "code-block":
                _fix_code_content(seg, sid, fixes)
            continue

        # ── 策略 2: scene_data 提升 ──
        sd = seg.get("scene_data")
        if sd and isinstance(sd, dict):
            promoted = False

            if schema == "diagram" and "nodes" in sd:
                seg["diagram"] = sd
                seg.pop("scene_data", None)
                fixes.append(f"[{sid}] scene_data(nodes) → diagram")
                promoted = True

            elif schema == "hero-stat" and "stats" in sd:
                seg["hero_stat"] = sd
                seg.pop("scene_data", None)
                fixes.append(f"[{sid}] scene_data(stats) → hero_stat")
                promoted = True

            elif schema == "social-card" and ("author" in sd or "platform" in sd):
                seg["social_card"] = sd
                seg.pop("scene_data", None)
                fixes.append(f"[{sid}] scene_data → social_card")
                promoted = True

            elif schema == "browser" and ("url" in sd or "contentLines" in sd):
                seg["browser_content"] = sd
                seg.pop("scene_data", None)
                fixes.append(f"[{sid}] scene_data → browser_content")
                promoted = True

            if promoted:
                continue

        # ── 策略 3: 从 slide_content 提取 hero_stat ──
        if schema == "hero-stat" and seg.get("slide_content"):
            sc = seg["slide_content"]
            bullets = sc.get("bullet_points", [])
            if bullets:
                import re
                stats = []
                for b in bullets:
                    m = re.match(r"([\d.]+%?x?)\s*[→>]?\s*(.*)", b)
                    if m:
                        stats.append({"value": m.group(1), "label": m.group(2).strip()})
                    else:
                        parts = b.split("→") if "→" in b else [b]
                        stats.append({"value": parts[0].strip()[:15], "label": parts[-1].strip()[:30]})
                if stats:
                    seg["hero_stat"] = {"stats": stats, "footnote": sc.get("title", "")}
                    fixes.append(f"[{sid}] slide_content.bullets → hero_stat ({len(stats)} stats)")
                    continue

        # ── 策略 4: 组件降级 ──
        if seg.get("slide_content"):
            old_comp = comp
            seg["component"] = "slide.tech-dark"
            fixes.append(f"[{sid}] {old_comp} → slide.tech-dark (has slide_content)")
        elif seg.get("terminal_session"):
            old_comp = comp
            seg["component"] = "terminal.aurora"
            fixes.append(f"[{sid}] {old_comp} → terminal.aurora (has session)")
        elif seg.get("recording_instruction") and seg.get("material") == "B":
            old_comp = comp
            seg["component"] = "terminal.aurora"
            # 从 recording_instruction 生成最小 terminal_session
            inst = seg["recording_instruction"]
            seg["terminal_session"] = [{"type": "output", "text": inst[:120]}]
            fixes.append(f"[{sid}] {old_comp} → terminal.aurora (from instruction)")

    # ── 缺图清理 ──
    for seg in segments:
        sid = seg.get("id", "?")

        # flash_meme 引用不存在的图片
        fm = seg.get("flash_meme")
        if fm:
            img = fm.get("image", "")
            if img and not (project_dir / img).exists():
                del seg["flash_meme"]
                fixes.append(f"[{sid}] flash_meme removed ({img} not found)")

        # image_content.image_path 非空但文件不存在
        ic = seg.get("image_content")
        if ic:
            path = ic.get("image_path", "")
            if path and not (project_dir / path).exists():
                # 如果有 source_method，清空 path 让 image_prepare 处理
                if ic.get("source_method"):
                    ic["image_path"] = ""
                    fixes.append(f"[{sid}] image_path cleared ({path} not found, has source_method)")
                else:
                    ic["image_path"] = ""
                    fixes.append(f"[{sid}] image_path cleared ({path} not found)")

    return script, fixes


def _fix_code_content(seg: dict, sid, fixes: list[str]):
    """修复 code_content 内部字段名。"""
    cc = seg.get("code_content")
    if not cc or not isinstance(cc, dict):
        return
    for wrong, correct in _CODE_CONTENT_RENAMES.items():
        if wrong in cc and correct not in cc:
            cc[correct] = cc.pop(wrong)
            fixes.append(f"[{sid}] code_content.{wrong} → {correct}")
