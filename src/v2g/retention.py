"""完播率回标：将 B 站留存曲线映射到 segment，更新素材 engagement_score。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import click

from v2g.asset_store import AssetStore
from v2g.config import Config


def _parse_retention_csv(csv_path: Path) -> list[tuple[float, float]]:
    """解析留存率 CSV。

    支持两种格式：
    1. 时间(秒), 留存率(%)     例如: 30, 85.2
    2. 时间(秒), 留存率(0-1)   例如: 30, 0.852

    Returns: [(time_sec, retention_pct), ...] 按时间排序
    """
    points: list[tuple[float, float]] = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue
            try:
                t = float(row[0].strip())
                r = float(row[1].strip())
            except ValueError:
                continue  # 跳过表头行
            # 自动检测：如果值 <= 1 认为是比例，转为百分比
            if r <= 1.0:
                r *= 100
            points.append((t, r))

    points.sort(key=lambda x: x[0])
    return points


def _interpolate_retention(
    points: list[tuple[float, float]],
    time: float,
) -> float:
    """在留存曲线上线性插值。"""
    if not points:
        return 100.0
    if time <= points[0][0]:
        return points[0][1]
    if time >= points[-1][0]:
        return points[-1][1]

    for i in range(1, len(points)):
        if points[i][0] >= time:
            t0, r0 = points[i - 1]
            t1, r1 = points[i]
            ratio = (time - t0) / max(t1 - t0, 0.001)
            return r0 + (r1 - r0) * ratio
    return points[-1][1]


def annotate_retention(
    cfg: Config,
    project_id: str,
    retention_csv: Path,
    store: AssetStore,
) -> dict[str, int]:
    """将完播率数据映射到 segment，更新素材 engagement_score。

    流程：
    1. 读取 script.json + timing.json 获取每个 segment 的时间范围
    2. 解析留存率 CSV
    3. 计算每个 segment 时间范围内的留存率变化：
       - 下降 >5%: engagement_score = -1
       - 变化 ±5% 以内: engagement_score = 0
       - 上升: engagement_score = 1
    4. 更新 SQLite 中对应素材的 engagement_score

    Returns: {clip_id: score} 映射
    """
    output_dir = cfg.output_dir / project_id
    script_path = output_dir / "script.json"
    timing_path = output_dir / "voiceover" / "timing.json"

    if not script_path.exists():
        raise FileNotFoundError(f"script.json not found: {script_path}")

    script = json.loads(script_path.read_text(encoding="utf-8"))
    segments = script.get("segments", [])

    timing = {}
    if timing_path.exists():
        timing = json.loads(timing_path.read_text(encoding="utf-8"))

    points = _parse_retention_csv(retention_csv)
    if not points:
        raise ValueError(f"No valid data in retention CSV: {retention_csv}")

    # 计算每个 segment 的时间偏移
    current_time = 0.0
    results: dict[str, int] = {}

    for seg in segments:
        seg_id = seg["id"]
        t = timing.get(str(seg_id))
        dur = t["duration"] if t else 5.0
        gap = t.get("gap_after", 0) if t else 0

        start_time = current_time
        end_time = current_time + dur

        # 计算该 segment 时间段内留存率变化
        r_start = _interpolate_retention(points, start_time)
        r_end = _interpolate_retention(points, end_time)
        delta = r_end - r_start

        # 打分
        if delta < -5:
            score = -1  # 明显流失
        elif delta > 2:
            score = 1   # 罕见的上升
        else:
            score = 0   # 正常

        clip_id = f"{project_id}_seg{seg_id}"
        results[clip_id] = score

        # 更新 SQLite
        if store.get(clip_id):
            store.update_engagement(clip_id, score)

        current_time = end_time + gap

    return results


def print_retention_report(
    results: dict[str, int],
    project_id: str,
):
    """格式化输出留存标注报告。"""
    click.echo(f"\n📊 留存标注报告: {project_id}")
    click.echo(f"   标注 segment 数: {len(results)}")

    good = sum(1 for s in results.values() if s == 1)
    neutral = sum(1 for s in results.values() if s == 0)
    bad = sum(1 for s in results.values() if s == -1)

    click.echo(f"   ↑ 好 ({good})  → 中性 ({neutral})  ↓ 差 ({bad})")
    click.echo()

    for clip_id, score in results.items():
        emoji = {1: "↑", 0: "→", -1: "↓"}[score]
        click.echo(f"   {emoji} {clip_id}: {score:+d}")
