"""Stage 2: 调用 yt-dlp 下载视频 + 英文字幕。"""

import re
import subprocess
from dataclasses import asdict
from pathlib import Path

import click

from v2g.config import Config
from v2g.checkpoint import PipelineState, SourceVideo


VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi"}

# macOS Homebrew 路径可能不在 venv PATH 中
_HOMEBREW_BIN = "/opt/homebrew/bin"


def _which(name: str) -> str | None:
    """shutil.which 的增强版，额外搜索 Homebrew 路径。"""
    import shutil
    found = shutil.which(name)
    if found:
        return found
    candidate = Path(_HOMEBREW_BIN) / name
    if candidate.exists():
        return str(candidate)
    return None


def _extract_video_id(video_id_or_url: str) -> str:
    """从 URL 或纯 ID 提取 video_id。"""
    if re.match(r"^[\w-]{11}$", video_id_or_url):
        return video_id_or_url
    patterns = [
        r"(?:v=|youtu\.be/|embed/)([^&?/]+)",
    ]
    for pat in patterns:
        m = re.search(pat, video_id_or_url)
        if m:
            return m.group(1)
    return video_id_or_url


def _build_youtube_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def _find_source_dir(video_id: str, cfg: Config) -> Path:
    """查找视频素材目录，按优先级搜索多个可能的位置。"""
    candidates = [
        cfg.sources_dir / video_id,                   # sources/{video_id} (新路径)
        Path("output/subtitle") / video_id,           # output/subtitle/{video_id} (旧路径，向后兼容)
        cfg.l2n_output_dir / video_id,                # l2n 配置路径
    ]
    for d in candidates:
        if d.exists() and any(d.iterdir()):
            return d
    return candidates[0]  # 默认新路径


def _ensure_source_dir(video_id: str, cfg: Config) -> Path:
    """确保 sources/{video_id}/ 目录存在，如果素材在旧路径则迁移。"""
    new_dir = cfg.sources_dir / video_id
    if new_dir.exists() and any(new_dir.iterdir()):
        return new_dir

    # 检查旧路径是否有素材
    old_candidates = [
        Path("output/subtitle") / video_id,
        cfg.l2n_output_dir / video_id,
    ]
    for old_dir in old_candidates:
        if old_dir.exists() and any(old_dir.iterdir()):
            # 将旧路径软链接到新路径（避免重复占用磁盘）
            new_dir.parent.mkdir(parents=True, exist_ok=True)
            if not new_dir.exists():
                new_dir.symlink_to(old_dir.resolve())
            return new_dir

    new_dir.mkdir(parents=True, exist_ok=True)
    return new_dir


def _find_existing_video(source_dir: Path) -> Path | None:
    """在目录中查找已有的视频文件。"""
    if not source_dir.exists():
        return None
    for f in source_dir.iterdir():
        if f.suffix.lower() in VIDEO_EXTS and not str(f).endswith(".part"):
            return f
    return None


def _download_subtitle(url: str, output_dir: Path) -> Path | None:
    """用 yt-dlp 下载英文字幕，返回 srt 路径。

    优先下载人工字幕，fallback 到自动生成字幕。
    """
    srt_path = output_dir / "subtitle_en.srt"
    if srt_path.exists():
        click.echo(f"   ⏭️ 英文字幕已存在: {srt_path.name}")
        return srt_path

    ytdlp = _which("yt-dlp") or "yt-dlp"

    # 先尝试人工字幕
    result = subprocess.run(
        [
            ytdlp,
            "--write-sub", "--sub-lang", "en",
            "--sub-format", "srt",
            "--skip-download",
            "--no-write-auto-sub",
            "-o", str(output_dir / "subtitle_en"),
            url,
        ],
        capture_output=True, text=True, timeout=60,
    )
    # yt-dlp 会写 subtitle_en.en.srt，重命名
    for f in output_dir.glob("subtitle_en.en.*"):
        if f.suffix in (".srt", ".vtt"):
            target = output_dir / f"subtitle_en{f.suffix}"
            f.rename(target)

    # 如果人工字幕没下到，尝试自动字幕
    if not srt_path.exists():
        result = subprocess.run(
            [
                ytdlp,
                "--write-auto-sub", "--sub-lang", "en",
                "--sub-format", "srt",
                "--skip-download",
                "-o", str(output_dir / "subtitle_en"),
                url,
            ],
            capture_output=True, text=True, timeout=60,
        )
        for f in output_dir.glob("subtitle_en.en.*"):
            if f.suffix in (".srt", ".vtt"):
                target = output_dir / f"subtitle_en{f.suffix}"
                f.rename(target)

    # vtt → srt 转换（如果只拿到 vtt）
    vtt_path = output_dir / "subtitle_en.vtt"
    if vtt_path.exists() and not srt_path.exists():
        _vtt_to_srt(vtt_path, srt_path)
        vtt_path.unlink()

    return srt_path if srt_path.exists() else None


