"""Notebook LM 集成：将 YouTube 视频/文章/PDF 喂给 Google NotebookLM 深度分析。

使用 notebooklm-py 库（pip install "notebooklm-py[browser]"）。
分析在 Google 服务器上完成，不消耗本地 LLM token。

首次使用需要登录：notebooklm login
"""

import asyncio
from datetime import date
from pathlib import Path

import click


async def _analyze_sources(sources: list[str], topic: str) -> dict:
    """创建 NotebookLM notebook，添加源，执行分析。"""
    try:
        from notebooklm import NotebookLMClient
    except ImportError:
        raise click.ClickException(
            "需要安装 notebooklm-py:\n"
            '  pip install "notebooklm-py[browser]"\n'
            "  playwright install chromium\n"
            "  notebooklm login"
        )

    async with await NotebookLMClient.from_storage() as client:
        # 创建 notebook
        nb_name = f"v2g-{topic[:30]}-{date.today()}"
        click.echo(f"   📓 创建 notebook: {nb_name}")
        nb = await client.notebooks.create(nb_name)

        # 添加源
        for src in sources:
            try:
                if src.startswith("http"):
                    click.echo(f"   📎 添加 URL: {src[:60]}")
                    await client.sources.add_url(nb.id, src)
                elif Path(src).exists():
                    click.echo(f"   📎 添加文件: {Path(src).name}")
                    await client.sources.add_file(nb.id, src)
                else:
                    click.echo(f"   ⚠️ 跳过无效源: {src[:60]}")
            except Exception as e:
                click.echo(f"   ⚠️ 添加源失败: {e}")

        # 分析
        click.echo("   🤖 NotebookLM 分析中（Google 服务器处理）...")
        questions = [
            f"请对这些内容做一个综合分析，主题是「{topic}」。包括：核心观点、关键发现、争议点。",
            f"如果要基于这些内容做一个视频，最佳的切入角度是什么？给出 3 个建议。",
            "这些内容中有哪些独特的见解或数据，是大多数人可能不知道的？",
        ]

        answers = []
        for q in questions:
            try:
                result = await client.chat.ask(nb.id, q)
                answers.append({"question": q, "answer": result.answer})
            except Exception as e:
                click.echo(f"   ⚠️ 问答失败: {e}")
                answers.append({"question": q, "answer": f"分析失败: {e}"})

        return {
            "notebook_id": nb.id,
            "notebook_name": nb_name,
            "sources_count": len(sources),
            "analysis": answers,
        }


def run_notebooklm(cfg, sources: list[str], topic: str) -> Path | None:
    """NotebookLM 分析主流程。"""
    from v2g.knowledge.obsidian import ObsidianWriter

    click.echo("📓 NotebookLM 深度分析")

    if not sources:
        click.echo("   ⚠️ 未提供源（YouTube URL / PDF / 文章 URL）")
        return None

    click.echo(f"   📌 话题: {topic}")
    click.echo(f"   📎 源数量: {len(sources)}")

    # 运行异步分析
    try:
        result = asyncio.run(_analyze_sources(sources, topic))
    except click.ClickException:
        raise
    except Exception as e:
        click.echo(f"   ⚠️ NotebookLM 分析失败: {e}")
        click.echo("   提示: 确保已运行 'notebooklm login' 完成 Google 认证")
        return None

    # 写入 Obsidian
    writer = ObsidianWriter(cfg.obsidian_vault_path)
    today = date.today()
    path = _write_notebooklm_report(writer, today, topic, sources, result)
    click.echo(f"   📝 已写入: {path}")

    return path


def _write_notebooklm_report(
    writer, today: date, topic: str, sources: list[str], result: dict
) -> Path:
    from v2g.knowledge.ideation import _topic_slug

    nlm_dir = writer.vault / "knowledge" / "notebooklm"
    nlm_dir.mkdir(parents=True, exist_ok=True)
    path = nlm_dir / f"{today}-{_topic_slug(topic)}.md"

    lines = [
        "---",
        f"date: {today}",
        "source: notebooklm",
        f"topic: {topic}",
        f"notebook_id: {result.get('notebook_id', '')}",
        "tags: [notebooklm, deep-analysis]",
        "---",
        "",
        f"# NotebookLM 深度分析: {topic}",
        "",
        "## 分析源",
        "",
    ]
    for s in sources:
        lines.append(f"- {s}")
    lines.append("")

    for item in result.get("analysis", []):
        lines.append(f"## {item['question']}")
        lines.append("")
        lines.append(item["answer"])
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path
