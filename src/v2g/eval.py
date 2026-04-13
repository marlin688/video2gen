"""脚本质量评估：规则化检查 script.json，不依赖 LLM。"""

import json
import math
import re
from pathlib import Path

import click

from v2g.config import Config
from v2g.quality_profile import resolve_quality_profile


BLOCKING_WARNING_NAMES = frozenset({
    "A素材 40-60%",
    "B素材 ≥20%",
    "总字数 400-5000",
    "开头不套话",
    "B段有 terminal_session",
    "素材类型交替",
    "视觉 schema 多样性",
    "无连续相同 schema",
    "无重复段落",
    "body段 A/B 交替",
    "教程可复现闭环",
    "教程含踩坑修复",
    "教程含前置条件/版本",
    "教程有适用边界对比",
    "教程高级组件≥2",
    "outro有可执行交付",
})


def get_blocking_warnings(report: dict) -> list[dict]:
    """返回会阻断质量门控的 warning 项。"""
    return [
        c for c in report.get("warning_failed", [])
        if c.get("name") in BLOCKING_WARNING_NAMES
    ]


def _segment_text(seg: dict) -> str:
    parts: list[str] = []
    for k in ("narration_zh", "recording_instruction", "notes", "component"):
        v = seg.get(k)
        if isinstance(v, str):
            parts.append(v)
    sc = seg.get("slide_content")
    if isinstance(sc, dict):
        title = sc.get("title")
        if isinstance(title, str):
            parts.append(title)
        chart_hint = sc.get("chart_hint")
        if isinstance(chart_hint, str):
            parts.append(chart_hint)
        bullets = sc.get("bullet_points")
        if isinstance(bullets, list):
            parts.extend(str(x) for x in bullets if isinstance(x, str))
    session = seg.get("terminal_session")
    if isinstance(session, list):
        for step in session:
            if not isinstance(step, dict):
                continue
            for k in ("text", "name", "target", "result"):
                v = step.get(k)
                if isinstance(v, str):
                    parts.append(v)
            lines = step.get("lines")
            if isinstance(lines, list):
                parts.extend(str(x) for x in lines if isinstance(x, str))
    return "\n".join(parts)


def _is_tutorial_script(script: dict, segments: list[dict], profile: dict) -> bool:
    """判断是否启用教程类检查规则。

    优先看 profile 的 content_type：
    - "tutorial" → 强制启用
    - "commentary" / "news" / "brand" → 强制关闭
    - "auto" → 用关键词猜测（仅 default profile）
    """
    content_type = profile.get("content_type", "auto")

    if content_type == "tutorial":
        return True
    if content_type in ("commentary", "news", "brand"):
        return False

    # auto: 关键词猜测（向后兼容）
    b_count = sum(1 for s in segments if s.get("material") == "B")
    if b_count < 2:
        return False

    text_parts: list[str] = []
    for k in ("title", "description"):
        v = script.get(k)
        if isinstance(v, str):
            text_parts.append(v.lower())
    text_parts.extend(str(t).lower() for t in script.get("tags", []) if isinstance(t, str))
    joined = "\n".join(text_parts)

    tutorial_signals = (
        "教程", "技巧", "实战", "上手", "工作流", "避坑", "配置",
    )
    return any(sig in joined for sig in tutorial_signals)