def _vtt_to_srt(vtt_path: Path, srt_path: Path) -> None:
    """简单的 VTT → SRT 转换。"""
    lines = vtt_path.read_text(encoding="utf-8").splitlines()
    srt_lines = []
    counter = 0
    i = 0
    # 跳过 VTT 头
    while i < len(lines) and not re.match(r"\d{2}:\d{2}", lines[i]):
        i += 1

    while i < len(lines):
        line = lines[i].strip()
        # 时间行
        if re.match(r"\d{2}:\d{2}", line) and "-->" in line:
            counter += 1
            # 转换时间格式：VTT 用 . 而 SRT 用 ,
            time_line = line.replace(".", ",")
            # 去掉 position/align 等属性
            time_line = re.sub(r"\s+(?:position|align|size|line):[^\s]+", "", time_line)
            srt_lines.append(str(counter))
            srt_lines.append(time_line)
            i += 1
            # 收集文本行
            while i < len(lines) and lines[i].strip():
                text = lines[i].strip()
                # 去掉 VTT 标签
                text = re.sub(r"<[^>]+>", "", text)
                if text:
                    srt_lines.append(text)
                i += 1
            srt_lines.append("")
        else:
            i += 1

    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")


def _download_video(url: str, output_dir: Path) -> Path | None:
    """用 yt-dlp 下载视频到指定目录，返回视频路径。"""
    existing = _find_existing_video(output_dir)
    if existing:
        click.echo(f"   ⏭️ 视频已存在: {existing.name}")
        return existing

    ytdlp = _which("yt-dlp") or "yt-dlp"
    ffmpeg_path = _which("ffmpeg")
    output_template = str(output_dir / "video.%(ext)s")

    cmd = [ytdlp]
    if ffmpeg_path:
        # 告诉 yt-dlp ffmpeg 的位置，下载最佳画质+音频合并
        cmd += ["--ffmpeg-location", str(Path(ffmpeg_path).parent)]
        cmd += ["-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"]
        cmd += ["--merge-output-format", "mp4"]
    else:
        # 无 ffmpeg: 下载已合并的最佳单流
        cmd += ["-f", "best[ext=mp4]/best"]

    cmd += ["-o", output_template, url]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())

    return _find_existing_video(output_dir)


def run_prepare(cfg: Config, video_id_or_url: str, model: str = "",
                whisper_model: str = "medium", use_whisper: bool = True) -> PipelineState:
    """执行 Stage 2: 下载英文字幕 + 下载视频。"""
    video_id = _extract_video_id(video_id_or_url)
    url = _build_youtube_url(video_id)

    state = PipelineState.load(cfg.output_dir, video_id)
    state.video_id = video_id
    state.video_url = url
    state.selected = True

    source_dir = _ensure_source_dir(video_id, cfg)

    # 1) 下载英文字幕
    if not state.subtitled:
        click.echo("📝 下载英文字幕...")
        try:
            srt_path = _download_subtitle(url, source_dir)
            if srt_path and srt_path.exists():
                click.echo(f"   ✅ 字幕: {srt_path}")
            else:
                click.echo("   ⚠️ 未找到英文字幕（视频可能无字幕）")
        except Exception as e:
            state.last_error = f"字幕下载失败: {e}"
            state.save(cfg.output_dir)
            raise click.ClickException(state.last_error)

        en_srt = source_dir / "subtitle_en.srt"
        zh_srt = source_dir / "subtitle_zh.srt"
        state.en_srt = str(en_srt.resolve()) if en_srt.exists() else ""
        state.zh_srt = str(zh_srt.resolve()) if zh_srt.exists() else ""
        # 单视频流程允许 zh/en 任一字幕作为脚本输入
        state.subtitled = bool(state.zh_srt or state.en_srt)
    else:
        click.echo("⏭️  字幕已存在，跳过")
        # 自愈：历史项目可能只有 en 或手动补了 zh，进入 prepare 时同步状态
        en_srt = source_dir / "subtitle_en.srt"
        zh_srt = source_dir / "subtitle_zh.srt"
        state.en_srt = str(en_srt.resolve()) if en_srt.exists() else ""
        state.zh_srt = str(zh_srt.resolve()) if zh_srt.exists() else ""
        state.subtitled = bool(state.zh_srt or state.en_srt)

    # 2) 下载视频
    if not state.downloaded:
        click.echo("📥 下载视频...")
        try:
            video_path = _download_video(url, source_dir)
            if video_path:
                state.source_video = str(video_path.resolve())
                click.echo(f"   ✅ 视频: {video_path.name}")
            else:
                click.echo("   ⚠️ 视频下载后未找到文件")
        except Exception as e:
            state.last_error = f"视频下载失败: {e}"
            state.save(cfg.output_dir)
            raise click.ClickException(state.last_error)

        state.downloaded = True
    else:
        click.echo("⏭️  视频已下载，跳过")

    state.last_error = ""
    state.save(cfg.output_dir)
    return state


