"""素材库：SQLite 存储 + 枚举校验 + 标签检索。

仿 scout/store.py 模式，存储视频片段元数据。
枚举值硬编码，不允许自由发挥。
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
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
                created_at TEXT
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
        self._conn.commit()

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
                engagement_score, file_path, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                meta.engagement_score, meta.file_path, now,
            ),
        )
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

    def count(self) -> int:
        """素材总数。"""
        row = self._conn.execute("SELECT COUNT(*) FROM assets").fetchone()
        return row[0] if row else 0

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
            lines.append(
                f"- `{a.clip_id}`: {a.visual_type}/{a.mood}, "
                f"tags=[{tags_str}], {a.duration:.1f}s, "
                f"freshness={a.freshness}"
            )
        return "\n".join(lines)

    def close(self):
        self._conn.close()

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
        )
