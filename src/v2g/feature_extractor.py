"""脚本特征提取：从 script.json 提取结构化指标，用于与视频表现关联分析。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VideoFeatures:
    """一个视频脚本的结构化特征。"""

    video_id: str
    title: str = ""
    segment_count: int = 0
    # 素材比例
    material_a_ratio: float = 0.0
    material_b_ratio: float = 0.0
    material_c_ratio: float = 0.0
    # Schema 多样性
    schema_diversity: int = 0
    schemas_used: list[str] = field(default_factory=list)
    # 旁白统计
    avg_narration_len: float = 0.0
    max_narration_len: int = 0
    min_narration_len: int = 0
    # 组件使用
    has_terminal: bool = False
    has_image_overlay: bool = False
    has_web_video: bool = False
    has_code_block: bool = False
    has_diagram: bool = False
    has_social_card: bool = False
    # Hook
    hook_type: str = ""  # intro 段使用的 schema
    # 时长
    total_duration_hint: float = 0.0


def extract_features(script_path: str | Path, video_id: str) -> VideoFeatures:
    """从 script.json 提取结构特征。"""
    path = Path(script_path)
    script = json.loads(path.read_text(encoding="utf-8"))

    segments = script.get("segments", [])
    n = len(segments)
    if n == 0:
        return VideoFeatures(video_id=video_id, title=script.get("title", ""))

    # 素材分布
    materials = [s.get("material", "A") for s in segments]
    a_count = materials.count("A")
    b_count = materials.count("B")
    c_count = materials.count("C")

    # Schema 检测
    schemas: set[str] = set()
    for seg in segments:
        schema = _detect_schema(seg)
        if schema:
            schemas.add(schema)

    # 旁白长度
    narr_lens = []
    for seg in segments:
        text = seg.get("narration_zh", "") or seg.get("narration_en", "") or ""
        narr_lens.append(len(text))

    # Hook 类型（第一段的 schema）
    hook_type = _detect_schema(segments[0]) if segments else ""

    # 组件检测
    schema_list = sorted(schemas)
    has = lambda s: s in schemas

    return VideoFeatures(
        video_id=video_id,
        title=script.get("title", ""),
        segment_count=n,
        material_a_ratio=round(a_count / n, 2) if n else 0,
        material_b_ratio=round(b_count / n, 2) if n else 0,
        material_c_ratio=round(c_count / n, 2) if n else 0,
        schema_diversity=len(schemas),
        schemas_used=schema_list,
        avg_narration_len=round(sum(narr_lens) / n, 1) if n else 0,
        max_narration_len=max(narr_lens) if narr_lens else 0,
        min_narration_len=min(narr_lens) if narr_lens else 0,
        has_terminal=has("terminal"),
        has_image_overlay=has("image-overlay"),
        has_web_video=has("web-video"),
        has_code_block=has("code-block"),
        has_diagram=has("diagram"),
        has_social_card=has("social-card"),
        hook_type=hook_type,
        total_duration_hint=script.get("total_duration_hint", 0),
    )


def _detect_schema(seg: dict) -> str:
    """检测单个 segment 使用的 schema。"""
    # 优先看 component 字段
    comp = seg.get("component", "")
    if comp:
        # "slide.tech-dark" → "slide"
        return comp.split(".")[0]

    # 根据数据字段推断
    if seg.get("terminal_session"):
        return "terminal"
    if seg.get("image_content"):
        return "image-overlay"
    if seg.get("web_video"):
        return "web-video"
    if seg.get("slide_content"):
        return "slide"
    if seg.get("source_start") is not None or seg.get("source_end") is not None:
        return "source-clip"
    if seg.get("recording_instruction"):
        return "recording"

    # 按 material 推断默认 schema
    mat = seg.get("material", "A")
    if mat == "A":
        return "slide"
    if mat == "B":
        return "terminal"
    if mat == "C":
        return "source-clip"
    return ""
