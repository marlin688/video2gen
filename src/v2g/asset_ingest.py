"""素材入库：视频切片 + 自动打标 + SQLite 写入。"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from v2g.asset_store import AssetMeta, AssetStore
from v2g.config import Config


# ── 自产素材入库 ─────────────────────────────────────────

# component → visual_type 映射
_COMPONENT_TO_VISUAL: dict[str, str] = {
    "slide": "text_slide",
    "terminal": "terminal",
    "recording": "screen_recording",
    "source-clip": "screen_recording",
    "code-block": "code_editor",
    "social-card": "screenshot",
    "diagram": "diagram",
    "hero-stat": "chart",
    "browser": "browser",
    "image-overlay": "image_overlay",
    "web-video": "web_video",
}

# segment.type → mood 映射
_TYPE_TO_MOOD: dict[str, str] = {
    "intro": "hook",
    "outro": "cta",
    "body": "explain",
}

# 产品关键词检测
_PRODUCT_KEYWORDS: dict[str, list[str]] = {
    "claude": ["claude", "anthropic"],
    "claude-code": ["claude code", "claude-code"],
    "cursor": ["cursor"],
    "github": ["github", "copilot"],
    "vscode": ["vscode", "vs code"],
    "chatgpt": ["chatgpt", "gpt-4", "gpt4"],
    "openai": ["openai"],
    "deepseek": ["deepseek"],
    "gemini": ["gemini"],
    "google": ["google"],
}


def _detect_products(text: str) -> list[str]:
    """从文本中检测产品关键词。"""
    text_lower = text.lower()
    found = []
    for product, keywords in _PRODUCT_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            found.append(product)
    return found or ["other"]


def _get_schema_from_segment(seg: dict) -> str:
    """从 segment 推断 visual_type。"""
    comp = seg.get("component", "")
    if comp:
        schema = comp.split(".")[0]
        return _COMPONENT_TO_VISUAL.get(schema, "text_slide")
    material = seg.get("material", "A")
    return {"A": "text_slide", "B": "terminal", "C": "screen_recording"}.get(
        material, "text_slide"
    )


def _extract_tags(seg: dict) -> list[str]:
    """从 segment 内容提取关键词标签。"""
    tags = []
    narration = seg.get("narration_zh", "")
    # 提取引号内的关键词
    quoted = re.findall(r"[「」""]([^「」""]{2,10})[「」""]", narration)
    tags.extend(quoted[:3])
    # slide title 作为标签
    sc = seg.get("slide_content")
    if sc and sc.get("title"):
        tags.append(sc["title"][:12])
    return tags[:5]


def ingest_from_video(
    cfg: Config,
    project_id: str,
    store: AssetStore,
) -> int:
    """视频发布后自动切片入库。

    流程：
    1. 读取 script.json + timing.json
    2. ffmpeg 按 segment 时间切割 final/video.mp4
    3. 自产素材从 script.json 继承标签
    4. 写入 SQLite

    Returns: 入库数量
    """
    output_dir = cfg.output_dir / project_id
    script_path = output_dir / "script.json"
    timing_path = output_dir / "voiceover" / "timing.json"
    video_path = output_dir / "final" / "video.mp4"
    clips_dir = output_dir / "asset_clips"

    if not script_path.exists():
        raise FileNotFoundError(f"script.json not found: {script_path}")
    if not video_path.exists():
        raise FileNotFoundError(f"final/video.mp4 not found: {video_path}")

    script = json.loads(script_path.read_text(encoding="utf-8"))
    segments = script.get("segments", [])

    timing = {}
    if timing_path.exists():
        timing = json.loads(timing_path.read_text(encoding="utf-8"))

    clips_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise FileNotFoundError("ffmpeg not found")

    # 计算每个 segment 的时间偏移
    current_time = 0.0
    seg_times: list[tuple[float, float]] = []
    for seg in segments:
        t = timing.get(str(seg["id"]))
        dur = t["duration"] if t else 5.0
        gap = t.get("gap_after", 0) if t else 0
        seg_times.append((current_time, current_time + dur))
        current_time += dur + gap

    count = 0
    for seg, (start, end) in zip(segments, seg_times):
        seg_id = seg["id"]
        clip_id = f"{project_id}_seg{seg_id}"
        clip_path = clips_dir / f"seg_{seg_id}.mp4"
        duration = end - start

        # ffmpeg 切片
        cmd = [
            ffmpeg, "-y",
            "-ss", str(start),
            "-i", str(video_path),
            "-t", str(duration),
            "-c", "copy",
            "-avoid_negative_ts", "1",
            str(clip_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue

        meta = AssetMeta(
            clip_id=clip_id,
            source_video=project_id,
            time_range_start=start,
            time_range_end=end,
            duration=duration,
            captured_date=today,
            visual_type=_get_schema_from_segment(seg),
            tags=_extract_tags(seg),
            product=_detect_products(seg.get("narration_zh", "")),
            mood=_TYPE_TO_MOOD.get(seg.get("type", "body"), "explain"),
            has_text_overlay=bool(seg.get("slide_content") or seg.get("image_content")),
            reusable=True,
            freshness="evergreen" if _get_schema_from_segment(seg) in ("diagram", "chart", "text_slide") else "current",
            file_path=str(clip_path.relative_to(cfg.output_dir)),
        )

        try:
            store.insert(meta)
            count += 1
        except ValueError:
            continue

    return count


# ── 外部素材 LLM 打标入库 ────────────────────────────────

def extract_keyframes(
    video_path: Path,
    output_dir: Path,
    count: int = 3,
) -> list[Path]:
    """从视频中抽取关键帧（首帧、中间帧、末帧）。"""
    from v2g.asset_normalize import get_video_info

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise FileNotFoundError("ffmpeg not found")

    info = get_video_info(video_path)
    duration = info["duration"]
    if duration <= 0:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    frames = []

    # 均匀分布的时间点
    timestamps = [0]
    if count >= 3:
        timestamps.append(duration / 2)
    timestamps.append(max(0, duration - 0.5))

    for i, ts in enumerate(timestamps[:count]):
        out = output_dir / f"frame_{i}.jpg"
        cmd = [
            ffmpeg, "-y",
            "-ss", str(ts),
            "-i", str(video_path),
            "-frames:v", "1",
            "-q:v", "2",
            str(out),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=10)
            if out.exists():
                frames.append(out)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue

    return frames
