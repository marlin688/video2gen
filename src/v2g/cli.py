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


@main.command("agent")
@click.argument("project_id")
@click.option("--source", "-s", "sources", multiple=True, required=True,
              help="素材路径或URL (可多次指定)。支持: .md, .srt, .txt, http(s)://")
@click.option("--topic", "-t", required=True, help="视频主题/标题方向")
@click.option("--model", default=None, help="LLM 模型")
@click.option("--duration", default=240, type=int, help="目标视频时长(秒)")
@click.pass_obj
def agent_cmd(cfg: Config, project_id, sources, topic, model, duration):
    """AI Agent 智能编排视频脚本 (支持 markdown/文章URL/字幕等多源输入)

    示例: v2g agent my-video -s article.md -s "https://mp.weixin.qq.com/s/xxx" -t "AI工具横评"
    """
    from v2g.agent import run_agent
    run_agent(cfg, project_id, sources, topic, model, duration)


@main.command()
@click.argument("project_id")
@click.pass_obj
def capture(cfg: Config, project_id):
    """自动采集 B 类素材: 素材库检索 → Playwright 截图 → 合成视频"""
    from v2g.autocap import run_capture
    run_capture(cfg, project_id)


@main.group()
def material():
    """素材库管理"""
    pass


@material.command("add")
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--keywords", "-k", required=True, help="关键词 (逗号分隔)")
@click.option("--desc", "-d", default="", help="素材描述")
@click.pass_obj
def material_add(cfg, file_path, keywords, desc):
    """向素材库添加素材"""
    from v2g.material_library import MaterialLibrary, MaterialEntry
    from pathlib import Path
    import shutil

    lib = MaterialLibrary()
    src = Path(file_path)
    # 复制到素材库目录
    dest_dir = lib.root / "recordings"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if not dest.exists():
        shutil.copy2(src, dest)

    entry = lib.add(MaterialEntry(
        type="recording",
        path=str(dest),
        keywords=[k.strip() for k in keywords.split(",")],
        description=desc or src.stem,
    ))
    click.echo(f"✅ 已添加: {entry.id} → {dest}")


@material.command("search")
@click.argument("query")
@click.pass_obj
def material_search(cfg, query):
    """搜索素材库"""
    from v2g.material_library import MaterialLibrary
    lib = MaterialLibrary()
    results = lib.search(query, top_k=5)
    if not results:
        click.echo("未找到匹配素材")
        return
    for r in results:
        click.echo(f"  [{r.id}] {r.type} | {r.description[:50]} | {', '.join(r.keywords[:3])}")


@material.command("list")
@click.pass_obj
def material_list(cfg):
    """列出素材库全部素材"""
    from v2g.material_library import MaterialLibrary
    lib = MaterialLibrary()
    entries = lib.list_all()
    if not entries:
        click.echo("素材库为空")
        return
    click.echo(f"📦 素材库: {len(entries)} 条")
    for e in entries:
        click.echo(f"  [{e.id}] {e.type:10s} | {e.description[:40]} | {', '.join(e.keywords[:3])}")


@main.group()
@click.option("--quiet", is_flag=True, help="安静模式 (适合 cron)")
@click.pass_obj
def knowledge(cfg: Config, quiet):
    """知识源监控 (GitHub / Twitter / 文章)"""
    pass


@knowledge.command("github")
@click.option("--since", default=7, type=int, help="查看最近 N 天 (默认 7)")
@click.option("--min-stars", default=50, type=int, help="最低星标数 (默认 50)")
@click.pass_obj
def knowledge_github(cfg: Config, since, min_stars):
    """GitHub AI 趋势监控"""
    from v2g.knowledge.github_trending import run_github_trending
    run_github_trending(cfg)


@knowledge.command("hn")
@click.option("--hours", default=24, type=int, help="搜索最近 N 小时 (默认 24)")
@click.option("--min-points", default=20, type=int, help="最低 points (默认 20)")
@click.pass_obj
def knowledge_hn(cfg: Config, hours, min_points):
    """Hacker News AI 热帖监控"""
    from v2g.knowledge.hn_monitor import run_hn_monitor
    run_hn_monitor(cfg, hours=hours, min_points=min_points)


