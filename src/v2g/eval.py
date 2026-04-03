"""脚本质量评估：规则化检查 script.json，不依赖 LLM。"""

import json
from pathlib import Path

import click

from v2g.config import Config


def run_eval(cfg: Config, video_id: str) -> dict:
    """评估 script.json 质量，返回评分报告。"""
    output_dir = cfg.output_dir / video_id
    script_path = output_dir / "script.json"
    if not script_path.exists():
        raise click.ClickException(f"脚本不存在: {script_path}")

    script = json.loads(script_path.read_text(encoding="utf-8"))
    segments = script.get("segments", [])

    report = {
        "video_id": video_id,
        "checks": [],
        "score": 0,
        "max_score": 0,
    }

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

    check("A素材 ≤40%", a_ratio <= 0.45, weight=2, detail=f"A={a_count}/{seg_count} ({a_ratio:.0%})")
    check("B素材 ≥30%", b_ratio >= 0.25, weight=2, detail=f"B={b_count}/{seg_count} ({b_ratio:.0%})")
    check("C素材存在", c_count > 0, detail=f"C={c_count}/{seg_count}")

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
    b_with_session = sum(
        1 for s in segments
        if s.get("material") == "B" and s.get("terminal_session")
    )
    check("B段有 terminal_session", b_with_session == b_count, weight=2,
          detail=f"{b_with_session}/{b_count} 段有结构化会话")

    # --- A 段 slide_content ---
    a_with_content = sum(
        1 for s in segments
        if s.get("material") == "A" and s.get("slide_content", {}).get("bullet_points")
    )
    check("A段有 slide_content", a_with_content == a_count,
          detail=f"{a_with_content}/{a_count} 段有卡片内容")

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

    # --- 元数据 ---
    meta_path = output_dir / "script_meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        report["meta"] = meta

    return report


def print_eval_report(report: dict):
    """格式化输出评估报告。"""
    score = report["score"]
    max_score = report["max_score"]
    pct = score / max(max_score, 1) * 100

    click.echo(f"\n📋 脚本质量评估: {report['video_id']}")
    click.echo(f"   总分: {score}/{max_score} ({pct:.0f}%)\n")

    for c in report["checks"]:
        icon = "✅" if c["passed"] else "❌"
        detail = f" — {c['detail']}" if c.get("detail") else ""
        weight = f" (×{c['weight']})" if c["weight"] > 1 else ""
        click.echo(f"   {icon} {c['name']}{weight}{detail}")

    if "meta" in report:
        meta = report["meta"]
        click.echo(f"\n   📎 生成信息:")
        click.echo(f"      模型: {meta.get('model', '?')}")
        click.echo(f"      Prompt hash: {meta.get('prompt_hash', '?')}")
        click.echo(f"      时间: {meta.get('timestamp', '?')}")

    click.echo()
