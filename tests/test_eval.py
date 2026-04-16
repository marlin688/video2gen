"""eval.py 纯函数测试：验证质量评估规则和分级逻辑。"""

import pytest

from v2g.eval import eval_script, eval_score_pct, get_blocking_warnings


# ── 辅助工厂 ─────────────────────────────────────────────────


def _seg(id, type="body", material="A", narration_zh="这是一段测试旁白内容，足够长度。", **kw):
    base = {
        "id": id,
        "type": type,
        "material": material,
        "narration_zh": narration_zh,
    }
    if material == "A" and "slide_content" not in kw and "component" not in kw:
        base["slide_content"] = {"title": f"标题{id}", "bullet_points": ["要点"]}
    if material == "B" and "terminal_session" not in kw and "component" not in kw:
        base["terminal_session"] = [{"type": "input", "text": "echo test"}]
    if material == "C":
        base.setdefault("source_start", 0.0)
        base.setdefault("source_end", 5.0)
    base.update(kw)
    return base


def _golden_script():
    """一个满分脚本模板：10 段，intro/outro 结构，A/B 交替，字数适中（总字数 >400）。"""
    return {
        "title": "AI 工具测评",
        "description": "深度测评 5 款 AI 编程助手",
        "tags": ["ai", "coding", "tools", "review"],
        "segments": [
            _seg(1, "intro", "C", "你有没有想过，为什么现在 AI 编程助手越来越多，市面上已经有几十款产品，但真正好用的却很少？今天我们就来深度测评五款主流工具。"),
            _seg(
                2,
                "body",
                "A",
                "首先来看第一款工具 Cursor，它的核心优势在于代码补全的准确率非常高，在我们的测试中达到了百分之八十五的首次通过率。",
                component="image-overlay.default",
                image_content={
                    "image_path": "",
                    "source_method": "search",
                    "source_query": "Cursor IDE code completion screenshot",
                    "overlay_text": "Cursor 实测",
                },
            ),
            _seg(3, "body", "B", "让我们实际演示一下 Cursor 的核心功能，看看它在真实项目中处理复杂重构任务时的表现究竟如何。"),
            _seg(
                4,
                "body",
                "C",
                "第二款工具 Copilot 走的是完全不同的路线，它更注重代码理解和重构能力，对大型代码库的支持也更好。",
                component="web-video.default",
                web_video={
                    "search_query": "GitHub Copilot demo coding workflow",
                    "overlay_text": "Copilot 演示",
                    "fallback_component": "slide.tech-dark",
                },
            ),
            _seg(5, "body", "B", "同样的测试场景下，Copilot 给出了完全不同的解决方案，我们来对比看看两种方案各自的优劣势。"),
            _seg(6, "body", "C", "从原始测评视频中可以看到，两款工具在响应速度和补全质量上的性能差异非常明显。"),
            _seg(7, "body", "A", "综合对比这五款工具之后，可以发现每款都有自己的最佳适用场景，没有一个万能的解决方案。"),
            _seg(8, "body", "B", "最后我们用一个完整的全栈项目来做端到端测试，模拟真实的日常开发工作流程。"),
            _seg(9, "body", "A", "测试结果的数据汇总如下，从补全速度、准确率和用户体验三个维度来逐项分析比较。"),
            _seg(10, "outro", "A", "以上就是本期五款 AI 编程工具深度测评的全部内容，如果觉得有帮助请点赞关注，我会持续更新更多工具评测！"),
        ],
    }


# ── 满分脚本测试 ─────────────────────────────────────────────


class TestGoldenScript:
    def test_passes_all_checks(self):
        report = eval_script(_golden_script(), "test")
        pct = eval_score_pct(report)
        assert pct >= 90
        assert report["has_critical"] is False

    def test_no_warning_or_critical(self):
        report = eval_script(_golden_script(), "test")
        assert len(report["critical_failed"]) == 0
        assert len(report["warning_failed"]) == 0


# ── 分级逻辑测试 ─────────────────────────────────────────────


