"""脚本质量评估：规则化检查 script.json，不依赖 LLM。"""

import json
from pathlib import Path

import click

from v2g.config import Config


def eval_script(script: dict, video_id: str = "") -> dict:
    """评估脚本质量（纯函数版，接受 dict），返回评分报告。

    可在脚本生成后立即调用，无需写入文件。
    先做 Pydantic 结构验证，再做业务规则检查。
    """
    segments = script.get("segments", [])

    report = {
        "video_id": video_id,
        "checks": [],
        "score": 0,
        "max_score": 0,
        "schema_errors": [],  # Pydantic 结构验证错误
    }

    # ── Schema 结构验证 (Pydantic) ──
    from v2g.schema import validate_script
    _parsed, schema_errors = validate_script(script)
    report["schema_errors"] = schema_errors

    def check(name: str, passed: bool, weight: int = 1, detail: str = ""):
        report["checks"].append({
            "name": name,
            "passed": passed,
            "weight": weight,
            "detail": detail,
        })
        report["max_score"] += weight
        if passed:
            report["score"] += weight

    # --- Schema 结构验证 ---
    check("JSON 结构合法", len(schema_errors) == 0, weight=3,
          detail=f"{len(schema_errors)} 个结构错误" if schema_errors else "")

    # --- 基础结构 ---
    check("有标题", bool(script.get("title")))
    check("有描述", bool(script.get("description")))
    check("有标签", len(script.get("tags", [])) >= 3, detail=f"{len(script.get('tags', []))} 个标签")

    # --- 段落数量 ---
    seg_count = len(segments)
    check("段落数 8-12", 8 <= seg_count <= 12, weight=2, detail=f"{seg_count} 段")

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
        if chars > 120:
            long_segs += 1

    check("总字数 400-1000", 400 <= total_chars <= 1000, weight=2, detail=f"{total_chars} 字")
    check("无过短段落 (<20字)", short_segs == 0, detail=f"{short_segs} 段过短")
    check("无过长段落 (>120字)", long_segs == 0, detail=f"{long_segs} 段过长")

    # --- 开头质量 ---
    if segments:
        first = segments[0]
        first_narration = first.get("narration_zh", "")
        boring_starts = ["大家好", "今天我们", "欢迎来到", "hello", "hi大家"]
        has_boring_start = any(first_narration.startswith(b) for b in boring_starts)
        check("开头不套话", not has_boring_start, weight=2,
              detail=f"开头: {first_narration[:30]}...")

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
    check("素材类型交替", consecutive <= 2, detail=f"{consecutive} 处连续相同素材")

    # --- 视觉 schema 多样性 ---
    def _seg_schema(seg: dict) -> str:
        comp = seg.get("component")
        if comp:
            return comp.split(".")[0]
        mat = seg.get("material", "A")
        return {"A": "slide", "B": "terminal", "C": "source-clip"}.get(mat, mat)

    schemas_used = {_seg_schema(s) for s in segments}
    check("视觉 schema 多样性", len(schemas_used) >= 3, weight=1,
          detail=f"使用了 {len(schemas_used)} 种 schema: {sorted(schemas_used)}")

    consecutive_schema = 0
    prev_schema = None
    for seg in segments:
        cur = _seg_schema(seg)
        if cur == prev_schema:
            consecutive_schema += 1
        prev_schema = cur
    check("无连续相同 schema", consecutive_schema <= 1, weight=1,
          detail=f"{consecutive_schema} 处连续相同 schema")

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
        check("body段 A/B 交替", alt_ratio >= 0.5, weight=2,
              detail=f"{alternations}/{len(body_materials)-1} 次交替 ({alt_ratio:.0%})")

    # --- 段间钩子检查 ---
    flat_endings = 0
    for seg in segments:
        if seg.get("type") != "body":
            continue
        narration = seg.get("narration_zh", "").rstrip()
        if narration and not any(narration.endswith(c) for c in ("？", "。", "！", "…", "——")):
            flat_endings += 1
    check("段落有结尾标点", flat_endings <= 1, detail=f"{flat_endings} 段缺结尾标点")

    # --- 高级组件使用 ---
    component_count = sum(1 for s in segments if s.get("component"))
    check("使用高级组件 (0-3)", component_count <= 3,
          detail=f"{component_count} 个高级组件")

    # --- 按 weight 分级汇总 ---
    critical_failed = [c for c in report["checks"] if not c["passed"] and c["weight"] >= 3]
    warning_failed = [c for c in report["checks"] if not c["passed"] and c["weight"] == 2]
    info_failed = [c for c in report["checks"] if not c["passed"] and c["weight"] <= 1]

    report["critical_failed"] = critical_failed
    report["warning_failed"] = warning_failed
    report["info_failed"] = info_failed
    report["has_critical"] = len(critical_failed) > 0

    return report


def eval_score_pct(report: dict) -> float:
    """从 report 中计算百分比得分 (0-100)。"""
    return report["score"] / max(report["max_score"], 1) * 100


def run_eval(cfg: Config, video_id: str) -> dict:
    """从文件评估 script.json 质量，返回评分报告。"""
    output_dir = cfg.output_dir / video_id
    script_path = output_dir / "script.json"
    if not script_path.exists():
        raise click.ClickException(f"脚本不存在: {script_path}")

    script = json.loads(script_path.read_text(encoding="utf-8"))
    report = eval_script(script, video_id)

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

    click.echo(f"\n📋 脚本质量评估: {report['video_id']}")
    click.echo(f"   总分: {score}/{max_score} ({pct:.0f}%)")

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
