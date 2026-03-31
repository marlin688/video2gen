"""Click CLI 入口。"""

import click

from v2g.config import Config
from v2g.checkpoint import PipelineState


pass_config = click.make_pass_decorator(Config, ensure=True)


@click.group()
@click.option("--env", default=None, help=".env 文件路径")
@click.pass_context
def main(ctx, env):
    """video2gen - YouTube 二创视频流水线"""
    ctx.ensure_object(dict)
    ctx.obj = Config.load(env)


@main.command()
@click.option("--csv", "csv_path", default=None, help="trending CSV 文件路径")
@click.option("--category", default=None, help="按分类筛选")
@click.option("--min-views", default=0, type=int, help="最低播放量")
@click.option("--limit", default=20, type=int, help="展示数量上限")
@click.pass_obj
def select(cfg: Config, csv_path, category, min_views, limit):
    """Stage 1: 从 trending 数据中选片"""
    from v2g.selector import interactive_select
    csv_file = csv_path or str(cfg.trending_csv)
    video = interactive_select(csv_file, category=category, min_views=min_views, limit=limit)
    if video:
        click.echo(f"\n✅ 已选择: {video['title']}")
        click.echo(f"   URL: https://www.youtube.com/watch?v={video['video_id']}")
        click.echo(f"   下一步: v2g prepare {video['video_id']}")


@main.command()
@click.argument("video_id_or_url")
@click.option("--model", default=None, help="翻译模型")
@click.option("--whisper-model", default="medium", help="Whisper 模型大小")
@click.option("--no-whisper", is_flag=True, help="使用 YouTube 字幕替代 Whisper")
@click.pass_obj
def prepare(cfg: Config, video_id_or_url, model, whisper_model, no_whisper):
    """Stage 2: 下载视频 + 生成字幕翻译 → sources/{video_id}/"""
    from v2g.preparer import run_prepare
    model = model or cfg.script_model
    state = run_prepare(cfg, video_id_or_url, model, whisper_model, not no_whisper)
    click.echo(f"\n✅ 准备完成: {state.video_id}")
    click.echo(f"   素材目录: sources/{state.video_id}/")
    click.echo(f"   下一步: v2g script {state.video_id}")


@main.command()
@click.argument("video_id")
@click.option("--model", default=None, help="脚本生成模型")
@click.pass_obj
def script(cfg: Config, video_id, model):
    """Stage 3: AI 生成二创解说脚本"""
    from v2g.scriptwriter import run_script
    model = model or cfg.script_model
    state = run_script(cfg, video_id, model)
    click.echo(f"\n✅ 脚本已生成:")
    click.echo(f"   脚本: output/{video_id}/script.md")
    click.echo(f"   录屏指南: output/{video_id}/recording_guide.md")
    click.echo(f"   录屏放入: output/{video_id}/recordings/")
    click.echo(f"   完成后运行: v2g review {video_id}")


@main.command()
@click.argument("video_id")
@click.pass_obj
def review(cfg: Config, video_id):
    """标记脚本审核通过 (确认录屏素材已就绪)"""
    state = PipelineState.load(cfg.output_dir, video_id)
    if not state.scripted:
        raise click.ClickException("脚本尚未生成，请先运行 v2g script")

    # 检查录屏素材状态
    from v2g.editor import check_recordings
    recordings_dir = cfg.output_dir / video_id / "recordings"
    missing = check_recordings(cfg.output_dir / video_id / "script.json", recordings_dir)
    if missing:
        click.echo(f"⚠️  以下录屏素材缺失 (合成时将使用占位卡片):")
        for seg_id, instruction in missing:
            click.echo(f"   Segment {seg_id}: {instruction}")
        if not click.confirm("是否继续标记审核通过？"):
            return

    state.script_reviewed = True
    state.last_error = ""
    state.save(cfg.output_dir)
    click.echo(f"✅ 脚本审核通过: {video_id}")
    click.echo(f"   下一步: v2g tts {video_id}")


@main.command()
@click.argument("video_id")
@click.option("--voice", default=None, help="TTS 声音 (默认: zh-CN-YunxiNeural)")
@click.option("--rate", default=None, help="语速 (默认: +5%)")
@click.pass_obj
def tts(cfg: Config, video_id, voice, rate):
    """Stage 4: TTS 配音 → output/{video_id}/voiceover/"""
    from v2g.tts import run_tts
    voice = voice or cfg.tts_voice
    rate = rate or cfg.tts_rate
    state = run_tts(cfg, video_id, voice, rate)
    click.echo(f"\n✅ TTS 配音完成: output/{video_id}/voiceover/full.mp3")
    click.echo(f"   下一步: v2g slides {video_id}")


@main.command()
@click.argument("video_id")
@click.option("--model", default=None, help="图片生成模型")
@click.pass_obj
def slides(cfg: Config, video_id, model):
    """Stage 5a: 生成 PPT 图文卡片"""
    from v2g.slides import run_slides
    model = model or cfg.script_model
    state = run_slides(cfg, video_id, model)
    click.echo(f"\n✅ 图文卡片生成完成: output/{video_id}/slides/")
    click.echo(f"   下一步: v2g assemble {video_id}")


@main.command()
@click.argument("video_id")
@click.pass_obj
def record(cfg: Config, video_id):
    """将截图序列合成为素材 B 录屏视频

    将操作截图放入 output/{video_id}/screenshots/seg_{id}/ 目录，
    按文件名排序即为步骤顺序。此命令将截图合成为录屏视频。
    """
    from v2g.recorder import run_auto_record
    run_auto_record(cfg, video_id)


