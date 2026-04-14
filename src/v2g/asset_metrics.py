"""素材库指标看板：命中率、复用率、成本与风控统计。"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from v2g.asset_store import AssetStore
from v2g.config import Config


def build_asset_metrics(
    cfg: Config,
    *,
    days: int = 30,
    write_files: bool = True,
) -> dict:
    """构建素材库 KPI 指标，并可选写入 output/asset_library/metrics。"""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(1, days))

    reports = list(_collect_resolve_reports(cfg.output_dir, cutoff=cutoff))

    checked = sum(int(r.get("checked_segments") or 0) for _, r in reports)
    checked_image = sum(int(r.get("checked_image_segments") or 0) for _, r in reports)
    checked_web = sum(int(r.get("checked_web_video_segments") or 0) for _, r in reports)
    local_hit = sum(int(r.get("resolved_local") or 0) for _, r in reports)
    remote_hit = sum(int(r.get("resolved_remote") or 0) for _, r in reports)
    unresolved = sum(int(r.get("unresolved") or 0) for _, r in reports)
    unknown_rights_hits = sum(int(r.get("unknown_rights_local_hits") or 0) for _, r in reports)

    local_image_hit = sum(int(r.get("resolved_local_image") or 0) for _, r in reports)
    remote_image_hit = sum(int(r.get("resolved_remote_image") or 0) for _, r in reports)
    local_web_hit = sum(int(r.get("resolved_local_web_video") or 0) for _, r in reports)
    remote_web_hit = sum(int(r.get("resolved_remote_web_video") or 0) for _, r in reports)

    project_ids = [pid for pid, _ in reports]
    unique_projects = sorted(set(project_ids))

    with AssetStore(cfg.output_dir / "assets.db") as store:
        assets = store.list_assets(reusable_only=False)
        usage = store.usage_stats()

    total_assets = len(assets)
    rights_counts = {
        "cleared": 0,
        "unknown": 0,
        "restricted": 0,
        "expired": 0,
    }
    stale_assets = 0
    blocked_assets = 0
    for asset in assets:
        status = asset.rights_status if asset.rights_status in rights_counts else "unknown"
        rights_counts[status] += 1
        if asset.freshness == "possibly_outdated":
            stale_assets += 1
        if status in {"restricted", "expired"}:
            blocked_assets += 1

    external_unit_cost = float(os.environ.get("ASSET_EXTERNAL_UNIT_COST", "0") or 0)
    external_estimated_cost = round(remote_hit * external_unit_cost, 4)

    denom_checked = max(checked, 1)
    denom_checked_image = max(checked_image, 1)
    denom_checked_web = max(checked_web, 1)
    denom_assets = max(total_assets, 1)

    metrics = {
        "version": "v1",
        "generated_at": now.isoformat(),
        "window_days": days,
        "projects_with_resolve": len(unique_projects),
        "project_ids": unique_projects,
        "resolve": {
            "checked_segments": checked,
            "checked_image_segments": checked_image,
            "checked_web_video_segments": checked_web,
            "resolved_local": local_hit,
            "resolved_remote": remote_hit,
            "unresolved": unresolved,
            "unknown_rights_local_hits": unknown_rights_hits,
            "local_hit_rate": round(local_hit / denom_checked, 4),
            "remote_fetch_rate": round(remote_hit / denom_checked, 4),
            "unresolved_rate": round(unresolved / denom_checked, 4),
            "image_local_hit_rate": round(local_image_hit / denom_checked_image, 4),
            "web_video_local_hit_rate": round(local_web_hit / denom_checked_web, 4),
            "image_remote_fetch_rate": round(remote_image_hit / denom_checked_image, 4),
            "web_video_remote_fetch_rate": round(remote_web_hit / denom_checked_web, 4),
        },
        "library": {
            "total_assets": total_assets,
            "blocked_assets": blocked_assets,
            "stale_assets": stale_assets,
            "rights_counts": rights_counts,
            "cleared_rate": round(rights_counts["cleared"] / denom_assets, 4),
            "unknown_rate": round(rights_counts["unknown"] / denom_assets, 4),
        },
        "reuse": {
            "total_usage": usage.get("total_usage", 0),
            "usage_projects": usage.get("usage_projects", 0),
            "reused_assets": usage.get("reused_assets", 0),
            "reused_asset_rate": round((usage.get("reused_assets", 0) / denom_assets), 4),
            "top_assets": usage.get("top_assets", []),
        },
        "cost": {
            "external_fetch_count": remote_hit,
            "external_unit_cost": external_unit_cost,
            "external_estimated_cost": external_estimated_cost,
        },
    }

    if write_files:
        _write_metrics_files(cfg.output_dir, metrics)

    return metrics


def _collect_resolve_reports(output_dir: Path, *, cutoff: datetime):
    for path in sorted(output_dir.glob("*/asset_resolve_report.json")):
        if not path.exists():
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if mtime < cutoff:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        yield path.parent.name, payload


def _write_metrics_files(output_dir: Path, metrics: dict) -> None:
    metrics_dir = output_dir / "asset_library" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    json_path = metrics_dir / f"metrics-{stamp}.json"
    latest_json = metrics_dir / "latest.json"
    md_path = metrics_dir / f"metrics-{stamp}.md"
    latest_md = metrics_dir / "latest.md"

    text_json = json.dumps(metrics, ensure_ascii=False, indent=2)
    json_path.write_text(text_json, encoding="utf-8")
    latest_json.write_text(text_json, encoding="utf-8")

    resolve = metrics.get("resolve", {})
    lib = metrics.get("library", {})
    reuse = metrics.get("reuse", {})
    cost = metrics.get("cost", {})

    md_lines = [
        "# Asset Metrics",
        "",
        f"- generated_at: {metrics.get('generated_at', '')}",
        f"- window_days: {metrics.get('window_days', '')}",
        f"- projects_with_resolve: {metrics.get('projects_with_resolve', 0)}",
        "",
        "## Resolve",
        f"- checked_segments: {resolve.get('checked_segments', 0)}",
        f"- local_hit_rate: {resolve.get('local_hit_rate', 0):.2%}",
        f"- remote_fetch_rate: {resolve.get('remote_fetch_rate', 0):.2%}",
        f"- unresolved_rate: {resolve.get('unresolved_rate', 0):.2%}",
        f"- image_local_hit_rate: {resolve.get('image_local_hit_rate', 0):.2%}",
        f"- web_video_local_hit_rate: {resolve.get('web_video_local_hit_rate', 0):.2%}",
        "",
        "## Library",
        f"- total_assets: {lib.get('total_assets', 0)}",
        f"- blocked_assets: {lib.get('blocked_assets', 0)}",
        f"- stale_assets: {lib.get('stale_assets', 0)}",
        f"- cleared_rate: {lib.get('cleared_rate', 0):.2%}",
        f"- unknown_rate: {lib.get('unknown_rate', 0):.2%}",
        "",
        "## Reuse",
        f"- total_usage: {reuse.get('total_usage', 0)}",
        f"- usage_projects: {reuse.get('usage_projects', 0)}",
        f"- reused_assets: {reuse.get('reused_assets', 0)}",
        f"- reused_asset_rate: {reuse.get('reused_asset_rate', 0):.2%}",
        "",
        "## Cost",
        f"- external_fetch_count: {cost.get('external_fetch_count', 0)}",
        f"- external_unit_cost: {cost.get('external_unit_cost', 0)}",
        f"- external_estimated_cost: {cost.get('external_estimated_cost', 0)}",
        "",
    ]
    text_md = "\n".join(md_lines)
    md_path.write_text(text_md, encoding="utf-8")
    latest_md.write_text(text_md, encoding="utf-8")