def eval_script(
    script: dict,
    video_id: str = "",
    quality_profile: str = "default",
    assets_db_path: Path | None = None,
) -> dict:
    """评估脚本质量（纯函数版，接受 dict），返回评分报告。

    可在脚本生成后立即调用，无需写入文件。
    先做 Pydantic 结构验证，再做业务规则检查。
    """
    segments = script.get("segments", [])

    profile = resolve_quality_profile(quality_profile)

    report = {
        "video_id": video_id,
        "quality_profile": profile["name"],
        "quality_profile_label": profile["label"],
        "quality_profile_weights": profile["weights"],
        "checks": [],
        "score": 0,
        "max_score": 0,
        "objective_score": 0,
        "objective_max_score": 0,
        "subjective_score": 0,
        "subjective_max_score": 0,
        "schema_errors": [],  # Pydantic 结构验证错误
    }

    # ── Schema 结构验证 (Pydantic) ──
    from v2g.schema import validate_script
    _parsed, schema_errors = validate_script(script)
    report["schema_errors"] = schema_errors

    def check(
        name: str,
        passed: bool,
        weight: int = 1,
        detail: str = "",
        category: str = "objective",
    ):
        if category not in {"objective", "subjective"}:
            category = "objective"
        report["checks"].append({
            "name": name,
            "passed": passed,
            "weight": weight,
            "detail": detail,
            "category": category,
        })
        report["max_score"] += weight
        if category == "subjective":
            report["subjective_max_score"] += weight
        else:
            report["objective_max_score"] += weight
        if passed:
            report["score"] += weight
            if category == "subjective":
                report["subjective_score"] += weight
            else:
                report["objective_score"] += weight

    # --- Schema 结构验证 ---
    check("JSON 结构合法", len(schema_errors) == 0, weight=3,
          detail=f"{len(schema_errors)} 个结构错误" if schema_errors else "")

    # --- 基础结构 ---
    check("有标题", bool(script.get("title")))
    check("有描述", bool(script.get("description")))
    check("有标签", len(script.get("tags", [])) >= 3, detail=f"{len(script.get('tags', []))} 个标签")

    # --- 段落数量 ---
    seg_count = len(segments)
    check("段落数 6-25", 6 <= seg_count <= 25, weight=2, detail=f"{seg_count} 段")

    # --- 素材分配 ---
    a_count = sum(1 for s in segments if s.get("material") == "A")
    b_count = sum(1 for s in segments if s.get("material") == "B")
    c_count = sum(1 for s in segments if s.get("material") == "C")

    a_ratio = a_count / max(seg_count, 1)
    b_ratio = b_count / max(seg_count, 1)

    check("A素材 40-60%", 0.35 <= a_ratio <= 0.65, weight=2,
          detail=f"A={a_count}/{seg_count} ({a_ratio:.0%})")
    check("B素材 ≥20%", b_ratio >= 0.15, weight=2,
          detail=f"B={b_count}/{seg_count} ({b_ratio:.0%})")
    check("C素材可选", True, detail=f"C={c_count}/{seg_count}")

    # --- 解说词质量 ---
    total_chars = 0
    short_segs = 0
    long_segs = 0
    for seg in segments:
        narration = seg.get("narration_zh", "")
        chars = len(narration)
        total_chars += chars
        if chars < 20:
            short_segs += 1
        if chars > 250:
            long_segs += 1

    check("总字数 400-5000", 400 <= total_chars <= 5000, weight=2, detail=f"{total_chars} 字")
    check("无过短段落 (<20字)", short_segs == 0, detail=f"{short_segs} 段过短")
    check("无过长段落 (>250字)", long_segs == 0, detail=f"{long_segs} 段过长")

    # --- 开头质量 ---
    if segments:
        first = segments[0]
        first_narration = first.get("narration_zh", "")
        boring_starts = ["大家好", "今天我们", "欢迎来到", "hello", "hi大家"]
        has_boring_start = any(first_narration.startswith(b) for b in boring_starts)
        check(
            "开头不套话",
            not has_boring_start,
            weight=2,
            detail=f"开头: {first_narration[:30]}...",
            category="subjective",
        )
    else:
        check("开头不套话", True, weight=2, detail="无段落", category="subjective")

    # --- B 段 terminal_session ---
    # 使用高级组件（如 code-block）的 B 段不需要 terminal_session
    b_need_session = sum(
        1 for s in segments
        if s.get("material") == "B" and not s.get("component")
    )
    b_with_session = sum(
        1 for s in segments
        if s.get("material") == "B" and not s.get("component") and s.get("terminal_session")
    )
    check("B段有 terminal_session", b_with_session == b_need_session, weight=2,
          detail=f"{b_with_session}/{b_need_session} 段有结构化会话")

    # --- A 段 slide_content ---
    # 使用高级组件（如 hero-stat/diagram）的 A 段不需要 slide_content
    a_need_content = sum(
        1 for s in segments
        if s.get("material") == "A" and not s.get("component")
    )
    a_with_content = sum(
        1 for s in segments
        if s.get("material") == "A" and not s.get("component")
        and s.get("slide_content", {}).get("bullet_points")
    )
    check("A段有 slide_content", a_with_content == a_need_content,
          detail=f"{a_with_content}/{a_need_content} 段有卡片内容")

    # --- C 段时间限制 ---
    c_over_10s = 0
    for seg in segments:
        if seg.get("material") == "C":
            duration = (seg.get("source_end", 0) - seg.get("source_start", 0))
            if duration > 10:
                c_over_10s += 1
    check("C段 ≤10秒", c_over_10s == 0, detail=f"{c_over_10s} 段超时")

    # --- 素材类型不连续 ---
    consecutive = 0
    for i in range(1, len(segments)):
        if segments[i].get("material") == segments[i - 1].get("material"):
            consecutive += 1
    check(
        "素材类型交替",
        consecutive <= 2,
        weight=2,
        detail=f"{consecutive} 处连续相同素材",
        category="subjective",
    )

    # --- 视觉 schema 多样性 ---
    def _seg_schema(seg: dict) -> str:
        comp = seg.get("component")
        if comp:
            return comp.split(".")[0]
        mat = seg.get("material", "A")
        return {"A": "slide", "B": "terminal", "C": "source-clip"}.get(mat, mat)

    schemas_used = {_seg_schema(s) for s in segments}
    check(
        "视觉 schema 多样性",
        len(schemas_used) >= (
            4 if profile.get("content_type") == "tutorial"
            else 2 if profile.get("content_type") == "brand"
            else 3
        ),
        weight=2,
        detail=(
            f"使用了 {len(schemas_used)} 种 schema: {sorted(schemas_used)}"
            f"（要求 ≥{4 if profile.get('content_type') == 'tutorial' else 2 if profile.get('content_type') == 'brand' else 3}）"
        ),
        category="objective",
    )

    # --- 显式 component 覆盖率 ---
    a_segs = [s for s in segments if s.get("material") == "A"]
    a_with_component = [s for s in a_segs if s.get("component")]
    if a_segs:
        coverage = len(a_with_component) / len(a_segs)
        check(
            "A素材段显式指定component",
            coverage >= 0.8,
            weight=2 if profile.get("content_type") == "tutorial" else 1,
            detail=f"{len(a_with_component)}/{len(a_segs)} 个 A 段有 component ({coverage:.0%})",
            category="objective",
        )

    # --- image-overlay 使用提醒 ---
    image_overlay_count = sum(
        1 for s in segments
        if (s.get("component", "").startswith("image-overlay") or s.get("image_content"))
    )
    check(
        "配图丰富度(image-overlay)",
        image_overlay_count >= 1,
        weight=1,
        detail=f"当前 {image_overlay_count} 个 image-overlay 段落（建议 2-4 个，用截图/搜图增强视觉）",
        category="subjective",
    )

    consecutive_schema = 0
    prev_schema = None
    for seg in segments:
        cur = _seg_schema(seg)
        if cur == prev_schema:
            consecutive_schema += 1
        prev_schema = cur
    check(
        "无连续相同 schema",
        consecutive_schema <= 1,
        weight=2,
        detail=f"{consecutive_schema} 处连续相同 schema",
        category="subjective",
    )

    # --- 内容去重检查 ---
    from difflib import SequenceMatcher
    duplicate_pairs = 0
    for i in range(len(segments)):
        for j in range(i + 1, len(segments)):
            narr_i = segments[i].get("narration_zh", "")
            narr_j = segments[j].get("narration_zh", "")
            if len(narr_i) > 20 and len(narr_j) > 20:
                ratio = SequenceMatcher(None, narr_i, narr_j).ratio()
                if ratio > 0.4:
                    duplicate_pairs += 1
    check(
        "无重复段落",
        duplicate_pairs == 0,
        weight=2,
        detail=f"{duplicate_pairs} 对段落内容高度相似",
        category="subjective",
    )

    # --- 脚本结构 (intro/body/outro) ---
    types = [s.get("type", "") for s in segments]
    has_intro = "intro" in types
    has_outro = "outro" in types
    check("有 intro 段", has_intro, weight=2)
    check("有 outro 段", has_outro, weight=1)

    # intro 在前、outro 在后
    if has_intro and has_outro:
        intro_idx = types.index("intro")
        outro_idx = len(types) - 1 - types[::-1].index("outro")
        check("结构顺序正确", intro_idx < outro_idx, detail="intro 在前, outro 在后")

    # body 段用 A→B 交替（统计主体段的 A/B 交替比例）
    body_materials = [s.get("material") for s in segments if s.get("type") == "body"]
    if len(body_materials) >= 4:
        alternations = sum(
            1 for i in range(1, len(body_materials))
            if body_materials[i] != body_materials[i - 1]
        )
        alt_ratio = alternations / max(len(body_materials) - 1, 1)
        check(
            "body段 A/B 交替",
            alt_ratio >= 0.5,
            weight=2,
            detail=f"{alternations}/{len(body_materials)-1} 次交替 ({alt_ratio:.0%})",
            category="subjective",
        )

    # --- 段间钩子检查 ---
    flat_endings = 0
    for seg in segments:
        if seg.get("type") != "body":
            continue
        narration = seg.get("narration_zh", "").rstrip()
        if narration and not any(narration.endswith(c) for c in ("？", "。", "！", "…", "——")):
            flat_endings += 1
    check(
        "段落有结尾标点",
        flat_endings <= 1,
        detail=f"{flat_endings} 段缺结尾标点",
        category="subjective",
    )

    # --- 高级组件使用 ---
    component_count = sum(1 for s in segments if s.get("component"))
    check("使用高级组件 (0-4)", component_count <= 4,
          detail=f"{component_count} 个高级组件")

    # --- 教程型脚本深度检查 ---
    if _is_tutorial_script(script, segments, profile):
        seg_texts = [_segment_text(s) for s in segments]

        # 1) 可复现闭环：B 段应具备「指令 + 可见输出」
        b_total = 0
        b_closed_loop = 0
        for seg in segments:
            if seg.get("material") != "B":
                continue
            b_total += 1
            rec = seg.get("recording_instruction")
            has_instruction = isinstance(rec, str) and bool(rec.strip())
            session = seg.get("terminal_session")
            has_input = False
            has_observable = False
            if isinstance(session, list):
                for step in session:
                    if not isinstance(step, dict):
                        continue
                    step_type = step.get("type")
                    if step_type == "input":
                        has_input = True
                    if step_type in {"output", "status", "tool"}:
                        if step.get("text") or step.get("result"):
                            has_observable = True
                        lines = step.get("lines")
                        if isinstance(lines, list) and len(lines) > 0:
                            has_observable = True
            if has_instruction and has_input and has_observable:
                b_closed_loop += 1

        need_closed_loop = max(1, math.ceil(b_total * 0.7)) if b_total else 0
        check(
            "教程可复现闭环",
            b_total == 0 or b_closed_loop >= need_closed_loop,
            weight=2,
            detail=f"{b_closed_loop}/{b_total} 段含输入→输出闭环",
            category="subjective",
        )

        # 2) 踩坑覆盖：至少 2 段提到问题与修复
        pitfall_kw = ("踩坑", "报错", "失败", "问题", "陷阱", "排查", "修复", "避坑", "卡住")
        pitfall_segments = sum(
            1 for text in seg_texts
            if any(kw in text for kw in pitfall_kw)
        )
        check(
            "教程含踩坑修复",
            pitfall_segments >= 2,
            weight=2,
            detail=f"{pitfall_segments} 段提到问题/修复",
            category="subjective",
        )

        # 3) 前置条件与版本：至少 1 段含版本号或环境前置
        env_kw = (
            "版本", "前置", "依赖", "环境", "mac", "windows", "linux",
            "python", "node", "npm", "pip", "conda", "ollama", "api key",
        )
        ver_re = re.compile(r"\bv?\d+\.\d+(?:\.\d+)?\b", re.IGNORECASE)
        precondition_segments = sum(
            1 for text in seg_texts
            if ver_re.search(text) or any(kw in text.lower() for kw in env_kw)
        )
        check(
            "教程含前置条件/版本",
            precondition_segments >= 1,
            weight=2,
            detail=f"{precondition_segments} 段含版本/环境信息",
            category="subjective",
        )

        # 4) 适用边界与对比：至少 1 段明确场景边界
        boundary_kw = ("vs", "对比", "适用", "不适用", "边界", "取舍", "场景", "不建议")
        boundary_segments = sum(
            1 for text in seg_texts
            if any(kw in text.lower() for kw in boundary_kw)
        )
        check(
            "教程有适用边界对比",
            boundary_segments >= 1,
            weight=2,
            detail=f"{boundary_segments} 段含适用边界/对比",
            category="subjective",
        )

        # 5) 高级组件：教程类至少 2 个高级组件
        check(
            "教程高级组件≥2",
            component_count >= 2,
            weight=2,
            detail=f"{component_count} 个高级组件",
            category="subjective",
        )

        # 6) 结尾交付：outro 至少有文件、命令、验证检查点
        outro_text = "\n".join(
            _segment_text(seg) for seg in segments if seg.get("type") == "outro"
        )
        file_re = re.compile(
            r"\b[\w./-]+\.(?:md|json|ya?ml|toml|env|txt|py|ts|tsx|js|sh)\b",
            re.IGNORECASE,
        )
        command_re = re.compile(
            r"(?:^|[\s`])(git|npm|pnpm|yarn|python|pip|uv|node|npx|claude|code)\b",
            re.IGNORECASE,
        )
        checkpoint_kw = ("看到", "确认", "检查", "验证", "输出", "出现", "通过")
        has_file = bool(file_re.search(outro_text))
        has_command = bool(command_re.search(outro_text))
        has_checkpoint = any(kw in outro_text for kw in checkpoint_kw)
        check(
            "outro有可执行交付",
            has_file and has_command and has_checkpoint,
            weight=2,
            detail=f"文件={has_file}, 命令={has_command}, 检查点={has_checkpoint}",
            category="subjective",
        )

    # --- scene_data 字段名正确性 ---
    from v2g.scene_data_validator import validate_and_fix_scene_data
    _, sd_warnings = validate_and_fix_scene_data(script, auto_fix=False)
    check("scene_data字段名正确", len(sd_warnings) == 0, weight=3,
          detail="; ".join(sd_warnings[:3]) if sd_warnings else "")

    # --- 历史 pattern 比对（info 级别，仅在有足够数据时触发） ---
    _add_historical_checks(report, script, check, assets_db_path=assets_db_path)

    # --- 按 weight 分级汇总 ---
    critical_failed = [c for c in report["checks"] if not c["passed"] and c["weight"] >= 3]
    warning_failed = [c for c in report["checks"] if not c["passed"] and c["weight"] == 2]
    info_failed = [c for c in report["checks"] if not c["passed"] and c["weight"] <= 1]

    report["critical_failed"] = critical_failed
    report["warning_failed"] = warning_failed
    report["info_failed"] = info_failed
    report["has_critical"] = len(critical_failed) > 0

    objective_pct = report["objective_score"] / max(report["objective_max_score"], 1) * 100
    subjective_pct = report["subjective_score"] / max(report["subjective_max_score"], 1) * 100
    w_obj = profile["weights"]["objective"]
    w_sub = profile["weights"]["subjective"]
    weighted_pct = objective_pct * w_obj + subjective_pct * w_sub
    report["objective_pct"] = objective_pct
    report["subjective_pct"] = subjective_pct
    report["weighted_pct"] = weighted_pct

    return report