@knowledge.command("twitter")
@click.option("--temperature", default=0.5, type=float, help="softmax temperature (默认 0.5)")
@click.option("--max-tweets", default=100, type=int, help="最大抓取数 (默认 100)")
@click.pass_obj
def knowledge_twitter(cfg: Config, temperature, max_tweets):
    """Twitter/X AI 话题监控 (需要 APIFY_TOKEN)"""
    from v2g.knowledge.twitter_monitor import run_twitter_monitor
    run_twitter_monitor(cfg, temperature=temperature, max_tweets=max_tweets)


@knowledge.command("article")
@click.option("--urls", default=None, help="文章 URL (分号分隔)")
@click.pass_obj
def knowledge_article(cfg: Config, urls):
    """文章监控 (RSS / 手动 URL / inbox)"""
    from v2g.knowledge.article_monitor import run_article_monitor
    url_list = [u.strip() for u in urls.split(";")] if urls else None
    run_article_monitor(cfg, urls=url_list)


@knowledge.command("ideation")
@click.argument("topic", required=False, default=None)
@click.option("--from-daily", is_flag=True, help="从今日 daily digest 自动提取话题")
@click.pass_obj
def knowledge_ideation(cfg: Config, topic, from_daily):
    """创意构思 + 竞品分析 (YouTube 竞争格局)"""
    from v2g.knowledge.ideation import run_ideation
    if not topic and not from_daily:
        raise click.ClickException("请指定话题或使用 --from-daily")
    run_ideation(cfg, topic=topic, from_daily=from_daily)


@knowledge.command("hook")
@click.argument("topic")
@click.option("--angle", "-a", default="", help="切入角度")
@click.pass_obj
def knowledge_hook(cfg: Config, topic, angle):
    """生成 5 个开场钩子变体 (前 30 秒)"""
    from v2g.knowledge.hook import run_hook
    run_hook(cfg, topic, angle)


@knowledge.command("title")
@click.argument("topic")
@click.option("--angle", "-a", default="", help="切入角度")
@click.option("--history", "-h", default=None, help="历史标题 JSON 文件 [{title, views, likes}]")
@click.pass_obj
def knowledge_title(cfg: Config, topic, angle, history):
    """生成分层标题 (Tier 1 稳健 / Tier 2 冒险) + 缩略图文字 + 历史对标"""
    from v2g.knowledge.title import run_title
    run_title(cfg, topic, angle, history_file=history)


@knowledge.command("outline")
@click.argument("topic")
@click.option("--angle", "-a", default="", help="切入角度")
@click.option("--duration", "-d", default=600, type=int, help="目标时长秒数 (默认 600)")
@click.pass_obj
def knowledge_outline(cfg: Config, topic, angle, duration):
    """生成视频大纲 (章节 + 视觉建议 + 参考资料)"""
    from v2g.knowledge.outline import run_outline
    run_outline(cfg, topic, angle, duration)


@knowledge.command("waterfall")
@click.argument("topic")
@click.option("--video-id", "-v", default=None, help="视频 ID (读取字幕/脚本)")
@click.option("--url", "-u", default=None, help="文章 URL")
@click.option("--file", "-f", "file_path", default=None, help="本地文件路径")
@click.pass_obj
def knowledge_waterfall(cfg: Config, topic, video_id, url, file_path):
    """内容瀑布: 视频/文章 → 博客 + Twitter 帖串 + LinkedIn 帖子"""
    from v2g.knowledge.waterfall import run_waterfall
    run_waterfall(cfg, topic, video_id=video_id, url=url, file_path=file_path)


@knowledge.command("shorts")
@click.argument("topic")
@click.option("--video-id", "-v", default=None, help="视频 ID (读取字幕/脚本)")
@click.option("--url", "-u", default=None, help="文章 URL")
@click.option("--file", "-f", "file_path", default=None, help="本地文件路径")
@click.pass_obj
def knowledge_shorts(cfg: Config, topic, video_id, url, file_path):
    """短视频再利用: 长内容 → 30/60/90 秒短视频脚本"""
    from v2g.knowledge.shorts import run_shorts
    run_shorts(cfg, topic, video_id=video_id, url=url, file_path=file_path)


@knowledge.command("notebooklm")
@click.argument("topic")
@click.option("--source", "-s", "sources", multiple=True, required=True,
              help="YouTube URL / 文章 URL / PDF 路径 (可多次指定)")
