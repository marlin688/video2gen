"""Stage 2: 调用 l2n 下载视频 + 生成字幕翻译。"""

import re
from dataclasses import asdict
from pathlib import Path

import click

from v2g.config import Config
from v2g.checkpoint import PipelineState, SourceVideo


def _extract_video_id(video_id_or_url: str) -> str:
    """从 URL 或纯 ID 提取 video_id。"""
    # 如果已经是纯 ID（11 位字母数字+连字符+下划线）
    if re.match(r"^[\w-]{11}$", video_id_or_url):
        return video_id_or_url
    # 尝试从 URL 提取
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


def run_prepare(cfg: Config, video_id_or_url: str, model: str,
                whisper_model: str = "medium", use_whisper: bool = True) -> PipelineState:
    """执行 Stage 2: 下载 + 字幕翻译。"""
    video_id = _extract_video_id(video_id_or_url)
    url = _build_youtube_url(video_id)

    state = PipelineState.load(cfg.output_dir, video_id)
    state.video_id = video_id
    state.video_url = url
    state.selected = True

    # l2n 使用 CWD 相对的 output/subtitle/ 目录
    # 检查两个可能的位置: CWD 下的和 l2n_output_dir 配置的
    def _find_video_dir() -> Path:
        """查找视频输出目录（兼容 l2n 的相对路径行为）。"""
        candidates = [
            Path("output/subtitle") / video_id,  # CWD 相对路径 (l2n 默认行为)
            cfg.l2n_output_dir / video_id,        # 配置的 l2n 输出目录
        ]
        for d in candidates:
            if d.exists() and any(d.iterdir()):
                return d
        return candidates[0]  # 默认返回第一个

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

        video_dir = _find_video_dir()
        state.subtitled = True
        state.en_srt = str((video_dir / "subtitle_en.srt").resolve())
        state.zh_srt = str((video_dir / "subtitle_zh.srt").resolve())
    else:
        click.echo("⏭️  字幕已存在，跳过")

    # 2) 下载视频
    if not state.downloaded:
        click.echo("📥 下载视频...")
        try:
            from l2n.downloader import download_video, _find_existing_video

            video_dir = _find_video_dir()
            existing = _find_existing_video(video_dir) if video_dir.exists() else None
            if existing and not str(existing).endswith(".part"):
                click.echo(f"   ⏭️ 视频已存在: {existing.name}")
                state.source_video = str(existing.resolve())
            else:
                download_video(url)
                video_dir = _find_video_dir()
                existing = _find_existing_video(video_dir)
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


def _find_video_dir_for(video_id: str, cfg: Config) -> Path:
    """查找视频输出目录。"""
    candidates = [
        Path("output/subtitle") / video_id,
        cfg.l2n_output_dir / video_id,
    ]
    for d in candidates:
        if d.exists() and any(d.iterdir()):
            return d
    return candidates[0]


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
            video_dir = _find_video_dir_for(src.video_id, cfg)
            src.en_srt_path = str((video_dir / "subtitle_en.srt").resolve())
            src.zh_srt_path = str((video_dir / "subtitle_zh.srt").resolve())
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
            video_dir = _find_video_dir_for(src.video_id, cfg)
            existing = _find_existing_video(video_dir) if video_dir.exists() else None
            if existing and not str(existing).endswith(".part"):
                src.source_video_path = str(existing.resolve())
            else:
                download_video(src.video_url)
                video_dir = _find_video_dir_for(src.video_id, cfg)
                existing = _find_existing_video(video_dir)
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
