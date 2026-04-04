"""钩子生成：为视频前 30 秒生成 5 个开场钩子变体。"""

from datetime import date
from pathlib import Path

import click


def generate_hooks(topic: str, angle: str, model: str, context: str = "") -> str:
    """LLM 生成 5 个钩子变体。"""
    from v2g.llm import call_llm
    from v2g.scout import _load_prompt

    system_prompt = _load_prompt("scout_hook.md")
    user_message = f"话题: {topic}"
    if angle:
        user_message += f"\n切入角度: {angle}"
    if context:
        user_message += f"\n\n## 背景参考\n{context}"

    return call_llm(system_prompt, user_message, model, temperature=0.5, max_tokens=2500)


def run_hook(cfg, topic: str, angle: str = "") -> Path | None:
    """钩子生成主流程。"""
    from v2g.scout import _load_today_context as load_ctx
    from v2g.scout.obsidian import ObsidianWriter

    click.echo("🎣 钩子生成")

    writer = ObsidianWriter(cfg.obsidian_vault_path)
    today = date.today()

    context = load_ctx(writer.vault, today)

    click.echo(f"   📌 话题: {topic}")
    if angle:
        click.echo(f"   🎯 角度: {angle}")
    click.echo("   🤖 LLM 生成中...")

    result = generate_hooks(topic, angle, cfg.scout_model, context)
    if not result:
        click.echo("   ⚠️ 生成失败")
        return None

    path = _write_hook_report(writer, today, topic, result)
    click.echo(f"   📝 已写入: {path}")
    return path


def _write_hook_report(writer, today: date, topic: str, content: str) -> Path:
    from v2g.scout.ideation import _topic_slug
    hook_dir = writer.vault / "scout" / "scripts"
    hook_dir.mkdir(parents=True, exist_ok=True)
    path = hook_dir / f"{today}-hook-{_topic_slug(topic)}.md"

    lines = [
        "---",
        f"date: {today}",
        "type: hook",
        f"topic: {topic}",
        "tags: [hook, script]",
        "---",
        "",
        f"# 钩子: {topic}",
        "",
        content,
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


