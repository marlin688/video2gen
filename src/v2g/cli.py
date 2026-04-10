"""Click CLI 入口。"""

import os
from pathlib import Path

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
@click.option("--profile", default="default", help="质量档位 (default / tutorial_general / anthropic_brand)")
@click.pass_obj
def script(cfg: Config, video_id, model, profile):
    """Stage 3: AI 生成二创解说脚本"""
    from v2g.scriptwriter import run_script
    model = model or cfg.script_model
    state = run_script(cfg, video_id, model, quality_profile=profile)
    click.echo(f"\n✅ 脚本已生成:")
    click.echo(f"   脚本: output/{video_id}/script.json (可读版: script.md)")
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

    # 检测 script.md 是否被编辑过但 script.json 未同步
    script_json = cfg.output_dir / video_id / "script.json"
    script_md = cfg.output_dir / video_id / "script.md"
    if script_md.exists() and script_json.exists():
        if script_md.stat().st_mtime > script_json.stat().st_mtime:
            click.echo("⚠️  检测到 script.md 修改时间晚于 script.json")
            click.echo("   script.json 是 TTS/渲染的数据源 (source of truth)")
            click.echo("   如已修改 script.md 中的旁白，请同步修改到 script.json 的 narration_zh 字段")
            if not click.confirm("确认 script.json 已是最终版本？"):
                return

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
@click.option("--model", "whisper_model", default="base",
              type=click.Choice(["tiny", "base", "small", "medium", "large"]),
              help="mlx-whisper 模型 (默认 base；small 对中文更准)")
@click.option("--force", is_flag=True,
              help="即使 word_timing.json 已存在也重新生成")
@click.pass_obj
def align(cfg: Config, video_id, whisper_model, force):
    """对已有 voiceover 运行词级对齐 (生成 voiceover/word_timing.json)。

    用于为旧项目补齐对齐文件，或用更大的 whisper 模型重跑以提升精度。
    需要已安装 mlx-whisper: pip install -e ".[subtitle]"
    """
    from v2g.subtitle import align_voiceover
    voiceover_dir = cfg.output_dir / video_id / "voiceover"
    if not voiceover_dir.exists():
        raise click.ClickException(f"voiceover 目录不存在: {voiceover_dir}")

    existing = voiceover_dir / "word_timing.json"
    if existing.exists() and not force:
        click.echo(f"⏭️  word_timing.json 已存在，使用 --force 强制重跑")
        return

    if existing.exists() and force:
        existing.unlink()
        click.echo("   🗑️  已删除旧 word_timing.json")

    result = align_voiceover(voiceover_dir, model_name=whisper_model)
    if result:
        click.echo(f"\n✅ 词级对齐完成: {result}")
    else:
        raise click.ClickException("词级对齐失败（详见上方日志）")


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
@click.option("--profile", default="default", help="质量档位 (default / tutorial_general / anthropic_brand)")
@click.option("--whisper-model", default="medium", help="Whisper 模型大小")
@click.pass_obj
def multi(cfg: Config, urls, topic, project_id, model, profile, whisper_model):
    """多源综合剪辑: 输入多个视频 URL (分号分隔)，AI 跨视频提炼生成一个综合视频

    示例: v2g multi "url1;url2;url3" --topic "Claude Code技巧"
    """
    import re
    model = model or cfg.script_model
    url_list = [u.strip() for u in urls.split(";") if u.strip()]
    if len(url_list) < 2:
        raise click.ClickException("至少需要 2 个视频 URL (分号分隔)")

    # 预检
    from v2g.pipeline import preflight_check, _print_preflight
    status, warnings = preflight_check("multi", model)
    _print_preflight(status, warnings)

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
        state = run_multi_script(cfg, project_id, model, quality_profile=profile)

    # 质量门控 (多源脚本用 run_multi_script 重试)
    from v2g.pipeline import _run_quality_gate
    from v2g.scriptwriter import run_multi_script as _regen_multi
    _run_quality_gate(
        cfg,
        project_id,
        model,
        max_retries=2,
        threshold=85,
        regen_fn=lambda c, v, m: _regen_multi(c, v, m, quality_profile=profile),
        quality_profile=profile,
    )

    # 人工审核
    if not state.script_reviewed:
        click.echo(f"\n✋ 暂停: 审阅脚本")
        click.echo(f"   脚本: output/{project_id}/script.json (可读版: script.md)")
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
@click.option("--profile", default="default", help="质量档位 (default / tutorial_general / anthropic_brand)")
@click.pass_obj
def agent_cmd(cfg: Config, project_id, sources, topic, model, duration, profile):
    """AI Agent 智能编排视频脚本 (支持 markdown/文章URL/字幕等多源输入)

    示例: v2g agent my-video -s article.md -s "https://mp.weixin.qq.com/s/xxx" -t "AI工具横评"
    """
    # 预检
    from v2g.pipeline import preflight_check, _print_preflight
    status, warnings = preflight_check("agent", model or cfg.script_model)
    _print_preflight(status, warnings)

    from v2g.agent import run_agent
    run_agent(cfg, project_id, sources, topic, model, duration, quality_profile=profile)


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
def scout(cfg: Config, quiet):
    """知识源监控 (GitHub / Twitter / 文章)"""
    pass


