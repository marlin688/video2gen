"""标题生成：Tier 1 稳健 + Tier 2 冒险，附带缩略图文字建议。支持历史标题性能对标。"""

import json
from datetime import date
from pathlib import Path

import click


def generate_titles(topic: str, angle: str, model: str, context: str = "",
                    history: str = "") -> str:
    """LLM 生成分层标题。"""
    from v2g.llm import call_llm
    from v2g.scout import _load_prompt

    system_prompt = _load_prompt("scout_title.md")
    user_message = f"话题: {topic}"
    if angle:
        user_message += f"\n切入角度: {angle}"
    if history:
        user_message += f"\n\n## 历史标题表现\n{history}"
    if context:
        user_message += f"\n\n## 背景参考\n{context}"

    return call_llm(system_prompt, user_message, model, temperature=0.5, max_tokens=2000)


def run_title(cfg, topic: str, angle: str = "",
              history_file: str | None = None) -> Path | None:
    """标题生成主流程。"""
    from v2g.scout import _load_today_context as load_ctx
    from v2g.scout.obsidian import ObsidianWriter

    click.echo("📛 标题生成")

    writer = ObsidianWriter(cfg.obsidian_vault_path)
    today = date.today()

    context = load_ctx(writer.vault, today)

    # 加载历史标题数据
    history = _load_title_history(writer.vault, history_file)
    if history:
        click.echo(f"   📊 已加载历史标题数据")

    click.echo(f"   📌 话题: {topic}")
    click.echo("   🤖 LLM 生成中...")

    result = generate_titles(topic, angle, cfg.scout_model, context, history)
    if not result:
        click.echo("   ⚠️ 生成失败")
        return None

    path = _write_title_report(writer, today, topic, result)
    click.echo(f"   📝 已写入: {path}")
    return path


def _load_title_history(vault_path: Path, history_file: str | None = None) -> str:
    """加载历史标题数据。

    优先级:
    1. 用户指定的 JSON/CSV 文件 (--history)
    2. 自动扫描 vault/scout/scripts/ 下的历史 title 文件
    """
    if history_file:
        return _load_history_from_file(history_file)
    return _scan_vault_titles(vault_path)


def _load_history_from_file(file_path: str) -> str:
    """从 JSON 文件加载历史标题。格式: [{title, views, likes}]"""
    p = Path(file_path)
    if not p.exists():
        click.echo(f"   ⚠️ 历史文件不存在: {file_path}")
        return ""

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return ""
        lines = ["以下是过去视频标题的实际表现数据，请参考这些模式来生成新标题：", ""]
        lines.append("| 标题 | 播放量 | 点赞 |")
        lines.append("|------|--------|------|")
        for item in data[:20]:  # 最多 20 条
            title = item.get("title", "")
            views = item.get("views", "N/A")
            likes = item.get("likes", "N/A")
            lines.append(f"| {title} | {views} | {likes} |")
        return "\n".join(lines)
    except (json.JSONDecodeError, KeyError) as e:
        click.echo(f"   ⚠️ 历史文件解析失败: {e}")
        return ""


def _scan_vault_titles(vault_path: Path) -> str:
    """扫描 Obsidian vault 中的历史 title 文件，提取已生成的标题作为参考。"""
    scripts_dir = vault_path / "scout" / "scripts"
    if not scripts_dir.exists():
        return ""

    title_files = sorted(scripts_dir.glob("*-title-*.md"), reverse=True)[:10]
    if not title_files:
        return ""

    lines = ["以下是你过去生成的标题，参考其中表现好的模式（如果有反馈标注）：", ""]
    for f in title_files:
        content = f.read_text(encoding="utf-8")
        # 提取 topic 和标题内容（跳过 frontmatter）
        in_frontmatter = False
        topic = ""
        body_lines = []
        for line in content.split("\n"):
            if line.strip() == "---":
                in_frontmatter = not in_frontmatter
                continue
            if in_frontmatter:
                if line.startswith("topic:"):
                    topic = line.split(":", 1)[1].strip()
                continue
            body_lines.append(line)

        # 取正文前 300 字符
        body = "\n".join(body_lines).strip()[:300]
        if body:
            lines.append(f"### {f.stem} (话题: {topic})")
            lines.append(body)
            lines.append("")

    return "\n".join(lines) if len(lines) > 2 else ""


def _write_title_report(writer, today: date, topic: str, content: str) -> Path:
    from v2g.scout.ideation import _topic_slug
    scripts_dir = writer.vault / "scout" / "scripts"
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