class TestGrading:
    def test_critical_on_bad_json(self):
        """空 segments 触发 schema 错误 → critical。"""
        report = eval_script({"title": "t", "description": "d", "tags": ["a", "b", "c"]}, "test")
        assert report["has_critical"] is True
        critical_names = [c["name"] for c in report["critical_failed"]]
        assert "JSON 结构合法" in critical_names

    def test_warning_on_material_ratio(self):
        """全 A 段 → A素材 40-60% 失败 (weight=2 → warning)。"""
        segments = [
            _seg(1, "intro", "A", "开场白。" * 5),
            *[_seg(i, "body", "A", f"第{i}段测试旁白。" * 3) for i in range(2, 10)],
            _seg(10, "outro", "A", "结尾内容。" * 5),
        ]
        script = {
            "title": "t", "description": "d", "tags": ["a", "b", "c"],
            "segments": segments,
        }
        report = eval_script(script, "test")
        warning_names = [c["name"] for c in report["warning_failed"]]
        assert "A素材 40-60%" in warning_names
        assert "B素材 ≥20%" in warning_names

    def test_info_on_missing_outro(self):
        """无 outro → weight=1 → info 级别。"""
        segments = [
            _seg(1, "intro", "A", "开场白内容。" * 5),
            *[_seg(i, "body", m, f"第{i}段内容。" * 3)
              for i, m in zip(range(2, 10), ["A", "B"] * 4)],
            _seg(10, "body", "A", "结尾内容。" * 5),  # type=body 而非 outro
        ]
        script = {
            "title": "t", "description": "d", "tags": ["a", "b", "c"],
            "segments": segments,
        }
        report = eval_script(script, "test")
        info_names = [c["name"] for c in report["info_failed"]]
        assert "有 outro 段" in info_names
        # outro 缺失是 info，不是 critical
        assert report["has_critical"] is False

    def test_has_critical_false_on_warnings_only(self):
        """只有 warning 没有 critical 时 has_critical 应为 False。"""
        segments = [
            _seg(1, "intro", "A", "开场白内容内容。" * 3),
            *[_seg(i, "body", "A", f"第{i}段内容。" * 3) for i in range(2, 10)],
            _seg(10, "outro", "A", "结尾内容内容。" * 3),
        ]
        script = {
            "title": "t", "description": "d", "tags": ["a", "b", "c"],
            "segments": segments,
        }
        report = eval_script(script, "test")
        # 全 A 段会有 material ratio warning，但 JSON 结构合法 → 无 critical
        assert report["has_critical"] is False


# ── 边界条件 ─────────────────────────────────────────────────


class TestEdgeCases:
    def test_boring_opening(self):
        """套话开头应被检测到。"""
        script = _golden_script()
        script["segments"][0]["narration_zh"] = "大家好，今天来看一下 AI 工具。"
        report = eval_script(script, "test")
        failed_names = [c["name"] for c in report["checks"] if not c["passed"]]
        assert "开头不套话" in failed_names

    def test_too_few_segments(self):
        segments = [_seg(i, "body", "A", "测试内容。" * 10) for i in range(1, 4)]
        script = {"title": "t", "description": "d", "tags": ["a", "b", "c"], "segments": segments}
        report = eval_script(script, "test")
        failed_names = [c["name"] for c in report["checks"] if not c["passed"]]
        assert "段落数 6-25" in failed_names

    def test_c_segment_over_10s(self):
        script = _golden_script()
        script["segments"][5]["source_end"] = 20.0  # C 段 20s > 10s
        report = eval_script(script, "test")
        failed_names = [c["name"] for c in report["checks"] if not c["passed"]]
        assert "C段 ≤10秒" in failed_names

    def test_score_percentage(self):
        report = eval_script(_golden_script(), "test")
        pct = eval_score_pct(report)
        assert 0 <= pct <= 100
        assert pct == report["score"] / report["max_score"] * 100