@scout.command("github")
@click.option("--since", default=7, type=int, help="查看最近 N 天 (默认 7)")
@click.option("--min-stars", default=50, type=int, help="最低星标数 (默认 50)")
@click.pass_obj
def scout_github(cfg: Config, since, min_stars):
    """GitHub AI 趋势监控"""
    from v2g.scout.github_trending import run_github_trending
    run_github_trending(cfg, since_days=since, min_stars=min_stars)


@scout.command("hn")
@click.option("--hours", default=24, type=int, help="搜索最近 N 小时 (默认 24)")
@click.option("--min-points", default=20, type=int, help="最低 points (默认 20)")
@click.pass_obj
def scout_hn(cfg: Config, hours, min_points):
    """Hacker News AI 热帖监控"""
    from v2g.scout.hn_monitor import run_hn_monitor
    run_hn_monitor(cfg, hours=hours, min_points=min_points)


@scout.command("twitter")
@click.option("--temperature", default=0.5, type=float, help="softmax temperature (默认 0.5)")
@click.option("--max-tweets", default=100, type=int, help="最大抓取数 (默认 100)")
@click.pass_obj
def scout_twitter(cfg: Config, temperature, max_tweets):
    """Twitter/X AI 话题监控 (需要 APIFY_TOKEN)"""
    from v2g.scout.twitter_monitor import run_twitter_monitor
    run_twitter_monitor(cfg, temperature=temperature, max_tweets=max_tweets)


@scout.command("article")
@click.option("--urls", default=None, help="文章 URL (分号分隔)")
@click.pass_obj
def scout_article(cfg: Config, urls):
    """文章监控 (RSS / 手动 URL / inbox)"""
    from v2g.scout.article_monitor import run_article_monitor
    url_list = [u.strip() for u in urls.split(";")] if urls else None
    run_article_monitor(cfg, urls=url_list)


@scout.command("ideation")
@click.argument("topic", required=False, default=None)
@click.option("--from-daily", is_flag=True, help="从今日 daily digest 自动提取话题")
@click.pass_obj
def scout_ideation(cfg: Config, topic, from_daily):
    """创意构思 + 竞品分析 (YouTube 竞争格局)"""
    from v2g.scout.ideation import run_ideation
    if not topic and not from_daily:
        raise click.ClickException("请指定话题或使用 --from-daily")
    run_ideation(cfg, topic=topic, from_daily=from_daily)


@scout.command("hook")
@click.argument("topic")
@click.option("--angle", "-a", default="", help="切入角度")
@click.pass_obj
def scout_hook(cfg: Config, topic, angle):
    """生成 5 个开场钩子变体 (前 30 秒)"""
    from v2g.scout.hook import run_hook
    run_hook(cfg, topic, angle)


@scout.command("title")
@click.argument("topic")
@click.option("--angle", "-a", default="", help="切入角度")
@click.option("--history", "-h", default=None, help="历史标题 JSON 文件 [{title, views, likes}]")
@click.pass_obj
def scout_title(cfg: Config, topic, angle, history):
    """生成分层标题 (Tier 1 稳健 / Tier 2 冒险) + 缩略图文字 + 历史对标"""
    from v2g.scout.title import run_title
    run_title(cfg, topic, angle, history_file=history)


