"""Stage 2: 调用 l2n 下载视频 + 生成字幕翻译。"""

import re
from dataclasses import asdict
from pathlib import Path

import click

from v2g.config import Config
from v2g.checkpoint import PipelineState, SourceVideo


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


def run_prepare(cfg: Config, video_id_or_url: str, model: str,
                whisper_model: str = "medium", use_whisper: bool = True) -> PipelineState:
    """执行 Stage 2: 下载 + 字幕翻译。"""
    video_id = _extract_video_id(video_id_or_url)
    url = _build_youtube_url(video_id)

    state = PipelineState.load(cfg.output_dir, video_id)
    state.video_id = video_id
    state.video_url = url
    state.selected = True

    # 1) 生成字幕
    if not state.subtitled:
        click.echo("📝 生成字幕翻译...")
        try:
            from l2n.subtitle import generate_subtitle
            srt_path = generate_subtitle(
                url, model,
                target_lang="zh",
                use_whisper=use_whisper,
                whisper_model=whisper_model,
            )
            click.echo(f"   ✅ 字幕: {srt_path}")
        except Exception as e:
            state.last_error = f"字幕生成失败: {e}"
            state.save(cfg.output_dir)
            raise click.ClickException(state.last_error)

        # l2n 可能把文件写到 output/subtitle/，确保迁移到 sources/
        source_dir = _ensure_source_dir(video_id, cfg)
        state.subtitled = True
        state.en_srt = str((source_dir / "subtitle_en.srt").resolve())
        state.zh_srt = str((source_dir / "subtitle_zh.srt").resolve())
    else:
        click.echo("⏭️  字幕已存在，跳过")

    # 2) 下载视频
    if not state.downloaded:
        click.echo("📥 下载视频...")
        try:
            from l2n.downloader import download_video, _find_existing_video

            source_dir = _ensure_source_dir(video_id, cfg)
            existing = _find_existing_video(source_dir) if source_dir.exists() else None
            if existing and not str(existing).endswith(".part"):
                click.echo(f"   ⏭️ 视频已存在: {existing.name}")
                state.source_video = str(existing.resolve())
            else:
                download_video(url)
                source_dir = _ensure_source_dir(video_id, cfg)
                existing = _find_existing_video(source_dir)
                if existing:
                    state.source_video = str(existing.resolve())
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
                      topic: str, model: str,
                      whisper_model: str = "medium",
                      use_whisper: bool = True) -> PipelineState:
    """批量准备 N 个源视频: 下载 + 字幕翻译。"""
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

        # 1) 字幕
        try:
            click.echo(f"   📝 字幕翻译...")
            from l2n.subtitle import generate_subtitle
            generate_subtitle(
                src.video_url, model,
                target_lang="zh",
                use_whisper=use_whisper,
                whisper_model=whisper_model,
            )
            source_dir = _ensure_source_dir(src.video_id, cfg)
            src.en_srt_path = str((source_dir / "subtitle_en.srt").resolve())
            src.zh_srt_path = str((source_dir / "subtitle_zh.srt").resolve())
            click.echo(f"   ✅ 字幕完成")
        except Exception as e:
            click.echo(f"   ❌ 字幕失败: {e}")
            all_done = False
            state.sources[i] = asdict(src)
            state.save(cfg.output_dir)
            continue

        # 2) 下载视频
        try:
            click.echo(f"   📥 下载视频...")
            from l2n.downloader import download_video, _find_existing_video
            source_dir = _ensure_source_dir(src.video_id, cfg)
            existing = _find_existing_video(source_dir) if source_dir.exists() else None
            if existing and not str(existing).endswith(".part"):
                src.source_video_path = str(existing.resolve())
            else:
                download_video(src.video_url)
                source_dir = _ensure_source_dir(src.video_id, cfg)
                existing = _find_existing_video(source_dir)
                if existing:
                    src.source_video_path = str(existing.resolve())
            click.echo(f"   ✅ 视频完成")
        except Exception as e:
            click.echo(f"   ❌ 视频下载失败: {e}")
            all_done = False
            state.sources[i] = asdict(src)
            state.save(cfg.output_dir)
            continue

        # 提取频道名和标题
        try:
            import subprocess, json as _json
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
