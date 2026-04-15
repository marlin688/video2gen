from pathlib import Path

from v2g.asset_library_layout import (
    build_library_asset_path,
    prune_missing_asset_records,
    reorganize_asset_library,
)
from v2g.asset_store import AssetMeta, AssetStore
from v2g.config import Config


def _cfg(tmp_path: Path) -> Config:
    cfg = Config()
    cfg.output_dir = tmp_path / "output"
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    return cfg


def test_build_library_asset_path_uses_visual_and_semantic_dirs(tmp_path: Path):
    cfg = _cfg(tmp_path)
    asset = AssetMeta(
        clip_id="img-abc123",
        source_video="proj-demo",
        time_range_start=0,
        time_range_end=0,
        duration=0,
        captured_date="2026-04-15",
        visual_type="image_overlay",
        tags=["pricing", "table"],
        product=["anthropic"],
        mood="explain",
        reusable=True,
        freshness="current",
        file_path="",
        source_kind="search_download",
        source_url="",
        asset_hash="abcdef1234567890",
        rights_status="unknown",
        semantic_type="pricing-table",
        entities=["Claude", "Anthropic"],
        scene_tags=["pricing", "官网截图"],
    )

    path = build_library_asset_path(cfg, asset, current_path=tmp_path / "tmp.png")
    assert path.parent.parent.name == "image_overlay"
    assert path.parent.name == "pricing_table"
    assert path.name.endswith("__abcdef1234.png")
    assert "claude" in path.name


def test_reorganize_asset_library_moves_flat_asset_and_updates_db(tmp_path: Path):
    cfg = _cfg(tmp_path)
    flat_file = cfg.output_dir / "asset_library" / "images" / "img_deadbeef.png"
    flat_file.parent.mkdir(parents=True, exist_ok=True)
    flat_file.write_bytes(b"image-bytes")

    with AssetStore(cfg.output_dir / "assets.db") as store:
        store.insert(
            AssetMeta(
                clip_id="img-flat",
                source_video="proj-demo",
                time_range_start=0,
                time_range_end=0,
                duration=0,
                captured_date="2026-04-15",
                visual_type="image_overlay",
                tags=["pricing", "table"],
                product=["anthropic"],
                mood="explain",
                reusable=True,
                freshness="current",
                file_path=str(flat_file),
                source_kind="search_download",
                source_url="",
                rights_status="unknown",
                semantic_type="pricing-table",
                entities=["Claude"],
                scene_tags=["pricing", "官网截图"],
            )
        )

    report = reorganize_asset_library(cfg)
    assert report["moved"] == 1

    with AssetStore(cfg.output_dir / "assets.db") as store:
        moved = store.get("img-flat")
        assert moved is not None
        assert "/asset_library/images/image_overlay/pricing_table/" in moved.file_path
        assert Path(moved.file_path).exists()
        assert not flat_file.exists()


def test_reorganize_asset_library_skips_seed_dirs_by_default(tmp_path: Path):
    cfg = _cfg(tmp_path)
    seeded_file = (
        cfg.output_dir
        / "asset_library"
        / "images"
        / "seed_web_20260414"
        / "image_overlay_100.jpg"
    )
    seeded_file.parent.mkdir(parents=True, exist_ok=True)
    seeded_file.write_bytes(b"seeded-image")

    with AssetStore(cfg.output_dir / "assets.db") as store:
        store.insert(
            AssetMeta(
                clip_id="seeded-asset",
                source_video="seed-web-2026-04-14",
                time_range_start=0,
                time_range_end=0,
                duration=0,
                captured_date="2026-04-15",
                visual_type="image_overlay",
                tags=["seed"],
                product=["other"],
                mood="explain",
                reusable=True,
                freshness="current",
                file_path=str(seeded_file),
                source_kind="manual_upload",
                rights_status="cleared",
            )
        )

    report = reorganize_asset_library(cfg)
    assert report["skipped_seed_dirs"] == 1

    with AssetStore(cfg.output_dir / "assets.db") as store:
        asset = store.get("seeded-asset")
        assert asset is not None
        assert asset.file_path == str(seeded_file)
        assert seeded_file.exists()


def test_prune_missing_asset_records_deletes_orphan_usage(tmp_path: Path):
    cfg = _cfg(tmp_path)
    missing_file = cfg.output_dir / "asset_library" / "images" / "missing.png"

    with AssetStore(cfg.output_dir / "assets.db") as store:
        store.insert(
            AssetMeta(
                clip_id="missing-asset",
                source_video="proj-demo",
                time_range_start=0,
                time_range_end=0,
                duration=0,
                captured_date="2026-04-15",
                visual_type="image_overlay",
                tags=["missing"],
                product=["other"],
                mood="explain",
                reusable=True,
                freshness="current",
                file_path=str(missing_file),
                source_kind="search_download",
                rights_status="unknown",
            )
        )
        store.record_usage(asset_id="missing-asset", project_id="proj-demo", segment_id=1)

    report = prune_missing_asset_records(cfg)
    assert report["missing"] == 1
    assert report["deleted"] == 1

    with AssetStore(cfg.output_dir / "assets.db") as store:
        assert store.get("missing-asset") is None
        assert store.list_recent_usage(asset_id="missing-asset") == []


