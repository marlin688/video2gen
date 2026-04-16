from pathlib import Path

from v2g.asset_review_ui import apply_batch_action, query_assets_for_review
from v2g.asset_store import AssetMeta, AssetStore


def _insert_asset(store: AssetStore, clip_id: str, *, tags=None, product=None, notes="") -> None:
    store.insert(
        AssetMeta(
            clip_id=clip_id,
            source_video="proj-seed",
            time_range_start=0,
            time_range_end=0,
            duration=0,
            captured_date="2026-04-14",
            visual_type="image_overlay",
            tags=tags or [],
            product=product or ["other"],
            mood="explain",
            reusable=True,
            freshness="current",
            file_path="",
            source_kind="manual_upload",
            rights_status="unknown",
            notes=notes,
        )
    )


def test_apply_batch_action_approve_and_block(tmp_path: Path):
    db_path = tmp_path / "assets.db"
    with AssetStore(db_path) as store:
        _insert_asset(store, "asset-1")
        _insert_asset(store, "asset-2")

        approve_res = apply_batch_action(
            store,
            asset_ids=["asset-1", "asset-2"],
            action="approve",
            payload={"license_scope": "commercial", "license_type": "manual_approved"},
        )
        assert approve_res["ok"] is True
        assert approve_res["updated_count"] == 2

        a1 = store.get("asset-1")
        assert a1 is not None
        assert a1.rights_status == "cleared"
        assert a1.reusable is True
        assert a1.license_scope == "commercial"
        assert a1.license_type == "manual_approved"

        block_res = apply_batch_action(
            store,
            asset_ids=["asset-2"],
            action="block",
            payload={"reason": "copyright risk"},
        )
        assert block_res["ok"] is True
        assert block_res["updated_count"] == 1

        a2 = store.get("asset-2")
        assert a2 is not None
        assert a2.rights_status == "restricted"
        assert a2.reusable is False
        assert "copyright risk" in a2.notes


def test_apply_batch_action_set_tags_merge_and_replace(tmp_path: Path):
    db_path = tmp_path / "assets.db"
    with AssetStore(db_path) as store:
        _insert_asset(store, "asset-1", tags=["alpha"], product=["other"], notes="seed")

        merge_res = apply_batch_action(
            store,
            asset_ids=["asset-1"],
            action="set_tags",
            payload={
                "tags": "beta,gamma",
                "products": "openai",
                "semantic_type": "pricing-table",
                "entities": "Claude,Anthropic",
                "scene_tags": "pricing,官网截图",
                "mood": "demo",
                "note": "reviewed",
                "tag_mode": "merge",
                "note_mode": "append",
                "quality_score": 5,
            },
        )
        assert merge_res["ok"] is True
        merged = store.get("asset-1")
        assert merged is not None
        assert merged.tags == ["alpha", "beta", "gamma"]
        assert merged.product == ["other", "openai"]
        assert merged.semantic_type == "pricing-table"
        assert merged.entities == ["Claude", "Anthropic"]
        assert merged.scene_tags == ["pricing", "官网截图"]
        assert merged.mood == "demo"
        assert merged.quality_score == 5
        assert "seed" in merged.notes and "reviewed" in merged.notes

        replace_res = apply_batch_action(
            store,
            asset_ids=["asset-1"],
            action="set_tags",
            payload={
                "tags": ["omega"],
                "products": ["github"],
                "entities": ["OpenAI"],
                "scene_tags": ["dashboard"],
                "tag_mode": "replace",
                "note": "replace-note",
                "note_mode": "replace",
            },
        )
        assert replace_res["ok"] is True
        replaced = store.get("asset-1")
        assert replaced is not None
        assert replaced.tags == ["omega"]
        assert replaced.product == ["github"]
        assert replaced.entities == ["OpenAI"]
        assert replaced.scene_tags == ["dashboard"]
        assert replaced.notes == "replace-note"


def test_apply_batch_action_remove_with_file(tmp_path: Path):
    db_path = tmp_path / "assets.db"
    media = tmp_path / "asset_library" / "images" / "x.png"
    media.parent.mkdir(parents=True, exist_ok=True)
    media.write_bytes(b"img")

    with AssetStore(db_path) as store:
        store.insert(
            AssetMeta(
                clip_id="asset-rm",
                source_video="proj-rm",
                time_range_start=0,
                time_range_end=0,
                duration=0,
                captured_date="2026-04-14",
                visual_type="image_overlay",
                tags=["rm"],
                product=["other"],
                mood="explain",
                reusable=True,
                freshness="current",
                file_path=str(media),
                source_kind="manual_upload",
                rights_status="unknown",
            )
        )

        res = apply_batch_action(
            store,
            asset_ids=["asset-rm"],
            action="remove",
            payload={"delete_file": True},
        )
        assert res["ok"] is True
        assert res["updated_count"] == 1
        assert store.get("asset-rm") is None
        assert media.exists() is False


def test_query_assets_for_review_project_and_queue(tmp_path: Path):
    db_path = tmp_path / "assets.db"
    with AssetStore(db_path) as store:
        _insert_asset(store, "pending-a", tags=["a"])
        store.update_asset("pending-a", rights_status="unknown")

        _insert_asset(store, "blocked-b", tags=["b"])
        store.update_asset("blocked-b", rights_status="restricted", reusable=False)

        _insert_asset(store, "old-c", tags=["c"])
        store.update_asset("old-c", rights_status="cleared")

        # assign project/date fields via upsert pattern
        p = store.get("pending-a")
        assert p is not None
        store.insert(
            AssetMeta(
                clip_id=p.clip_id,
                source_video="proj-A",
                time_range_start=0,
                time_range_end=0,
                duration=0,
                captured_date="2026-04-10",
                visual_type=p.visual_type,
                tags=p.tags,
                product=p.product,
                mood=p.mood,
                reusable=p.reusable,
                freshness=p.freshness,
                file_path=p.file_path,
                source_kind=p.source_kind,
                rights_status=p.rights_status,
            )
        )

        b = store.get("blocked-b")
        assert b is not None
        store.insert(
            AssetMeta(
                clip_id=b.clip_id,
                source_video="proj-B",
                time_range_start=0,
                time_range_end=0,
                duration=0,
                captured_date="2026-04-14",
                visual_type=b.visual_type,
                tags=b.tags,
                product=b.product,
                mood=b.mood,
                reusable=b.reusable,
                freshness=b.freshness,
                file_path=b.file_path,
                source_kind=b.source_kind,
                rights_status=b.rights_status,
            )
        )

        c = store.get("old-c")
        assert c is not None
        store.insert(
            AssetMeta(
                clip_id=c.clip_id,
                source_video="proj-A",
                time_range_start=0,
                time_range_end=0,
                duration=0,
                captured_date="2026-03-01",
                visual_type=c.visual_type,
                tags=c.tags,
                product=c.product,
                mood=c.mood,
                reusable=c.reusable,
                freshness=c.freshness,
                file_path=c.file_path,
                source_kind=c.source_kind,
                rights_status=c.rights_status,
            )
        )

        pending = query_assets_for_review(
            store,
            queue="review_pending",
            show_all=True,
            limit=20,
        )
        assert [a.clip_id for a in pending] == ["pending-a"]

        proj_a_recent = query_assets_for_review(
            store,
            project_id="proj-A",
            date_from="2026-04-01",
            show_all=True,
            limit=20,
        )
        assert [a.clip_id for a in proj_a_recent] == ["pending-a"]

        blocked = query_assets_for_review(
            store,
            queue="blocked",
            show_all=True,
            limit=20,
        )
        assert [a.clip_id for a in blocked] == ["blocked-b"]
