"""schema.py 纯函数测试：验证 Pydantic 模型的结构校验行为。"""

import pytest

from v2g.schema import validate_script, ScriptData, ScriptSegment


# ── 辅助工厂 ─────────────────────────────────────────────────


def _make_segment(id: int = 1, type: str = "body", material: str = "A", **kw):
    """生成一个最小合法 segment dict。"""
    base = {
        "id": id,
        "type": type,
        "material": material,
        "narration_zh": kw.pop("narration_zh", "测试旁白内容，用于验证。"),
    }
    # A 类默认带 slide_content
    if material == "A" and "slide_content" not in kw and "component" not in kw:
        base["slide_content"] = {"title": "测试标题", "bullet_points": ["要点1"]}
    # B 类默认带 terminal_session
    if material == "B" and "terminal_session" not in kw and "recording_instruction" not in kw and "component" not in kw:
        base["terminal_session"] = [{"type": "input", "text": "echo hello"}]
    # C 类默认带 source 时间
    if material == "C" and "source_start" not in kw:
        base["source_start"] = 0.0
        base["source_end"] = 5.0
    base.update(kw)
    return base


def _make_script(segments=None, **kw):
    """生成一个最小合法 script dict。"""
    base = {
        "title": kw.pop("title", "测试视频"),
        "description": kw.pop("description", "测试描述"),
        "tags": kw.pop("tags", ["ai", "test", "demo"]),
        "segments": segments or [
            _make_segment(1, "intro", "A"),
            _make_segment(2, "body", "B"),
            _make_segment(3, "outro", "A"),
        ],
    }
    base.update(kw)
    return base


# ── 正向测试 ─────────────────────────────────────────────────


class TestValidScript:
    def test_minimal_valid(self):
        data, errors = validate_script(_make_script())
        assert errors == []
        assert isinstance(data, ScriptData)
        assert len(data.segments) == 3

    def test_optional_fields_absent(self):
        """source_channel, total_duration_hint 等可选字段缺失不报错。"""
        script = _make_script()
        data, errors = validate_script(script)
        assert errors == []
        assert data.source_channel is None
        assert data.total_duration_hint is None

    def test_all_material_types(self):
        segments = [
            _make_segment(1, "intro", "A"),
            _make_segment(2, "body", "B"),
            _make_segment(3, "body", "C"),
            _make_segment(4, "outro", "A"),
        ]
        data, errors = validate_script(_make_script(segments=segments))
        assert errors == []
        assert [s.material for s in data.segments] == ["A", "B", "C", "A"]

    def test_with_component(self):
        seg = _make_segment(1, "body", "B", component="terminal.aurora")
        data, errors = validate_script(_make_script(segments=[seg]))
        assert errors == []
        assert data.segments[0].component == "terminal.aurora"

    def test_multi_source_fields(self):
        script = _make_script(
            source_channel="TestChannel",
            total_duration_hint=120.5,
            sources_used=["src1", "src2"],
        )
        data, errors = validate_script(script)
        assert errors == []
        assert data.source_channel == "TestChannel"
        assert data.total_duration_hint == 120.5
        assert data.sources_used == ["src1", "src2"]

    def test_code_block_annotations_string_keys(self):
        """annotations 的 key 应为 string（JSON 序列化后的行号）。"""
        seg = _make_segment(1, "body", "B", component="code-block.default",
                            code_content={
                                "fileName": "main.py",
                                "language": "python",
                                "code": ["print('hello')", "x = 1"],
                                "highlightLines": [1],
                                "annotations": {"1": "关键行"},
                            })
        data, errors = validate_script(_make_script(segments=[seg]))
        assert errors == []
        assert data.segments[0].code_content.annotations == {"1": "关键行"}

    def test_diagram_edge_from_alias(self):
        """diagram edge 的 'from' 字段通过 alias 映射到 from_。"""
        seg = _make_segment(1, "body", "A", component="diagram.default",
                            diagram={
                                "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
                                "edges": [{"from": "a", "to": "b"}],
                            })
        data, errors = validate_script(_make_script(segments=[seg]))
        assert errors == []
        assert data.segments[0].diagram.edges[0].from_ == "a"

    def test_diagram_tree_card_fields(self):
        """diagram node 的 tree-card 扩展字段（subtitle, items, status）正常解析。"""
        seg = _make_segment(1, "body", "A", component="diagram.tree-card",
                            diagram={
                                "title": "/tech-debt tailored per project",
                                "nodes": [
                                    {"id": "root", "label": "Root Project"},
                                    {
                                        "id": "app1", "label": "SaaS App", "type": "primary",
                                        "subtitle": "React + Node",
                                        "items": [
                                            {"text": "3 duplicated hooks", "tag": "duplication"},
                                            {"text": "unused components", "tag": "unused"},
                                        ],
                                        "status": "✓ Complete",
                                    },
                                ],
                                "edges": [{"from": "root", "to": "app1"}],
                            })
        data, errors = validate_script(_make_script(segments=[seg]))
        assert errors == []
        node = data.segments[0].diagram.nodes[1]
        assert node.subtitle == "React + Node"
        assert len(node.items) == 2
        assert node.items[0].text == "3 duplicated hooks"
        assert node.items[0].tag == "duplication"
        assert node.status == "✓ Complete"


