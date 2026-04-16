"""脚本结构自动修复：组件↔数据字段不匹配、字段名错误、缺图清理。

在 scene_data_validator 之后、eval 之前调用。修复策略：
1. 字段名纠正：diagram_data → diagram, filename → fileName 等
2. 字段位置纠正：scene_data 里的数据提升到正确的顶层字段
3. 组件降级：组件无对应数据时降级到有数据的备选组件
4. 缺图清理：引用不存在的图片文件时清理引用
5. 可选强约束：确保至少存在 image-overlay + web-video 段，并补齐可在线检索字段
"""

from __future__ import annotations

import re
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

_SCHEMA_MATERIAL: dict[str, str] = {
    "slide": "A",
    "browser": "A",
    "diagram": "A",
    "hero-stat": "A",
    "code-block": "A",
    "social-card": "A",
    "image-overlay": "A",
    "terminal": "B",
    "recording": "B",
    "web-video": "C",
    "source-clip": "C",
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


def fix_script(
    script: dict,
    project_dir: Path,
    *,
    ensure_rich_media: bool = False,
) -> tuple[dict, list[str]]:
    """自动修复脚本结构问题。

    Args:
        script: script.json 的 dict
        project_dir: 项目目录（用于检查文件是否存在）
        ensure_rich_media: 是否强制保证脚本包含 image-overlay + web-video 段落

    Returns:
        (修复后的 script, 修复日志列表)
    """
    fixes: list[str] = []
    segments = script.get("segments", [])

    for seg in segments:
        sid = seg.get("id", "?")
        comp = seg.get("component", "")
        schema = comp.split(".")[0] if comp else ""

        if schema == "hero-stat" and isinstance(seg.get("hero_stat"), list):
            seg["hero_stat"] = {"stats": seg["hero_stat"]}
            fixes.append(f"[{sid}] hero_stat list → dict(stats)")

        if not schema:
            continue

        required_field = _COMPONENT_DATA_FIELD.get(schema)
        if not required_field:
            continue

        # 已经有正确的数据字段 → 跳过
        if seg.get(required_field):
            # 但检查内部字段名 / 兼容旧结构
            if schema == "code-block":
                _fix_code_content(seg, sid, fixes)
            elif schema == "browser":
                _fix_browser_content(seg, sid, fixes)
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

            elif schema == "diagram" and "steps" in sd:
                seg["diagram"] = _pipeline_scene_data_to_diagram(sd)
                seg.pop("scene_data", None)
                fixes.append(f"[{sid}] scene_data(steps) → diagram")
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
                _fix_browser_content(seg, sid, fixes)
                fixes.append(f"[{sid}] scene_data → browser_content")
                promoted = True

            elif schema == "diagram" and "left" in sd and "right" in sd:
                seg["diagram"] = _dual_card_scene_data_to_diagram(sd)
                seg.pop("scene_data", None)
                fixes.append(f"[{sid}] scene_data(dual-card) → diagram")
                promoted = True

            if promoted:
                continue

        # ── 策略 3: 从 slide_content 提取 hero_stat ──
        if schema == "hero-stat" and seg.get("slide_content"):
            sc = seg["slide_content"]
            bullets = sc.get("bullet_points", [])
            if bullets:
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
        elif seg.get("material") == "A" and seg.get("narration_zh"):
            old_comp = comp
            seg["component"] = "slide.tech-dark"
            seg["slide_content"] = _slide_content_from_narration(seg)
            fixes.append(f"[{sid}] {old_comp} → slide.tech-dark (from narration)")

    # ── component / material 语义归一 ──
    for seg in segments:
        _normalize_component_material(seg, fixes)

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

    if ensure_rich_media:
        _ensure_rich_media_presence(segments, fixes)

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
    code = cc.get("code")
    if isinstance(code, str):
        cc["code"] = code.splitlines() or [code]
        fixes.append(f"[{sid}] code_content.code string → list")


def _fix_browser_content(seg: dict, sid, fixes: list[str]):
    """兼容 browser_content 的旧字段名，补齐 schema 必需字段。"""
    bc = seg.get("browser_content")
    if not isinstance(bc, dict):
        return

    changed: list[str] = []

    if not bc.get("tabTitle"):
        candidate = (
            bc.get("active_tab")
            or bc.get("title")
            or (bc.get("tabs") or [None])[0]
            or "浏览器"
        )
        bc["tabTitle"] = str(candidate)
        changed.append("tabTitle")

    if not bc.get("pageTitle") and bc.get("title"):
        bc["pageTitle"] = str(bc.get("title"))
        changed.append("pageTitle")

    content_lines = bc.get("contentLines")
    if not isinstance(content_lines, list) or not content_lines:
        lines: list[str] = []
        for key in ("summary", "highlight_text"):
            value = bc.get(key)
            if value:
                lines.append(str(value))
        tabs = bc.get("tabs")
        if isinstance(tabs, list) and tabs:
            lines.append("Tabs: " + " / ".join(str(t) for t in tabs[:4]))
        if bc.get("url"):
            lines.append(str(bc.get("url")))
        if not lines:
            lines.append(str(bc.get("pageTitle") or bc.get("tabTitle") or "页面内容"))
        bc["contentLines"] = lines[:5]
        changed.append("contentLines")

    if changed:
        fixes.append(f"[{sid}] browser_content normalized ({', '.join(changed)})")


def _dual_card_scene_data_to_diagram(scene_data: dict) -> dict:
    """将 dual-card 风格的 scene_data 转成通用 diagram 数据。"""

    def _normalize_type(value: str | None, fallback: str) -> str:
        val = str(value or fallback)
        if val in {"default", "primary", "success", "warning", "danger"}:
            return val
        return fallback

    def _normalize_items(items) -> list[dict]:
        normalized: list[dict] = []
        if not isinstance(items, list):
            return normalized
        for item in items:
            if isinstance(item, dict):
                text = str(item.get("text") or "").strip()
                if not text:
                    continue
                entry = {"text": text}
                tag = str(item.get("tag") or "").strip()
                if tag:
                    entry["tag"] = tag
                normalized.append(entry)
            elif isinstance(item, str) and item.strip():
                normalized.append({"text": item.strip()})
        return normalized

    left = scene_data.get("left") if isinstance(scene_data.get("left"), dict) else {}
    right = scene_data.get("right") if isinstance(scene_data.get("right"), dict) else {}

    return {
        "nodes": [
            {
                "id": "left",
                "label": str(left.get("title") or "左侧"),
                "type": _normalize_type(left.get("type"), "warning"),
                "items": _normalize_items(left.get("items")),
                "status": str(left.get("footer") or "").strip() or None,
            },
            {
                "id": "right",
                "label": str(right.get("title") or "右侧"),
                "type": _normalize_type(right.get("type"), "primary"),
                "items": _normalize_items(right.get("items")),
                "status": str(right.get("footer") or "").strip() or None,
            },
        ],
        "edges": [
            {
                "from": "left",
                "to": "right",
                "label": str(scene_data.get("arrowLabel") or "").strip() or None,
            }
        ],
    }


def _pipeline_scene_data_to_diagram(scene_data: dict) -> dict:
    """将 pipeline 风格的 steps 转成通用 diagram 数据。"""
    steps = scene_data.get("steps") if isinstance(scene_data.get("steps"), list) else []
    nodes: list[dict] = []
    edges: list[dict] = []
    for idx, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        node_id = f"step-{idx}"
        nodes.append({
            "id": node_id,
            "label": str(step.get("title") or f"步骤{idx}"),
            "type": "primary" if idx == 1 else "success" if idx == len(steps) else "default",
            "icon": str(step.get("icon") or "").strip() or None,
            "keywords": [str(k) for k in step.get("keywords", []) if str(k).strip()],
        })
        if idx > 1:
            edges.append({"from": f"step-{idx-1}", "to": node_id})
    return {"nodes": nodes, "edges": edges, "direction": "LR"}


def _slide_content_from_narration(seg: dict) -> dict:
    """从 narration 生成兜底 slide_content，保证 A 段可渲染。"""
    narration = str(seg.get("narration_zh") or "").strip()
    clauses = [
        c.strip()
        for c in re.split(r"[。！？!?；;，,]", narration)
        if c.strip()
    ]
    if not clauses:
        clauses = ["核心观点", "补充说明"]
    title = clauses[0][:18] or "核心观点"
    bullet_points = [(c[:30] if len(c) > 30 else c) for c in clauses[:3]]
    if len(bullet_points) == 1:
        bullet_points.append("展开这个判断背后的原因")
    return {
        "title": title,
        "bullet_points": bullet_points,
        "chart_hint": "",
    }


def _segment_schema(seg: dict) -> str:
    comp = str(seg.get("component") or "").strip()
    return comp.split(".")[0] if comp else ""


def _normalize_component_material(seg: dict, fixes: list[str]) -> None:
    """按显式组件把 material 纠正到渲染语义一致的值。"""
    schema = _segment_schema(seg)
    if not schema:
        return

    expected = _SCHEMA_MATERIAL.get(schema)
    if not expected:
        return

    current = str(seg.get("material") or "").strip()
    if current and current != expected:
        sid = seg.get("id", "?")
        seg["material"] = expected
        fixes.append(f"[{sid}] material {current} → {expected} (schema {schema})")


def _query_from_segment(seg: dict, fallback: str) -> str:
    parts: list[str] = []
    sc = seg.get("slide_content")
    if isinstance(sc, dict):
        title = str(sc.get("title") or "").strip()
        if title:
            parts.append(title)
        bullets = sc.get("bullet_points")
        if isinstance(bullets, list):
            for bullet in bullets[:2]:
                bullet_text = str(bullet).strip()
                if bullet_text:
                    parts.append(bullet_text)
    for k in ("narration_zh", "notes"):
        v = str(seg.get(k) or "").strip()
        if not v:
            continue
        clause = re.split(r"[。！？!?；;，,]", v)[0].strip()
        if clause:
            parts.append(clause)

    cleaned: list[str] = []
    for part in parts:
        part = re.sub(r"https?://\S+", "", part)
        part = re.sub(r"`[^`]+`", "", part)
        part = re.sub(r"\s+", " ", part).strip("。！？!?,，;；:： ")
        if part:
            cleaned.append(part)

    merged = " ".join(cleaned[:2]).strip()
    merged = re.sub(r"\s+", " ", merged)
    if not merged:
        return fallback
    if not re.search(r"[A-Za-z0-9]", merged) and len(merged) > 36:
        return fallback
    return merged[:60]


def _needs_query_refresh(query: str) -> bool:
    query = re.sub(r"\s+", " ", str(query or "").strip())
    if not query:
        return True
    if len(query) > 60:
        return True
    punctuation_hits = sum(query.count(ch) for ch in "，。！？；;,.")
    if punctuation_hits >= 3 and not re.search(r"[A-Za-z0-9]", query):
        return True
    return False


def _overlay_text_from_segment(seg: dict, fallback: str) -> str:
    text = str(seg.get("narration_zh") or "").strip()
    if not text:
        text = fallback
    text = re.sub(r"\s+", " ", text).strip("。！？!?,，")
    if len(text) > 16:
        text = text[:16]
    return text or fallback


def _choose_segment_for_rich_media(segments: list[dict], excluded: set[int]) -> dict | None:
    def _find(predicate):
        for seg in segments:
            if id(seg) in excluded:
                continue
            schema = _segment_schema(seg)
            if predicate(seg, schema):
                return seg
        return None

    passes = (
        lambda s, schema: s.get("material") == "A" and s.get("type") == "body" and schema in {"", "slide"},
        lambda s, schema: s.get("material") == "A" and schema in {"", "slide"},
        lambda s, schema: s.get("material") == "A" and s.get("type") == "body" and schema not in {"image-overlay", "web-video"},
        lambda s, schema: s.get("material") == "A" and schema not in {"image-overlay", "web-video"},
        lambda s, schema: s.get("type") == "body" and schema not in {"image-overlay", "web-video"},
        lambda _s, schema: schema not in {"image-overlay", "web-video"},
    )
    for p in passes:
        hit = _find(p)
        if hit is not None:
            return hit
    return None


def _ensure_image_overlay_segment(seg: dict, fixes: list[str]) -> None:
    sid = seg.get("id", "?")
    old_comp = str(seg.get("component") or "")
    if old_comp != "image-overlay.default":
        seg["component"] = "image-overlay.default"
        fixes.append(f"[{sid}] {old_comp or '(none)'} → image-overlay.default (rich media)")

    ic = seg.get("image_content")
    if not isinstance(ic, dict):
        ic = {}
        seg["image_content"] = ic
        fixes.append(f"[{sid}] image_content auto-created")

    image_path = str(ic.get("image_path") or "").strip()
    ic["image_path"] = image_path

    method = str(ic.get("source_method") or "").strip()
    if not image_path and method not in {"screenshot", "search", "generate"}:
        ic["source_method"] = "search"
        fixes.append(f"[{sid}] image_content.source_method set to search")

    source_query = str(ic.get("source_query") or "").strip()
    if not image_path and (not source_query or _needs_query_refresh(source_query)):
        ic["source_query"] = _query_from_segment(seg, "AI tech product screenshot")
        fixes.append(f"[{sid}] image_content.source_query auto-filled")

    if not ic.get("overlay_text"):
        ic["overlay_text"] = _overlay_text_from_segment(seg, "关键现场")
    if not ic.get("ken_burns"):
        ic["ken_burns"] = "zoom-in"
    if not ic.get("semantic_type"):
        ic["semantic_type"] = "news-screenshot"


def _ensure_web_video_segment(seg: dict, fixes: list[str]) -> None:
    sid = seg.get("id", "?")
    old_comp = str(seg.get("component") or "")
    old_fallback = old_comp if old_comp and not old_comp.startswith("web-video") else "slide.tech-dark"
    if old_comp != "web-video.default":
        seg["component"] = "web-video.default"
        fixes.append(f"[{sid}] {old_comp or '(none)'} → web-video.default (rich media)")

    wv = seg.get("web_video")
    if not isinstance(wv, dict):
        wv = {}
        seg["web_video"] = wv
        fixes.append(f"[{sid}] web_video auto-created")

    query = str(wv.get("search_query") or "").strip()
    if not query or _needs_query_refresh(query):
        wv["search_query"] = _query_from_segment(seg, "AI software demo screen recording")
        fixes.append(f"[{sid}] web_video.search_query auto-filled")

    source_url = str(wv.get("source_url") or "").strip()
    if not source_url:
        wv["source_url"] = None

    if not wv.get("overlay_text"):
        wv["overlay_text"] = _overlay_text_from_segment(seg, "真实演示")
    if not wv.get("overlay_position"):
        wv["overlay_position"] = "bottom"
    if not wv.get("filter"):
        wv["filter"] = "none"
    if not wv.get("fallback_component"):
        wv["fallback_component"] = old_fallback


def _ensure_rich_media_presence(segments: list[dict], fixes: list[str]) -> None:
    image_segments = [s for s in segments if _segment_schema(s) == "image-overlay"]
    web_segments = [s for s in segments if _segment_schema(s) == "web-video"]

    for seg in image_segments:
        _ensure_image_overlay_segment(seg, fixes)
    for seg in web_segments:
        _ensure_web_video_segment(seg, fixes)

    used: set[int] = set()
    if not image_segments:
        chosen_image = _choose_segment_for_rich_media(segments, used)
        if chosen_image is not None:
            used.add(id(chosen_image))
            _ensure_image_overlay_segment(chosen_image, fixes)

    if not web_segments:
        chosen_web = _choose_segment_for_rich_media(segments, used)
        if chosen_web is not None:
            used.add(id(chosen_web))
            _ensure_web_video_segment(chosen_web, fixes)
