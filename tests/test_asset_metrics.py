import json
from pathlib import Path

from v2g.asset_metrics import build_asset_metrics
from v2g.asset_store import AssetMeta, AssetStore
from v2g.config import Config


def _cfg(tmp_path: Path) -> Config:
    cfg = Config()
    cfg.output_dir = tmp_path / "output"
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    return cfg


def test_asset_store_usage_and_metrics(tmp_path):
    cfg = _cfg(tmp_path)

    # 构造两条 resolve 报告（跨项目）
    p1 = cfg.output_dir / "proj-a"
    p1.mkdir(parents=True, exist_ok=True)
    (p1 / "asset_resolve_report.json").write_text(
        json.dumps(
            {
                "checked_segments": 5,
                "checked_image_segments": 3,
                "checked_web_video_segments": 2,
                "resolved_local": 3,
                "resolved_remote": 1,
                "resolved_local_image": 2,
                "resolved_remote_image": 1,
                "resolved_local_web_video": 1,
                "resolved_remote_web_video": 0,
                "unresolved": 1,
                "unknown_rights_local_hits": 1,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    p2 = cfg.output_dir / "proj-b"
    p2.mkdir(parents=True, exist_ok=True)
    (p2 / "asset_resolve_report.json").write_text(
        json.dumps(
            {
                "checked_segments": 4,
                "checked_image_segments": 2,
                "checked_web_video_segments": 2,
                "resolved_local": 2,
                "resolved_remote": 2,
                "resolved_local_image": 1,
                "resolved_remote_image": 1,
                "resolved_local_web_video": 1,
                "resolved_remote_web_video": 1,
                "unresolved": 0,
                "unknown_rights_local_hits": 0,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    lib_file = cfg.output_dir / "asset_library" / "images" / "a.png"
    lib_file.parent.mkdir(parents=True, exist_ok=True)
    lib_file.write_bytes(b"img")

    with AssetStore(cfg.output_dir / "assets.db") as store:
        store.insert(
            AssetMeta(
                clip_id="asset-1",
                source_video="proj-a",
                time_range_start=0,
                time_range_end=0,
                duration=0,
                captured_date="2026-04-14",
                visual_type="image_overlay",
                tags=["demo"],
                product=["openai"],
                mood="explain",
                reusable=True,
                freshness="current",
                file_path=str(lib_file),
                source_kind="manual_upload",
                rights_status="cleared",
                license_type="manual",
                license_scope="commercial",
                asset_hash="hash-asset-1",
            )
        )
        store.record_usage(asset_id="asset-1", project_id="proj-a", segment_id=1, asset_role="image-overlay")
        store.record_usage(asset_id="asset-1", project_id="proj-b", segment_id=2, asset_role="image-overlay")

    metrics = build_asset_metrics(cfg, days=30, write_files=True)

    assert metrics["resolve"]["checked_segments"] == 9
    assert metrics["resolve"]["resolved_local"] == 5
    assert metrics["resolve"]["resolved_remote"] == 3
    assert metrics["resolve"]["unresolved"] == 1
    assert metrics["reuse"]["total_usage"] == 2
    assert metrics["reuse"]["reused_assets"] == 1
    assert metrics["library"]["total_assets"] == 1
    assert metrics["library"]["rights_counts"]["cleared"] == 1

    latest_json = cfg.output_dir / "asset_library" / "metrics" / "latest.json"
    latest_md = cfg.output_dir / "asset_library" / "metrics" / "latest.md"
    assert latest_json.exists()
    assert latest_md.exists()