@main.command()
@click.argument("video_id")
@click.pass_obj
def assemble(cfg: Config, video_id):
    """Stage 5b: 三素材合成最终视频 → output/{video_id}/final/"""
    from v2g.editor import run_assemble
    state = run_assemble(cfg, video_id)
    click.echo(f"\n✅ 视频合成完成: output/{video_id}/final/video.mp4")


@main.command()
@click.argument("urls", type=str)
@click.option("--topic", required=True, help="主题名称 (如 'Claude Code技巧')")
@click.option("--project-id", default=None, help="项目 ID (默认自动生成)")
@click.option("--model", default=None, help="LLM 模型")
@click.option("--whisper-model", default="medium", help="Whisper 模型大小")
@click.pass_obj
def multi(cfg: Config, urls, topic, project_id, model, whisper_model):
    """多源综合剪辑: 输入多个视频 URL (分号分隔)，AI 跨视频提炼生成一个综合视频

    示例: v2g multi "url1;url2;url3" --topic "Claude Code技巧"
    """
    import re
    model = model or cfg.script_model
    url_list = [u.strip() for u in urls.split(";") if u.strip()]
    if len(url_list) < 2:
        raise click.ClickException("至少需要 2 个视频 URL (分号分隔)")

    # 生成 project_id
    if not project_id:
        slug = re.sub(r"[^\w\u4e00-\u9fff]+", "_", topic)[:20].strip("_")
        project_id = f"multi_{slug}"

    click.echo(f"🚀 多源综合剪辑")
    click.echo(f"   主题: {topic}")
    click.echo(f"   项目 ID: {project_id}")
    click.echo(f"   源视频: {len(url_list)} 个\n")

    # Stage 1: 批量准备
    from v2g.preparer import run_multi_prepare
    state = run_multi_prepare(cfg, url_list, project_id, topic, model, whisper_model)

    if not state.subtitled:
        click.echo("\n⚠️ 部分视频准备失败，请修复后重新运行")
        return

    # Stage 2: 多源脚本
    if not state.scripted:
        click.echo("\n" + "=" * 50)
        click.echo("🤖 Stage 2: 多源综合脚本")
        click.echo("=" * 50)
        from v2g.scriptwriter import run_multi_script
        state = run_multi_script(cfg, project_id, model)

    # 人工审核
    if not state.script_reviewed:
        click.echo(f"\n✋ 暂停: 审阅脚本")
        click.echo(f"   脚本: output/{project_id}/script.md")
        click.echo(f"   完成后运行: v2g review {project_id}")
        click.echo(f"   然后继续: v2g multi \"{urls}\" --topic \"{topic}\" --project-id {project_id}")
        return

    # Stage 3: TTS
    if not state.tts_done:
        from v2g.tts import run_tts
        state = run_tts(cfg, project_id, cfg.tts_voice, cfg.tts_rate)

    # Stage 4: Slides
    if not state.slides_done:
        from v2g.slides import run_slides
        state = run_slides(cfg, project_id, model)

    click.echo(f"\n✅ Python 端完成!")
    click.echo(f"   下一步 Remotion 渲染:")
    click.echo(f"   cd remotion-video && node render.mjs {project_id}")


@main.command()
@click.argument("video_id_or_url")
@click.option("--model", default=None, help="LLM 模型")
@click.option("--whisper-model", default="medium", help="Whisper 模型大小")
@click.pass_obj
def run(cfg: Config, video_id_or_url, model, whisper_model):
    """单视频全流程运行 (带人工审核暂停点)"""
    from v2g.pipeline import run_pipeline
    model = model or cfg.script_model
    run_pipeline(cfg, video_id_or_url, model, whisper_model)


@main.command()
@click.argument("video_id")
@click.pass_obj
def status(cfg: Config, video_id):
    """查看流水线进度"""
    state = PipelineState.load(cfg.output_dir, video_id)
    if not state.created_at:
        click.echo(f"❌ 未找到 {video_id} 的流水线记录")
        return

    click.echo(f"📋 流水线状态: {video_id}")
    click.echo(f"   URL: {state.video_url}")
    click.echo(f"   创建时间: {state.created_at}")
    click.echo()

    stages = [
        ("selected", "选片"),
        ("downloaded", "下载视频"),
        ("subtitled", "字幕翻译"),
        ("scripted", "AI 脚本"),
        ("script_reviewed", "脚本审核 ✋"),
        ("tts_done", "TTS 配音"),
        ("slides_done", "PPT 图文"),
        ("assembled", "视频合成"),
        ("final_reviewed", "成片审核 ✋"),
    ]
    for attr, label in stages:
        done = getattr(state, attr)
        icon = "✅" if done else "⬜"
        click.echo(f"   {icon} {label}")

    if state.last_error:
        click.echo(f"\n   ❌ 最近错误: {state.last_error}")

    # 素材就绪状态
    recordings_dir = cfg.output_dir / video_id / "recordings"
    if recordings_dir.exists():
        files = list(recordings_dir.iterdir())
        click.echo(f"\n   📁 录屏素材: {len(files)} 个文件")
    else:
        click.echo(f"\n   📁 录屏素材: 未就绪")

    # 最终输出
    final_dir = cfg.output_dir / video_id / "final"
    if final_dir.exists():
        finals = [f.name for f in final_dir.iterdir() if not f.name.startswith(".")]
        if finals:
            click.echo(f"   📁 最终输出: {', '.join(finals)}")


if __name__ == "__main__":
    main()