@scout.command("outline")
@click.argument("topic")
@click.option("--angle", "-a", default="", help="切入角度")
@click.option("--duration", "-d", default=600, type=int, help="目标时长秒数 (默认 600)")
@click.pass_obj
def scout_outline(cfg: Config, topic, angle, duration):
    """生成视频大纲 (章节 + 视觉建议 + 参考资料)"""
    from v2g.scout.outline import run_outline
    run_outline(cfg, topic, angle, duration)


@scout.command("waterfall")
@click.argument("topic")
@click.option("--video-id", "-v", default=None, help="视频 ID (读取字幕/脚本)")
@click.option("--url", "-u", default=None, help="文章 URL")
@click.option("--file", "-f", "file_path", default=None, help="本地文件路径")
@click.pass_obj
def scout_waterfall(cfg: Config, topic, video_id, url, file_path):
    """内容瀑布: 视频/文章 → 博客 + Twitter 帖串 + LinkedIn 帖子"""
    from v2g.scout.waterfall import run_waterfall
    run_waterfall(cfg, topic, video_id=video_id, url=url, file_path=file_path)


@scout.command("shorts")
@click.argument("topic")
@click.option("--video-id", "-v", default=None, help="视频 ID (读取字幕/脚本)")
@click.option("--url", "-u", default=None, help="文章 URL")
@click.option("--file", "-f", "file_path", default=None, help="本地文件路径")
@click.pass_obj
def scout_shorts(cfg: Config, topic, video_id, url, file_path):
    """短视频再利用: 长内容 → 30/60/90 秒短视频脚本"""
    from v2g.scout.shorts import run_shorts
    run_shorts(cfg, topic, video_id=video_id, url=url, file_path=file_path)


@scout.command("notebooklm")
@click.argument("topic", required=False, default=None)
@click.option("--source", "-s", "sources", multiple=True,
              help="YouTube URL / 文章 URL / PDF 路径 (可多次指定)")
@click.option("--from-ideation", is_flag=True, help="从今日 ideation 自动选话题 + 提取 URL")
@click.pass_obj
def scout_notebooklm(cfg: Config, topic, sources, from_ideation):
    """NotebookLM 深度分析 (Google 服务器处理，不消耗本地 token)

    示例: v2g scout notebooklm "Claude Code" -s "https://youtube.com/watch?v=xxx" -s paper.pdf
    \b
    或从 ideation 自动读取:
    v2g scout notebooklm --from-ideation
    """
    from datetime import date
    from v2g.scout.notebooklm import run_notebooklm

    if from_ideation:
        from v2g.scout.url_extractor import (
            list_ideation_topics, select_topic_interactive,
            extract_urls_from_vault, match_urls_to_topic,
        )
        vault = Path(cfg.obsidian_vault_path) if cfg.obsidian_vault_path and str(cfg.obsidian_vault_path) != "." else Path("output")
        today = date.today()
        topics = list_ideation_topics(vault, today)
        selected = select_topic_interactive(topics)
        if not selected:
            return
        topic = selected["title"]
        # 自动提取匹配的 URL
        all_urls = extract_urls_from_vault(vault, today)
        matched = match_urls_to_topic(all_urls, selected)
        if matched:
            click.echo(f"   🔗 匹配到 {len(matched)} 个相关 URL:")
            for u in matched:
                click.echo(f"      [{u['source_type']}] {u['title'][:50] or u['url'][:50]}")
            sources = [u["url"] for u in matched]
        else:
            click.echo("   ⚠️ 未匹配到相关 URL，请手动指定 -s")
            return

    if not topic:
        raise click.ClickException("请指定话题或使用 --from-ideation")
    if not sources:
        raise click.ClickException("请指定 -s URL 或使用 --from-ideation")

    run_notebooklm(cfg, list(sources), topic)


