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
    audit = project_dir / "workflow_audit.json"

    assert workflow.exists()
    assert manifest.exists()
    assert run_log.exists()
    assert audit.exists()

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["project_id"] == "demo"
    assert payload["version"] == "v2"
    assert any(a.get("path") == "workflow.md" or a.get("path") == "checkpoint.json" for a in payload["artifacts"])
    assert any(a.get("path") == "storyboard.md" for a in payload["artifacts"])
    assert any(a.get("path") == "workflow_audit.json" for a in payload["artifacts"])
    assert any(a.get("path") == "asset_resolve_report.json" for a in payload["artifacts"])

    lines = [l for l in run_log.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["seq"] == 1
    assert row["event_id"]
    assert row["stage"] == "prepare"
    assert row["status"] == "start"

    audit_payload = json.loads(audit.read_text(encoding="utf-8"))
    assert audit_payload["project_id"] == "demo"
    assert audit_payload["run_log_count"] == 1
    assert audit_payload["latest_stage"] == "prepare"


def test_manifest_updates_with_new_artifacts(tmp_path):
    project_dir = tmp_path / "demo2"
    (project_dir / "final").mkdir(parents=True, exist_ok=True)
    (project_dir / "final" / "video.mp4").write_bytes(b"fake")

    sync_workflow_contract(project_dir, "demo2", stage="assemble", status="ok")
    payload = json.loads((project_dir / "artifacts_manifest.json").read_text(encoding="utf-8"))

    video_entry = next(a for a in payload["artifacts"] if a.get("path") == "final/video.mp4")
    assert video_entry["exists"] is True
    assert video_entry["size_bytes"] == 4


def test_workflow_audit_aggregates_asset_resolve_warnings(tmp_path):
    project_dir = tmp_path / "demo3"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "asset_resolve_report.json").write_text(
        json.dumps(
            {
                "checked_segments": 6,
                "resolved_local": 2,
                "resolved_remote": 2,
                "unresolved": 2,
                "unknown_rights_local_hits": 1,
                "unresolved_segment_ids": [4, 6],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    sync_workflow_contract(project_dir, "demo3", stage="assets_resolve", status="ok")
    payload = json.loads((project_dir / "workflow_audit.json").read_text(encoding="utf-8"))
    assert payload["asset_resolve"]["unresolved"] == 2
    assert payload["asset_resolve"]["unknown_rights_local_hits"] == 1
    kinds = {a["kind"] for a in payload["alerts"]}
    assert "asset_unresolved" in kinds
    assert "asset_rights_unknown" in kinds