def test_prune_missing_asset_records_dry_run_keeps_rows(tmp_path: Path):
    cfg = _cfg(tmp_path)
    missing_file = cfg.output_dir / "asset_library" / "images" / "dry-run-missing.png"

    with AssetStore(cfg.output_dir / "assets.db") as store:
        store.insert(
            AssetMeta(
                clip_id="missing-dry-run",
                source_video="proj-demo",
                time_range_start=0,
                time_range_end=0,
                duration=0,
                captured_date="2026-04-15",
                visual_type="image_overlay",
                tags=["missing"],
                product=["other"],
                mood="explain",
                reusable=True,
                freshness="current",
                file_path=str(missing_file),
                source_kind="search_download",
                rights_status="unknown",
            )
        )

    report = prune_missing_asset_records(cfg, dry_run=True)
    assert report["missing"] == 1
    assert report["deleted"] == 0

    with AssetStore(cfg.output_dir / "assets.db") as store:
        assert store.get("missing-dry-run") is not None


def test_build_library_asset_path_curated_numbered_name_falls_back_to_generic(tmp_path: Path):
    cfg = _cfg(tmp_path)
    asset = AssetMeta(
        clip_id="seeded-image",
        source_video="seed-web-2026-04-14",
        time_range_start=0,
        time_range_end=0,
        duration=0,
        captured_date="2026-04-15",
        visual_type="image_overlay",
        tags=["wechat"],
        product=["other"],
        mood="explain",
        reusable=True,
        freshness="current",
        file_path="",
        source_kind="manual_upload",
        rights_status="cleared",
    )

    path = build_library_asset_path(
        cfg,
        asset,
        current_path=tmp_path / "image_overlay_101.jpg",
    )
    assert path.parent.parent.name == "image_overlay"
    assert path.parent.name == "generic"


def test_build_library_asset_path_prefers_meaningful_tag_after_generic_prefix(tmp_path: Path):
    cfg = _cfg(tmp_path)
    asset = AssetMeta(
        clip_id="product-ui-dashboard",
        source_video="seed-web-2026-04-14",
        time_range_start=0,
        time_range_end=0,
        duration=0,
        captured_date="2026-04-15",
        visual_type="product_ui",
        tags=["product_ui", "ui", "dashboard", "github", "actions", "screenshot"],
        product=["github"],
        mood="demo",
        reusable=True,
        freshness="current",
        file_path="",
        source_kind="manual_upload",
        rights_status="cleared",
        asset_hash="20a9e14d74abcd",
    )

    path = build_library_asset_path(
        cfg,
        asset,
        current_path=tmp_path / "product_ui_037.png",
    )
    assert path.parent.parent.name == "product_ui"
    assert path.parent.name == "dashboard"
    assert path.name.startswith("github_actions")


def test_build_library_asset_path_stable_for_existing_canonical_name(tmp_path: Path):
    cfg = _cfg(tmp_path)
    current = (
        cfg.output_dir
        / "asset_library"
        / "images"
        / "product_ui"
        / "dashboard"
        / "github_actions__20a9e14d74.png"
    )
    asset = AssetMeta(
        clip_id="product-ui-dashboard",
        source_video="seed-web-2026-04-14",
        time_range_start=0,
        time_range_end=0,
        duration=0,
        captured_date="2026-04-15",
        visual_type="product_ui",
        tags=["product_ui", "ui", "dashboard", "github", "actions", "screenshot"],
        product=["github"],
        mood="demo",
        reusable=True,
        freshness="current",
        file_path=str(current),
        source_kind="manual_upload",
        rights_status="cleared",
        asset_hash="20a9e14d74abcd",
    )

    path = build_library_asset_path(cfg, asset, current_path=current)
    assert path == current


def test_build_library_asset_path_avoids_repeating_semantic_tokens(tmp_path: Path):
    cfg = _cfg(tmp_path)
    asset = AssetMeta(
        clip_id="pricing-table",
        source_video="seed-wechat",
        time_range_start=0,
        time_range_end=0,
        duration=0,
        captured_date="2026-04-15",
        visual_type="chart",
        tags=["chart", "pricing", "table", "claude", "anthropic"],
        product=["anthropic"],
        mood="explain",
        reusable=True,
        freshness="current",
        file_path="",
        source_kind="manual_upload",
        rights_status="cleared",
        asset_hash="76dadf8cedabcd",
        semantic_type="pricing-table",
        entities=["Anthropic", "Claude"],
    )

    path = build_library_asset_path(cfg, asset, current_path=tmp_path / "chart.png")
    assert path.parent.name == "pricing_table"
    assert path.name.startswith("anthropic_claude__")