@scout.command("script")
@click.argument("topic", required=False, default=None)
@click.option("--angle", "-a", default="", help="切入角度")
@click.option("--duration", "-d", default=600, type=int, help="目标时长秒数 (默认 600)")
@click.option("--from-ideation", is_flag=True, help="从今日 ideation 自动选话题和角度")
@click.pass_obj
def scout_script(cfg: Config, topic, angle, duration, from_ideation):
    """一键运行: 钩子 + 标题 + 大纲"""
    from v2g.scout.hook import run_hook
    from v2g.scout.title import run_title
    from v2g.scout.outline import run_outline

    if from_ideation:
        from datetime import date
        from v2g.scout.url_extractor import list_ideation_topics, select_topic_interactive
        vault = Path(cfg.obsidian_vault_path) if cfg.obsidian_vault_path and str(cfg.obsidian_vault_path) != "." else Path("output")
        topics = list_ideation_topics(vault, date.today())
        selected = select_topic_interactive(topics)
        if not selected:
            return
        topic = selected["title"]
        angle = angle or selected.get("angle_context", "")

    if not topic:
        raise click.ClickException("请指定话题或使用 --from-ideation")

    run_hook(cfg, topic, angle)
    click.echo()
    run_title(cfg, topic, angle)
    click.echo()
    run_outline(cfg, topic, angle, duration)
    click.echo("\n✅ 脚本三件套生成完成")


@scout.command("plan")
@click.option("--skip-notebooklm", is_flag=True, help="跳过 NotebookLM 分析")
@click.option("--duration", "-d", default=600, type=int, help="目标时长秒数 (默认 600)")
@click.option("--topic-index", "-i", default=None, type=int, help="直接选择第 N 个话题（非交互模式）")
@click.pass_obj
def scout_plan(cfg: Config, skip_notebooklm, duration, topic_index):
    """一键脚本规划: 选话题 → NotebookLM(可选) → 钩子 + 标题 + 大纲"""
    from datetime import date
    from v2g.scout.url_extractor import (
        list_ideation_topics, select_topic_interactive,
        extract_urls_from_vault, match_urls_to_topic,
    )
    from v2g.scout.hook import run_hook
    from v2g.scout.title import run_title
    from v2g.scout.outline import run_outline

    vault = Path(cfg.obsidian_vault_path) if cfg.obsidian_vault_path and str(cfg.obsidian_vault_path) != "." else Path("output")
    today = date.today()

    # 1. 选话题
    click.echo("📋 选择话题\n")
    topics = list_ideation_topics(vault, today)
    selected = select_topic_interactive(topics, topic_index)
    if not selected:
        return

    topic = selected["title"]
    angle = selected.get("angle_context", "")
    click.echo()

    # 2. NotebookLM 深度分析（可选）
    if not skip_notebooklm:
        try:
            from v2g.scout.notebooklm import run_notebooklm

            all_urls = extract_urls_from_vault(vault, today)
            matched = match_urls_to_topic(all_urls, selected)
            if matched:
                click.echo(f"🔗 匹配到 {len(matched)} 个相关 URL:")
                for u in matched:
                    click.echo(f"   [{u['source_type']}] {u['title'][:50] or u['url'][:50]}")
                click.echo()
                sources = [u["url"] for u in matched]
                run_notebooklm(cfg, sources, topic)
            else:
                click.echo("ℹ️ 未匹配到相关 URL，跳过 NotebookLM\n")
        except ImportError:
            click.echo("ℹ️ notebooklm-py 未安装，跳过 NotebookLM 分析\n")
        except Exception as e:
            click.echo(f"⚠️ NotebookLM 分析失败: {e}\n")
    else:
        click.echo("ℹ️ 跳过 NotebookLM 分析\n")

    # 3. 脚本三件套
    click.echo("📝 生成脚本规划\n")
    run_hook(cfg, topic, angle)
    click.echo()
    run_title(cfg, topic, angle)
    click.echo()
    run_outline(cfg, topic, angle, duration)
    click.echo("\n✅ 脚本规划完成")


