"""全流程编排：串联所有阶段 + 人工审核暂停。"""

import click

from v2g.config import Config
from v2g.checkpoint import PipelineState
from v2g.preparer import _extract_video_id


def run_pipeline(cfg: Config, video_id_or_url: str, model: str,
                 whisper_model: str = "medium"):
    """执行完整流水线，在人工审核点暂停。"""
    video_id = _extract_video_id(video_id_or_url)
    state = PipelineState.load(cfg.output_dir, video_id)

    click.echo(f"🚀 video2gen 流水线: {video_id}")
    click.echo(f"   当前阶段: {state.current_stage}\n")

    # Stage 2: 下载 + 字幕翻译
    if not state.subtitled or not state.downloaded:
        click.echo("=" * 50)
        click.echo("📥 Stage 2: 下载 + 字幕翻译")
        click.echo("=" * 50)
        from v2g.preparer import run_prepare
        state = run_prepare(cfg, video_id_or_url, model, whisper_model)

    # Stage 3: AI 脚本
    if not state.scripted:
        click.echo("\n" + "=" * 50)
        click.echo("🤖 Stage 3: AI 解说脚本")
        click.echo("=" * 50)
        from v2g.scriptwriter import run_script
        state = run_script(cfg, video_id, model)

    # 人工审核点 1: 脚本审核
    if not state.script_reviewed:
        click.echo("\n" + "=" * 50)
        click.echo("✋ 暂停: 脚本审核")
        click.echo("=" * 50)
        click.echo(f"   脚本: output/{video_id}/script.md")
        click.echo(f"   录屏指南: output/{video_id}/recording_guide.md")
        click.echo(f"\n   请完成以下操作:")
        click.echo(f"   1. 审阅并编辑 script.md / script.json")
        click.echo(f"   2. 按 recording_guide.md 录制操作视频")
        click.echo(f"   3. 将录屏放入 output/{video_id}/recordings/")
        click.echo(f"   4. 运行: v2g review {video_id}")
        click.echo(f"   5. 重新运行: v2g run {video_id_or_url} --model {model}")
        return

    # Stage 4: TTS 配音
    if not state.tts_done:
        click.echo("\n" + "=" * 50)
        click.echo("🎙️ Stage 4: TTS 配音")
        click.echo("=" * 50)
        from v2g.tts import run_tts
        state = run_tts(cfg, video_id, cfg.tts_voice, cfg.tts_rate)

    # Stage 5a: PPT 图文
    if not state.slides_done:
        click.echo("\n" + "=" * 50)
        click.echo("📊 Stage 5a: PPT 图文卡片")
        click.echo("=" * 50)
        from v2g.slides import run_slides
        state = run_slides(cfg, video_id, model)

    # 自动录屏: 将 screenshots/ 下的截图合成为录屏视频
    from v2g.recorder import run_auto_record
    rec_count = run_auto_record(cfg, video_id)
    if rec_count > 0:
        click.echo(f"   🖥️ 自动生成 {rec_count} 段录屏视频")

    # Stage 5b: 视频合成
    if not state.assembled:
        click.echo("\n" + "=" * 50)
        click.echo("🎬 Stage 5b: 视频合成")
        click.echo("=" * 50)
        from v2g.editor import run_assemble
        state = run_assemble(cfg, video_id)

    # 完成
    click.echo("\n" + "=" * 50)
    click.echo("🎉 流水线完成!")
    click.echo("=" * 50)
    click.echo(f"   最终视频: output/{video_id}/final.mp4")

    if state.final_video:
        from pathlib import Path
        final = Path(state.final_video)
        if final.exists():
            size_mb = final.stat().st_size / (1024 * 1024)
            click.echo(f"   文件大小: {size_mb:.1f}MB")