def _add_historical_checks(
    report: dict,
    script: dict,
    check,
    assets_db_path: Path | None = None,
) -> None:
    """基于历史高表现视频数据添加 info 级别的 pattern 比对。

    只在 assets.db 有 ≥3 个有 stats+features 的视频时触发。
    所有检查为 info（weight=1），不影响 pass/fail 判定。
    """
    from pathlib import Path

    if assets_db_path is None:
        return

    db_path = Path(assets_db_path)
    if not db_path.exists():
        return

    try:
        from v2g.asset_store import AssetStore
        with AssetStore(db_path) as store:
            patterns = store.get_high_performing_patterns()
            if not patterns:
                return

            segments = script.get("segments", [])
            n = len(segments)
            if n == 0:
                return

            # 当前脚本特征
            materials = [s.get("material", "A") for s in segments]
            cur_b_ratio = materials.count("B") / n

            schemas = set()
            for seg in segments:
                comp = seg.get("component", "")
                if comp:
                    schemas.add(comp.split(".")[0])
                elif seg.get("terminal_session"):
                    schemas.add("terminal")
                elif seg.get("slide_content"):
                    schemas.add("slide")
            cur_diversity = len(schemas)

            narr_lens = [len(s.get("narration_zh", "") or "") for s in segments]
            cur_avg_narr = sum(narr_lens) / n if n else 0

            avg_b = patterns["avg_material_b"]
            avg_div = patterns["avg_schema_diversity"]
            avg_narr = patterns["avg_narration_len"]
            sample = patterns["sample_size"]

            # B 素材比例偏差
            if abs(cur_b_ratio - avg_b) > 0.15:
                check(
                    f"[历史] B素材比例偏离高表现均值",
                    False, weight=1,
                    detail=f"当前 {cur_b_ratio:.0%} vs 高表现视频均值 {avg_b:.0%} (n={sample})"
                )

            # Schema 多样性偏差
            if cur_diversity < avg_div - 1:
                check(
                    f"[历史] Schema多样性低于高表现均值",
                    False, weight=1,
                    detail=f"当前 {cur_diversity} 种 vs 高表现视频均值 {avg_div:.1f} 种 (n={sample})"
                )

            # 旁白密度偏差
            if cur_avg_narr > 0 and avg_narr > 0 and abs(cur_avg_narr - avg_narr) > 20:
                direction = "过长" if cur_avg_narr > avg_narr else "过短"
                check(
                    f"[历史] 旁白平均字数{direction}",
                    False, weight=1,
                    detail=f"当前 {cur_avg_narr:.0f} 字 vs 高表现视频均值 {avg_narr:.0f} 字 (n={sample})"
                )
    except Exception:
        pass  # 历史检查不应阻塞主流程


