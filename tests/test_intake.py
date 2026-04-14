"""intake 路由测试。"""

from v2g.config import Config
from v2g.intake import create_intake_contract


def _cfg(tmp_path):
    cfg = Config()
    cfg.output_dir = tmp_path
    return cfg


def test_intake_detects_keyword_entry_a(tmp_path):
    path, payload = create_intake_contract(_cfg(tmp_path), source="Claude Code")
    assert path.exists()
    assert payload["entry_type"] == "A"
    assert payload["route"]["workflow"] == "content_pipeline"


def test_intake_detects_youtube_url_as_d(tmp_path):
    _, payload = create_intake_contract(
        _cfg(tmp_path),
        source="https://www.youtube.com/watch?v=abcdefghijk",
    )
    assert payload["entry_type"] == "D"
    assert "v2g run" in payload["route"]["suggested_command"]


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
