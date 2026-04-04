"""从 vault 文件提取 URL + ideation 话题选择。"""

import re
from datetime import date
from pathlib import Path

import click


# ── 停用词 ──

_STOP_WORDS = frozenset(
    "的 是 与 在 了 和 或 从 到 为 对 把 被 让 给 用 向 "
    "这 那 个 们 中 上 下 也 都 就 又 而 但 如 如果 因为 所以 "
    "for the a an of to in and or is are was were be been "
    "by on at with from as it its this that not but if how what "
    "can will do does did has have had".split()
)


# ── URL 提取 ──


def extract_urls_from_vault(vault_path: Path, today: date) -> list[dict]:
    """从当天的 GitHub/HN/Twitter/Ideation 报告中提取 URL + 标题。

    返回: [{"url": str, "title": str, "source_type": str}, ...]
    """
    results = []

    # GitHub: ### [name](https://github.com/user/repo)
    gh_file = vault_path / "scout" / "github" / f"{today}-trending.md"
    if gh_file.exists():
        content = gh_file.read_text(encoding="utf-8")
        for m in re.finditer(r"### \[([^\]]+)\]\((https://github\.com/[^\)]+)\)", content):
            results.append({"url": m.group(2), "title": m.group(1), "source_type": "github"})

    # HN: ### [title](hn_url) + [原文链接](source_url)
    # 原文链接的标题从上方 ### 标题行关联
    hn_file = vault_path / "scout" / "hn" / f"{today}-hn.md"
    if hn_file.exists():
        content = hn_file.read_text(encoding="utf-8")
        # 按 ### 块拆分，同时提取标题和原文链接
        hn_blocks = re.split(r"^### ", content, flags=re.MULTILINE)
        for block in hn_blocks[1:]:
            # 提取 HN 标题
            title_match = re.match(r"\[([^\]]+)\]\((https://news\.ycombinator\.com/[^\)]+)\)", block)
            block_title = title_match.group(1) if title_match else ""
            if title_match:
                results.append({"url": title_match.group(2), "title": block_title, "source_type": "hn"})
            # 原文链接继承块标题
            for m in re.finditer(r"\[原文链接\]\(([^\)]+)\)", block):
                results.append({"url": m.group(1), "title": block_title, "source_type": "article"})

    # Twitter: ### @author + > text + [链接](url)
    # 推文链接对 NotebookLM 价值有限（x.com 反爬），提取推文中嵌入的外部链接更有用
    tw_file = vault_path / "scout" / "twitter" / f"{today}-curated.md"
    if tw_file.exists():
        content = tw_file.read_text(encoding="utf-8")
        blocks = re.split(r"^### ", content, flags=re.MULTILINE)
        for block in blocks[1:]:
            quote = re.search(r"^> (.+)", block, re.MULTILINE)
            title = quote.group(1)[:80] if quote else ""
            # 推文内嵌的外部链接（非 t.co 短链，取实际 URL）
            for m in re.finditer(r"https://(?!x\.com|t\.co)[^\s\)]+", block):
                results.append({"url": m.group(0), "title": title, "source_type": "twitter"})
            # 推文自身链接作为备选
            tw_match = re.search(r"\[链接\]\((https://x\.com/[^\)]+)\)", block)
            if tw_match:
                results.append({"url": tw_match.group(1), "title": title, "source_type": "twitter"})

    # YouTube: 从 ideation 文件提取竞品视频 URL
    ideation_dir = vault_path / "scout" / "ideation"
    if ideation_dir.exists():
        for f in ideation_dir.glob(f"{today}-*.md"):
            content = f.read_text(encoding="utf-8")
            for m in re.finditer(r"\[([^\]]+)\]\((https://www\.youtube\.com/watch\?v=[^\)]+)\)", content):
                results.append({"url": m.group(2), "title": m.group(1), "source_type": "youtube"})

    return results


# ── URL 匹配 ──


_SOURCE_PRIORITY = {"youtube": 0, "article": 1, "github": 2, "hn": 3, "twitter": 4}


def _tokenize(text: str) -> list[str]:
    """分词：按空格/标点拆分，去停用词，去短词。"""
    tokens = re.split(r"[\s\-_/,.;:!?()（）【】「」""''·、。！？，；：]+", text.lower())
    return [t for t in tokens if t and len(t) >= 2 and t not in _STOP_WORDS]


def match_urls_to_topic(
    all_urls: list[dict], topic_info: dict, max_results: int = 8,
) -> list[dict]:
    """纯字符串匹配，按关键词命中数排序，返回 top N URL。

    策略：
    1. 按关键词匹配打分
    2. 每个 source_type 保证至少 1 个（如果有匹配的话）
    3. 剩余名额按分数排序填充

    topic_info: {"title": str, "angle_context": str}
    返回: [{"url", "title", "source_type", "match_score"}, ...]
    """
    keywords = _tokenize(topic_info.get("title", "") + " " + topic_info.get("angle_context", ""))
    if not keywords:
        return []

    scored = []
    for item in all_urls:
        target = (item.get("title", "") + " " + item.get("url", "")).lower()
        score = sum(1 for kw in keywords if kw in target)
        if score > 0:
            scored.append({**item, "match_score": score})

    if not scored:
        return []

    # 按 score 降序排序
    scored.sort(key=lambda x: (-x["match_score"], _SOURCE_PRIORITY.get(x["source_type"], 9)))

    # 每个 source_type 至少选 1 个最高分的
    selected = []
    seen_urls = set()
    by_type: dict[str, list[dict]] = {}
    for item in scored:
        by_type.setdefault(item["source_type"], []).append(item)

    for stype in ("youtube", "article", "github", "hn"):
        if stype in by_type:
            best = by_type[stype][0]
            if best["url"] not in seen_urls:
                selected.append(best)
                seen_urls.add(best["url"])

    # 剩余名额按分数排序填充
    for item in scored:
        if len(selected) >= max_results:
            break
        if item["url"] not in seen_urls:
            selected.append(item)
            seen_urls.add(item["url"])

    return selected