class TestTutorialDepthChecks:
    def test_tutorial_missing_depth_rules_raise_warnings(self):
        """教程类脚本缺失深度信息应触发新增 warning。"""
        script = {
            "title": "Claude Code + Obsidian 教程",
            "description": "从零搭建工作流",
            "tags": ["Claude Code", "Obsidian", "教程"],
            "segments": [
                _seg(1, "intro", "A", "今天我们快速搭一个工作流。"),
                _seg(2, "body", "B", "先执行命令搭建目录结构。",
                     recording_instruction="1. 创建目录 2. 写配置",
                     terminal_session=[{"type": "input", "text": "mkdir vault"}]),
                _seg(3, "body", "A", "接着把配置拆成模板。"),
                _seg(4, "body", "B", "再跑一次自动化流程。",
                     recording_instruction="1. 运行命令",
                     terminal_session=[{"type": "input", "text": "claude run"}]),
                _seg(5, "body", "A", "最后优化一下流程。"),
                _seg(6, "outro", "A", "这套流程你照着做就行。"),
            ],
        }

        report = eval_script(script, "tutorial")
        warning_names = [c["name"] for c in report["warning_failed"]]
        assert "教程含踩坑修复" in warning_names
        assert "教程含前置条件/版本" in warning_names
        assert "outro有可执行交付" in warning_names

        blocking_names = [c["name"] for c in get_blocking_warnings(report)]
        assert "教程含踩坑修复" in blocking_names


class TestBlockingWarningsByProfile:
    def test_commentary_does_not_block_material_alternation(self):
        script = {
            "title": "AI 热点评",
            "description": "讨论最近的 AI 概念泡沫",
            "tags": ["ai", "commentary", "market"],
            "segments": [
                _seg(1, "intro", "A", "开头内容。" * 8),
                _seg(2, "body", "B", "第二段内容。" * 6),
                _seg(3, "body", "B", "第三段内容。" * 6),
                _seg(4, "body", "A", "第四段内容。" * 6),
                _seg(5, "body", "A", "第五段内容。" * 6),
                _seg(6, "body", "B", "第六段内容。" * 6),
                _seg(7, "body", "B", "第七段内容。" * 6),
                _seg(8, "outro", "A", "收尾内容。" * 8),
            ],
        }

        report = eval_script(script, "commentary", quality_profile="commentary")
        failed_names = [c["name"] for c in report["warning_failed"]]
        assert "素材类型交替" in failed_names
        assert "body段 A/B 交替" in failed_names

        blocking_names = [c["name"] for c in get_blocking_warnings(report)]
        assert "素材类型交替" not in blocking_names
        assert "body段 A/B 交替" not in blocking_names

    def test_commentary_does_not_block_consecutive_schema(self):
        report = {
            "quality_profile": "commentary",
            "warning_failed": [
                {"name": "无连续相同 schema"},
                {"name": "视觉 schema 多样性"},
            ],
        }
        blocking_names = [c["name"] for c in get_blocking_warnings(report)]
        assert "无连续相同 schema" not in blocking_names
        assert "视觉 schema 多样性" in blocking_names


def test_eval_flags_component_material_mismatch():
    script = {
        "title": "AI 热点评",
        "description": "测试 component/material 错位",
        "tags": ["ai", "commentary", "market"],
        "segments": [
            _seg(1, "intro", "A", "开场内容。" * 8),
            _seg(
                2,
                "body",
                "B",
                "这里应该是配图段。" * 6,
                component="image-overlay.default",
                image_content={"image_path": "", "source_method": "search", "source_query": "Claude pricing"},
            ),
            _seg(
                3,
                "body",
                "B",
                "这里应该是动态视频段。" * 6,
                component="web-video.default",
                web_video={"search_query": "AI coding demo", "fallback_component": "slide.tech-dark"},
            ),
            _seg(4, "outro", "A", "收尾内容。" * 8),
        ],
    }
    report = eval_script(script, "commentary", quality_profile="commentary")
    failed_names = [c["name"] for c in report["warning_failed"]]
    assert "组件与素材语义一致" in failed_names
    blocking_names = [c["name"] for c in get_blocking_warnings(report)]
    assert "组件与素材语义一致" in blocking_names
