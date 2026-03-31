"""素材 B 自动录屏: 通过 computer-use 截图序列合成视频。

工作流程:
1. 读取 script.json 中素材 B 段的 recording_instruction
2. 将操作指令拆解为步骤
3. 用 computer-use MCP 逐步执行操作并截图
4. 将截图序列用 FFmpeg 合成为视频

注意: 此模块需要在 Claude Code 会话中运行（有 computer-use MCP 权限）。
单独使用时作为截图序列 → 视频的合成工具。
"""

import json
import subprocess
from pathlib import Path

import click

from v2g.config import Config
from v2g.checkpoint import PipelineState


def _get_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def screenshots_to_video(
    screenshots_dir: Path,
    output_path: Path,
    duration: float,
    width: int = 1920,
    height: int = 1080,
    fps: int = 1,
) -> bool:
    """将一组截图合成为视频。

    每张截图显示 duration/N 秒，通过 FFmpeg concat + 定时实现幻灯片效果。
    适用于静态操作展示（输入命令、展示配置文件等）。

    Args:
        screenshots_dir: 截图目录，文件按名称排序
        output_path: 输出视频路径
        duration: 目标视频总时长（秒）
        width/height: 输出分辨率
        fps: 帧率（截图场景用 1-2 fps 即可）
    """
    # 收集截图文件
    images = sorted([
        f for f in screenshots_dir.iterdir()
        if f.suffix.lower() in (".png", ".jpg", ".jpeg")
    ])

    if not images:
        click.echo(f"   ⚠️ 无截图文件: {screenshots_dir}")
        return False

    # 每张图的显示时长
    per_image = max(1.0, duration / len(images))

    ffmpeg = _get_ffmpeg()

    # 方案: 为每张图生成一段视频，然后 concat
    temp_dir = output_path.parent / "_rec_temp"
    temp_dir.mkdir(exist_ok=True)

    seg_files = []
    for i, img in enumerate(images):
        seg_path = temp_dir / f"img_{i:03d}.mp4"
        result = subprocess.run(
            [ffmpeg, "-y",
             "-loop", "1", "-i", str(img),
             "-t", str(per_image),
             "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black",
             "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
             "-r", "30", "-an",
             str(seg_path)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0 and seg_path.exists():
            seg_files.append(seg_path)

    if not seg_files:
        return False

    # Concat
    concat_list = temp_dir / "concat.txt"
    with open(concat_list, "w") as f:
        for sf in seg_files:
            f.write(f"file '{sf.resolve()}'\n")

    result = subprocess.run(
        [ffmpeg, "-y",
         "-f", "concat", "-safe", "0",
         "-i", str(concat_list),
         "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
         "-an", str(output_path)],
        capture_output=True, text=True, timeout=120,
    )

    # 清理
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

    return result.returncode == 0 and output_path.exists()


def generate_recording_from_screenshots(
    cfg: Config, video_id: str, seg_id: int
) -> Path | None:
    """为指定 segment 从截图目录生成录屏视频。

    截图应放在 output/{video_id}/screenshots/seg_{seg_id}/ 目录下。
    """
    output_dir = cfg.output_dir / video_id
    screenshots_dir = output_dir / "screenshots" / f"seg_{seg_id}"
    recordings_dir = output_dir / "recordings"
    recordings_dir.mkdir(exist_ok=True)

    if not screenshots_dir.exists() or not any(screenshots_dir.iterdir()):
        return None

    # 读取 TTS 时长作为目标时长
    timing_path = output_dir / "voiceover_timing.json"
    if timing_path.exists():
        timing = json.loads(timing_path.read_text(encoding="utf-8"))
        duration = timing.get(str(seg_id), {}).get("duration", 15.0)
    else:
        duration = 15.0

    output_path = recordings_dir / f"seg_{seg_id}.mp4"
    click.echo(f"   🖥️ Segment {seg_id}: {len(list(screenshots_dir.iterdir()))} 张截图 → 视频...")

    if screenshots_to_video(screenshots_dir, output_path, duration,
                            cfg.video_width, cfg.video_height):
        click.echo(f"   ✅ {output_path.name}")
        return output_path
    else:
        click.echo(f"   ❌ 合成失败")
        return None


def run_auto_record(cfg: Config, video_id: str) -> int:
    """自动将所有截图目录转为录屏视频。返回成功数。

    用户需要提前将截图放入:
        output/{video_id}/screenshots/seg_{id}/
    每个目录下的图片按文件名排序即为操作步骤顺序。
    """
    output_dir = cfg.output_dir / video_id
    screenshots_base = output_dir / "screenshots"

    if not screenshots_base.exists():
        click.echo("📁 未找到 screenshots/ 目录")
        click.echo(f"   请将操作截图放入: {screenshots_base}/seg_{{id}}/")
        return 0

    # 读取脚本找到所有素材 B 段
    script_path = output_dir / "script.json"
    if not script_path.exists():
        raise click.ClickException("脚本不存在，请先运行 v2g script")

    script_data = json.loads(script_path.read_text(encoding="utf-8"))
    b_segments = [s for s in script_data.get("segments", []) if s.get("material") == "B"]

    if not b_segments:
        click.echo("ℹ️ 脚本中无素材 B 段")
        return 0

    click.echo(f"🖥️ 自动录屏: {len(b_segments)} 段素材 B")
    success = 0
    for seg in b_segments:
        seg_id = seg.get("id", 0)
        result = generate_recording_from_screenshots(cfg, video_id, seg_id)
        if result:
            success += 1

    click.echo(f"\n✅ 自动录屏完成: {success}/{len(b_segments)}")
    return success
