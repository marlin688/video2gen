"""全流程编排：串联所有阶段 + 人工审核暂停。"""

import click

from v2g.config import Config
from v2g.checkpoint import PipelineState
from v2g.preparer import _extract_video_id


def _run_quality_gate(cfg: Config, video_id: str, model: str,
                      max_retries: int = 2, threshold: float = 85,
                      regen_fn=None):
    """脚本质量门控：评估 script.json，低于阈值自动重新生成。

    Args:
        regen_fn: 可选的重新生成回调 fn(cfg, video_id, model) -> state。
                  默认使用 scriptwriter.run_script (单源流程)。
                  多源流程传入 run_multi_script，agent 流程不重试。
    """
    import json
    from v2g.eval import eval_script, eval_score_pct, print_eval_report

    script_path = cfg.output_dir / video_id / "script.json"
    if not script_path.exists():
        return

    script = json.loads(script_path.read_text(encoding="utf-8"))
    report = eval_script(script, video_id)
    pct = eval_score_pct(report)

    click.echo(f"\n📋 质量门控: {pct:.0f}% (阈值: {threshold:.0f}%)")
    if pct >= threshold:
        click.echo(f"   ✅ 通过")
        return

    # 低于阈值，打印失败项
    print_eval_report(report)

    if regen_fn is None and max_retries > 0:
        from v2g.scriptwriter import run_script
        regen_fn = lambda c, v, m: run_script(c, v, m)

    if regen_fn is None:
        click.echo(f"⚠️ 质量未达标 ({pct:.0f}%)，无重试函数，继续使用当前脚本")
        return

    failed = [c["name"] for c in report["checks"] if not c["passed"]]

    for attempt in range(1, max_retries + 1):
        click.echo(f"\n🔄 质量不达标，重试 {attempt}/{max_retries}...")
        click.echo(f"   失败项: {', '.join(failed)}")

        # 清除 scripted 状态并重新生成
        state = PipelineState.load(cfg.output_dir, video_id)
        state.scripted = False
        state.save(cfg.output_dir)

        state = regen_fn(cfg, video_id, model)

        script = json.loads(script_path.read_text(encoding="utf-8"))
        report = eval_script(script, video_id)
        pct = eval_score_pct(report)

        click.echo(f"   📋 重试结果: {pct:.0f}%")
        if pct >= threshold:
            click.echo(f"   ✅ 通过")
            return

        failed = [c["name"] for c in report["checks"] if not c["passed"]]

    # 所有重试用完，打印报告但继续流程（不阻断）
    click.echo(f"\n⚠️ {max_retries} 次重试后仍未达标 ({pct:.0f}%)，继续使用当前脚本")
    print_eval_report(report)


def run_pipeline(cfg: Config, video_id_or_url: str, model: str,
                 whisper_model: str = "medium", auto: bool = False):
    """执行完整流水线，在人工审核点暂停（auto=True 时跳过审核）。"""
    video_id = _extract_video_id(video_id_or_url)
    state = PipelineState.load(cfg.output_dir, video_id)

    click.echo(f"🚀 video2gen 流水线: {video_id}" + (" [自动模式]" if auto else ""))
    click.echo(f"   当前阶段: {state.current_stage}\n")

    # Stage 2: 下载 + 字幕翻译
    if not state.subtitled or not state.downloaded:
        click.echo("=" * 50)
        click.echo("📥 Stage 2: 下载 + 字幕翻译")
        click.echo("=" * 50)
        from v2g.preparer import run_prepare
        state = run_prepare(cfg, video_id_or_url, model, whisper_model)

    # Stage 3: AI 脚本 (含质量门控)
    if not state.scripted:
        click.echo("\n" + "=" * 50)
        click.echo("🤖 Stage 3: AI 解说脚本")
        click.echo("=" * 50)
        from v2g.scriptwriter import run_script
        state = run_script(cfg, video_id, model)

    # Stage 3.5: 质量门控 — eval 评分，低于阈值自动重试
    _run_quality_gate(cfg, video_id, model, max_retries=2, threshold=85)

    # 人工审核点 1: 脚本审核
    if not state.script_reviewed:
        if auto:
            click.echo("\n" + "=" * 50)
            click.echo("⚡ 自动模式: 跳过脚本审核")
            click.echo("=" * 50)
            click.echo("   B 类素材将使用终端动画自动生成")
            state.script_reviewed = True
            state.save(cfg.output_dir)
        else:
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
    click.echo(f"   最终视频: output/{video_id}/final/video.mp4")

    if state.final_video:
        from pathlib import Path
        final = Path(state.final_video)
        if final.exists():
            size_mb = final.stat().st_size / (1024 * 1024)
            click.echo(f"   文件大小: {size_mb:.1f}MB")
