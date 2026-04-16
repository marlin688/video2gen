from pathlib import Path

from v2g.script_fixer import fix_script


def _base_script() -> dict:
    return {
        "title": "测试",
        "description": "测试",
        "tags": ["ai", "video", "test"],
        "segments": [
            {
                "id": 1,
                "type": "intro",
                "material": "A",
                "narration_zh": "开场说一个今天热点。",
                "component": "slide.tech-dark",
                "slide_content": {"title": "Intro", "bullet_points": ["要点"]},
            },
            {
                "id": 2,
                "type": "body",
                "material": "B",
                "narration_zh": "展示终端步骤。",
                "component": "terminal.aurora",
                "terminal_session": [{"type": "input", "text": "echo hello"}],
            },
            {
                "id": 3,
                "type": "body",
                "material": "A",
                "narration_zh": "讲一下产品演示细节。",
                "component": "slide.feature-grid",
                "slide_content": {"title": "Body", "bullet_points": ["步骤1", "步骤2"]},
            },
        ],
    }


def test_fix_script_enforces_rich_media_presence(tmp_path: Path):
    script = _base_script()

    fixed, logs = fix_script(script, tmp_path, ensure_rich_media=True)
    assert logs

    segments = fixed["segments"]
    image_segments = [s for s in segments if (s.get("component") or "").startswith("image-overlay")]
    web_segments = [s for s in segments if (s.get("component") or "").startswith("web-video")]

    assert len(image_segments) >= 1
    assert len(web_segments) >= 1

    image_content = image_segments[0].get("image_content")
    assert isinstance(image_content, dict)
    assert image_content.get("image_path") == ""
    assert image_content.get("source_method") in {"search", "screenshot", "generate"}
    assert image_content.get("source_query")

    web_video = web_segments[0].get("web_video")
    assert isinstance(web_video, dict)
    assert web_video.get("search_query")
    assert web_video.get("fallback_component")


def test_fix_script_does_not_enforce_when_disabled(tmp_path: Path):
    script = _base_script()

    fixed, _ = fix_script(script, tmp_path, ensure_rich_media=False)
    segments = fixed["segments"]
    schemas = {(s.get("component") or "").split(".")[0] for s in segments if s.get("component")}

    assert "image-overlay" not in schemas
    assert "web-video" not in schemas


def test_fix_script_normalizes_existing_rich_media_payload(tmp_path: Path):
    script = {
        "title": "测试",
        "description": "测试",
        "tags": ["ai", "video", "test"],
        "segments": [
            {
                "id": 1,
                "type": "body",
                "material": "A",
                "narration_zh": "这是配图段。",
                "component": "image-overlay.default",
                "image_content": {"image_path": ""},
            },
            {
                "id": 2,
                "type": "body",
                "material": "A",
                "narration_zh": "这是动态视频段。",
                "component": "web-video.default",
                "web_video": {},
            },
        ],
    }

    fixed, logs = fix_script(script, tmp_path, ensure_rich_media=True)
    assert logs

    image = fixed["segments"][0]["image_content"]
    assert image.get("source_method") == "search"
    assert image.get("source_query")

    web_video = fixed["segments"][1]["web_video"]
    assert web_video.get("search_query")
    assert web_video.get("fallback_component")


def test_fix_script_normalizes_hero_stat_list_payload(tmp_path: Path):
    script = {
        "title": "测试",
        "description": "测试",
        "tags": ["ai", "video", "test"],
        "segments": [
            {
                "id": 1,
                "type": "body",
                "material": "A",
                "narration_zh": "这是一个关键数据段。",
                "component": "hero-stat.default",
                "hero_stat": [
                    {"label": "增速", "value": "175%", "trend": "up"},
                    {"label": "风险", "value": "更高", "trend": "down"},
                ],
            }
        ],
    }

    fixed, logs = fix_script(script, tmp_path, ensure_rich_media=False)
    assert any("hero_stat list" in log for log in logs)
    assert fixed["segments"][0]["hero_stat"]["stats"][0]["label"] == "增速"


def test_fix_script_normalizes_browser_content_legacy_fields(tmp_path: Path):
    script = {
        "title": "测试",
        "description": "测试",
        "tags": ["ai", "video", "test"],
        "segments": [
            {
                "id": 1,
                "type": "body",
                "material": "B",
                "narration_zh": "这是一个浏览器段。",
                "component": "browser.default",
                "browser_content": {
                    "title": "AI 概念与市场情绪",
                    "active_tab": "Markets",
                    "summary": "标题很猛，落地很虚",
                    "tabs": ["News", "Markets", "AI"],
                },
            }
        ],
    }

    fixed, logs = fix_script(script, tmp_path, ensure_rich_media=False)
    assert any("browser_content normalized" in log for log in logs)
    browser = fixed["segments"][0]["browser_content"]
    assert browser["tabTitle"] == "Markets"
    assert browser["pageTitle"] == "AI 概念与市场情绪"
    assert browser["contentLines"][0] == "标题很猛，落地很虚"


