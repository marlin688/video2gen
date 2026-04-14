"""scriptwriter sidecar 一致性测试。"""

import copy
import json

from v2g.scriptwriter import sync_script_sidecars, validate_script_sidecars


def _sample_script(material: str = "A") -> dict:
    seg = {
        "id": 1,
        "type": "intro",
        "material": material,
        "narration_zh": "第一句。第二句。",
    }
    if material == "A":
        seg["slide_content"] = {"title": "标题", "bullet_points": ["要点1"]}
    elif material == "B":
        seg["terminal_session"] = [{"type": "input", "text": "echo hello"}]
    else:
        seg["source_start"] = 0.0
        seg["source_end"] = 5.0

    return {
        "title": "测试标题",
        "description": "测试描述",
        "tags": ["ai", "test", "video"],
        "segments": [seg],
    }


def test_sidecars_validate_after_sync(tmp_path):
    script = _sample_script("A")
    sync_script_sidecars(script, tmp_path)

    issues = validate_script_sidecars(script, tmp_path)
    assert issues == []

    shot_plan = json.loads((tmp_path / "shot_plan.json").read_text(encoding="utf-8"))
    assert shot_plan["shots"]
    first_shot = shot_plan["shots"][0]
    assert first_shot["shot_type"]
    assert first_shot["camera_move"]
    assert first_shot["lighting_tag"]

    render_plan = json.loads((tmp_path / "render_plan.json").read_text(encoding="utf-8"))
    first_seg = render_plan["segments"][0]
    cine = first_seg["cinematography"]
    assert cine["shot_type"]
    assert cine["camera_move"]
    assert cine["lighting_tag"]
    assert 0.0 <= float(cine["camera_intensity"]) <= 1.2


def test_sidecars_detect_stale_plan(tmp_path):
    script = _sample_script("A")
    sync_script_sidecars(script, tmp_path)

    # 模拟 script.json 被修改但 sidecar 未刷新
    changed = copy.deepcopy(script)
    changed["segments"][0]["material"] = "B"
    changed["segments"][0].pop("slide_content", None)
    changed["segments"][0]["terminal_session"] = [
        {"type": "input", "text": "python -V"}
    ]

    issues = validate_script_sidecars(changed, tmp_path)
    assert issues
    assert any("visual_type" in i or "material" in i for i in issues)


def test_sidecars_detect_missing_files(tmp_path):
    script = _sample_script("A")
    issues = validate_script_sidecars(script, tmp_path)
    assert "缺少 sidecar: shot_plan.json" in issues
    assert "缺少 sidecar: render_plan.json" in issues


def test_sync_sidecars_generates_storyboard(tmp_path):
    script = _sample_script("A")
    sync_script_sidecars(script, tmp_path)

    storyboard = tmp_path / "storyboard.md"
    assert storyboard.exists()
    content = storyboard.read_text(encoding="utf-8")
    assert "逐句文案（口语化）" in content
    assert "逐句画面编排（Step 6b 逐句匹配）" in content


def test_shot_plan_prefers_image_overlay_asset_path(tmp_path):
    script = {
        "title": "图片分镜",
        "description": "demo",
        "tags": ["ai", "image"],
        "segments": [
            {
                "id": 1,
                "type": "body",
                "material": "A",
                "component": "image-overlay.default",
                "narration_zh": "这是图片演示。",
                "image_content": {
                    "image_path": "images/prompt-guide.png",
                    "overlay_text": "官方截图 + 箭头标注",
                },
            }
        ],
    }
    sync_script_sidecars(script, tmp_path)

    shot_plan = json.loads((tmp_path / "shot_plan.json").read_text(encoding="utf-8"))
    shot = shot_plan["shots"][0]
    assert shot["asset_path"] == "images/prompt-guide.png"
    assert shot["scene_hint"].startswith("官方截图 + 箭头标注")


def test_shot_plan_scene_hint_is_beat_level_and_short(tmp_path):
    script = {
        "title": "逐句标签",
        "description": "demo",
        "tags": ["ai", "hint"],
        "segments": [
            {
                "id": 1,
                "type": "body",
                "material": "A",
                "component": "slide.tech-dark",
                "narration_zh": "第一句是一个非常明确的观点。第二句补充操作步骤和结论。",
                "slide_content": {
                    "title": "一个很长很长的标题应该被压缩显示",
                    "bullet_points": ["同样很长的要点描述也不该整段重复出现"],
                },
            }
        ],
    }
    sync_script_sidecars(script, tmp_path)

    shot_plan = json.loads((tmp_path / "shot_plan.json").read_text(encoding="utf-8"))
    assert len(shot_plan["shots"]) == 2

    hint_1 = shot_plan["shots"][0]["scene_hint"]
    hint_2 = shot_plan["shots"][1]["scene_hint"]
    assert hint_1 != hint_2
    assert len(hint_1) <= 20
    assert len(hint_2) <= 20
