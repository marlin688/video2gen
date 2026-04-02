"""标题生成：Tier 1 稳健 + Tier 2 冒险，附带缩略图文字建议。"""

from datetime import date
from pathlib import Path

import click


def generate_titles(topic: str, angle: str, model: str, context: str = "") -> str:
    """LLM 生成分层标题。"""
    from v2g.llm import call_llm
    from v2g.knowledge import _load_prompt

    system_prompt = _load_prompt("knowledge_title.md")
    user_message = f"话题: {topic}"
    if angle:
        user_message += f"\n切入角度: {angle}"
    if context:
        user_message += f"\n\n## 背景参考\n{context}"

    return call_llm(system_prompt, user_message, model, temperature=0.5, max_tokens=2000)


def run_title(cfg, topic: str, angle: str = "") -> Path | None:
    """标题生成主流程。"""
    from v2g.knowledge import _load_today_context as load_ctx
    from v2g.knowledge.obsidian import ObsidianWriter

    click.echo("📛 标题生成")

    writer = ObsidianWriter(cfg.obsidian_vault_path)
    today = date.today()

    context = load_ctx(writer.vault, today)

    click.echo(f"   📌 话题: {topic}")
    click.echo("   🤖 LLM 生成中...")

    result = generate_titles(topic, angle, cfg.knowledge_model, context)
    if not result:
        click.echo("   ⚠️ 生成失败")
        return None

    path = _write_title_report(writer, today, topic, result)
    click.echo(f"   📝 已写入: {path}")
    return path


def _write_title_report(writer, today: date, topic: str, content: str) -> Path:
    from v2g.knowledge.ideation import _topic_slug
    scripts_dir = writer.vault / "knowledge" / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    path = scripts_dir / f"{today}-title-{_topic_slug(topic)}.md"

    lines = [
        "---",
        f"date: {today}",
        "type: title",
        f"topic: {topic}",
        "tags: [title, script]",
        "---",
        "",
        f"# 标题: {topic}",
        "",
        content,
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