@scout.command("produce")
@click.option("--topic-index", "-i", default=None, type=int, help="直接选择第 N 个话题")
@click.option("--duration", "-d", default=240, type=int, help="目标视频时长秒数 (默认 240)")
@click.option("--model", default=None, help="LLM 模型")
@click.option("--profile", default="tutorial_general", help="质量档位 (default / tutorial_general / anthropic_brand)")
@click.option("--skip-download", is_flag=True, help="跳过视频下载（仅用已有 sources/）")
@click.pass_obj
def scout_produce(cfg: Config, topic_index, duration, model, profile, skip_download):
    """一键生产: 选话题 → 选视频下载 → agent 生成 script.json

    从 ideation 竞品视频中选择素材，结合 scout scripts 上下文，
    自动调用 agent 生成可渲染的 script.json。
    """
    from datetime import date
    from v2g.scout.url_extractor import (
        list_ideation_topics, select_topic_interactive,
        extract_youtube_from_ideation, select_videos_auto,
        find_scout_scripts,
    )
    from v2g.scout.ideation import _topic_slug

    vault = Path(cfg.obsidian_vault_path) if cfg.obsidian_vault_path and str(cfg.obsidian_vault_path) != "." else Path("output")
    today = date.today()

    # 1. 选话题
    click.echo("📋 选择话题\n")
    topics = list_ideation_topics(vault, today)
    selected = select_topic_interactive(topics, topic_index)
    if not selected:
        return
    topic = selected["title"]
    slug = _topic_slug(topic)
    click.echo()

    # 2. 选竞品视频下载
    videos_to_download = []
    if not skip_download:
        click.echo("📺 选择竞品视频下载\n")
        all_videos = extract_youtube_from_ideation(selected["source_path"])
        if all_videos:
            videos_to_download = select_videos_auto(all_videos, max_select=2)
        else:
            click.echo("   ℹ️ ideation 中无竞品视频（YOUTUBE_API_KEY 未设置？）")
        click.echo()

    # 3. 下载视频
    downloaded_ids = []
    if videos_to_download:
        from v2g.preparer import _which
        if not _which("yt-dlp"):
            click.echo("⚠️ yt-dlp 未安装，跳过视频下载（pip install yt-dlp）\n")
        else:
            click.echo("📥 下载视频\n")
            for v in videos_to_download:
                vid = v["video_id"]
                click.echo(f"   📥 [{v['channel'][:15]}] {v['title'][:40]}...")
                try:
                    from v2g.preparer import run_prepare
                    run_prepare(cfg, vid)
                    downloaded_ids.append(vid)
                    click.echo(f"   ✅ {vid} 下载完成")
                except Exception as e:
                    click.echo(f"   ⚠️ {vid} 下载失败: {e}")
            click.echo()

    # 4. 组装 agent 素材
    click.echo("🔧 组装素材\n")
    sources = []

    # scout scripts（hook/title/outline）
    scout_files = find_scout_scripts(vault, today, slug)
    for f in scout_files:
        sources.append(str(f))
        click.echo(f"   📎 {f.name}")

    # 下载的视频字幕
    for vid in downloaded_ids:
        srt_candidates = [
            cfg.sources_dir / vid / "subtitle_zh.srt",
            cfg.sources_dir / vid / "subtitle_en.srt",
        ]
        for srt in srt_candidates:
            if srt.exists():
                sources.append(str(srt))
                click.echo(f"   📎 {srt.name} ({vid})")
                break

    # 没有下载视频时提示（scout scripts 仍然可以作为 agent 素材）
    if not downloaded_ids:
        click.echo("   ℹ️ 无视频素材（agent 将仅基于 scout scripts 生成，无 material C 原片）")

    if not sources:
        click.echo("   ⚠️ 无可用素材，请先运行 scout plan 或手动下载视频")
        return

    click.echo(f"\n   共 {len(sources)} 个素材")
    click.echo()

    # 5. 生成 project_id
    project_id = f"{slug[:20]}-{today}".lower().replace(" ", "-")

    # 5.5 推文截图注入
    tw_json = vault / "scout" / "twitter" / f"{today}-curated.json"
    if tw_json.exists():
        import json as _json
        click.echo("🐦 推文截图\n")
        curated_tweets = _json.loads(tw_json.read_text(encoding="utf-8"))
        curated_tweets.sort(key=lambda t: t.get("total_score", 0), reverse=True)

        images_dir = cfg.output_dir / project_id / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        tweet_image_paths: dict = {}
        try:
            from v2g.scout.tweet_screenshot import capture_tweet_screenshots
            tweet_image_paths = capture_tweet_screenshots(
                curated_tweets, images_dir, max_tweets=5,
            )
        except Exception as e:
            click.echo(f"   ⚠️ 推文截图失败: {e}")

        from v2g.scout.tweet_context import generate_tweet_context
        ctx_path = cfg.output_dir / project_id / "tweet_context.md"
        generate_tweet_context(curated_tweets[:5], tweet_image_paths, ctx_path)
        sources.append(str(ctx_path))
        click.echo(f"   📎 tweet_context.md ({len(tweet_image_paths)} 张截图)\n")
    else:
        click.echo("🐦 无今日推文数据，跳过\n")

    click.echo(f"🤖 启动 Agent 脚本生成: {project_id}\n")

    # 6. 调用 agent（自动确认大纲，≥85 分通过）
    from v2g.agent import run_agent
    run_agent(
        cfg=cfg,
        project_id=project_id,
        sources=tuple(sources),
        topic=topic,
        model=model,
        duration=duration,
        auto_confirm=True,
        auto_confirm_threshold=85,
        quality_profile=profile,
    )