@click.pass_obj
def knowledge_notebooklm(cfg: Config, topic, sources):
    """NotebookLM 深度分析 (Google 服务器处理，不消耗本地 token)

    示例: v2g knowledge notebooklm "Claude Code" -s "https://youtube.com/watch?v=xxx" -s paper.pdf
    """
    from v2g.knowledge.notebooklm import run_notebooklm
    run_notebooklm(cfg, list(sources), topic)


@knowledge.command("script")
@click.argument("topic")
@click.option("--angle", "-a", default="", help="切入角度")
@click.option("--duration", "-d", default=600, type=int, help="目标时长秒数 (默认 600)")
@click.pass_obj
def knowledge_script(cfg: Config, topic, angle, duration):
    """一键运行: 钩子 + 标题 + 大纲"""
    from v2g.knowledge.hook import run_hook
    from v2g.knowledge.title import run_title
    from v2g.knowledge.outline import run_outline

    run_hook(cfg, topic, angle)
    click.echo()
    run_title(cfg, topic, angle)
    click.echo()
    run_outline(cfg, topic, angle, duration)
    click.echo("\n✅ 脚本三件套生成完成")


@knowledge.command("all")
@click.pass_obj
def knowledge_all(cfg: Config):
    """运行全部知识源 + 生成每日汇总"""
    from datetime import date

    results = {}

    # GitHub
    try:
        from v2g.knowledge.github_trending import run_github_trending
        path = run_github_trending(cfg)
        if path:
            results["github"] = path
    except Exception as e:
        click.echo(f"⚠️ GitHub 监控失败: {e}")

    click.echo()

    # Hacker News
    try:
        from v2g.knowledge.hn_monitor import run_hn_monitor
        path = run_hn_monitor(cfg)
        if path:
            results["hn"] = path
    except Exception as e:
        click.echo(f"⚠️ Hacker News 监控失败: {e}")

    click.echo()

    # Articles
    try:
        from v2g.knowledge.article_monitor import run_article_monitor
        path = run_article_monitor(cfg)
        if path:
            results["articles"] = path
    except Exception as e:
        click.echo(f"⚠️ 文章监控失败: {e}")

    click.echo()

    # 每日汇总
    if results:
        click.echo("📋 生成每日汇总...")
        try:
            from v2g.knowledge.obsidian import ObsidianWriter
            from v2g.llm import call_llm
            from v2g.knowledge import _load_prompt

            # 读取各源报告内容
            sections_input = {}
            for name, path in results.items():
                try:
                    content = path.read_text(encoding="utf-8")[:2000]
                    sections_input[name] = content
                except Exception:
                    pass

            if sections_input:
                system_prompt = _load_prompt("knowledge_daily.md")
                user_msg = "\n\n---\n\n".join(
                    f"## {name}\n{content}" for name, content in sections_input.items()
                )
                digest = call_llm(system_prompt, user_msg, cfg.knowledge_model, temperature=0.3, max_tokens=1000)

                writer = ObsidianWriter(cfg.obsidian_vault_path)
                digest_path = writer.write_daily_digest(date.today(), {"汇总": digest})
                click.echo(f"   📝 每日汇总: {digest_path}")
        except Exception as e:
            click.echo(f"   ⚠️ 汇总生成失败: {e}")

    # 创意构思（从 daily digest 提取话题）
    if results:
        click.echo()
        try:
            from v2g.knowledge.ideation import run_ideation
            run_ideation(cfg, from_daily=True)
        except Exception as e:
            click.echo(f"⚠️ 创意构思失败: {e}")

    click.echo("\n✅ 知识源监控完成")


@main.command()
@click.argument("video_id_or_url")
@click.option("--model", default=None, help="LLM 模型")
@click.option("--whisper-model", default="medium", help="Whisper 模型大小")
@click.option("--auto", is_flag=True, default=False, help="全自动模式: 跳过人工审核，B类素材使用终端动画")
@click.pass_obj
def run(cfg: Config, video_id_or_url, model, whisper_model, auto):
    """单视频全流程运行 (带人工审核暂停点，--auto 跳过审核)"""
    from v2g.pipeline import run_pipeline
    model = model or cfg.script_model
    run_pipeline(cfg, video_id_or_url, model, whisper_model, auto=auto)


@main.command("eval")
@click.argument("video_id")
@click.pass_obj
def eval_script(cfg: Config, video_id):
    """评估脚本质量（规则化检查，不消耗 LLM 额度）"""
    from v2g.eval import run_eval, print_eval_report
    report = run_eval(cfg, video_id)
    print_eval_report(report)


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
