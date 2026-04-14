"""统一入口路由：A/B/C/D/E 识别并产出 intake.json。"""

from __future__ import annotations

import json
import re
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


def _build_route(entry_type: str, source: str, project_id: str, topic: str) -> dict:
    s = source.strip()
    topic_text = topic.strip() or _slug(source, 18)

    if entry_type == "A":
        return {
            "workflow": "content_pipeline",
            "suggested_command": f'v2g scout script "{s}"',
            "target_stage": "scout_script",
        }
    if entry_type == "B":
        return {
            "workflow": "video",
            "suggested_command": f'v2g agent {project_id} -s "{s}" -t "{topic_text}"',
            "target_stage": "agent_script",
        }
    if entry_type == "C":
        return {
            "workflow": "video",
            "suggested_command": f'v2g agent {project_id} -s "{s}" -t "{topic_text}"',
            "target_stage": "agent_script",
        }
    if entry_type == "D":
        if _URL_RE.match(s) or _YT_ID_RE.match(s):
            return {
                "workflow": "video",
                "suggested_command": f"v2g run {s}",
                "target_stage": "run_pipeline",
            }
        return {
            "workflow": "video",
            "suggested_command": f'v2g agent {project_id} -s "{s}" -t "{topic_text}"',
            "target_stage": "agent_script",
        }
    return {
        "workflow": "optimize",
        "suggested_command": f'v2g scout waterfall "{topic_text}" --url "{s}"',
        "target_stage": "waterfall",
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
    route = _build_route(entry_type, source, pid, topic)

    payload = {
        "version": "v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_id": pid,
        "entry_type": entry_type,
        "detected_by": reason,
        "source": source,
        "keyword": keyword,
        "topic": topic,
        "route": route,
    }

    project_dir = cfg.output_dir / pid
    project_dir.mkdir(parents=True, exist_ok=True)
    path = project_dir / "intake.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    sync_workflow_contract(
        project_dir=project_dir,
        project_id=pid,
        stage="intake",
        status="ok",
        message=f"入口识别: {entry_type}",
        extra={"detected_by": reason, "source": source},
    )
    return path, payload
