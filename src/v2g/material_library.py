"""素材库：索引、检索、管理可复用的视频素材。"""

import json
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

import click


LIBRARY_DIR = Path("materials")


@dataclass
class MaterialEntry:
    """素材库中的一条记录。"""

    id: str = ""
    type: str = ""  # "recording" | "capture" | "screenshot"
    path: str = ""  # 相对于项目根目录的路径
    keywords: list[str] = field(default_factory=list)
    description: str = ""
    created_at: str = ""
    source_project: str = ""
    duration: float = 0.0  # 视频时长（秒），图片为 0

    def __post_init__(self):
        if not self.id:
            self.id = uuid.uuid4().hex[:12]
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


class MaterialLibrary:
    """基于 JSON 索引的素材库。"""

    def __init__(self, library_dir: Path | None = None):
        self.root = library_dir or LIBRARY_DIR
        self.index_path = self.root / "index.json"
        self._entries: list[MaterialEntry] = []
        self._load()

    def _load(self):
        if self.index_path.exists():
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            self._entries = [
                MaterialEntry(**{k: v for k, v in e.items() if k in MaterialEntry.__dataclass_fields__})
                for e in data
            ]

    def _save(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(
            json.dumps([asdict(e) for e in self._entries], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, entry: MaterialEntry):
        """添加素材到库。"""
        # 去重：相同 path 的不重复添加
        for existing in self._entries:
            if existing.path == entry.path:
                # 更新已有记录
                existing.keywords = entry.keywords
                existing.description = entry.description
                self._save()
                return existing
        self._entries.append(entry)
        self._save()
        return entry

    def search(self, query: str, top_k: int = 3) -> list[MaterialEntry]:
        """基于关键词匹配搜索素材。

        对 query 分词后，与每条素材的 keywords + description 做交集匹配，
        按匹配词数降序排列。
        """
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scored = []
        for entry in self._entries:
            # 检查文件是否还存在
            if not Path(entry.path).exists():
                continue
            entry_tokens = set()
            for kw in entry.keywords:
                entry_tokens.update(_tokenize(kw))
            entry_tokens.update(_tokenize(entry.description))

            overlap = query_tokens & entry_tokens
            # 要求至少匹配 30% 的查询词，防止 "code" 等高频词误匹配
            if overlap and len(overlap) >= max(2, len(query_tokens) * 0.3):
                scored.append((len(overlap) / len(query_tokens), entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]

    def list_all(self) -> list[MaterialEntry]:
        return list(self._entries)

    def remove(self, entry_id: str) -> bool:
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.id != entry_id]
        if len(self._entries) < before:
            self._save()
            return True
        return False


def _tokenize(text: str) -> set[str]:
    """简单分词：提取中文词、英文词、数字。"""
    # 英文/数字用空格和标点分割
    tokens = set(re.findall(r'[a-zA-Z0-9_\-\.]+', text.lower()))
    # 中文按 2-gram 切分（简单有效）
    chinese = re.findall(r'[\u4e00-\u9fff]+', text)
    for seg in chinese:
        tokens.add(seg)
        for i in range(len(seg) - 1):
            tokens.add(seg[i:i + 2])
    return tokens
