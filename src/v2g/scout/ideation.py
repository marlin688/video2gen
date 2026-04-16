"""创意构思 + 竞品分析：YouTube 竞品搜索 + LLM 竞争格局分析 + 创意生成。"""

import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import click


def search_youtube_videos(
    api_key: str,
    query: str,
    max_results: int = 50,
    region: str = "US",
    since_days: int = 30,
) -> list[dict]:
    """YouTube Data API v3 搜索 + 统计数据。

    两步调用：search (获取视频 ID) → videos (获取 statistics)。
    配额: ~150 units/次，免费 10,000 units/天。
    """
    import httpx

    if not api_key:
        return []

    click.echo(f"   🔍 YouTube 搜索: {query[:50]}")

    # Step 1: search（优先拉最近内容，再按热度重排）
    published_after = (
        (datetime.now(timezone.utc) - timedelta(days=since_days))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    try:
        resp = httpx.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "type": "video",
                "q": query,
                "maxResults": min(max_results, 50),
                "regionCode": region,
                "order": "date",
                "publishedAfter": published_after,
                "key": api_key,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
    except Exception as e:
        click.echo(f"   ⚠️ YouTube 搜索失败: {e}")
        return []

    if not items:
        click.echo("   ℹ️ YouTube 无结果")
        return []

    # Step 2: 批量获取 statistics
    video_ids = [item["id"]["videoId"] for item in items if "videoId" in item.get("id", {})]
    if not video_ids:
        return []

    stats_map = {}
    # 分批请求（每次最多 50 个）
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        try:
            stats_resp = httpx.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "statistics,contentDetails",
                    "id": ",".join(batch),
                    "key": api_key,
                },
                timeout=30.0,
            )
            stats_resp.raise_for_status()
            for v in stats_resp.json().get("items", []):
                stats_map[v["id"]] = v
        except Exception as e:
            click.echo(f"   ⚠️ YouTube statistics 获取失败: {e}")

    # 合并
    videos = []
    for item in items:
        vid = item.get("id", {}).get("videoId", "")
        if not vid:
            continue
        snippet = item.get("snippet", {})
        stats_item = stats_map.get(vid, {})
        stats = stats_item.get("statistics", {})
        videos.append(_normalize_video(vid, snippet, stats))

    # 二次排序：近期热度优先（播放量 + 互动）并兼顾新鲜度
    now = datetime.now(timezone.utc).date()

    def _score(v: dict) -> float:
        try:
            pub = date.fromisoformat(v.get("published_at", ""))
        except Exception:
            pub = now
        age_days = max((now - pub).days, 0)
        freshness = 1.0 / (1.0 + age_days / 7.0)
        engagement = v.get("views", 0) + 2 * v.get("likes", 0) + 3 * v.get("comments", 0)
        return engagement * freshness

    videos.sort(key=_score, reverse=True)

    click.echo(f"   ✅ 找到 {len(videos)} 个视频 (最近 {since_days} 天)")
    return videos


def _normalize_video(video_id: str, snippet: dict, statistics: dict) -> dict:
    return {
        "video_id": video_id,
        "title": snippet.get("title", ""),
        "channel": snippet.get("channelTitle", ""),
        "published_at": snippet.get("publishedAt", "")[:10],
        "views": int(statistics.get("viewCount", 0)),
        "likes": int(statistics.get("likeCount", 0)),
        "comments": int(statistics.get("commentCount", 0)),
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }


def analyze_competition(
    videos: list[dict], topic: str, model: str, context: str = ""
) -> str:
    """LLM 竞争格局分析 + 创意生成。"""
    from v2g.llm import call_llm
    from v2g.scout import _load_prompt

    system_prompt = _load_prompt("scout_ideation.md")

    # 构造视频摘要
    if videos:
        video_lines = []
        for v in videos[:30]:  # 限制 30 个
            video_lines.append(
                f"- [{v['channel']}] {v['title']}\n"
                f"  👁 {v['views']:,} | ❤️ {v['likes']:,} | 💬 {v['comments']:,} | {v['published_at']}\n"
                f"  {v['url']}"
            )
        user_message = f"话题: {topic}\n\n## YouTube 竞品视频\n\n" + "\n\n".join(video_lines)
    else:
        user_message = (
            f"话题: {topic}\n\n"
            "（无 YouTube 竞品数据，请基于话题本身和你对 AI Tech 领域的理解生成创意）"
        )

    if context:
        user_message += f"\n\n## 背景参考\n\n{context}"

    try:
        return call_llm(system_prompt, user_message, model, temperature=0.4, max_tokens=3000)
    except Exception as e:
        click.echo(f"   ⚠️ LLM 分析失败: {e}")
        return ""