def test_fix_script_promotes_dual_card_scene_data(tmp_path: Path):
    script = {
        "title": "测试",
        "description": "测试",
        "tags": ["ai", "video", "test"],
        "segments": [
            {
                "id": 1,
                "type": "body",
                "material": "A",
                "narration_zh": "双卡总结。",
                "component": "diagram.dual-card",
                "scene_data": {
                    "arrowLabel": "从外包自己 -> 放大自己",
                    "left": {
                        "title": "错误托管",
                        "type": "warning",
                        "items": [{"text": "敏感代码整段贴入", "tag": "✗"}],
                        "footer": "省事一时",
                    },
                    "right": {
                        "title": "增强式使用",
                        "type": "primary",
                        "items": [{"text": "先脱敏再提问", "tag": "✓"}],
                        "footer": "长期更稳",
                    },
                },
            }
        ],
    }

    fixed, logs = fix_script(script, tmp_path, ensure_rich_media=False)
    assert any("scene_data(dual-card)" in log for log in logs)
    diagram = fixed["segments"][0]["diagram"]
    assert diagram["nodes"][0]["label"] == "错误托管"
    assert diagram["edges"][0]["from"] == "left"


def test_fix_script_promotes_pipeline_scene_data(tmp_path: Path):
    script = {
        "title": "测试",
        "description": "测试",
        "tags": ["ai", "video", "test"],
        "segments": [
            {
                "id": 1,
                "type": "body",
                "material": "A",
                "narration_zh": "流程图说明。",
                "component": "diagram.pipeline",
                "scene_data": {
                    "steps": [
                        {"title": "发现问题", "icon": "Alert", "keywords": ["Sentry", "触发"]},
                        {"title": "定位原因", "icon": "Search", "keywords": ["日志", "排查"]},
                        {"title": "提交结果", "icon": "GitPullRequest", "keywords": ["PR", "同步"]},
                    ]
                },
            }
        ],
    }

    fixed, logs = fix_script(script, tmp_path, ensure_rich_media=False)
    assert any("scene_data(steps)" in log for log in logs)
    diagram = fixed["segments"][0]["diagram"]
    assert len(diagram["nodes"]) == 3
    assert diagram["edges"][0]["from"] == "step-1"


def test_fix_script_normalizes_code_content_string_code(tmp_path: Path):
    script = {
        "title": "测试",
        "description": "测试",
        "tags": ["ai", "video", "test"],
        "segments": [
            {
                "id": 1,
                "type": "body",
                "material": "B",
                "narration_zh": "配置示例。",
                "component": "code-block.default",
                "code_content": {
                    "fileName": "ai-policy.yaml",
                    "language": "yaml",
                    "code": "public: ok\nsecret: local_only",
                },
            }
        ],
    }

    fixed, logs = fix_script(script, tmp_path, ensure_rich_media=False)
    assert any("code_content.code string" in log for log in logs)
    assert fixed["segments"][0]["code_content"]["code"] == ["public: ok", "secret: local_only"]


def test_fix_script_normalizes_material_from_component_schema(tmp_path: Path):
    script = {
        "title": "测试",
        "description": "测试",
        "tags": ["ai", "video", "test"],
        "segments": [
            {
                "id": 1,
                "type": "body",
                "material": "B",
                "narration_zh": "真实配图段。",
                "component": "image-overlay.default",
                "image_content": {"image_path": "", "source_method": "search", "source_query": "Claude pricing"},
            },
            {
                "id": 2,
                "type": "body",
                "material": "B",
                "narration_zh": "真实动态段。",
                "component": "web-video.default",
                "web_video": {"search_query": "AI coding demo", "fallback_component": "slide.tech-dark"},
            },
            {
                "id": 3,
                "type": "body",
                "material": "C",
                "narration_zh": "终端演示。",
                "component": "terminal.aurora",
                "terminal_session": [{"type": "input", "text": "echo ok"}],
            },
        ],
    }

    fixed, logs = fix_script(script, tmp_path, ensure_rich_media=False)
    assert any("material B → A (schema image-overlay)" in log for log in logs)
    assert any("material B → C (schema web-video)" in log for log in logs)
    assert any("material C → B (schema terminal)" in log for log in logs)
    assert fixed["segments"][0]["material"] == "A"
    assert fixed["segments"][1]["material"] == "C"
    assert fixed["segments"][2]["material"] == "B"


def test_fix_script_downgrades_empty_a_component_to_slide(tmp_path: Path):
    script = {
        "title": "测试",
        "description": "测试",
        "tags": ["ai", "video", "test"],
        "segments": [
            {
                "id": 1,
                "type": "body",
                "material": "A",
                "narration_zh": "结果最关键的地方，是你一看交付物就知道有没有价值。",
                "component": "hero-stat.default",
            }
        ],
    }

    fixed, logs = fix_script(script, tmp_path, ensure_rich_media=False)
    assert any("slide.tech-dark (from narration)" in log for log in logs)
    assert fixed["segments"][0]["component"] == "slide.tech-dark"
    assert fixed["segments"][0]["slide_content"]["bullet_points"]