# ── Ideation 话题列表 ──


def list_ideation_topics(vault_path: Path, today: date) -> list[dict]:
    """扫描当天的 ideation 文件，返回话题列表。

    返回: [{"title": str, "tier": str, "angle_context": str, "source_path": Path}, ...]
    """
    ideation_dir = vault_path / "scout" / "ideation"
    if not ideation_dir.exists():
        return []

    topics = []
    for f in sorted(ideation_dir.glob(f"{today}-*.md")):
        content = f.read_text(encoding="utf-8")

        # 提取 frontmatter 中的 topic
        fm_match = re.search(r"^topic:\s*(.+)$", content, re.MULTILINE)
        if not fm_match:
            continue
        title = fm_match.group(1).strip()

        # 提取 Tier 1 推荐的第一个创意的完整段落作为 angle_context
        angle_context = _extract_tier1_context(content)

        topics.append({
            "title": title,
            "tier": "A" if angle_context else "",
            "angle_context": angle_context,
            "source_path": f,
        })

    return topics


def _extract_tier1_context(content: str) -> str:
    """从 ideation 内容中提取第一个 Tier 1 推荐的完整段落。"""
    # 去掉 YAML frontmatter
    content = re.sub(r"^---\n.*?\n---\n", "", content, count=1, flags=re.DOTALL)

    # 找所有创意条目（**N. 标题** 开头的段落）
    entries = re.split(r"\n(?=\*\*\d+\.)", content)
    for entry in entries:
        if "Tier 1" in entry:
            clean = re.sub(r"\*\*", "", entry).strip()
            return clean[:500]

    # fallback: 找"最终推荐"段落
    final = re.search(r"###?\s*最终推荐\s*\n(.+?)(?=\n###|\Z)", content, re.DOTALL)
    if final:
        return final.group(1).strip()[:500]

    return ""


# ── 交互选择 ──


def select_topic_interactive(topics: list[dict], topic_index: int | None = None) -> dict | None:
    """交互式选择话题。topic_index 非 None 时直接选择（非交互模式）。"""
    if not topics:
        click.echo("   ⚠️ 未找到 ideation 话题，请先运行 v2g scout all")
        return None

    if topic_index is not None:
        if 0 <= topic_index < len(topics):
            selected = topics[topic_index]
            click.echo(f"   📌 自动选择: {selected['title']}")
            return selected
        click.echo(f"   ⚠️ 话题索引 {topic_index} 超出范围 (0-{len(topics)-1})")
        return None

    if len(topics) == 1:
        click.echo(f"   📌 唯一话题: {topics[0]['title']}")
        return topics[0]

    click.echo("   📋 今日 ideation 话题:")
    for i, t in enumerate(topics):
        tier_tag = f" [Tier 1]" if t.get("tier") == "A" else ""
        click.echo(f"      [{i}] {t['title']}{tier_tag}")

    choice = click.prompt("   选择话题编号", type=int, default=0)
    if 0 <= choice < len(topics):
        return topics[choice]

    click.echo("   ⚠️ 无效选择")
    return None


# ── 竞品视频提取与选择 ──


def extract_youtube_from_ideation(ideation_path: Path) -> list[dict]:
    """从 ideation 文件提取竞品 YouTube 视频列表。

    返回: [{"channel": str, "title": str, "url": str, "video_id": str,
            "views": int, "likes": int, "comments": int}, ...]
    """
    content = ideation_path.read_text(encoding="utf-8")
    videos = []

    # 格式: - [频道] [标题](URL)\n  👁 views | ❤️ likes | 💬 comments
    pattern = re.compile(
        r"- \[([^\]]+)\] \[([^\]]+)\]\((https://www\.youtube\.com/watch\?v=([^)]+))\)\s*\n"
        r"\s*👁\s*([\d,]+)\s*\|\s*❤️\s*([\d,]+)\s*\|\s*💬\s*([\d,]+)",
    )
    for m in pattern.finditer(content):
        videos.append({
            "channel": m.group(1).strip(),
            "title": m.group(2).strip(),
            "url": m.group(3),
            "video_id": m.group(4),
            "views": int(m.group(5).replace(",", "")),
            "likes": int(m.group(6).replace(",", "")),
            "comments": int(m.group(7).replace(",", "")),
        })

    # 按播放量降序
    videos.sort(key=lambda v: -v["views"])
    return videos


def select_videos_auto(
    videos: list[dict], max_select: int = 2,
) -> list[dict]:
    """自动选择竞品视频：按播放量取 top N。

    已按播放量降序排列，直接取前 max_select 个。
    """
    if not videos:
        click.echo("   ⚠️ 未找到竞品视频")
        return []

    selected = videos[:max_select]
    click.echo(f"   📺 自动选择 {len(selected)} 个竞品视频（按播放量）:")
    for v in selected:
        click.echo(f"      👁 {v['views']:>8,} | [{v['channel'][:15]}] {v['title'][:50]}")

    return selected


def find_scout_scripts(vault_path: Path, today: date, topic_slug: str) -> list[Path]:
    """查找与话题匹配的 scout script 文件（hook/title/outline）。"""
    scripts_dir = vault_path / "scout" / "scripts"
    if not scripts_dir.exists():
        return []

    matched = []
    for prefix in ("hook", "title", "outline"):
        for f in scripts_dir.glob(f"{today}-{prefix}-*.md"):
            # slug 模糊匹配
            if topic_slug[:15] in f.stem:
                matched.append(f)
                break
    return matched