def eval_score_pct(report: dict, weighted: bool = False) -> float:
    """从 report 中计算百分比得分 (0-100)。

    默认返回原始规则分 (score/max_score) 以兼容历史调用方。
    weighted=True 时返回分层加权分（objective/subjective）。
    """
    raw_pct = report["score"] / max(report["max_score"], 1) * 100
    if weighted:
        return float(report.get("weighted_pct", raw_pct))
    return raw_pct


def run_eval(cfg: Config, video_id: str, quality_profile: str = "default") -> dict:
    """从文件评估 script.json 质量，返回评分报告。"""
    output_dir = cfg.output_dir / video_id
    script_path = output_dir / "script.json"
    if not script_path.exists():
        raise click.ClickException(f"脚本不存在: {script_path}")

    script = json.loads(script_path.read_text(encoding="utf-8"))
    report = eval_script(
        script,
        video_id,
        quality_profile=quality_profile,
        assets_db_path=cfg.output_dir / "assets.db",
    )

    # 附加元数据
    meta_path = output_dir / "script_meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        report["meta"] = meta

    return report


def print_eval_report(report: dict):
    """格式化输出评估报告（按 critical/warning/info 分级）。"""
    score = report["score"]
    max_score = report["max_score"]
    pct = score / max(max_score, 1) * 100
    weighted_pct = report.get("weighted_pct", pct)

    click.echo(f"\n📋 脚本质量评估: {report['video_id']}")
    click.echo(f"   规则分: {score}/{max_score} ({pct:.0f}%)")
    if "quality_profile" in report:
        click.echo(
            f"   档位: {report['quality_profile']} "
            f"(objective {report['quality_profile_weights']['objective']:.0%} / "
            f"subjective {report['quality_profile_weights']['subjective']:.0%})"
        )
    if "objective_pct" in report and "subjective_pct" in report:
        click.echo(
            f"   分层: objective {report['objective_pct']:.0f}% | "
            f"subjective {report['subjective_pct']:.0f}%"
        )
    click.echo(f"   综合分: {weighted_pct:.0f}%")

    # 按分级输出失败项
    critical_failed = report.get("critical_failed", [])
    warning_failed = report.get("warning_failed", [])
    info_failed = report.get("info_failed", [])

    if critical_failed:
        click.echo(f"\n   🔴 Critical ({len(critical_failed)}):")
        for c in critical_failed:
            detail = f" — {c['detail']}" if c.get("detail") else ""
            click.echo(f"      ❌ {c['name']} (×{c['weight']}){detail}")

    if warning_failed:
        click.echo(f"\n   🟡 Warning ({len(warning_failed)}):")
        for c in warning_failed:
            detail = f" — {c['detail']}" if c.get("detail") else ""
            click.echo(f"      ❌ {c['name']} (×{c['weight']}){detail}")

    if info_failed:
        click.echo(f"\n   ℹ️  Info ({len(info_failed)}):")
        for c in info_failed:
            detail = f" — {c['detail']}" if c.get("detail") else ""
            click.echo(f"      ❌ {c['name']}{detail}")

    passed_count = sum(1 for c in report["checks"] if c["passed"])
    if passed_count > 0:
        click.echo(f"\n   ✅ Passed: {passed_count} 项通过")

    # Schema 验证错误详情
    schema_errors = report.get("schema_errors", [])
    if schema_errors:
        click.echo(f"\n   🔴 结构验证错误 ({len(schema_errors)} 项):")
        for i, err in enumerate(schema_errors[:10], 1):
            click.echo(f"      {i}. {err}")
        if len(schema_errors) > 10:
            click.echo(f"      ... 还有 {len(schema_errors) - 10} 项")

    if "meta" in report:
        meta = report["meta"]
        click.echo(f"\n   📎 生成信息:")
        click.echo(f"      模型: {meta.get('model', '?')}")
        click.echo(f"      Prompt hash: {meta.get('prompt_hash', '?')}")
        click.echo(f"      时间: {meta.get('timestamp', '?')}")

    click.echo()
