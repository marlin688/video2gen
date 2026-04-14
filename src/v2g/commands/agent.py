"""Agent-related CLI commands."""

from __future__ import annotations

import click

from v2g.config import Config


def register_agent_commands(main: click.Group) -> None:
    @main.command("agent")
    @click.argument("project_id")
    @click.option(
        "--source",
        "-s",
        "sources",
        multiple=True,
        required=True,
        help="素材路径或 URL。支持本地 .md/.srt/.txt/.mp4 与 http(s)://",
    )
    @click.option("--topic", "-t", required=True, help="视频主题/标题方向")
    @click.option("--model", default=None, help="LLM 模型")
    @click.option("--duration", default=240, type=int, help="目标视频时长(秒)")
    @click.option(
        "--profile",
        default="default",
        help="质量档位 (default / tutorial_general / anthropic_brand / tech_explainer)",
    )
    @click.pass_obj
    def agent_cmd(cfg: Config, project_id, sources, topic, model, duration, profile):
        """AI Agent 智能编排视频脚本。"""
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
