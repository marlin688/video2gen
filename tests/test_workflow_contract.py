"""workflow_contract 模块测试。"""

import json

from v2g.workflow_contract import sync_workflow_contract


def test_sync_workflow_contract_creates_files(tmp_path):
    project_dir = tmp_path / "demo"
    sync_workflow_contract(
        project_dir=project_dir,
        project_id="demo",
        stage="prepare",
        status="start",
        message="开始",
    )

    workflow = project_dir / "workflow.md"
    manifest = project_dir / "artifacts_manifest.json"
    run_log = project_dir / "run_log.jsonl"

    assert workflow.exists()
    assert manifest.exists()
    assert run_log.exists()

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["project_id"] == "demo"
    assert any(a.get("path") == "workflow.md" or a.get("path") == "checkpoint.json" for a in payload["artifacts"])
    assert any(a.get("path") == "storyboard.md" for a in payload["artifacts"])

    lines = [l for l in run_log.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["stage"] == "prepare"
    assert row["status"] == "start"


def test_manifest_updates_with_new_artifacts(tmp_path):
    project_dir = tmp_path / "demo2"
    (project_dir / "final").mkdir(parents=True, exist_ok=True)
    (project_dir / "final" / "video.mp4").write_bytes(b"fake")

    sync_workflow_contract(project_dir, "demo2", stage="assemble", status="ok")
    payload = json.loads((project_dir / "artifacts_manifest.json").read_text(encoding="utf-8"))

    video_entry = next(a for a in payload["artifacts"] if a.get("path") == "final/video.mp4")
    assert video_entry["exists"] is True
    assert video_entry["size_bytes"] == 4