@scout.command("all")
@click.pass_obj
def scout_all(cfg: Config):
    """运行全部知识源 + 生成每日汇总"""
    from datetime import date

    results = {}

    # GitHub
    try:
        from v2g.scout.github_trending import run_github_trending
        path = run_github_trending(cfg)
        if path:
            results["github"] = path
    except Exception as e:
        click.echo(f"⚠️ GitHub 监控失败: {e}")

    click.echo()

    # Hacker News
    try:
        from v2g.scout.hn_monitor import run_hn_monitor
        path = run_hn_monitor(cfg)
        if path:
            results["hn"] = path
    except Exception as e:
        click.echo(f"⚠️ Hacker News 监控失败: {e}")

    click.echo()

    # Twitter
    try:
        from v2g.scout.twitter_monitor import run_twitter_monitor
        path = run_twitter_monitor(cfg)
        if path:
            results["twitter"] = path
    except Exception as e:
        click.echo(f"⚠️ Twitter 监控失败: {e}")

    click.echo()

    # Articles
    try:
        from v2g.scout.article_monitor import run_article_monitor
        path = run_article_monitor(cfg)
        if path:
            results["articles"] = path
    except Exception as e:
        click.echo(f"⚠️ 文章监控失败: {e}")

    click.echo()

    # 每日汇总（即使本次无新数据，也读取当天已有报告生成 digest）
    today = date.today()
    click.echo("📋 生成每日汇总...")
    try:
        from v2g.scout.obsidian import ObsidianWriter
        from v2g.llm import call_llm
        from v2g.scout import _load_prompt

        # 优先用本次新产出的路径，否则回退到当天已有的报告文件
        vault = Path(cfg.obsidian_vault_path) if cfg.obsidian_vault_path and str(cfg.obsidian_vault_path) != "." else Path("output")
        fallback_paths = {
            "github": vault / "scout" / "github" / f"{today}-trending.md",
            "hn": vault / "scout" / "hn" / f"{today}-hn.md",
            "twitter": vault / "scout" / "twitter" / f"{today}-curated.md",
            "articles": vault / "scout" / "articles" / f"{today}-articles.md",
        }
        sections_input = {}
        for name in ("github", "hn", "twitter", "articles"):
            src = results.get(name) or fallback_paths[name]
            try:
                if src.exists():
                    content = src.read_text(encoding="utf-8")[:4000]
                    sections_input[name] = content
            except Exception:
                pass

        if sections_input:
            system_prompt = _load_prompt("scout_daily.md")
            user_msg = "\n\n---\n\n".join(
                f"## {name}\n{content}" for name, content in sections_input.items()
            )
            digest = call_llm(system_prompt, user_msg, cfg.scout_model, temperature=0.3, max_tokens=1000)

            # 质量检查：digest 太短或 LLM 明确表示无法生成时跳过写入
            _bad_signals = ("无法生成", "需要完整", "没有可用")
            digest_stripped = digest.strip()
            if len(digest_stripped) < 80:
                click.echo(f"   ⚠️ 汇总内容过短（{len(digest_stripped)}字），跳过写入")
            elif any(s in digest_stripped[:200] for s in _bad_signals):
                click.echo(f"   ⚠️ 汇总质量不佳（LLM 表示数据不足），跳过写入")
            else:
                writer = ObsidianWriter(cfg.obsidian_vault_path)
                digest_path = writer.write_daily_digest(today, {"汇总": digest})
                click.echo(f"   📝 每日汇总: {digest_path}")
        else:
            click.echo("   ℹ️ 无当天报告可汇总")
    except Exception as e:
        click.echo(f"   ⚠️ 汇总生成失败: {e}")

    # 创意构思（从 daily digest 提取话题）
    click.echo()
    try:
        from v2g.scout.ideation import run_ideation
        run_ideation(cfg, from_daily=True)
    except Exception as e:
        click.echo(f"⚠️ 创意构思失败: {e}")

    click.echo("\n✅ 知识源监控完成")


