"""scriptwriter 电影语言标签与逐句拆分回归测试。"""

from v2g.scriptwriter import (
    _infer_cinematography_tags,
    _infer_segment_cinematography,
    _split_narration_to_beats,
)


def test_screen_rhythm_fast_still_prefers_static_move():
    seg = {
        "id": 1,
        "type": "body",
        "material": "B",
        "rhythm": "fast",
        "terminal_session": [{"type": "input", "text": "python main.py"}],
    }
    tags = _infer_cinematography_tags(seg, "先看命令输出", beat_id=1)
    assert tags["shot_type"] == "screen"
    assert tags["camera_move"] == "static"
    assert tags["camera_intensity"] == 0.0


def test_tag_source_only_script_when_valid_explicit_value_used():
    seg_invalid = {
        "id": 1,
        "type": "body",
        "material": "A",
        "shot_type": "unknown-shot",
        "camera_move": "bad-move",
        "lighting_tag": "bad-light",
        "camera_intensity": "oops",
    }
    auto_tags = _infer_cinematography_tags(seg_invalid, "普通说明", beat_id=1)
    assert auto_tags["tag_source"] == "auto"

    seg_valid = {
        "id": 2,
        "type": "body",
        "material": "A",
        "camera_move": "push-in",
    }
    script_tags = _infer_cinematography_tags(seg_valid, "普通说明", beat_id=1)
    assert script_tags["tag_source"] == "script"
    assert script_tags["camera_move"] == "push-in"


def test_segment_tags_aggregate_from_beats_not_only_first_sentence():
    seg = {
        "id": 3,
        "type": "body",
        "material": "A",
        "narration_zh": "先铺垫背景。这里有严重风险会失败。",
    }
    seg_beats = [
        {"beat_id": 1, "text": "先铺垫背景"},
        {"beat_id": 2, "text": "这里有严重风险会失败"},
    ]
    beat_timeline = {
        1: {"duration_sec": 0.8},
        2: {"duration_sec": 3.2},
    }
    tags = _infer_segment_cinematography(seg, 0, seg_beats=seg_beats, beat_timeline=beat_timeline)
    assert tags["lighting_tag"] == "dramatic"


def test_split_beats_preserve_command_url_and_path_tokens():
    narration = (
        "先执行 `v2g scout produce -i 0`，然后打开 https://example.com/demo/path?a=1，"
        "再看 /tmp/work/demo.txt。最后总结。"
    )
    beats = _split_narration_to_beats(narration)
    assert any("v2g scout produce -i 0" in b for b in beats)
    assert any("https://example.com/demo/path?a=1" in b for b in beats)
    assert any("/tmp/work/demo.txt" in b for b in beats)
