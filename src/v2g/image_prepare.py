"""配图预处理：render 前扫描 script.json，自动执行配图并填充 image_path。

用法:
    v2g image prepare <project_id>

流程:
    1. 读取 script.json
    2. 找出所有 image_content.source_method 非空但 image_path 为空的 segment
    3. 调用 image_source.source_image() 获取图片
    4. 将结果路径写回 script.json 的 image_path
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from v2g.config import Config
from v2g.image_source import source_image


def prepare_images(cfg: Config, project_id: str) -> int:
    """扫描 script.json，自动配图，返回成功配图数量。"""
    output_dir = cfg.output_dir / project_id
    script_path = output_dir / "script.json"
    images_dir = output_dir / "images"

    if not script_path.exists():
        raise FileNotFoundError(f"script.json 不存在: {script_path}")

    script = json.loads(script_path.read_text(encoding="utf-8"))
    segments = script.get("segments", [])

    count = 0
    modified = False

    for seg in segments:
        ic = seg.get("image_content")
        if not ic:
            continue

        method = ic.get("source_method", "")
        query = ic.get("source_query", "")
        current_path = ic.get("image_path", "")

        # 跳过：没有 source_method 或已有 image_path
        if not method or not query:
            continue
        if current_path and current_path != "":
            # 已经有路径了，检查文件是否存在
            full = output_dir / current_path
            if full.exists():
                continue

        # 执行配图
        click.echo(f"   [{seg.get('id', '?')}] {method}: {query[:50]}")
        kwargs = {}
        api_key = _get_api_key(cfg, method)
        if api_key:
            kwargs["api_key"] = api_key
        result = source_image(
            query=query,
            method=method,
            output_dir=images_dir,
            **kwargs,
        )

        if result:
            # 写入相对路径（相对于 output/{pid}/）
            rel_path = str(result.relative_to(output_dir))
            ic["image_path"] = rel_path
            modified = True
            count += 1
        else:
            click.echo(f"   ⚠️ [{seg.get('id', '?')}] 配图失败，保留原状")

    if modified:
        script_path.write_text(
            json.dumps(script, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        click.echo(f"\n✅ 配图完成: {count} 张，script.json 已更新")

    return count


def _get_api_key(cfg: Config, method: str) -> str:
    """根据配图方式获取对应的 API key。"""
    import os
    if method == "search":
        return os.environ.get("BING_IMAGE_API_KEY", "")
    if method == "generate":
        return os.environ.get("GPT_API_KEY", "")
    return ""
