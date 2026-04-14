"""配图预处理（兼容入口）。

当前实现委托给 ``asset_resolver``：
- 优先复用本地素材库
- 缺失时在线配图
- 回填 script.json 的 image_path
"""

from __future__ import annotations

from v2g.asset_resolver import resolve_project_assets
from v2g.config import Config


def prepare_images(cfg: Config, project_id: str) -> int:
    """兼容旧 API：返回本次成功解析的图片数量。"""
    report = resolve_project_assets(cfg, project_id)
    return int(report.get("resolved_local", 0)) + int(report.get("resolved_remote", 0))
