"""通用 SQLite 去重存储，三源（github/twitter/article）共享。"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


class KnowledgeStore:
    """轻量级 SQLite 存储，用于知识源去重。"""

    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS seen_items (
                source TEXT,
                item_id TEXT,
                data TEXT,
                fetched_at TEXT,
                PRIMARY KEY (source, item_id)
            )"""
        )
        self._conn.commit()

    def is_seen(self, source: str, item_id: str) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM seen_items WHERE source=? AND item_id=?",
            (source, item_id),
        )
        return cur.fetchone() is not None

    def filter_new(
        self,
        source: str,
        items: list[dict],
        key_fn: Callable[[dict], str],
    ) -> list[dict]:
        """过滤掉已见过的 item，返回新 item 列表。"""
        result = []
        for item in items:
            item_id = key_fn(item)
            if not self.is_seen(source, item_id):
                result.append(item)
        return result

    def mark_seen(self, source: str, item_id: str, data: Any = None):
        now = datetime.now(timezone.utc).isoformat()
        data_str = json.dumps(data, ensure_ascii=False) if data else "{}"
        self._conn.execute(
            """INSERT OR REPLACE INTO seen_items (source, item_id, data, fetched_at)
               VALUES (?, ?, ?, ?)""",
            (source, item_id, data_str, now),
        )
        self._conn.commit()

    def mark_seen_batch(self, source: str, items: list[dict], key_fn: Callable[[dict], str]):
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            (source, key_fn(item), json.dumps(item, ensure_ascii=False), now)
            for item in items
        ]
        self._conn.executemany(
            """INSERT OR REPLACE INTO seen_items (source, item_id, data, fetched_at)
               VALUES (?, ?, ?, ?)""",
            rows,
        )
        self._conn.commit()

    def close(self):
        self._conn.close()
