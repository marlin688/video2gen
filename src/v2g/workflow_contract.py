"""项目级 workflow 文件契约：workflow.md / artifacts_manifest.json / run_log.jsonl。"""

from __future__ import annotations

import json
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
        "## Input Contract",
        "- `intake.json`: 入口路由契约（可选）",
        "- `script.json`: 下游 stage 的唯一脚本真源",
        "",
        "## Output Contract",
        "- `artifacts_manifest.json`: 当前项目产物索引（自动更新）",
        "- `run_log.jsonl`: 关键阶段执行日志（append-only）",
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
    artifacts = [
        _file_entry(project_dir, "workflow.md", "workflow_contract"),
        _file_entry(project_dir, "run_log.jsonl", "run_log"),
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
        _file_entry(project_dir, "final/video.mp4", "final_video"),
        _file_entry(project_dir, "final/subtitles.srt", "final_subtitles"),
        _glob_entry(project_dir, "slides/*.png", "slides"),
        _glob_entry(project_dir, "voiceover/segments/*.mp3", "voice_segments"),
        _glob_entry(project_dir, "recordings/*.mp4", "recordings"),
        _glob_entry(project_dir, "images/*", "images"),
        _glob_entry(project_dir, "web_videos/*", "web_videos"),
    ]

    payload = {
        "version": "v1",
        "project_id": project_id,
        "generated_at": _now_iso(),
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
    record = {
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
    write_artifacts_manifest(project_dir, project_id)
    if stage:
        append_run_log(
            project_dir=project_dir,
            stage=stage,
            status=status,
            message=message,
            extra=extra,
        )
