import json
from pathlib import Path

from v2g.asset_store import AssetStore
from v2g.material_library import MaterialEntry, MaterialLibrary


def test_material_library_migrates_legacy_index(tmp_path: Path):
    materials_dir = tmp_path / "materials"
    materials_dir.mkdir()
    legacy_path = materials_dir / "index.json"
    legacy_path.write_text(
        json.dumps(
            [
                {
                    "id": "legacy-1",
                    "type": "recording",
                    "path": str(tmp_path / "materials" / "recordings" / "demo.mp4"),
                    "keywords": ["claude", "demo"],
                    "description": "Claude demo clip",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    db_path = tmp_path / "output" / "assets.db"
    library = MaterialLibrary(library_dir=materials_dir, db_path=db_path)

    entries = library.list_all()
    assert len(entries) == 1
    assert entries[0].id == "legacy-1"
    assert entries[0].description == "Claude demo clip"

    with AssetStore(db_path) as store:
        stored = store.get("legacy-1")
        assert stored is not None
        assert stored.notes == "Claude demo clip"
        assert stored.visual_type == "screen_recording"

    library.remove("legacy-1")
    assert library.list_all() == []

    reloaded = MaterialLibrary(library_dir=materials_dir, db_path=db_path)
    assert reloaded.list_all() == []


def test_material_library_add_and_search_uses_asset_store(tmp_path: Path):
    db_path = tmp_path / "output" / "assets.db"
    materials_dir = tmp_path / "materials"
    clip_path = materials_dir / "recordings" / "cursor-demo.mp4"
    clip_path.parent.mkdir(parents=True)
    clip_path.write_bytes(b"video")

    library = MaterialLibrary(library_dir=materials_dir, db_path=db_path)
    library.add(
        MaterialEntry(
            id="manual-demo",
            type="recording",
            path=str(clip_path),
            keywords=["cursor", "terminal", "agent"],
            description="Cursor terminal walkthrough",
        )
    )

    results = library.search("cursor terminal", top_k=3)
    assert [entry.id for entry in results] == ["manual-demo"]
