"""Stage 5b: FFmpeg 三素材合成最终视频。"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import click

from v2g.config import Config
from v2g.checkpoint import PipelineState


# ─── FFmpeg 路径解析 ────────────────────────────────────────

def _get_ffmpeg() -> str:
    """获取支持 drawtext/ass 的 ffmpeg 路径。
    优先使用 imageio-ffmpeg 捆绑的完整版本（自带 libfreetype/libass），
    fallback 到系统 PATH 中的 ffmpeg。
    """
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def _get_ffprobe() -> str:
    """获取 ffprobe 路径（与 ffmpeg 同目录）。"""
    ffmpeg = _get_ffmpeg()
    if ffmpeg != "ffmpeg":
        probe = Path(ffmpeg).parent / "ffprobe"
        if probe.exists():
            return str(probe)
    return "ffprobe"


FFMPEG = _get_ffmpeg()
FFPROBE = _get_ffprobe()


# ─── 工具函数 ───────────────────────────────────────────────

def _ffprobe_duration(path: Path) -> float:
    """获取媒体文件时长。"""
    result = subprocess.run(
        [FFPROBE, "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, timeout=10,
    )
    return float(result.stdout.strip())


def _run_ffmpeg(args: list[str], timeout: int = 600):
    """执行 FFmpeg 命令。"""
    result = subprocess.run(
        [FFMPEG, "-y"] + args,
        capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg 失败: {result.stderr[-500:]}")


def _find_cjk_font() -> str | None:
    """查找系统 CJK 字体。"""
    candidates = [
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
    ]
    for f in candidates:
        if Path(f).exists():
            return f
    return None


def _strip_emoji(text: str) -> str:
    """去掉 emoji 和特殊 Unicode 符号，保留中英文和基础标点。"""
    # 保留: CJK 汉字、ASCII、基础标点、常见中文标点
    return re.sub(
        r'[^\u4e00-\u9fff\u3000-\u303f\uff00-\uffef'
        r'a-zA-Z0-9\s'
        r'.,;:!?\-+=/()（）【】《》、。，；：！？""''…—\n]',
        '', text
    )


# ─── 素材处理 ───────────────────────────────────────────────

def _make_slide_video(slide_path: Path, duration: float, output_path: Path,
                      width: int, height: int, fps: int):
    """将静态图片转为指定时长的视频片段。"""
    _run_ffmpeg([
        "-loop", "1", "-i", str(slide_path),
        "-t", str(duration),
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
               f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black",
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-r", str(fps), "-an",
        str(output_path),
    ])


def _make_placeholder_video(text: str, duration: float, output_path: Path,
                            width: int, height: int, fps: int):
    """用 drawtext 生成占位卡片视频（黑底 + 一行简要描述）。"""
    # 只取前 30 字作为简要描述
    short = _strip_emoji(text)[:30].replace("'", "\u2019").replace(":", " ")
    font = _find_cjk_font()
    fontfile = f":fontfile={font}" if font else ""

    _run_ffmpeg([
        "-f", "lavfi",
        "-i", f"color=c=0x1a1a2e:s={width}x{height}:d={duration}:r={fps}",
        "-vf", f"drawtext=text='{short}'"
               f":fontsize=42:fontcolor=0xaaaaaa"
               f":x=(w-text_w)/2:y=(h-text_h)/2"
               f"{fontfile}",
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-an",
        str(output_path),
    ])


def _extract_clip(source_video: Path, start: float, end: float, output_path: Path,
                  width: int, height: int, fps: int, source_channel: str = ""):
    """从原视频提取片段，静音 + 裁掉底部硬字幕 + drawtext 水印。"""
    duration = end - start

    # crop 掉底部 15% 遮挡原视频硬字幕，再 pad 回原尺寸
    crop_h = int(height * 0.85)
    vf_parts = [
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black",
        f"crop={width}:{crop_h}:0:0,"
        f"pad={width}:{height}:0:0:color=black",
    ]

    # drawtext 水印
    if source_channel:
        safe_ch = source_channel.replace("'", "\u2019").replace(":", " ")
        font = _find_cjk_font()
        fontfile = f":fontfile={font}" if font else ""
        vf_parts.append(
            f"drawtext=text='Source  {safe_ch}'"
            f":fontsize=28:fontcolor=white@0.7"
            f":x=30:y=25:borderw=1:bordercolor=black@0.5"
            f"{fontfile}"
        )

    vf = ",".join(vf_parts)
    _run_ffmpeg([
        "-ss", str(start), "-t", str(duration),
        "-i", str(source_video),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-r", str(fps), "-an",
        str(output_path),
    ])


def _loop_to_duration(input_path: Path, target_duration: float, output_path: Path):
    """原速播放视频片段，播完后定格最后一帧直到填满目标时长。"""
    actual_duration = _ffprobe_duration(input_path)
    if actual_duration <= 0:
        shutil.copy2(input_path, output_path)
        return

    if actual_duration >= target_duration:
        # 片段已够长，直接裁剪到目标时长
        _run_ffmpeg([
            "-i", str(input_path),
            "-t", str(target_duration),
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-an",
            str(output_path),
        ])
    else:
        # 原速播放 + tpad 定格最后一帧填满剩余时长
        pad_duration = target_duration - actual_duration
        _run_ffmpeg([
            "-i", str(input_path),
            "-vf", f"tpad=stop_mode=clone:stop_duration={pad_duration:.2f}",
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-an",
            str(output_path),
        ])


def _speed_adjust(input_path: Path, target_duration: float, output_path: Path):
    """变速调整视频以匹配目标时长。"""
    actual_duration = _ffprobe_duration(input_path)
    if actual_duration <= 0:
        return

    speed_factor = actual_duration / target_duration
    speed_factor = max(0.5, min(2.0, speed_factor))

    if abs(speed_factor - 1.0) < 0.05:
        shutil.copy2(input_path, output_path)
        return

    _run_ffmpeg([
        "-i", str(input_path),
        "-vf", f"setpts=PTS/{speed_factor}",
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-an",
        str(output_path),
    ])


# ─── ASS 字幕生成 (逐句分段) ──────────────────────────────

def _split_narration(text: str, duration: float) -> list[tuple[str, float, float]]:
    """将一段 narration 按标点切分为多条字幕，均匀分配时间。

    返回 [(字幕文本, 相对起始秒, 相对结束秒), ...]
    每条字幕最多 2 行 x 18 字 = 36 字。
    """
    # 按中文句号、问号、感叹号、逗号（长句时）切分
    parts = re.split(r'(?<=[。！？；])', text.strip())
    # 去空
    parts = [p.strip() for p in parts if p.strip()]

    # 合并太短的片段（< 8 字合到前一条）
    merged = []
    for p in parts:
        if merged and len(merged[-1]) < 8:
            merged[-1] += p
        else:
            merged.append(p)
    if not merged:
        merged = [text]

    # 如果某条仍超 36 字，按逗号再拆
    final = []
    for m in merged:
        if len(m) <= 36:
            final.append(m)
        else:
            sub = re.split(r'(?<=[，,])', m)
            buf = ""
            for s in sub:
                if len(buf) + len(s) <= 36:
                    buf += s
                else:
                    if buf:
                        final.append(buf)
                    buf = s
            if buf:
                final.append(buf)

    if not final:
        final = [text]

    # 按字数比例分配时间
    total_chars = sum(len(f) for f in final)
    if total_chars == 0:
        return [(text, 0.0, duration)]

    result = []
    t = 0.0
    for f in final:
        seg_dur = duration * len(f) / total_chars
        # 每条字幕最多 2 行 x 18 字
        display = f
        if len(display) > 18:
            display = display[:18] + "\\N" + display[18:36]
        result.append((display, t, t + seg_dur))
        t += seg_dur

    return result


def _generate_ass(segments: list[dict], timing: dict,
                  width: int, height: int,
                  skip_material_a: bool = True) -> str:
    """生成 ASS 字幕文件，逐句显示。

    skip_material_a: 素材 A (PPT) 段不加字幕（卡片已有文字）。
    """
    font = _find_cjk_font()
    fontname = "Hiragino Sans GB" if font and "Hiragino" in font else "PingFang SC"

    header = f"""[Script Info]