@main.command()
@click.argument("video_id_or_url")
@click.option("--model", default=None, help="LLM 模型")
@click.option("--whisper-model", default="medium", help="Whisper 模型大小")
@click.option("--profile", default="default", help="质量档位 (default / tutorial_general / anthropic_brand)")
@click.option("--auto", is_flag=True, default=False, help="全自动模式: 跳过人工审核，B类素材使用终端动画")
@click.pass_obj
def run(cfg: Config, video_id_or_url, model, whisper_model, profile, auto):
    """单视频全流程运行 (带人工审核暂停点，--auto 跳过审核)"""
    from v2g.pipeline import run_pipeline
    model = model or cfg.script_model
    run_pipeline(cfg, video_id_or_url, model, whisper_model, auto=auto, quality_profile=profile)


@main.command()
@click.argument("video_id")
@click.pass_obj
def preview(cfg: Config, video_id):
    """渲染各段关键帧预览 (比完整渲染快 10x+)"""
    import subprocess
    remotion_dir = Path(__file__).parent.parent.parent / "remotion-video"
    preview_mjs = remotion_dir / "preview.mjs"
    if not preview_mjs.exists():
        raise click.ClickException(f"preview.mjs 不存在: {preview_mjs}")

    click.echo(f"🖼️  渲染静帧预览: {video_id}")
    result = subprocess.run(
        ["node", str(preview_mjs), video_id,
         "--output-dir", str(cfg.output_dir)],
        cwd=str(remotion_dir),
    )
    if result.returncode != 0:
        raise click.ClickException("预览渲染失败")


@main.command("config")
@click.pass_obj
def config_list(cfg: Config):
    """列出所有配置项及当前值（对比 .env.example）"""
    import re
    from pathlib import Path

    env_example = Path(__file__).parent.parent.parent.parent / ".env.example"
    if not env_example.exists():
        raise click.ClickException(f".env.example 不存在: {env_example}")

    # 从 .env.example 解析所有变量名和注释
    lines = env_example.read_text(encoding="utf-8").splitlines()
    current_section = ""
    entries: list[tuple[str, str, str]] = []  # (name, current_value, section)

    for line in lines:
        line = line.strip()
        if line.startswith("# ---") and line.endswith("---"):
            current_section = line.strip("# -").strip()
            continue
        if line.startswith("#") and "=" in line:
            # 被注释掉的变量 (可选配置)
            var_line = line.lstrip("# ")
            name = var_line.split("=")[0].strip()
            if name and name.isupper():
                val = os.environ.get(name, "")
                entries.append((name, val, current_section))
        elif "=" in line and not line.startswith("#"):
            name = line.split("=")[0].strip()
            if name and name.isupper():
                val = os.environ.get(name, "")
                entries.append((name, val, current_section))

    # 输出
    click.echo("📋 v2g 配置一览\n")
    last_section = ""
    set_count = 0
    for name, val, section in entries:
        if section != last_section:
            click.echo(f"\n  [{section}]")
            last_section = section
        if val:
            # 隐藏 API key 中间部分
            display = val
            if "KEY" in name or "TOKEN" in name:
                display = val[:6] + "..." + val[-4:] if len(val) > 12 else "***"
            click.echo(f"    ✅ {name} = {display}")
            set_count += 1
        else:
            click.echo(f"    ⬜ {name}")

    click.echo(f"\n  共 {len(entries)} 项，已设置 {set_count} 项")


@main.command("eval")
@click.argument("video_id")
@click.option("--profile", default="default", help="质量档位 (default / tutorial_general / anthropic_brand)")
@click.pass_obj
def eval_script(cfg: Config, video_id, profile):
    """评估脚本质量（规则化检查，不消耗 LLM 额度）"""
    from v2g.eval import run_eval, print_eval_report
    report = run_eval(cfg, video_id, quality_profile=profile)
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