# ── 错误检测 ─────────────────────────────────────────────────


class TestInvalidScript:
    def test_missing_title(self):
        script = _make_script()
        del script["title"]
        _, errors = validate_script(script)
        assert len(errors) > 0
        assert any("title" in e for e in errors)

    def test_missing_segments(self):
        script = _make_script()
        del script["segments"]
        _, errors = validate_script(script)
        assert len(errors) > 0

    def test_invalid_material(self):
        seg = _make_segment(1, "body", "A")
        seg["material"] = "X"
        _, errors = validate_script(_make_script(segments=[seg]))
        assert len(errors) > 0

    def test_invalid_segment_type(self):
        seg = _make_segment(1, "body", "A")
        seg["type"] = "middle"
        _, errors = validate_script(_make_script(segments=[seg]))
        assert len(errors) > 0

    def test_invalid_component_format(self):
        seg = _make_segment(1, "body", "B", component="bad-format")
        _, errors = validate_script(_make_script(segments=[seg]))
        assert len(errors) > 0

    def test_unknown_component_schema(self):
        seg = _make_segment(1, "body", "B", component="unknown-schema.style")
        _, errors = validate_script(_make_script(segments=[seg]))
        assert len(errors) > 0

    def test_material_a_missing_slide_content(self):
        seg = _make_segment(1, "body", "A")
        del seg["slide_content"]
        _, errors = validate_script(_make_script(segments=[seg]))
        assert len(errors) > 0

    def test_social_card_component_requires_social_card_data(self):
        seg = _make_segment(1, "body", "A", component="social-card.default")
        _, errors = validate_script(_make_script(segments=[seg]))
        assert len(errors) > 0
        assert any("social-card" in e or "social_card" in e for e in errors)

    def test_social_card_component_with_social_card_data(self):
        seg = _make_segment(
            1,
            "body",
            "A",
            component="social-card.default",
            social_card={
                "platform": "twitter",
                "author": "@test",
                "text": "hello",
            },
        )
        data, errors = validate_script(_make_script(segments=[seg]))
        assert errors == []
        assert data.segments[0].social_card.platform == "twitter"

    def test_material_b_missing_session_and_instruction(self):
        seg = _make_segment(1, "body", "B")
        del seg["terminal_session"]
        _, errors = validate_script(_make_script(segments=[seg]))
        assert len(errors) > 0

    def test_material_c_invalid_time_range(self):
        seg = _make_segment(1, "body", "C", source_start=10.0, source_end=5.0)
        _, errors = validate_script(_make_script(segments=[seg]))
        assert len(errors) > 0

    def test_extra_fields_ignored(self):
        """额外字段不报错（ConfigDict extra='ignore'）。"""
        seg = _make_segment(1, "body", "A", unknown_field="should be ignored")
        data, errors = validate_script(_make_script(segments=[seg]))
        assert errors == []