def run_multi_prepare(cfg: Config, urls: list[str], project_id: str,
                      topic: str, model: str = "",
                      whisper_model: str = "medium",
                      use_whisper: bool = True) -> PipelineState:
    """批量准备 N 个源视频: 下载字幕 + 下载视频。"""
    state = PipelineState.load(cfg.output_dir, project_id)
    state.project_id = project_id
    state.video_id = project_id
    state.topic = topic
    state.created_at = state.created_at or __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()

    # 初始化 sources（如果首次运行）
    existing_ids = {s["video_id"] if isinstance(s, dict) else s.video_id for s in state.sources}

    for url in urls:
        vid = _extract_video_id(url.strip())
        if vid in existing_ids:
            continue
        state.sources.append(asdict(SourceVideo(
            video_id=vid,
            video_url=_build_youtube_url(vid),
        )))

    total = len(state.sources)
    click.echo(f"📦 多源准备: {total} 个视频, 主题: {topic}\n")

    all_done = True
    for i, src_dict in enumerate(state.sources):
        src = SourceVideo(**src_dict) if isinstance(src_dict, dict) else src_dict
        click.echo(f"{'='*50}")
        click.echo(f"[{i+1}/{total}] {src.video_url}")

        if src.prepared:
            click.echo(f"⏭️  已完成，跳过\n")
            continue

        source_dir = _ensure_source_dir(src.video_id, cfg)

        # 1) 字幕
        try:
            click.echo(f"   📝 下载英文字幕...")
            srt_path = _download_subtitle(src.video_url, source_dir)
            en_srt = source_dir / "subtitle_en.srt"
            src.en_srt_path = str(en_srt.resolve()) if en_srt.exists() else ""
            src.zh_srt_path = ""
            if srt_path:
                click.echo(f"   ✅ 字幕完成")
            else:
                click.echo(f"   ⚠️ 未找到英文字幕")
        except Exception as e:
            click.echo(f"   ❌ 字幕失败: {e}")
            all_done = False
            state.sources[i] = asdict(src)
            state.save(cfg.output_dir)
            continue

        # 2) 下载视频
        try:
            click.echo(f"   📥 下载视频...")
            video_path = _download_video(src.video_url, source_dir)
            if video_path:
                src.source_video_path = str(video_path.resolve())
            click.echo(f"   ✅ 视频完成")
        except Exception as e:
            click.echo(f"   ❌ 视频下载失败: {e}")
            all_done = False
            state.sources[i] = asdict(src)
            state.save(cfg.output_dir)
            continue

        # 提取频道名和标题
        try:
            import json as _json
            result = subprocess.run(
                ["yt-dlp", "--dump-json", "--no-download", src.video_url],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                info = _json.loads(result.stdout)
                src.channel_name = info.get("channel", info.get("uploader", ""))
                src.title = info.get("title", "")
        except Exception:
            pass

        src.prepared = True
        state.sources[i] = asdict(src)
        state.save(cfg.output_dir)
        click.echo()

    state.subtitled = all_done
    state.downloaded = all_done
    state.selected = True
    state.save(cfg.output_dir)

    done_count = sum(1 for s in state.get_sources() if s.prepared)
    click.echo(f"\n📊 准备完成: {done_count}/{total}")
    return state
