"""Compatibility wrapper for the legacy material library API.

Material metadata now lives in ``output/assets.db`` via ``AssetStore``.
This module keeps the old ``MaterialLibrary`` interface working so existing
CLI commands and autocap flows do not need a flag day migration.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from v2g.asset_store import AssetMeta, AssetStore


LIBRARY_DIR = Path("materials")
DEFAULT_DB_PATH = Path("output") / "assets.db"
_LEGACY_MIGRATION_KEY = "legacy_material_index_migrated"


@dataclass
class MaterialEntry:
    """Legacy material entry shape used by CLI and autocap."""

    id: str = ""
    type: str = ""
    path: str = ""
    keywords: list[str] = field(default_factory=list)
    description: str = ""
    created_at: str = ""
    source_project: str = ""
    duration: float = 0.0

    def __post_init__(self):
        if not self.id:
            self.id = uuid.uuid4().hex[:12]
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


class MaterialLibrary:
    """Adapter that backs the old material library API with ``AssetStore``."""

    def __init__(
        self,
        library_dir: Path | None = None,
        db_path: Path | None = None,
    ):
        self.root = library_dir or LIBRARY_DIR
        self.index_path = self.root / "index.json"
        self.db_path = db_path or DEFAULT_DB_PATH
        self._migrate_legacy_index()

    def _migrate_legacy_index(self) -> None:
        if not self.index_path.exists():
            return

        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return

        with AssetStore(self.db_path) as store:
            if store.get_meta(_LEGACY_MIGRATION_KEY) == "1":
                return
            for raw in data:
                entry = MaterialEntry(
                    **{
                        key: value
                        for key, value in raw.items()
                        if key in MaterialEntry.__dataclass_fields__
                    }
                )
                store.upsert_manual_asset(
                    file_path=entry.path,
                    keywords=entry.keywords,
                    description=entry.description,
                    asset_type=entry.type,
                    source_project=entry.source_project,
                    duration=entry.duration,
                    clip_id=entry.id,
                    created_at=entry.created_at,
                )
            store.set_meta(_LEGACY_MIGRATION_KEY, "1")

    def add(self, entry: MaterialEntry) -> MaterialEntry:
        with AssetStore(self.db_path) as store:
            meta = store.upsert_manual_asset(
                file_path=entry.path,
                keywords=entry.keywords,
                description=entry.description,
                asset_type=entry.type,
                source_project=entry.source_project,
                duration=entry.duration,
                clip_id=entry.id,
                created_at=entry.created_at,
            )
        return self._meta_to_entry(meta)

    def search(self, query: str, top_k: int = 3) -> list[MaterialEntry]:
        with AssetStore(self.db_path) as store:
            metas = store.search_text(query, limit=top_k)
        return [self._meta_to_entry(meta) for meta in metas]

    def list_all(self) -> list[MaterialEntry]:
        with AssetStore(self.db_path) as store:
            metas = store.list_assets(reusable_only=True)
        return [self._meta_to_entry(meta) for meta in metas]

    def remove(self, entry_id: str) -> bool:
        with AssetStore(self.db_path) as store:
            return store.delete(entry_id)

    @staticmethod
    def _meta_to_entry(meta: AssetMeta) -> MaterialEntry:
        return MaterialEntry(
            id=meta.clip_id,
            type=_material_type_from_visual(meta.visual_type),
            path=meta.file_path,
            keywords=list(meta.tags),
            description=meta.notes or Path(meta.file_path).stem,
            created_at="",
            source_project=meta.source_video,
            duration=meta.duration,
        )


def _material_type_from_visual(visual_type: str) -> str:
    if visual_type == "screenshot":
        return "screenshot"
    if visual_type == "screen_recording":
        return "recording"
    return visual_type
