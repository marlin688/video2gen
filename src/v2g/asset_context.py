"""素材库上下文注入：为脚本生成提供可复用素材和历史 engagement 数据。

在 scriptwriter.py 或 agent.py 的 prompt 构建阶段调用，
将素材库信息注入 LLM context。
"""

from __future__ import annotations

from pathlib import Path

from v2g.asset_store import AssetStore
from v2g.config import Config


def build_asset_context(cfg: Config) -> str:
    """构建素材库上下文，用于注入脚本生成 prompt。

    包含两部分：
    1. 可用素材列表（前期全量，后期过滤后 top N）
    2. 历史 engagement 统计（10+ 期视频后有数据）

    Returns: 注入 user_message 的文本，空字符串表示无数据
    """
    db_path = cfg.output_dir / "assets.db"
    if not db_path.exists():
        return ""

    parts: list[str] = []

    try:
        with AssetStore(db_path) as store:
            total = store.count()
            if total == 0:
                return ""

            # 素材列表
            context = store.to_context(limit=30)
            if context:
                parts.append(context)

            # engagement 统计
            engagement = store.aggregate_engagement()
            if engagement:
                parts.append("\n## 历史留存表现（基于过往视频完播率）\n")
                for combo, score in sorted(engagement.items(), key=lambda x: -x[1]):
                    emoji = "+" if score > 0 else ""
                    parts.append(f"- {combo}: {emoji}{score:.1f} 平均留存表现")
                parts.append(
                    "\n请参考以上数据分配素材类型，优先使用留存表现好的组合。"
                )
    except Exception:
        return ""

    return "\n".join(parts)