Title: video2gen subtitles
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{fontname},48,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,40,40,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    current_time = 0.0

    for seg in segments:
        seg_id = str(seg.get("id", 0))
        narration = seg.get("narration_zh", "").strip()
        material = seg.get("material", "")

        if not narration or seg_id not in timing:
            continue

        duration = timing[seg_id]["duration"]

        # 素材 A 段不叠字幕（卡片本身已有文字内容）
        if skip_material_a and material == "A":
            current_time += duration
            continue

        # 逐句切分
        sub_parts = _split_narration(narration, duration)
        for text, rel_start, rel_end in sub_parts:
            abs_start = current_time + rel_start
            abs_end = current_time + rel_end
            start_str = _seconds_to_ass_time(abs_start)
            end_str = _seconds_to_ass_time(abs_end)
            events.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text}")

        current_time += duration

    return header + "\n".join(events) + "\n"


def _seconds_to_ass_time(seconds: float) -> str:
    """秒 → ASS 时间格式 (H:MM:SS.CC)。"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


# ─── 审核辅助 ──────────────────────────────────────────────

def check_recordings(script_json_path: Path, recordings_dir: Path) -> list[tuple[int, str]]:
    """检查录屏素材就绪状态，返回缺失的 (seg_id, instruction) 列表。"""
    if not script_json_path.exists():
        return []

    script_data = json.loads(script_json_path.read_text(encoding="utf-8"))
    missing = []

    for seg in script_data.get("segments", []):
        if seg.get("material") != "B":
            continue
        seg_id = seg.get("id", 0)
        found = any(
            (recordings_dir / f"seg_{seg_id}{ext}").exists()
            for ext in [".mp4", ".mov", ".webm", ".mkv"]
        )
        if not found:
            missing.append((seg_id, seg.get("recording_instruction", "无说明")))

    return missing


def _find_recording(recordings_dir: Path, seg_id: int) -> Path | None:
    """查找录屏文件。"""
    for ext in [".mp4", ".mov", ".webm", ".mkv"]:
        path = recordings_dir / f"seg_{seg_id}{ext}"
        if path.exists():
            return path
    return None


# ─── 主合成流程 ────────────────────────────────────────────

def run_assemble(cfg: Config, video_id: str) -> PipelineState:
    """执行 Stage 5b: 三素材合成最终视频。"""
    from v2g.workflow_contract import sync_workflow_contract

    state = PipelineState.load(cfg.output_dir, video_id)
    if not state.slides_done:
        raise click.ClickException("图文卡片尚未生成，请先运行 v2g slides")

    if state.assembled:
        click.echo("⏭️  视频已合成，跳过")
        sync_workflow_contract(
            cfg.output_dir / video_id, video_id,
            stage="assemble", status="skip",
            message="视频已合成，跳过",
        )
        return state

    output_dir = cfg.output_dir / video_id
    sync_workflow_contract(
        output_dir, video_id,
        stage="assemble", status="start",
        message="开始 FFmpeg 合成",
    )
    temp_dir = output_dir / "_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    w, h, fps = cfg.video_width, cfg.video_height, cfg.video_fps

    # 加载数据
    script_data = json.loads(Path(state.script_json).read_text(encoding="utf-8"))
    timing_path = output_dir / "voiceover" / "timing.json"
    if not timing_path.exists():
        # 向后兼容旧路径
        timing_path = output_dir / "voiceover_timing.json"
    timing = json.loads(timing_path.read_text(encoding="utf-8"))

    segments = script_data.get("segments", [])
    source_channel = script_data.get("source_channel", "")
    source_video = Path(state.source_video) if state.source_video else None

    slides_dir = output_dir / "slides"
    recordings_dir = output_dir / "recordings"

    # --- 素材 C 时长校验: clamp ≤ 10s ---
    for seg in segments:
        if seg.get("material") == "C":
            start = seg.get("source_start", 0)
            end = seg.get("source_end", start + 8)
            if end - start > 10:
                seg["source_end"] = start + 10

    click.echo(f"🎬 视频合成 ({len(segments)} 段)")
    segment_videos = []

    for seg in segments:
        seg_id = seg.get("id", 0)
        material = seg.get("material", "A")
        seg_id_str = str(seg_id)

        if seg_id_str not in timing:
            click.echo(f"   ⚠️ Segment {seg_id}: 无 TTS 时长信息，跳过")
            continue

        tts_duration = timing[seg_id_str]["duration"]
        raw_path = temp_dir / f"raw_{seg_id}.mp4"
        final_seg_path = temp_dir / f"seg_{seg_id}.mp4"

        click.echo(f"   Segment {seg_id} [{material}] ({tts_duration:.1f}s): ", nl=False)

        try:
            if material == "A":
                slide_path = slides_dir / f"slide_{seg_id}.png"
                if slide_path.exists():
                    _make_slide_video(slide_path, tts_duration, final_seg_path, w, h, fps)
                else:
                    title = seg.get("slide_content", {}).get("title", "Info Card")
                    _make_placeholder_video(title, tts_duration, final_seg_path, w, h, fps)

            elif material == "B":
                recording = _find_recording(recordings_dir, seg_id)
                if recording:
                    _extract_clip(recording, 0, _ffprobe_duration(recording),
                                  raw_path, w, h, fps)
                    _speed_adjust(raw_path, tts_duration, final_seg_path)
                else:
                    # 无录屏时降级为图文卡片（与素材 A 同样处理）
                    instruction = seg.get("recording_instruction", "需要录屏")
                    steps = [s.strip() for s in re.split(r'[，。；]', instruction) if s.strip()]
                    fallback_content = {
                        "title": "操作演示",
                        "bullet_points": [f"第{i+1}步：{s}" for i, s in enumerate(steps)],
                    }
                    # 生成卡片图片再转视频
                    slide_path = slides_dir / f"slide_{seg_id}_fallback.png"
                    from v2g.slides import generate_slide_image
                    generate_slide_image(fallback_content, seg_id, slide_path, w, h)
                    _make_slide_video(slide_path, tts_duration,
                                     final_seg_path, w, h, fps)

            elif material == "C":
                if source_video and source_video.exists():
                    start = seg.get("source_start", 0)
                    # 直接取 tts_duration 长度的片段，原速播放
                    end = start + tts_duration
                    _extract_clip(source_video, start, end, raw_path,
                                  w, h, fps, source_channel)
                    shutil.copy2(raw_path, final_seg_path)
                else:
                    _make_placeholder_video("原视频不可用", tts_duration,
                                           final_seg_path, w, h, fps)

            if final_seg_path.exists():
                segment_videos.append(final_seg_path)
                click.echo("✅")
            else:
                click.echo("❌ 文件未生成")

        except Exception as e:
            click.echo(f"❌ {e}")
            _make_placeholder_video(f"Segment {seg_id}", tts_duration,
                                    final_seg_path, w, h, fps)
            if final_seg_path.exists():
                segment_videos.append(final_seg_path)

    if not segment_videos:
        sync_workflow_contract(
            output_dir, video_id,
            stage="assemble", status="error",
            message="没有成功生成任何视频片段",
        )
        raise click.ClickException("没有成功生成任何视频片段")

    # 拼接所有片段（无字幕、无音频）
    click.echo("   🔗 拼接视频片段...")
    concat_list = temp_dir / "concat.txt"
    with open(concat_list, "w") as f:
        for vp in segment_videos:
            f.write(f"file '{vp.resolve()}'\n")

    concat_path = temp_dir / "concat.mp4"
    _run_ffmpeg([
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-an",
        str(concat_path),
    ])

    # 生成 ASS 字幕（逐句分段，素材 A 不加字幕）
    click.echo("   📝 生成 ASS 字幕...")
    ass_content = _generate_ass(segments, timing, w, h, skip_material_a=True)
    final_dir = output_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    ass_path = final_dir / "subtitles.ass"
    ass_path.write_text(ass_content, encoding="utf-8")

    # 最终合成: 视频 + ASS 字幕 + 音频
    click.echo("   🎨 最终合成 (ASS 字幕烧录 + 音频混合)...")
    final_path = final_dir / "video.mp4"
    voiceover_path = Path(state.voiceover)

    # 使用 ass filter 烧录字幕（需要 libass）
    _run_ffmpeg([
        "-i", str(concat_path),
        "-i", str(voiceover_path),
        "-vf", f"ass='{ass_path}'",
        "-c:v", "libx264", "-preset", "medium", "-crf", str(cfg.video_crf),
        "-c:a", "aac", "-b:a", "192k",
        "-r", str(fps),
        "-movflags", "+faststart",
        "-shortest",
        str(final_path),
    ])

    # 清理临时文件
    shutil.rmtree(temp_dir, ignore_errors=True)

    if final_path.exists():
        size_mb = final_path.stat().st_size / (1024 * 1024)
        duration = _ffprobe_duration(final_path)
        click.echo(f"   ✅ 完成: {final_path.name} ({size_mb:.1f}MB, {duration:.0f}s)")
    else:
        sync_workflow_contract(
            output_dir, video_id,
            stage="assemble", status="error",
            message="最终视频合成失败",
        )
        raise click.ClickException("最终视频合成失败")

    state.assembled = True
    state.final_video = str(final_path)
    state.last_error = ""
    state.save(cfg.output_dir)
    sync_workflow_contract(
        output_dir, video_id,
        stage="assemble", status="ok",
        message="视频合成完成",
        extra={"final_video": str(final_path)},
    )
    return state
