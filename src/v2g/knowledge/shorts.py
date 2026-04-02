"""短视频再利用：将长视频内容提炼为 30/60/90 秒短视频脚本。"""

from datetime import date
from pathlib import Path

import click


def generate_shorts(content: str, topic: str, model: str, context: str = "") -> str:
    """LLM 生成三个时长版本的短视频脚本。"""
    from v2g.llm import call_llm
    from v2g.knowledge import _load_prompt

    system_prompt = _load_prompt("knowledge_shorts.md")
    user_message = f"话题: {topic}\n\n## 原始内容\n{content}"
    if context:
        user_message += f"\n\n## 背景参考\n{context}"

    return call_llm(system_prompt, user_message, model, temperature=0.5, max_tokens=3500)


def run_shorts(cfg, topic: str, video_id: str | None = None,
               url: str | None = None, file_path: str | None = None) -> Path | None:
    """短视频再利用主流程。"""
    from v2g.knowledge import _load_today_context as load_ctx, _load_video_content
    from v2g.knowledge.obsidian import ObsidianWriter

    click.echo("🎬 短视频再利用")

    writer = ObsidianWriter(cfg.obsidian_vault_path)
    today = date.today()

    # 加载原始内容
    try:
        content, source_desc = _load_video_content(cfg, video_id, url, file_path)
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"   ⚠️ {e}")
        return None

    context = load_ctx(writer.vault, today)

    click.echo(f"   📌 话题: {topic}")
    click.echo(f"   📄 {source_desc}")
    click.echo("   🤖 LLM 生成中...")

    result = generate_shorts(content, topic, cfg.knowledge_model, context)
    if not result:
        click.echo("   ⚠️ 生成失败")
        return None

    path = _write_shorts_report(writer, today, topic, result, source_desc)
    click.echo(f"   📝 已写入: {path}")
    return path


def _write_shorts_report(writer, today: date, topic: str, content: str,
                         source_desc: str = "") -> Path:
    from v2g.knowledge.ideation import _topic_slug
    dist_dir = writer.vault / "knowledge" / "distribution"
    dist_dir.mkdir(parents=True, exist_ok=True)
    path = dist_dir / f"{today}-shorts-{_topic_slug(topic)}.md"

    lines = [
        "---",
        f"date: {today}",
        "type: shorts",
        f"topic: {topic}",
        f"source: \"{source_desc}\"",
        "tags: [distribution, shorts, tiktok, reels]",
        "---",
        "",
        f"# 短视频脚本: {topic}",
        "",
        content,
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
