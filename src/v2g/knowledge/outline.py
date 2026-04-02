"""大纲生成：章节结构 + 视觉建议 + 参考资料。"""

from datetime import date
from pathlib import Path

import click


def generate_outline(
    topic: str, angle: str, model: str, duration: int = 600, context: str = ""
) -> str:
    """LLM 生成视频大纲。"""
    from v2g.llm import call_llm
    from v2g.knowledge import _load_prompt

    system_prompt = _load_prompt("knowledge_outline.md")
    user_message = f"话题: {topic}\n目标时长: {duration // 60} 分钟"
    if angle:
        user_message += f"\n切入角度: {angle}"
    if context:
        user_message += f"\n\n## 背景参考\n{context}"

    return call_llm(system_prompt, user_message, model, temperature=0.4, max_tokens=3000)


def run_outline(cfg, topic: str, angle: str = "", duration: int = 600) -> Path | None:
    """大纲生成主流程。"""
    from v2g.knowledge.obsidian import ObsidianWriter

    click.echo("📋 大纲生成")

    writer = ObsidianWriter(cfg.obsidian_vault_path)
    today = date.today()

    # 加载今日上下文 + ideation 报告（如果有）
    context = _load_context(writer.vault, today, topic)

    click.echo(f"   📌 话题: {topic}")
    click.echo(f"   ⏱️ 目标时长: {duration // 60} 分钟")
    click.echo("   🤖 LLM 生成中...")

    result = generate_outline(topic, angle, cfg.knowledge_model, duration, context)
    if not result:
        click.echo("   ⚠️ 生成失败")
        return None

    path = _write_outline_report(writer, today, topic, result)
    click.echo(f"   📝 已写入: {path}")
    return path


def _write_outline_report(writer, today: date, topic: str, content: str) -> Path:
    from v2g.knowledge.ideation import _topic_slug
    scripts_dir = writer.vault / "knowledge" / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    path = scripts_dir / f"{today}-outline-{_topic_slug(topic)}.md"

    lines = [
        "---",
        f"date: {today}",
        "type: outline",
        f"topic: {topic}",
        "tags: [outline, script]",
        "---",
        "",
        f"# 大纲: {topic}",
        "",
        content,
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _load_context(vault_path: Path, today: date, topic: str) -> str:
    """加载 daily digest + 相关 ideation 报告。"""
    import re
    context = ""

    # daily digest
    daily = vault_path / "daily" / f"{today}.md"
    if daily.exists():
        context += daily.read_text(encoding="utf-8")[:1500]

    # 查找匹配的 ideation 报告
    ideation_dir = vault_path / "knowledge" / "ideation"
    if ideation_dir.exists():
        slug = re.sub(r"[^\w\u4e00-\u9fff]+", "-", topic)[:20].strip("-").lower()
        for f in ideation_dir.glob(f"{today}-*.md"):
            if slug and slug in f.name.lower():
                context += "\n\n---\n" + f.read_text(encoding="utf-8")[:2000]
                break

    return context
