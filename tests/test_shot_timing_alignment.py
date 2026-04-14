"""shot_plan/render_plan 与 TTS timing 对齐测试。"""

import json

from v2g.scriptwriter import sync_script_sidecars


def _script() -> dict:
    return {
        "title": "Timing Demo",
        "description": "demo",
        "tags": ["ai", "timing", "demo"],
        "segments": [
            {
                "id": 1,
                "type": "intro",
                "material": "A",
                "narration_zh": "第一句。第二句。",
                "slide_content": {"title": "S1", "bullet_points": ["a"]},
            },
            {
                "id": 2,
                "type": "body",
                "material": "B",
                "narration_zh": "第三句。第四句。",
                "terminal_session": [{"type": "input", "text": "echo hi"}],
            },
        ],
    }


def test_shot_plan_has_timeline_when_tts_timing_exists(tmp_path):
    output_dir = tmp_path
    voiceover_dir = output_dir / "voiceover"
    voiceover_dir.mkdir(parents=True, exist_ok=True)
    timing = {
        "1": {"duration": 4.0, "gap_after": 0.5},
        "2": {"duration": 6.0, "gap_after": 0.0},
    }
    (voiceover_dir / "timing.json").write_text(
        json.dumps(timing, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    sync_script_sidecars(_script(), output_dir)

    shot_plan = json.loads((output_dir / "shot_plan.json").read_text(encoding="utf-8"))
    render_plan = json.loads((output_dir / "render_plan.json").read_text(encoding="utf-8"))

    assert shot_plan["has_timing"] is True
    assert render_plan["has_timing"] is True

    shots = shot_plan["shots"]
    assert len(shots) == 4
    assert abs(shots[0]["start_sec"] - 0.0) < 1e-6
    assert abs(shots[1]["end_sec"] - 4.0) < 1e-6
    assert abs(shots[2]["start_sec"] - 4.5) < 1e-6
    assert abs(shots[3]["end_sec"] - 10.5) < 1e-6

    segs = render_plan["segments"]
    assert segs[0]["start_sec"] == 0.0
    assert segs[0]["end_sec"] == 4.0
    assert segs[1]["start_sec"] == 4.5
    assert segs[1]["end_sec"] == 10.5


def test_shot_plan_without_timing_has_no_windows(tmp_path):
    sync_script_sidecars(_script(), tmp_path)
    shot_plan = json.loads((tmp_path / "shot_plan.json").read_text(encoding="utf-8"))
    assert shot_plan["has_timing"] is False
    assert all(s.get("start_sec") is None for s in shot_plan["shots"])
