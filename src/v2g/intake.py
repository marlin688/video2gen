"""统一入口路由：A/B/C/D/E 识别并产出 intake.json。"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from v2g.config import Config
from v2g.workflow_contract import sync_workflow_contract

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)
_YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
_SCRIPT_EXT = {".md", ".txt", ".json"}
_SUBTITLE_EXT = {".srt", ".vtt", ".ass"}


def _slug(text: str, max_len: int = 24) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "_", text.strip()).strip("_")
    return (s or "project")[:max_len]


def _detect_entry_type(source: str, keyword: str) -> tuple[str, str]:
    s = source.strip()
    p = Path(s)

    if _URL_RE.match(s):
        if "youtube.com" in s or "youtu.be" in s:
            return "D", "youtube_url"
        return "E", "url"

    if p.exists():
        suffix = p.suffix.lower()
        if suffix in _VIDEO_EXT:
            return "D", "local_video"
        if suffix in _SUBTITLE_EXT:
            return "D", "subtitle_file"
        if suffix in _SCRIPT_EXT:
            return ("C", "script_file+keyword") if keyword else ("B", "script_file")

    if _YT_ID_RE.match(s):
        return "D", "youtube_video_id"

    if keyword:
        return "C", "text+keyword"

    if len(s) > 80 or any(c in s for c in ("\n", "。", "！", "?", "？")):
        return "B", "long_text"

    return "A", "keyword"


def _materialize_inline_source(project_dir: Path, source: str, *, keyword: str, topic: str) -> str:
    """将 inline 文本落盘，避免后续链路依赖命令行长字符串。"""
    input_dir = project_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    path = input_dir / "source_text.md"
    payload = "\n".join(
        [
            "# Intake Source Text",
            "",
            f"- created_at: {datetime.now(timezone.utc).isoformat()}",
            f"- keyword: {keyword}",
            f"- topic: {topic}",
            "",
            "## Content",
            source.strip(),
            "",
        ]
    )
    path.write_text(payload, encoding="utf-8")
    return str(path.resolve())


def _normalize_source(
    source: str,
    *,
    entry_type: str,
    detected_by: str,
    project_dir: Path,
    keyword: str,
    topic: str,
) -> tuple[str, str]:
    """标准化 source，返回 (normalized_source, normalized_kind)。"""
    s = source.strip()
    p = Path(s)

    if p.exists():
        return str(p.resolve()), "file"

    if _YT_ID_RE.match(s):
        return f"https://www.youtube.com/watch?v={s}", "youtube_video_id"

    if _URL_RE.match(s):
        return s, "url"

    if entry_type in {"B", "C", "D"} and detected_by in {
        "long_text", "text+keyword", "subtitle_file", "local_video",
    }:
        return _materialize_inline_source(project_dir, s, keyword=keyword, topic=topic), "inline_text_file"

    if entry_type in {"B", "C"} and not s:
        return _materialize_inline_source(project_dir, "", keyword=keyword, topic=topic), "inline_text_file"

    return s, "keyword"


def _cmd_str(argv: list[str]) -> str:
    return "v2g " + " ".join(shlex.quote(a) for a in argv)


def _build_route(
    entry_type: str,
    *,
    source: str,
    normalized_source: str,
    detected_by: str,
    project_id: str,
    topic: str,
) -> dict:
    topic_text = topic.strip() or _slug(source, 18)

    if entry_type == "A":
        run_argv = ["scout", "script", source.strip()]
        return {
            "workflow": "content_pipeline",
            "target_stage": "scout_script",
            "run_argv": run_argv,
            "suggested_command": _cmd_str(run_argv),
        }

    if entry_type in {"B", "C"}:
        run_argv = ["agent", project_id, "-s", normalized_source, "-t", topic_text]
        return {
            "workflow": "video",
            "target_stage": "agent_script",
            "run_argv": run_argv,
            "suggested_command": _cmd_str(run_argv),
        }

    if entry_type == "D":
        if detected_by in {"youtube_url", "youtube_video_id"}:
            run_argv = ["run", normalized_source]
            return {
                "workflow": "video",
                "target_stage": "run_pipeline",
                "run_argv": run_argv,
                "suggested_command": _cmd_str(run_argv),
            }

        run_argv = ["agent", project_id, "-s", normalized_source, "-t", topic_text]
        return {
            "workflow": "video",
            "target_stage": "agent_script",
            "run_argv": run_argv,
            "suggested_command": _cmd_str(run_argv),
        }

    run_argv = ["scout", "waterfall", topic_text, "--url", normalized_source]
    return {
        "workflow": "optimize",
        "target_stage": "waterfall",
        "run_argv": run_argv,
        "suggested_command": _cmd_str(run_argv),
    }


def create_intake_contract(
    cfg: Config,
    source: str,
    keyword: str = "",
    topic: str = "",
    project_id: str | None = None,
) -> tuple[Path, dict]:
    """识别入口并写入 output/{project}/intake.json。"""
    entry_type, reason = _detect_entry_type(source, keyword)
    pid = project_id or f"intake_{_slug(topic or source)}-{datetime.now().strftime('%Y-%m-%d')}"

    project_dir = cfg.output_dir / pid
    project_dir.mkdir(parents=True, exist_ok=True)

    normalized_source, normalized_kind = _normalize_source(
        source,
        entry_type=entry_type,
        detected_by=reason,
        project_dir=project_dir,
        keyword=keyword,
        topic=topic,
    )
    route = _build_route(
        entry_type,
        source=source,
        normalized_source=normalized_source,
        detected_by=reason,
        project_id=pid,
        topic=topic,
    )

    payload = {
        "version": "v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_id": pid,
        "entry_type": entry_type,
        "detected_by": reason,
        "source": source,
        "normalized_source": normalized_source,
        "normalized_source_kind": normalized_kind,
        "keyword": keyword,
        "topic": topic,
        "route": route,
        "dispatchable": bool(route.get("run_argv")),
    }

    path = project_dir / "intake.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    sync_workflow_contract(
        project_dir=project_dir,
        project_id=pid,
        stage="intake",
        status="ok",
        message=f"入口识别: {entry_type}",
        extra={
            "detected_by": reason,
            "source": source,
            "normalized_source": normalized_source,
            "target_stage": route.get("target_stage", ""),
        },
    )
    return path, payload


def load_intake_contract(cfg: Config, project_id: str) -> tuple[Path, dict]:
    """读取既有 intake.json。"""
    path = cfg.output_dir / project_id / "intake.json"
    if not path.exists():
        raise FileNotFoundError(f"intake.json 不存在: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"intake.json 非法: {path}")
    return path, payload


def execute_intake_route(cfg: Config, payload: dict, *, dry_run: bool = False) -> int:
    """执行 intake 路由。返回进程退出码。"""
    route = payload.get("route") if isinstance(payload, dict) else {}
    route = route if isinstance(route, dict) else {}
    run_argv = route.get("run_argv")
    if not isinstance(run_argv, list) or not run_argv:
        raise ValueError("intake route 缺少 run_argv，无法执行")

    project_id = str(payload.get("project_id") or "")
    if not project_id:
        raise ValueError("intake payload 缺少 project_id")

    project_dir = cfg.output_dir / project_id
    cmd = [sys.executable, "-m", "v2g.cli", *[str(x) for x in run_argv]]

    sync_workflow_contract(
        project_dir=project_dir,
        project_id=project_id,
        stage="intake_dispatch",
        status="start",
        message="开始执行 intake 路由",
        extra={"run_argv": run_argv, "dry_run": dry_run},
    )

    if dry_run:
        sync_workflow_contract(
            project_dir=project_dir,
            project_id=project_id,
            stage="intake_dispatch",
            status="dry_run",
            message="dry-run：未实际执行",
            extra={"run_argv": run_argv},
        )
        return 0

    proc = subprocess.run(cmd)
    status = "ok" if proc.returncode == 0 else "error"
    sync_workflow_contract(
        project_dir=project_dir,
        project_id=project_id,
        stage="intake_dispatch",
        status=status,
        message="intake 路由执行完成" if status == "ok" else "intake 路由执行失败",
        extra={"run_argv": run_argv, "returncode": proc.returncode},
    )
    return int(proc.returncode)
