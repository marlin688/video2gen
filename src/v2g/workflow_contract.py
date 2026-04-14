"""项目级 workflow 文件契约：workflow.md / artifacts_manifest.json / run_log.jsonl。"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _file_entry(project_dir: Path, rel_path: str, role: str) -> dict:
    path = project_dir / rel_path
    exists = path.exists()
    entry = {
        "path": rel_path,
        "role": role,
        "exists": exists,
    }
    if exists and path.is_file():
        stat = path.stat()
        entry["size_bytes"] = stat.st_size
        entry["updated_at"] = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    return entry


def _glob_entry(project_dir: Path, pattern: str, role: str) -> dict:
    files = [p for p in project_dir.glob(pattern) if p.is_file()]
    files = sorted(files, key=lambda p: str(p))
    sample = [str(p.relative_to(project_dir)) for p in files[:10]]
    return {
        "pattern": pattern,
        "role": role,
        "count": len(files),
        "sample": sample,
    }


def ensure_workflow_md(project_dir: Path, project_id: str) -> Path:
    """创建 workflow.md（已存在则不覆盖）。"""
    project_dir.mkdir(parents=True, exist_ok=True)
    path = project_dir / "workflow.md"
    if path.exists():
        return path

    content = "\n".join([
        f"# Workflow Contract - {project_id}",
        "",
        "Version: v2",
        "",
        "## Input Contract",
        "- `intake.json`: 入口路由契约（可选）",
        "- `script.json`: 下游 stage 的唯一脚本真源",
        "- `asset_resolve_report.json`: 素材解析报告（命中来源/缺失项/版权状态）",
        "",
        "## Output Contract",
        "- `artifacts_manifest.json`: 当前项目产物索引（自动更新）",
        "- `run_log.jsonl`: 关键阶段执行日志（append-only）",
        "- `workflow_audit.json`: 阶段回放 + 告警聚合（用于复盘与审计）",
        "- `final/video.mp4`: 最终成片（如已完成）",
        "",
        "## Stage Order",
        "1. prepare",
        "2. script",
        "3. review",
        "4. tts",
        "5. slides",
        "6. render/assemble",
        "",
        "## Asset Governance",
        "- 本地素材优先复用，缺失时再在线补图。",
        "- 版权字段：`rights_status` = cleared / unknown / restricted / expired。",
        "- 建议商业发布前启用严格模式：仅复用 `rights_status=cleared` 素材。",
        "",
        "## Notes",
        "- `script.md` 为可读导出，不是数据真源。",
        "- 任何 stage 失败都应写入 `run_log.jsonl`。",
        "",
    ])
    path.write_text(content, encoding="utf-8")
    return path


def write_artifacts_manifest(project_dir: Path, project_id: str) -> Path:
    """更新 artifacts_manifest.json。"""
    project_dir.mkdir(parents=True, exist_ok=True)
    logs = _load_run_log(project_dir)
    latest = logs[-1] if logs else {}
    status_counter = Counter(row.get("status", "") for row in logs if row.get("status"))

    artifacts = [
        _file_entry(project_dir, "workflow.md", "workflow_contract"),
        _file_entry(project_dir, "run_log.jsonl", "run_log"),
        _file_entry(project_dir, "workflow_audit.json", "audit"),
        _file_entry(project_dir, "checkpoint.json", "state"),
        _file_entry(project_dir, "intake.json", "contract"),
        _file_entry(project_dir, "outline.json", "outline"),
        _file_entry(project_dir, "script.json", "script"),
        _file_entry(project_dir, "script.md", "script_export"),
        _file_entry(project_dir, "script_beats.md", "script_beats"),
        _file_entry(project_dir, "storyboard.md", "storyboard"),
        _file_entry(project_dir, "shot_plan.json", "shot_plan"),
        _file_entry(project_dir, "render_plan.json", "render_plan"),
        _file_entry(project_dir, "recording_guide.md", "recording_guide"),
        _file_entry(project_dir, "voiceover/full.mp3", "voiceover"),
        _file_entry(project_dir, "voiceover/timing.json", "timing"),
        _file_entry(project_dir, "voiceover/word_timing.json", "word_timing"),
        _file_entry(project_dir, "asset_resolve_report.json", "asset_resolve_report"),
        _file_entry(project_dir, "final/video.mp4", "final_video"),
        _file_entry(project_dir, "final/subtitles.srt", "final_subtitles"),
        _glob_entry(project_dir, "slides/*.png", "slides"),
        _glob_entry(project_dir, "voiceover/segments/*.mp3", "voice_segments"),
        _glob_entry(project_dir, "recordings/*.mp4", "recordings"),
        _glob_entry(project_dir, "images/*", "images"),
        _glob_entry(project_dir, "web_videos/*", "web_videos"),
    ]

    payload = {
        "version": "v2",
        "project_id": project_id,
        "generated_at": _now_iso(),
        "latest_stage": latest.get("stage", ""),
        "latest_status": latest.get("status", ""),
        "run_log_count": len(logs),
        "status_counts": dict(status_counter),
        "artifacts": artifacts,
    }
    path = project_dir / "artifacts_manifest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def append_run_log(
    project_dir: Path,
    stage: str,
    status: str,
    message: str = "",
    extra: dict | None = None,
) -> Path:
    """追加一条阶段执行日志。"""
    project_dir.mkdir(parents=True, exist_ok=True)
    prev_logs = _load_run_log(project_dir)
    seq = len(prev_logs) + 1
    record = {
        "event_id": f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{seq:04d}",
        "seq": seq,
        "ts": _now_iso(),
        "stage": stage,
        "status": status,
        "message": message,
    }
    if extra:
        record["extra"] = extra

    path = project_dir / "run_log.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def _load_run_log(project_dir: Path) -> list[dict]:
    path = project_dir / "run_log.jsonl"
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _load_asset_resolve_report(project_dir: Path) -> dict:
    path = project_dir / "asset_resolve_report.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def write_workflow_audit(project_dir: Path, project_id: str) -> Path:
    """写入 workflow_audit.json，聚合阶段日志和素材解析告警。"""
    logs = _load_run_log(project_dir)
    asset_report = _load_asset_resolve_report(project_dir)

    stage_counts = Counter(row.get("stage", "") for row in logs if row.get("stage"))
    status_counts = Counter(row.get("status", "") for row in logs if row.get("status"))
    latest = logs[-1] if logs else {}
    errors = [row for row in logs if row.get("status") == "error"]

    alerts: list[dict] = []
    if errors:
        alerts.append(
            {
                "level": "error",
                "kind": "stage_error",
                "count": len(errors),
                "message": f"{len(errors)} 个阶段出现 error 状态",
            }
        )
    unresolved = int(asset_report.get("unresolved") or 0) if asset_report else 0
    if unresolved > 0:
        alerts.append(
            {
                "level": "warning",
                "kind": "asset_unresolved",
                "count": unresolved,
                "message": f"{unresolved} 个分段素材未解析",
                "segments": list(asset_report.get("unresolved_segment_ids") or []),
            }
        )
    unknown_hits = int(asset_report.get("unknown_rights_local_hits") or 0) if asset_report else 0
    if unknown_hits > 0:
        alerts.append(
            {
                "level": "warning",
                "kind": "asset_rights_unknown",
                "count": unknown_hits,
                "message": f"{unknown_hits} 个本地命中素材版权状态未知",
            }
        )

    payload = {
        "version": "v1",
        "project_id": project_id,
        "generated_at": _now_iso(),
        "run_log_count": len(logs),
        "latest_stage": latest.get("stage", ""),
        "latest_status": latest.get("status", ""),
        "stage_counts": dict(stage_counts),
        "status_counts": dict(status_counts),
        "error_events": len(errors),
        "asset_resolve": {
            "checked_segments": int(asset_report.get("checked_segments") or 0),
            "kept_existing": int(asset_report.get("kept_existing") or 0),
            "resolved_local": int(asset_report.get("resolved_local") or 0),
            "resolved_remote": int(asset_report.get("resolved_remote") or 0),
            "unresolved": unresolved,
            "unknown_rights_local_hits": unknown_hits,
            "unresolved_segment_ids": list(asset_report.get("unresolved_segment_ids") or []),
        },
        "alerts": alerts,
    }
    path = project_dir / "workflow_audit.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def sync_workflow_contract(
    project_dir: Path,
    project_id: str,
    stage: str | None = None,
    status: str = "ok",
    message: str = "",
    extra: dict | None = None,
) -> None:
    """确保 workflow 契约文件存在，并可选写入阶段日志。"""
    ensure_workflow_md(project_dir, project_id)
    if stage:
        append_run_log(
            project_dir=project_dir,
            stage=stage,
            status=status,
            message=message,
            extra=extra,
        )
    write_workflow_audit(project_dir, project_id)
    write_artifacts_manifest(project_dir, project_id)