# ── 素材库管理 ────────────────────────────────────────────


@main.group()
def assets():
    """素材库管理（入库、打标、检索、保鲜）"""


@assets.command("ingest")
@click.argument("project_id")
@click.pass_obj
def assets_ingest(cfg: Config, project_id):
    """自产素材入库：切片 + 自动打标 + 写入 SQLite"""
    from v2g.asset_store import AssetStore
    from v2g.asset_ingest import ingest_from_video

    db_path = cfg.output_dir / "assets.db"
    with AssetStore(db_path) as store:
        count = ingest_from_video(cfg, project_id, store)
        total = store.count()
        click.echo(f"✅ 入库 {count} 个片段，素材库总量: {total}")


@assets.command("refresh")
@click.pass_obj
def assets_refresh(cfg: Config):
    """月度保鲜扫描：标记过期素材"""
    from v2g.asset_store import AssetStore

    db_path = cfg.output_dir / "assets.db"
    with AssetStore(db_path) as store:
        marked = store.mark_stale()
        stale = store.count_stale()
        total = store.count()
        click.echo(f"🔄 本次标记 {marked} 个素材为 possibly_outdated")
        click.echo(f"   素材库: {total} 总量, {stale} 个过期")


@assets.command("stats")
@click.pass_obj
def assets_stats(cfg: Config):
    """查看素材库统计"""
    from v2g.asset_store import AssetStore

    db_path = cfg.output_dir / "assets.db"
    if not db_path.exists():
        click.echo("❌ 素材库不存在，请先运行 v2g assets ingest")
        return

    with AssetStore(db_path) as store:
        total = store.count()
        stale = store.count_stale()
        click.echo(f"📊 素材库统计:")
        click.echo(f"   总量: {total}")
        click.echo(f"   过期: {stale}")

        engagement = store.aggregate_engagement()
        if engagement:
            click.echo(f"\n   📈 留存表现 (样本≥5):")
            for combo, score in engagement.items():
                emoji = "↑" if score > 0 else "↓" if score < 0 else "→"
                click.echo(f"      {emoji} {combo}: {score:+.2f}")


@assets.command("annotate")
@click.argument("project_id")
@click.option("--retention", "retention_csv", required=True, type=click.Path(exists=True),
              help="B 站留存率 CSV 文件路径")
@click.pass_obj
def assets_annotate(cfg: Config, project_id, retention_csv):
    """完播率回标：将留存曲线映射到 segment"""
    from v2g.asset_store import AssetStore
    from v2g.retention import annotate_retention, print_retention_report

    db_path = cfg.output_dir / "assets.db"
    with AssetStore(db_path) as store:
        results = annotate_retention(cfg, project_id, Path(retention_csv), store)
        print_retention_report(results, project_id)


@assets.command("context")
@click.option("--limit", default=30, type=int, help="最大素材数")
@click.pass_obj
def assets_context(cfg: Config, limit):
    """输出 LLM context 格式的素材列表"""
    from v2g.asset_store import AssetStore

    db_path = cfg.output_dir / "assets.db"
    if not db_path.exists():
        click.echo("素材库为空")
        return

    with AssetStore(db_path) as store:
        ctx = store.to_context(limit=limit)
        if ctx:
            click.echo(ctx)
        else:
            click.echo("素材库为空")


@assets.command("prefetch")
@click.option("--twitter", default=None, help="逗号分隔的 Twitter 用户名")
@click.option("--person", default=None, help="逗号分隔的人物名（英文）")
@click.option("--refresh", is_flag=True, help="强制重新下载（忽略缓存）")
@click.pass_obj
def assets_prefetch(cfg: Config, twitter, person, refresh):
    """预取素材：Twitter 头像 / 人物照片 / Meme 模板"""
    from v2g.asset_prefetch import prefetch_all

    out_dir = cfg.output_dir / "prefetch"
    twitter_users = [u.strip() for u in twitter.split(",")] if twitter else None
    persons = [p.strip() for p in person.split(",")] if person else None

    results = prefetch_all(
        out_dir,
        twitter_users=twitter_users,
        persons=persons,
        refresh=refresh,
    )
    click.echo(f"\n📦 素材目录: {out_dir}")
    click.echo(f"   总计: {len(results)} 个文件")


if __name__ == "__main__":
    main()
