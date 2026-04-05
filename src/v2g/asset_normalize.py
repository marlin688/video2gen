"""外部素材预处理：分辨率适配、编码统一、音频处理。"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

TARGET_WIDTH = 1920
TARGET_HEIGHT = 1080


def _find_ffmpeg() -> str:
    """查找 ffmpeg 可执行文件。"""
    ff = shutil.which("ffmpeg")
    if ff:
        return ff
    raise FileNotFoundError(
        "ffmpeg 未找到，请安装 ffmpeg 或设置 PATH"
    )


def _find_ffprobe() -> str:
    """查找 ffprobe 可执行文件。"""
    fp = shutil.which("ffprobe")
    if fp:
        return fp
    raise FileNotFoundError(
        "ffprobe 未找到，请安装 ffmpeg 或设置 PATH"
    )


def get_video_info(input_path: Path) -> dict:
    """获取视频基本信息（宽高、时长、编码）。"""
    ffprobe = _find_ffprobe()
    cmd = [
        ffprobe, "-v", "quiet",
        "-print_format", "json",
        "-show_streams", "-show_format",
        str(input_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    import json
    data = json.loads(result.stdout)

    video_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
        None,
    )
    if not video_stream:
        return {"width": 0, "height": 0, "duration": 0, "codec": "unknown"}

    return {
        "width": int(video_stream.get("width", 0)),
        "height": int(video_stream.get("height", 0)),
        "duration": float(data.get("format", {}).get("duration", 0)),
        "codec": video_stream.get("codec_name", "unknown"),
    }


def normalize_video(
    input_path: Path,
    output_path: Path,
    *,
    target_width: int = TARGET_WIDTH,
    target_height: int = TARGET_HEIGHT,
    mute: bool = True,
    clip_start: float | None = None,
    clip_end: float | None = None,
) -> Path:
    """统一处理外部视频素材。

    - 分辨率适配 target_width x target_height（居中裁切 + 高斯模糊背景填充）
    - 编码统一为 H.264
    - 音频默认静音
    - 可选时间段截取
    """
    ffmpeg = _find_ffmpeg()
    info = get_video_info(input_path)

    cmd = [ffmpeg, "-y"]

    # 时间段截取
    if clip_start is not None:
        cmd += ["-ss", str(clip_start)]
    cmd += ["-i", str(input_path)]
    if clip_end is not None and clip_start is not None:
        cmd += ["-t", str(clip_end - clip_start)]
    elif clip_end is not None:
        cmd += ["-t", str(clip_end)]

    # 决定缩放策略
    src_w, src_h = info["width"], info["height"]
    src_ratio = src_w / max(src_h, 1)
    target_ratio = target_width / target_height

    if abs(src_ratio - target_ratio) < 0.05:
        # 接近目标比例，直接缩放
        vf = f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black"
    else:
        # 比例差异大：模糊背景 + 前景居中
        vf = (
            f"split[bg][fg];"
            f"[bg]scale={target_width}:{target_height}:force_original_aspect_ratio=increase,"
            f"crop={target_width}:{target_height},gblur=sigma=30[bgout];"
            f"[fg]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease[fgout];"
            f"[bgout][fgout]overlay=(W-w)/2:(H-h)/2"
        )

    cmd += [
        "-filter_complex" if "split" in vf else "-vf", vf,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
    ]

    if mute:
        cmd += ["-an"]
    else:
        cmd += ["-c:a", "aac", "-b:a", "128k"]

    cmd.append(str(output_path))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def normalize_image(
    input_path: Path,
    output_path: Path,
    *,
    target_width: int = TARGET_WIDTH,
    target_height: int = TARGET_HEIGHT,
) -> Path:
    """统一处理外部图片素材。

    - 缩放到目标分辨率（保持比例，黑边填充）
    - 输出 PNG 格式
    """
    ffmpeg = _find_ffmpeg()
    cmd = [
        ffmpeg, "-y",
        "-i", str(input_path),
        "-vf", f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black",
        "-frames:v", "1",
        str(output_path),
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path