def extract_topics_from_daily(vault_path: Path, today: date) -> list[str]:
    """从 daily digest 的'内容创作建议'部分提取话题。"""
    daily_path = vault_path / "daily" / f"{today}.md"
    if not daily_path.exists():
        return []

    content = daily_path.read_text(encoding="utf-8")

    # 质量门控：digest 太短或含"不完整/缺失"等信号说明数据质量差，不提取话题
    _bad_signals = ("不完整", "缺失", "无法生成", "需要完整", "没有可用")
    if len(content.strip()) < 200 or any(s in content[:300] for s in _bad_signals):
        return []

    # 截取"内容创作建议"部分（到下一个 ### 或文件结束）
    match = re.search(r"###?\s*内容创作建议(.*?)(?=###|\Z)", content, re.DOTALL)
    section = match.group(1) if match else content

    topics = []
    # 模式1: **① 选题标题** 或 **选题一：标题**
    topics.extend(re.findall(r"\*\*[①②③④⑤\d]*[.、:：]?\s*(.+?)\*\*", section))
    # 模式2: 「选题」
    topics.extend(re.findall(r"[「「](.+?)[」」]", section))

    # 过滤明显不是话题的内容（知识源名称、通用标签等）
    _noise = {"GitHub 趋势", "Hacker News", "Twitter 精选", "文章摘要",
              "每日汇总", "知识源", "内容创作", "汇总"}

    # 去重（模糊匹配：如果 A 是 B 的子串则视为重复），过滤过短/过长/噪音
    unique = []
    for t in topics:
        t = t.strip().strip("「」「」""\"'")
        if len(t) <= 4 or len(t) >= 50:
            continue
        if t in _noise:
            continue
        # 检查是否已有类似话题
        is_dup = any(t in existing or existing in t for existing in unique)
        if not is_dup:
            unique.append(t)
    return unique[:5]


def _topic_slug(topic: str) -> str:
    """生成文件名友好的 slug。"""
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "-", topic)[:30].strip("-")
    return slug or "untitled"


def run_ideation(cfg, topic: str | None = None, from_daily: bool = False) -> list[Path]:
    """创意构思主流程。"""
    from v2g.scout.obsidian import ObsidianWriter

    click.echo("💡 创意构思 + 竞品分析")

    writer = ObsidianWriter(cfg.obsidian_vault_path)
    today = date.today()

    # 确定话题列表
    topics = []
    if topic:
        topics = [topic]
    elif from_daily:
        topics = extract_topics_from_daily(writer.vault, today)
        if topics:
            click.echo(f"   📋 从 daily digest 提取 {len(topics)} 个话题:")
            for t in topics:
                click.echo(f"      • {t}")
        else:
            click.echo("   ℹ️ 未找到今日 daily digest 或无可提取话题")
            return []

    if not topics:
        click.echo("   ℹ️ 无话题可分析")
        return []

    # 读取今日知识源上下文（给 LLM 参考）
    context = ""
    for source_file in [
        writer.vault / "scout" / "github" / f"{today}-trending.md",
        writer.vault / "scout" / "hn" / f"{today}-hn.md",
    ]:
        if source_file.exists():
            # 只取分析部分（前 1000 字），避免 prompt 过长
            text = source_file.read_text(encoding="utf-8")[:1000]
            context += f"\n\n{text}"

    paths = []
    for t in topics:
        click.echo(f"\n   📌 分析话题: {t}")

        # YouTube 搜索
        videos = search_youtube_videos(cfg.youtube_api_key, t)
        if not videos and cfg.youtube_api_key:
            click.echo("   ℹ️ YouTube 无竞品数据")
        elif not cfg.youtube_api_key:
            click.echo("   ℹ️ YOUTUBE_API_KEY 未设置，降级模式（无竞品数据）")

        # LLM 分析
        click.echo("   🤖 LLM 竞品分析中...")
        analysis = analyze_competition(videos, t, cfg.scout_model, context)

        # Obsidian 输出
        path = _write_ideation_report(writer, today, t, videos, analysis)
        click.echo(f"   📝 已写入: {path}")
        paths.append(path)

    return paths


def _write_ideation_report(
    writer, today: date, topic: str, videos: list[dict], analysis: str
) -> Path:
    slug = _topic_slug(topic)
    ideation_dir = writer.vault / "scout" / "ideation"
    ideation_dir.mkdir(parents=True, exist_ok=True)
    path = ideation_dir / f"{today}-{slug}.md"

    lines = [
        "---",
        f"date: {today}",
        "source: ideation",
        f"topic: {topic}",
        f"tags: [ideation, competitive-analysis]",
        "---",
        "",
        f"# 创意构思: {topic}",
        "",
    ]

    if analysis:
        lines += [analysis, ""]

    if videos:
        lines.append(f"## 竞品视频 ({len(videos)} 个)\n")
        for v in videos[:20]:
            lines.append(f"- [{v['channel']}] [{v['title']}]({v['url']})")
            lines.append(
                f"  👁 {v['views']:,} | ❤️ {v['likes']:,} | 💬 {v['comments']:,} | 🗓 {v.get('published_at', '')}"
            )
            lines.append("")
    else:
        lines.append("*无 YouTube 竞品数据（YOUTUBE_API_KEY 未设置或搜索无结果）*\n")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path
