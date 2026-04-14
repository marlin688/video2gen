"""intake 路由测试。"""

import json

from v2g.config import Config
from v2g.intake import create_intake_contract, execute_intake_route


def _cfg(tmp_path):
    cfg = Config()
    cfg.output_dir = tmp_path
    return cfg


def test_intake_detects_keyword_entry_a(tmp_path):
    path, payload = create_intake_contract(_cfg(tmp_path), source="Claude Code")
    assert path.exists()
    assert payload["entry_type"] == "A"
    assert payload["route"]["workflow"] == "content_pipeline"
    assert payload["route"]["run_argv"] == ["scout", "script", "Claude Code"]


def test_intake_detects_youtube_url_as_d(tmp_path):
    _, payload = create_intake_contract(
        _cfg(tmp_path),
        source="https://www.youtube.com/watch?v=abcdefghijk",
    )
    assert payload["entry_type"] == "D"
    assert "v2g run" in payload["route"]["suggested_command"]
    assert payload["route"]["run_argv"] == [
        "run",
        "https://www.youtube.com/watch?v=abcdefghijk",
    ]


def test_intake_detects_script_file_with_keyword_as_c(tmp_path):
    script_file = tmp_path / "demo.md"
    script_file.write_text("这是脚本文案", encoding="utf-8")
    _, payload = create_intake_contract(
        _cfg(tmp_path),
        source=str(script_file),
        keyword="AI 视频",
    )
    assert payload["entry_type"] == "C"
    assert payload["route"]["target_stage"] == "agent_script"
    assert payload["normalized_source"] == str(script_file.resolve())
    assert payload["route"]["run_argv"][0] == "agent"


def test_intake_materializes_inline_text_for_b_entry(tmp_path):
    long_text = "这是一个较长的口播稿，包含多句内容。第二句继续讲解。第三句用于测试。"
    _, payload = create_intake_contract(_cfg(tmp_path), source=long_text)
    assert payload["entry_type"] == "B"
    assert payload["normalized_source_kind"] == "inline_text_file"

    source_file = tmp_path / payload["project_id"] / "input" / "source_text.md"
    assert source_file.exists()
    assert payload["normalized_source"] == str(source_file.resolve())
    assert payload["route"]["run_argv"][0] == "agent"


def test_intake_execute_dry_run_writes_dispatch_log(tmp_path):
    cfg = _cfg(tmp_path)
    _, payload = create_intake_contract(
        cfg,
        source="Claude Code",
    )
    rc = execute_intake_route(cfg, payload, dry_run=True)
    assert rc == 0

    run_log_path = tmp_path / payload["project_id"] / "run_log.jsonl"
    rows = [
        json.loads(line)
        for line in run_log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    statuses = [r.get("status") for r in rows if r.get("stage") == "intake_dispatch"]
    assert "start" in statuses
    assert "dry_run" in statuses
