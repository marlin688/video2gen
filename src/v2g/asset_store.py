"""素材库：SQLite 存储 + 枚举校验 + 标签检索。

仿 scout/store.py 模式，存储视频片段元数据。
枚举值硬编码，不允许自由发挥。
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

# ── 枚举值定义（强制从中选择） ────────────────────────────

VISUAL_TYPES = frozenset({
    "screen_recording", "product_ui", "terminal", "browser",
    "code_editor", "diagram", "chart", "text_slide", "person",
    "screenshot", "image_overlay", "web_video",
})

PRODUCTS = frozenset({
    "claude", "claude-code", "cursor", "github", "vscode", "chatgpt",
    "openai", "anthropic", "google", "deepseek", "gemini", "other",
})

MOODS = frozenset({
    "hook", "problem", "explain", "demo", "reveal", "compare",
    "celebrate", "warning", "summary", "cta",
})

FRESHNESS_VALUES = frozenset({"current", "possibly_outdated", "evergreen"})
RIGHTS_STATUS_VALUES = frozenset({"unknown", "cleared", "restricted", "expired"})
SOURCE_KIND_VALUES = frozenset({
    "project_generated", "manual_upload", "library_reuse",
    "search_download", "screenshot", "ai_generated", "external",
})

# 保鲜阈值（月）
_FRESHNESS_THRESHOLDS = {
    "product_ui": 3,
    "screenshot": 3,
    "screen_recording": 6,
    "terminal": 6,
    "browser": 6,
}
# 不过期的类型
_EVERGREEN_TYPES = frozenset({"diagram", "chart", "text_slide"})


# ── 数据模型 ─────────────────────────────────────────────

@dataclass
class AssetMeta:
    clip_id: str
    source_video: str
    time_range_start: float
    time_range_end: float
    duration: float
    captured_date: str  # ISO date (YYYY-MM-DD)
    visual_type: str
    tags: list[str] = field(default_factory=list)
    product: list[str] = field(default_factory=list)
    mood: str = "explain"
    has_text_overlay: bool = False
    has_useful_audio: bool = False
    reusable: bool = True
    freshness: str = "current"
    engagement_score: int | None = None  # -1/0/1
    file_path: str = ""
    notes: str = ""
    source_kind: str = "project_generated"
    source_url: str = ""
    asset_hash: str = ""
    rights_status: str = "unknown"
    license_type: str = ""
    license_scope: str = ""
    expires_at: str = ""  # ISO date YYYY-MM-DD

    def validate(self) -> list[str]:
        """校验枚举值，返回错误列表。"""
        errors = []
        if self.visual_type not in VISUAL_TYPES:
            errors.append(f"Invalid visual_type: '{self.visual_type}', must be one of {sorted(VISUAL_TYPES)}")
        if self.mood not in MOODS:
            errors.append(f"Invalid mood: '{self.mood}', must be one of {sorted(MOODS)}")
        for p in self.product:
            if p not in PRODUCTS:
                errors.append(f"Invalid product: '{p}', must be one of {sorted(PRODUCTS)}")
        if self.freshness not in FRESHNESS_VALUES:
            errors.append(f"Invalid freshness: '{self.freshness}', must be one of {sorted(FRESHNESS_VALUES)}")
        if self.rights_status not in RIGHTS_STATUS_VALUES:
            errors.append(f"Invalid rights_status: '{self.rights_status}', must be one of {sorted(RIGHTS_STATUS_VALUES)}")
        if self.source_kind not in SOURCE_KIND_VALUES:
            errors.append(f"Invalid source_kind: '{self.source_kind}', must be one of {sorted(SOURCE_KIND_VALUES)}")
        if self.engagement_score is not None and self.engagement_score not in (-1, 0, 1):
            errors.append(f"Invalid engagement_score: {self.engagement_score}, must be -1/0/1")
        return errors


# ── 存储层 ───────────────────────────────────────────────

class AssetStore:
    """SQLite 素材库。"""

    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _init_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS store_meta (
                key TEXT PRIMARY KEY,
                value TEXT DEFAULT ''
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS video_stats (
                bvid TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                title TEXT DEFAULT '',
                view_count INTEGER DEFAULT 0,
                like_count INTEGER DEFAULT 0,
                coin_count INTEGER DEFAULT 0,
                fav_count INTEGER DEFAULT 0,
                share_count INTEGER DEFAULT 0,
                danmaku_count INTEGER DEFAULT 0,
                reply_count INTEGER DEFAULT 0,
                duration INTEGER DEFAULT 0,
                interact_rate INTEGER DEFAULT 0,
                crash_rate INTEGER DEFAULT 0,
                play_trans_fan_rate INTEGER DEFAULT 0,
                viewer_tags TEXT DEFAULT '[]',
                tip TEXT DEFAULT '',
                fetched_at TEXT
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS video_features (
                video_id TEXT PRIMARY KEY,
                title TEXT DEFAULT '',
                segment_count INTEGER DEFAULT 0,
                material_a_ratio REAL DEFAULT 0,
                material_b_ratio REAL DEFAULT 0,
                material_c_ratio REAL DEFAULT 0,
                schema_diversity INTEGER DEFAULT 0,
                schemas_used TEXT DEFAULT '[]',
                avg_narration_len REAL DEFAULT 0,
                max_narration_len INTEGER DEFAULT 0,
                min_narration_len INTEGER DEFAULT 0,
                has_terminal INTEGER DEFAULT 0,
                has_image_overlay INTEGER DEFAULT 0,
                has_web_video INTEGER DEFAULT 0,
                has_code_block INTEGER DEFAULT 0,
                has_diagram INTEGER DEFAULT 0,
                has_social_card INTEGER DEFAULT 0,
                hook_type TEXT DEFAULT '',
                total_duration_hint REAL DEFAULT 0,
                extracted_at TEXT
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS assets (
                clip_id TEXT PRIMARY KEY,
                source_video TEXT NOT NULL,
                time_range_start REAL,
                time_range_end REAL,
                duration REAL,
                captured_date TEXT,
                visual_type TEXT NOT NULL,
                tags TEXT DEFAULT '[]',
                product TEXT DEFAULT '[]',
                mood TEXT NOT NULL,
                has_text_overlay INTEGER DEFAULT 0,
                has_useful_audio INTEGER DEFAULT 0,
                reusable INTEGER DEFAULT 1,
                freshness TEXT DEFAULT 'current',
                engagement_score INTEGER,
                file_path TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                source_kind TEXT DEFAULT 'project_generated',
                source_url TEXT DEFAULT '',
                asset_hash TEXT DEFAULT '',
                rights_status TEXT DEFAULT 'unknown',
                license_type TEXT DEFAULT '',
                license_scope TEXT DEFAULT '',
                expires_at TEXT DEFAULT '',
                created_at TEXT
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS asset_tags (
                asset_id TEXT NOT NULL,
                tag_type TEXT NOT NULL,
                tag_value TEXT NOT NULL,
                score REAL DEFAULT 1.0,
                source TEXT DEFAULT '',
                created_at TEXT,
                PRIMARY KEY (asset_id, tag_type, tag_value)
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS asset_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                video_id TEXT DEFAULT '',
                segment_id INTEGER DEFAULT 0,
                asset_role TEXT DEFAULT '',
                used_at TEXT,
                render_version TEXT DEFAULT '',
                resolver_stage TEXT DEFAULT '',
                note TEXT DEFAULT ''
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS asset_rights (
                asset_id TEXT PRIMARY KEY,
                owner TEXT DEFAULT '',
                rights_status TEXT DEFAULT 'unknown',
                license_type TEXT DEFAULT '',
                license_scope TEXT DEFAULT '',
                platform_allowlist TEXT DEFAULT '[]',
                proof_url TEXT DEFAULT '',
                proof_note TEXT DEFAULT '',
                valid_from TEXT DEFAULT '',
                expires_at TEXT DEFAULT '',
                updated_at TEXT
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS asset_versions (
                version_id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                transform_type TEXT DEFAULT '',
                parent_version_id TEXT DEFAULT '',
                checksum TEXT DEFAULT '',
                created_at TEXT,
                meta_json TEXT DEFAULT '{}'
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_visual_type ON assets(visual_type)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mood ON assets(mood)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_freshness ON assets(freshness)"
        )
        self._ensure_asset_columns()
        self._conn.commit()

    def _ensure_asset_columns(self) -> None:
        """Perform lightweight schema migrations for existing databases."""
        columns = {
            row["name"] for row in self._conn.execute("PRAGMA table_info(assets)").fetchall()
        }
        migrations = {
            "notes": "ALTER TABLE assets ADD COLUMN notes TEXT DEFAULT ''",
            "source_kind": "ALTER TABLE assets ADD COLUMN source_kind TEXT DEFAULT 'project_generated'",
            "source_url": "ALTER TABLE assets ADD COLUMN source_url TEXT DEFAULT ''",
            "asset_hash": "ALTER TABLE assets ADD COLUMN asset_hash TEXT DEFAULT ''",
            "rights_status": "ALTER TABLE assets ADD COLUMN rights_status TEXT DEFAULT 'unknown'",
            "license_type": "ALTER TABLE assets ADD COLUMN license_type TEXT DEFAULT ''",
            "license_scope": "ALTER TABLE assets ADD COLUMN license_scope TEXT DEFAULT ''",
            "expires_at": "ALTER TABLE assets ADD COLUMN expires_at TEXT DEFAULT ''",
        }
        for col, sql in migrations.items():
            if col not in columns:
                self._conn.execute(sql)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_assets_asset_hash ON assets(asset_hash)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_assets_rights_status ON assets(rights_status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_asset_tags_type_value ON asset_tags(tag_type, tag_value)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_asset_usage_asset_project ON asset_usage(asset_id, project_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_asset_usage_project ON asset_usage(project_id, used_at)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_asset_versions_asset ON asset_versions(asset_id, created_at)"
        )

    def insert(self, meta: AssetMeta) -> None:
        """插入素材，校验枚举值。"""
        errors = meta.validate()
        if errors:
            raise ValueError(f"Asset validation failed: {'; '.join(errors)}")

        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """INSERT OR REPLACE INTO assets
               (clip_id, source_video, time_range_start, time_range_end,
                duration, captured_date, visual_type, tags, product, mood,
                has_text_overlay, has_useful_audio, reusable, freshness,
                engagement_score, file_path, notes, source_kind, source_url,
                asset_hash, rights_status, license_type, license_scope,
                expires_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                meta.clip_id, meta.source_video,
                meta.time_range_start, meta.time_range_end,
                meta.duration, meta.captured_date,
                meta.visual_type,
                json.dumps(meta.tags, ensure_ascii=False),
                json.dumps(meta.product, ensure_ascii=False),
                meta.mood,
                int(meta.has_text_overlay), int(meta.has_useful_audio),
                int(meta.reusable), meta.freshness,
                meta.engagement_score, meta.file_path, meta.notes,
                meta.source_kind, meta.source_url, meta.asset_hash,
                meta.rights_status, meta.license_type, meta.license_scope,
                meta.expires_at, now,
            ),
        )
        self._sync_asset_tags(meta, now)
        self._upsert_asset_rights(meta, now)
        self._register_asset_version(meta, now)
        self._conn.commit()

    def insert_batch(self, metas: list[AssetMeta]) -> int:
        """批量插入，返回成功数量。跳过校验失败的条目。"""
        count = 0
        for meta in metas:
            if not meta.validate():
                self.insert(meta)
                count += 1
        return count

    def get(self, clip_id: str) -> AssetMeta | None:
        """按 clip_id 精确查找。"""
        row = self._conn.execute(
            "SELECT * FROM assets WHERE clip_id = ?", (clip_id,)
        ).fetchone()
        return self._row_to_meta(row) if row else None

    def search(
        self,
        *,
        visual_type: str | None = None,
        product: str | None = None,
        mood: str | None = None,
        freshness: str | None = None,
        reusable_only: bool = True,
        commercial_only: bool = False,
        allow_unknown_rights: bool = True,
        limit: int = 20,
    ) -> list[AssetMeta]:
        """标签硬过滤检索。"""
        conditions = []
        params: list = []

        if visual_type:
            conditions.append("visual_type = ?")
            params.append(visual_type)
        if mood:
            conditions.append("mood = ?")
            params.append(mood)
        if freshness:
            conditions.append("freshness = ?")
            params.append(freshness)
        if reusable_only:
            conditions.append("reusable = 1")
        if commercial_only:
            if allow_unknown_rights:
                conditions.append("rights_status IN ('cleared', 'unknown')")
            else:
                conditions.append("rights_status = 'cleared'")
        if product:
            # JSON array 包含检查
            conditions.append("product LIKE ?")
            params.append(f'%"{product}"%')

        where = " AND ".join(conditions) if conditions else "1=1"
        # 新素材优先
        query = f"SELECT * FROM assets WHERE {where} ORDER BY captured_date DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_meta(r) for r in rows]

    def is_asset_usable(
        self,
        asset: AssetMeta,
        *,
        require_cleared_rights: bool = False,
        allow_possibly_outdated: bool = True,
    ) -> bool:
        """判断素材是否可直接复用（本地素材库检索时的安全门）。"""
        if not asset.reusable:
            return False
        if asset.rights_status in {"restricted", "expired"}:
            return False
        if require_cleared_rights and asset.rights_status != "cleared":
            return False
        if not allow_possibly_outdated and asset.freshness == "possibly_outdated":
            return False
        if asset.expires_at:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if asset.expires_at <= today:
                return False
        return True

    def search_local_first(
        self,
        query: str,
        *,
        visual_type: str | None = None,
        mood: str | None = None,
        require_cleared_rights: bool = False,
        allow_possibly_outdated: bool = False,
        limit: int = 8,
    ) -> list[AssetMeta]:
        """本地库优先检索：先按语义检索，再按标签补齐。"""
        query = (query or "").strip()
        candidates: list[AssetMeta] = []
        if query:
            candidates.extend(
                self.search_text(
                    query,
                    limit=max(limit * 4, 24),
                    reusable_only=True,
                )
            )

        if len(candidates) < limit:
            # 语义检索不足时，按标签拉一批候选补齐。
            candidates.extend(
                self.search(
                    visual_type=visual_type,
                    mood=mood,
                    reusable_only=True,
                    commercial_only=require_cleared_rights,
                    allow_unknown_rights=not require_cleared_rights,
                    limit=max(limit * 4, 24),
                )
            )

        seen: set[str] = set()
        filtered: list[AssetMeta] = []
        for asset in candidates:
            if asset.clip_id in seen:
                continue
            seen.add(asset.clip_id)
            if visual_type and asset.visual_type != visual_type:
                continue
            if mood and asset.mood != mood:
                continue
            if not self.is_asset_usable(
                asset,
                require_cleared_rights=require_cleared_rights,
                allow_possibly_outdated=allow_possibly_outdated,
            ):
                continue
            if asset.file_path and not Path(asset.file_path).exists():
                continue
            filtered.append(asset)
            if len(filtered) >= limit:
                break

        return filtered

    def count(self) -> int:
        """素材总数。"""
        row = self._conn.execute("SELECT COUNT(*) FROM assets").fetchone()
        return row[0] if row else 0

    def get_meta(self, key: str, default: str = "") -> str:
        """Read a metadata value from the store."""
        row = self._conn.execute(
            "SELECT value FROM store_meta WHERE key = ?",
            (key,),
        ).fetchone()
        return row["value"] if row else default

    def set_meta(self, key: str, value: str) -> None:
        """Persist a metadata value in the store."""
        self._conn.execute(
            """INSERT OR REPLACE INTO store_meta (key, value)
               VALUES (?, ?)""",
            (key, value),
        )
        self._conn.commit()

    def get_by_hash(self, asset_hash: str) -> AssetMeta | None:
        """按文件 hash 查找素材。"""
        if not asset_hash:
            return None
        row = self._conn.execute(
            "SELECT * FROM assets WHERE asset_hash = ? ORDER BY created_at DESC LIMIT 1",
            (asset_hash,),
        ).fetchone()
        return self._row_to_meta(row) if row else None

    def get_by_file_path(self, file_path: str) -> AssetMeta | None:
        """按 file_path 精确查找素材。"""
        row = self._conn.execute(
            "SELECT * FROM assets WHERE file_path = ? ORDER BY created_at DESC LIMIT 1",
            (str(Path(file_path)),),
        ).fetchone()
        return self._row_to_meta(row) if row else None

    def list_assets(
        self,
        *,
        reusable_only: bool = False,
        visual_type: str | None = None,
        rights_status: str | None = None,
        limit: int | None = None,
    ) -> list[AssetMeta]:
        """List assets ordered by recency."""
        query = "SELECT * FROM assets"
        params: list = []
        conditions: list[str] = []
        if reusable_only:
            conditions.append("reusable = 1")
        if visual_type:
            conditions.append("visual_type = ?")
            params.append(visual_type)
        if rights_status:
            conditions.append("rights_status = ?")
            params.append(rights_status)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY captured_date DESC, created_at DESC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_meta(r) for r in rows]

    def search_text(
        self,
        query: str,
        *,
        limit: int = 5,
        reusable_only: bool = True,
    ) -> list[AssetMeta]:
        """Search assets by free-text overlap across notes, tags, and metadata."""
        query_tokens = _tokenize_text(query)
        if not query_tokens:
            return []

        candidates = self.list_assets(reusable_only=reusable_only)
        scored: list[tuple[float, AssetMeta]] = []
        min_hits = 1 if len(query_tokens) <= 2 else max(
            2, math.ceil(len(query_tokens) * 0.3)
        )

        for asset in candidates:
            asset_tokens = _asset_tokens(asset)
            overlap = query_tokens & asset_tokens
            if len(overlap) < min_hits:
                continue

            freshness_bonus = 0.05 if asset.freshness == "current" else 0.0
            audio_bonus = 0.03 if asset.has_useful_audio else 0.0
            score = len(overlap) / len(query_tokens) + freshness_bonus + audio_bonus
            scored.append((score, asset))

        scored.sort(
            key=lambda item: (
                item[0],
                item[1].captured_date,
                item[1].clip_id,
            ),
            reverse=True,
        )
        return [asset for _, asset in scored[:limit]]

    def delete(self, clip_id: str) -> bool:
        """Delete an asset by clip id."""
        cur = self._conn.execute(
            "DELETE FROM assets WHERE clip_id = ?",
            (clip_id,),
        )
        self._conn.execute("DELETE FROM asset_tags WHERE asset_id = ?", (clip_id,))
        self._conn.execute("DELETE FROM asset_rights WHERE asset_id = ?", (clip_id,))
        self._conn.execute("DELETE FROM asset_versions WHERE asset_id = ?", (clip_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def record_usage(
        self,
        *,
        asset_id: str,
        project_id: str,
        segment_id: int = 0,
        asset_role: str = "",
        video_id: str = "",
        render_version: str = "",
        resolver_stage: str = "assets_resolve",
        note: str = "",
    ) -> None:
        """记录素材在项目中的使用事件。"""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """INSERT INTO asset_usage
               (asset_id, project_id, video_id, segment_id, asset_role, used_at,
                render_version, resolver_stage, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                asset_id,
                project_id,
                video_id,
                int(segment_id),
                asset_role,
                now,
                render_version,
                resolver_stage,
                note,
            ),
        )
        self._conn.commit()

    def list_recent_usage(
        self,
        *,
        asset_id: str | None = None,
        project_id: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """列出素材使用记录。"""
        conditions: list[str] = []
        params: list = []
        if asset_id:
            conditions.append("asset_id = ?")
            params.append(asset_id)
        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        params.append(max(1, int(limit)))
        rows = self._conn.execute(
            f"""SELECT id, asset_id, project_id, video_id, segment_id, asset_role,
                       used_at, render_version, resolver_stage, note
                FROM asset_usage
                {where}
                ORDER BY used_at DESC, id DESC
                LIMIT ?""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def update_asset(
        self,
        clip_id: str,
        *,
        rights_status: str | None = None,
        license_type: str | None = None,
        license_scope: str | None = None,
        expires_at: str | None = None,
        reusable: bool | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
        product: list[str] | None = None,
        mood: str | None = None,
        source_url: str | None = None,
        source_kind: str | None = None,
        file_path: str | None = None,
    ) -> AssetMeta | None:
        """更新素材核心字段（含版权字段），并同步 tags/rights/version。"""
        existing = self.get(clip_id)
        if existing is None:
            return None

        updated = replace(
            existing,
            rights_status=rights_status if rights_status is not None else existing.rights_status,
            license_type=license_type if license_type is not None else existing.license_type,
            license_scope=license_scope if license_scope is not None else existing.license_scope,
            expires_at=expires_at if expires_at is not None else existing.expires_at,
            reusable=reusable if reusable is not None else existing.reusable,
            notes=notes if notes is not None else existing.notes,
            tags=_dedupe_preserve_order(tags) if tags is not None else existing.tags,
            product=_dedupe_preserve_order(product) if product is not None else existing.product,
            mood=mood if mood is not None else existing.mood,
            source_url=source_url if source_url is not None else existing.source_url,
            source_kind=source_kind if source_kind is not None else existing.source_kind,
            file_path=str(Path(file_path)) if file_path is not None else existing.file_path,
        )
        if file_path is not None:
            updated.asset_hash = _compute_file_hash(Path(updated.file_path))

        self.insert(updated)
        return updated

    def usage_stats(self) -> dict:
        """聚合素材复用统计，供运营/商业化指标看板使用。"""
        total_usage = self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM asset_usage"
        ).fetchone()["cnt"]
        usage_projects = self._conn.execute(
            "SELECT COUNT(DISTINCT project_id) AS cnt FROM asset_usage"
        ).fetchone()["cnt"]
        reused_assets = self._conn.execute(
            """SELECT COUNT(*) AS cnt FROM (
                   SELECT asset_id
                   FROM asset_usage
                   GROUP BY asset_id
                   HAVING COUNT(DISTINCT project_id) >= 2
               )"""
        ).fetchone()["cnt"]
        top_rows = self._conn.execute(
            """SELECT asset_id,
                      COUNT(*) AS use_count,
                      COUNT(DISTINCT project_id) AS project_count
               FROM asset_usage
               GROUP BY asset_id
               ORDER BY use_count DESC, project_count DESC
               LIMIT 10"""
        ).fetchall()
        return {
            "total_usage": int(total_usage or 0),
            "usage_projects": int(usage_projects or 0),
            "reused_assets": int(reused_assets or 0),
            "top_assets": [
                {
                    "asset_id": row["asset_id"],
                    "use_count": int(row["use_count"] or 0),
                    "project_count": int(row["project_count"] or 0),
                }
                for row in top_rows
            ],
        }

    def list_source_projects(self, limit: int = 200) -> list[dict]:
        """Return grouped project/source stats for review UI filters."""
        rows = self._conn.execute(
            """SELECT source_video, COUNT(*) AS asset_count
               FROM assets
               WHERE source_video != ''
               GROUP BY source_video
               ORDER BY asset_count DESC, source_video ASC
               LIMIT ?""",
            (max(1, int(limit)),),
        ).fetchall()
        return [
            {
                "project_id": row["source_video"],
                "asset_count": int(row["asset_count"] or 0),
            }
            for row in rows
        ]

    def upsert_manual_asset(
        self,
        *,
        file_path: str,
        keywords: list[str],
        description: str = "",
        asset_type: str = "recording",
        source_project: str = "",
        duration: float = 0.0,
        clip_id: str = "",
        created_at: str = "",
        rights_status: str = "cleared",
        license_type: str = "manual",
        license_scope: str = "commercial",
        source_url: str = "",
        source_kind: str = "manual_upload",
        expires_at: str = "",
    ) -> AssetMeta:
        """Insert or update a manually curated asset in the unified store."""
        existing = self._conn.execute(
            "SELECT clip_id FROM assets WHERE file_path = ?",
            (file_path,),
        ).fetchone()
        normalized_path = str(Path(file_path))
        resolved_clip_id = (
            existing["clip_id"]
            if existing
            else (clip_id or _manual_clip_id(normalized_path))
        )
        created_ts = created_at or datetime.now(timezone.utc).isoformat()
        captured_date = created_ts[:10]

        meta = AssetMeta(
            clip_id=resolved_clip_id,
            source_video=source_project or "manual-library",
            time_range_start=0.0,
            time_range_end=duration,
            duration=duration,
            captured_date=captured_date,
            visual_type=_normalize_manual_visual_type(asset_type),
            tags=_dedupe_preserve_order(keywords),
            product=_infer_products(description, keywords),
            mood="demo",
            reusable=True,
            freshness="current",
            file_path=normalized_path,
            notes=description.strip(),
            source_kind=source_kind,
            source_url=source_url.strip(),
            asset_hash=_compute_file_hash(Path(normalized_path)),
            rights_status=rights_status,
            license_type=license_type,
            license_scope=license_scope,
            expires_at=expires_at,
        )
        self.insert(meta)
        return meta

    def count_stale(self) -> int:
        """过期素材数量。"""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM assets WHERE freshness = 'possibly_outdated'"
        ).fetchone()
        return row[0] if row else 0

    def update_engagement(self, clip_id: str, score: int) -> None:
        """更新单个素材的 engagement_score。"""
        if score not in (-1, 0, 1):
            raise ValueError(f"engagement_score must be -1/0/1, got {score}")
        self._conn.execute(
            "UPDATE assets SET engagement_score = ? WHERE clip_id = ?",
            (score, clip_id),
        )
        self._conn.commit()

    def mark_stale(self) -> int:
        """批量标记过期素材。返回标记数量。

        规则：
        - product_ui/screenshot: 3 个月 → possibly_outdated
        - screen_recording/terminal/browser: 6 个月 → possibly_outdated
        - evergreen 类型不标记
        """
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        total_marked = 0

        for vtype, months in _FRESHNESS_THRESHOLDS.items():
            cutoff = (now - timedelta(days=months * 30)).strftime("%Y-%m-%d")
            cur = self._conn.execute(
                """UPDATE assets
                   SET freshness = 'possibly_outdated'
                   WHERE visual_type = ?
                     AND freshness = 'current'
                     AND captured_date < ?""",
                (vtype, cutoff),
            )
            total_marked += cur.rowcount

        self._conn.commit()
        return total_marked

    def aggregate_engagement(self) -> dict[str, float]:
        """按 visual_type x mood 聚合 engagement_score 平均值。

        只输出样本数 >= 5 的组合。
        """
        rows = self._conn.execute(
            """SELECT visual_type || '+' || mood AS combo,
                      AVG(engagement_score) AS avg_score,
                      COUNT(*) AS cnt
               FROM assets
               WHERE engagement_score IS NOT NULL
               GROUP BY visual_type, mood
               HAVING cnt >= 5
               ORDER BY avg_score DESC"""
        ).fetchall()
        return {row["combo"]: round(row["avg_score"], 2) for row in rows}

    def to_context(self, limit: int = 30) -> str:
        """生成 LLM context 文本，列出可用素材。"""
        assets = self.search(limit=limit)
        if not assets:
            return ""
        lines = ["## 可用素材库（可选复用）\n"]
        for a in assets:
            tags_str = ", ".join(a.tags[:3]) if a.tags else ""
            note_str = f", note={a.notes[:24]}" if a.notes else ""
            lines.append(
                f"- `{a.clip_id}`: {a.visual_type}/{a.mood}, "
                f"tags=[{tags_str}], {a.duration:.1f}s, "
                f"freshness={a.freshness}{note_str}"
            )
        return "\n".join(lines)

    # ── video_stats 方法 ──────────────────────────────────

    def upsert_video_stats(
        self,
        bvid: str,
        project_id: str,
        *,
        title: str = "",
        view_count: int = 0,
        like_count: int = 0,
        coin_count: int = 0,
        fav_count: int = 0,
        share_count: int = 0,
        danmaku_count: int = 0,
        reply_count: int = 0,
        duration: int = 0,
        interact_rate: int = 0,
        crash_rate: int = 0,
        play_trans_fan_rate: int = 0,
        viewer_tags: list[str] | None = None,
        tip: str = "",
    ) -> None:
        """插入或更新视频级别的 stats。"""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """INSERT OR REPLACE INTO video_stats
               (bvid, project_id, title, view_count, like_count, coin_count,
                fav_count, share_count, danmaku_count, reply_count, duration,
                interact_rate, crash_rate, play_trans_fan_rate, viewer_tags, tip,
                fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (bvid, project_id, title, view_count, like_count, coin_count,
             fav_count, share_count, danmaku_count, reply_count, duration,
             interact_rate, crash_rate, play_trans_fan_rate,
             json.dumps(viewer_tags or [], ensure_ascii=False), tip, now),
        )
        self._conn.commit()

    def get_video_stats(self, bvid: str) -> dict | None:
        """按 bvid 获取 video stats。"""
        row = self._conn.execute(
            "SELECT * FROM video_stats WHERE bvid = ?", (bvid,)
        ).fetchone()
        return dict(row) if row else None

    def list_video_stats(self) -> list[dict]:
        """列出所有 video stats。"""
        rows = self._conn.execute(
            "SELECT * FROM video_stats ORDER BY fetched_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def aggregate_video_performance(self) -> dict:
        """聚合视频级别表现指标，用于 LLM context。

        返回: {
            "total_videos": int,
            "avg_like_rate": float,  # 平均点赞率 (like/view)
            "avg_coin_rate": float,  # 平均投币率
            "avg_fav_rate": float,   # 平均收藏率
        }
        """
        row = self._conn.execute("""
            SELECT COUNT(*) as cnt,
                   AVG(CASE WHEN view_count > 0
                        THEN CAST(like_count AS REAL) / view_count ELSE 0 END) as avg_like_rate,
                   AVG(CASE WHEN view_count > 0
                        THEN CAST(coin_count AS REAL) / view_count ELSE 0 END) as avg_coin_rate,
                   AVG(CASE WHEN view_count > 0
                        THEN CAST(fav_count AS REAL) / view_count ELSE 0 END) as avg_fav_rate
            FROM video_stats
            WHERE view_count > 0
        """).fetchone()
        if not row or row["cnt"] == 0:
            return {}
        return {
            "total_videos": row["cnt"],
            "avg_like_rate": round(row["avg_like_rate"], 4),
            "avg_coin_rate": round(row["avg_coin_rate"], 4),
            "avg_fav_rate": round(row["avg_fav_rate"], 4),
        }

    def all_bvids(self) -> list[tuple[str, str]]:
        """返回所有 (bvid, project_id) 对。"""
        rows = self._conn.execute(
            "SELECT bvid, project_id FROM video_stats"
        ).fetchall()
        return [(r["bvid"], r["project_id"]) for r in rows]

    # ── video_features 方法 ────────────────────────────────

    def upsert_video_features(self, feat) -> None:
        """插入或更新视频特征。feat: VideoFeatures dataclass。"""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """INSERT OR REPLACE INTO video_features
               (video_id, title, segment_count,
                material_a_ratio, material_b_ratio, material_c_ratio,
                schema_diversity, schemas_used, avg_narration_len,
                max_narration_len, min_narration_len,
                has_terminal, has_image_overlay, has_web_video,
                has_code_block, has_diagram, has_social_card,
                hook_type, total_duration_hint, extracted_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                feat.video_id, feat.title, feat.segment_count,
                feat.material_a_ratio, feat.material_b_ratio, feat.material_c_ratio,
                feat.schema_diversity,
                json.dumps(feat.schemas_used, ensure_ascii=False),
                feat.avg_narration_len,
                feat.max_narration_len, feat.min_narration_len,
                int(feat.has_terminal), int(feat.has_image_overlay),
                int(feat.has_web_video), int(feat.has_code_block),
                int(feat.has_diagram), int(feat.has_social_card),
                feat.hook_type, feat.total_duration_hint, now,
            ),
        )
        self._conn.commit()

    def get_high_performing_patterns(self) -> dict | None:
        """关联 video_stats + video_features，返回高互动视频的平均特征。

        "高互动" = like_rate (like/view) 高于中位数的视频。
        需要至少 3 个有 stats + features 的视频。
        """
        rows = self._conn.execute("""
            SELECT f.*, s.view_count, s.like_count, s.interact_rate, s.crash_rate
            FROM video_features f
            JOIN video_stats s ON f.video_id = s.project_id
            WHERE s.view_count > 0
            ORDER BY CAST(s.like_count AS REAL) / s.view_count DESC
        """).fetchall()

        if len(rows) < 3:
            return None

        # 取前半部分作为"高表现"组
        top_n = max(1, len(rows) // 2)
        top_rows = rows[:top_n]

        def avg(key):
            vals = [r[key] for r in top_rows if r[key] is not None]
            return round(sum(vals) / len(vals), 2) if vals else 0

        # 统计 schema 使用频率
        schema_freq: dict[str, int] = {}
        for r in top_rows:
            schemas = json.loads(r["schemas_used"]) if r["schemas_used"] else []
            for s in schemas:
                schema_freq[s] = schema_freq.get(s, 0) + 1

        top_schemas = sorted(schema_freq.items(), key=lambda x: -x[1])

        return {
            "sample_size": top_n,
            "total_videos": len(rows),
            "avg_segment_count": avg("segment_count"),
            "avg_material_a": avg("material_a_ratio"),
            "avg_material_b": avg("material_b_ratio"),
            "avg_schema_diversity": avg("schema_diversity"),
            "avg_narration_len": avg("avg_narration_len"),
            "avg_crash_rate": avg("crash_rate"),
            "schema_ranking": [(s, f"{c}/{top_n}") for s, c in top_schemas[:6]],
        }

    def close(self):
        self._conn.close()

    def _sync_asset_tags(self, meta: AssetMeta, now: str) -> None:
        """同步 asset_tags，确保 tags/产品/情绪字段可结构化检索。"""
        self._conn.execute("DELETE FROM asset_tags WHERE asset_id = ?", (meta.clip_id,))
        rows: list[tuple[str, str, str, float, str, str]] = []
        for t in _dedupe_preserve_order(meta.tags):
            rows.append((meta.clip_id, "topic", t, 1.0, "asset_insert", now))
        for p in _dedupe_preserve_order(meta.product):
            rows.append((meta.clip_id, "product", p, 1.0, "asset_insert", now))
        rows.append((meta.clip_id, "mood", meta.mood, 1.0, "asset_insert", now))
        rows.append((meta.clip_id, "visual_type", meta.visual_type, 1.0, "asset_insert", now))
        rows.append((meta.clip_id, "source_kind", meta.source_kind, 1.0, "asset_insert", now))
        self._conn.executemany(
            """INSERT OR REPLACE INTO asset_tags
               (asset_id, tag_type, tag_value, score, source, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            rows,
        )

    def _upsert_asset_rights(self, meta: AssetMeta, now: str) -> None:
        """同步 asset_rights，形成独立版权审计记录。"""
        self._conn.execute(
            """INSERT OR REPLACE INTO asset_rights
               (asset_id, owner, rights_status, license_type, license_scope,
                platform_allowlist, proof_url, proof_note, valid_from, expires_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                meta.clip_id,
                meta.source_video,
                meta.rights_status,
                meta.license_type,
                meta.license_scope,
                json.dumps([], ensure_ascii=False),
                meta.source_url,
                meta.notes[:240],
                "",
                meta.expires_at,
                now,
            ),
        )

    def _register_asset_version(self, meta: AssetMeta, now: str) -> None:
        """注册资产版本，记录派生链路。"""
        if not meta.file_path:
            return
        checksum = meta.asset_hash or _compute_file_hash(Path(meta.file_path))
        version_seed = f"{meta.clip_id}|{meta.file_path}|{checksum}"
        version_id = f"ver-{hashlib.sha1(version_seed.encode('utf-8')).hexdigest()[:14]}"
        self._conn.execute(
            """INSERT OR REPLACE INTO asset_versions
               (version_id, asset_id, file_path, transform_type, parent_version_id,
                checksum, created_at, meta_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                version_id,
                meta.clip_id,
                meta.file_path,
                meta.source_kind,
                "",
                checksum,
                now,
                json.dumps({"license_type": meta.license_type}, ensure_ascii=False),
            ),
        )

    @staticmethod
    def _row_to_meta(row: sqlite3.Row) -> AssetMeta:
        return AssetMeta(
            clip_id=row["clip_id"],
            source_video=row["source_video"],
            time_range_start=row["time_range_start"] or 0,
            time_range_end=row["time_range_end"] or 0,
            duration=row["duration"] or 0,
            captured_date=row["captured_date"] or "",
            visual_type=row["visual_type"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            product=json.loads(row["product"]) if row["product"] else [],
            mood=row["mood"],
            has_text_overlay=bool(row["has_text_overlay"]),
            has_useful_audio=bool(row["has_useful_audio"]),
            reusable=bool(row["reusable"]),
            freshness=row["freshness"] or "current",
            engagement_score=row["engagement_score"],
            file_path=row["file_path"] or "",
            notes=row["notes"] or "",
            source_kind=row["source_kind"] or "project_generated",
            source_url=row["source_url"] or "",
            asset_hash=row["asset_hash"] or "",
            rights_status=row["rights_status"] or "unknown",
            license_type=row["license_type"] or "",
            license_scope=row["license_scope"] or "",
            expires_at=row["expires_at"] or "",
        )


def _normalize_manual_visual_type(asset_type: str) -> str:
    normalized = (asset_type or "").strip().lower()
    if normalized in {"recording", "capture"}:
        return "screen_recording"
    if normalized == "screenshot":
        return "screenshot"
    if normalized in VISUAL_TYPES:
        return normalized
    return "screen_recording"


def _infer_products(description: str, keywords: list[str]) -> list[str]:
    text = " ".join([description, *keywords]).lower()
    inferred = [product for product in PRODUCTS if product in text and product != "other"]
    return inferred[:3] if inferred else ["other"]


def _manual_clip_id(file_path: str) -> str:
    stem = Path(file_path).stem or "asset"
    safe_stem = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-") or "asset"
    digest = hashlib.sha1(file_path.encode("utf-8")).hexdigest()[:8]
    return f"manual-{safe_stem}-{digest}"


def _compute_file_hash(path: Path) -> str:
    try:
        hasher = hashlib.sha1()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return ""


def _asset_tokens(asset: AssetMeta) -> set[str]:
    tokens = set()
    for value in (
        asset.clip_id,
        asset.source_video,
        asset.visual_type,
        asset.mood,
        asset.file_path,
        asset.notes,
    ):
        tokens.update(_tokenize_text(value))
    for group in (asset.tags, asset.product):
        for value in group:
            tokens.update(_tokenize_text(value))
    return tokens


def _tokenize_text(text: str) -> set[str]:
    if not text:
        return set()
    tokens = set(re.findall(r"[a-zA-Z0-9_\-\.]+", text.lower()))
    for seg in re.findall(r"[\u4e00-\u9fff]+", text):
        tokens.add(seg)
        for i in range(len(seg) - 1):
            tokens.add(seg[i : i + 2])
    return tokens


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result
