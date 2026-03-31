"""Stage 1: 从 youtube-trending CSV 中选片。"""

import csv
from pathlib import Path

import click


def load_videos(csv_path: str, category: str | None = None,
                min_views: int = 0) -> list[dict]:
    """读取 CSV 并按条件筛选。"""
    path = Path(csv_path)
    if not path.exists():
        raise click.ClickException(f"CSV 文件不存在: {csv_path}")

    videos = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            view_count = int(row.get("view_count", 0) or 0)
            if view_count < min_views:
                continue
            if category and category.lower() not in row.get("category_name", "").lower():
                continue
            videos.append(row)

    # 按播放量降序
    videos.sort(key=lambda v: int(v.get("view_count", 0) or 0), reverse=True)
    return videos


def _format_duration(seconds: int) -> str:
    """秒 → 可读时长。"""
    h, m = divmod(seconds, 3600)
    m, s = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _format_views(count: int) -> str:
    """播放量格式化。"""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return str(count)


def interactive_select(csv_path: str, category: str | None = None,
                       min_views: int = 0, limit: int = 20) -> dict | None:
    """交互式选片：展示列表，用户输入编号。"""
    videos = load_videos(csv_path, category, min_views)
    if not videos:
        click.echo("未找到符合条件的视频")
        return None

    display = videos[:limit]
    click.echo(f"\n📺 共 {len(videos)} 个视频 (展示前 {len(display)} 个)\n")

    # 收集所有分类
    categories = sorted(set(v.get("category_name", "?") for v in display))
    if len(categories) > 1:
        click.echo(f"   分类: {', '.join(categories)}\n")

    click.echo(f"{'#':>3}  {'播放量':>8}  {'时长':>7}  {'频道':20}  标题")
    click.echo("-" * 90)
    for i, v in enumerate(display, 1):
        views = _format_views(int(v.get("view_count", 0) or 0))
        dur = _format_duration(int(v.get("duration_seconds", 0) or 0))
        channel = v.get("channel_name", "?")[:20]
        title = v.get("title", "?")[:50]
        click.echo(f"{i:>3}  {views:>8}  {dur:>7}  {channel:20}  {title}")

    click.echo()
    while True:
        choice = click.prompt("选择视频编号 (0 取消)", type=int, default=0)
        if choice == 0:
            return None
        if 1 <= choice <= len(display):
            return display[choice - 1]
        click.echo(f"请输入 1-{len(display)} 之间的数字")
