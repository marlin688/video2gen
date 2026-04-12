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
            # 素材列表（assets 表可能为空，但 video_stats/features 可能有数据）
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

            # video 级别互动率统计
            perf = store.aggregate_video_performance()
            if perf and perf.get("total_videos", 0) >= 3:
                parts.append(f"\n## 历史视频互动率（{perf['total_videos']} 个视频平均）\n")
                parts.append(f"- 点赞率: {perf['avg_like_rate']:.2%}")
                parts.append(f"- 投币率: {perf['avg_coin_rate']:.2%}")
                parts.append(f"- 收藏率: {perf['avg_fav_rate']:.2%}")

            # 创作中心诊断数据（流失率/互动率/受众标签）
            all_stats = store.list_video_stats()
            diagnosed = [s for s in all_stats if s.get("interact_rate", 0) > 0]
            if len(diagnosed) >= 2:
                avg_crash = sum(s["crash_rate"] for s in diagnosed) / len(diagnosed)
                avg_interact = sum(s["interact_rate"] for s in diagnosed) / len(diagnosed)
                parts.append(f"\n## B站创作中心诊断（{len(diagnosed)} 个视频平均）\n")
                parts.append(f"- 平均互动率: {avg_interact / 100:.2f}%")
                parts.append(f"- 平均流失率: {avg_crash / 100:.2f}%")
                # 收集受众标签频率
                import json as _json
                tag_freq: dict[str, int] = {}
                for s in diagnosed:
                    tags = _json.loads(s.get("viewer_tags", "[]")) if isinstance(s.get("viewer_tags"), str) else s.get("viewer_tags", [])
                    for tag in tags:
                        tag_freq[tag] = tag_freq.get(tag, 0) + 1
                if tag_freq:
                    top_tags = sorted(tag_freq.items(), key=lambda x: -x[1])[:8]
                    parts.append(f"- 受众兴趣标签: {', '.join(t[0] for t in top_tags)}")
                parts.append("\n请关注流失率，尽量在开头 30 秒内用强 hook 降低流失。")

            # 高表现视频的结构模式
            patterns = store.get_high_performing_patterns()
            if patterns:
                n = patterns["sample_size"]
                parts.append(f"\n## 高表现视频的结构模式（top {n}/{patterns['total_videos']} 个视频）\n")
                parts.append(f"- 平均段数: {patterns['avg_segment_count']:.0f}")
                parts.append(f"- A/B 素材比例: {patterns['avg_material_a']:.0%} / {patterns['avg_material_b']:.0%}")
                parts.append(f"- Schema 多样性: {patterns['avg_schema_diversity']:.1f} 种")
                parts.append(f"- 平均旁白: {patterns['avg_narration_len']:.0f} 字/段")
                if patterns.get("schema_ranking"):
                    ranking = ", ".join(f"{s}({c})" for s, c in patterns["schema_ranking"])
                    parts.append(f"- Schema 使用频率: {ranking}")
                parts.append("\n请参考以上高表现视频的结构模式来分配素材和选择组件。")
    except Exception:
        return ""

    return "\n".join(parts)
