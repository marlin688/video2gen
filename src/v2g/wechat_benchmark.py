"""公众号媒体基准对比。

默认抓取中国科技媒体前一天的公开文章样本，使用同一套
“媒体竞争力”口径和自家文章做横向对比。
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx

from v2g.wechat_pipeline import (
    IMAGE_RE,
    LINK_RE,
    _check,
    _extract_image_refs,
    _extract_title,
    _number_fact_count,
    _score_checks,
    _slugify,
    _source_domains,
    _strip_markdown,
    _wechat_readability_ok,
)


_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


SOURCE_CONFIGS = {
    "qbitai": {
        "name": "量子位",
        "kind": "wordpress",
        "api_url": "https://www.qbitai.com/wp-json/wp/v2/posts",
    },
    "jiqizhixin": {
        "name": "机器之心",
        "kind": "html",
        "listing_urls": ["https://www.jiqizhixin.com/articles", "https://www.jiqizhixin.com/rss"],
        "blocked_marker": "机器之心·数据服务",
    },
    "aiera": {
        "name": "新智元",
        "kind": "wordpress",
        "api_url": "https://aiera.com.cn/wp-json/wp/v2/posts",
    },
}


@dataclass
class BenchmarkArticle:
    source_key: str
    source_name: str
    title: str
    url: str
    published_at: str
    markdown: str
    html: str = ""
    discovery: str = "auto"


def run_benchmark(
    output_dir: Path,
    *,
    article_source: str | Path | None = None,
    target_date: date | None = None,
    per_source: int = 2,
    manual_urls: tuple[str, ...] = (),
    beat_margin: float = 0.0,
) -> dict:
    """抓取媒体样本并输出对比报告。"""
    resolved_date = target_date or yesterday_china()
    benchmark_dir = output_dir / "wechat_benchmark" / resolved_date.isoformat()
    benchmark_dir.mkdir(parents=True, exist_ok=True)

    articles: list[BenchmarkArticle] = []
    notes: list[dict[str, str]] = []

    for source_key, config in SOURCE_CONFIGS.items():
        try:
            found = discover_articles(source_key, config, resolved_date, per_source=per_source)
            articles.extend(found)
            if len(found) < per_source:
                notes.append({
                    "source": config["name"],
                    "level": "warning",
                    "message": f"只发现 {len(found)}/{per_source} 篇 {resolved_date.isoformat()} 样本",
                })
        except Exception as exc:  # noqa: BLE001 - benchmark should degrade per source
            notes.append({
                "source": config["name"],
                "level": "warning",
                "message": str(exc),
            })

    for raw in manual_urls:
        try:
            articles.append(fetch_manual_article(raw))
        except Exception as exc:  # noqa: BLE001
            notes.append({"source": "manual", "level": "warning", "message": f"{raw}: {exc}"})

    rows = []
    if article_source:
        own = load_local_article(article_source)
        rows.append(score_benchmark_article(own, source_label="AGI通识"))

    for article in articles:
        rows.append(score_benchmark_article(article))

    media_rows = [r for r in rows if r["source"] != "AGI通识"]
    benchmark_media_rows = [r for r in media_rows if r.get("eligible_for_average")]
    expected_source_names = [config["name"] for config in SOURCE_CONFIGS.values()]
    source_effective_counts = {
        name: sum(1 for row in benchmark_media_rows if row["source"] == name)
        for name in expected_source_names
    }
    source_total_counts = {
        name: sum(1 for row in media_rows if row["source"] == name)
        for name in expected_source_names
    }
    missing_effective_sources = [name for name, count in source_effective_counts.items() if count < 1]
    missing_sample_sources = [name for name, count in source_total_counts.items() if count < 1]
    own_rows = [r for r in rows if r["source"] == "AGI通识"]
    media_avg_all = round(sum(r["score_pct"] for r in media_rows) / len(media_rows), 1) if media_rows else 0.0
    media_avg = round(sum(r["score_pct"] for r in benchmark_media_rows) / len(benchmark_media_rows), 1) if benchmark_media_rows else 0.0
    media_top = max(benchmark_media_rows, key=lambda r: r["score_pct"]) if benchmark_media_rows else None
    media_top_score = media_top["score_pct"] if media_top else None
    own_score = own_rows[0]["score_pct"] if own_rows else None
    own_delta_vs_top = round(own_score - media_top_score, 1) if own_score is not None and media_top_score is not None else None
    own_beats_media_top = own_delta_vs_top is not None and own_delta_vs_top >= beat_margin

    report = {
        "target_date": resolved_date.isoformat(),
        "per_source": per_source,
        "beat_margin": beat_margin,
        "generated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "sources": expected_source_names,
        "media_average": media_avg,
        "media_average_all": media_avg_all,
        "media_effective_sample_count": len(benchmark_media_rows),
        "media_total_sample_count": len(media_rows),
        "source_effective_counts": source_effective_counts,
        "source_total_counts": source_total_counts,
        "missing_effective_sources": missing_effective_sources,
        "missing_sample_sources": missing_sample_sources,
        "media_top_score": media_top_score,
        "media_top_title": media_top["title"] if media_top else "",
        "media_top_source": media_top["source"] if media_top else "",
        "own_score": own_score,
        "own_delta_vs_media_avg": round(own_score - media_avg, 1) if own_score is not None and benchmark_media_rows else None,
        "own_delta_vs_media_top": own_delta_vs_top,
        "own_beats_media_top": own_beats_media_top,
        "articles": sorted(rows, key=lambda r: r["score_pct"], reverse=True),
        "notes": notes,
    }
    (benchmark_dir / "benchmark.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (benchmark_dir / "benchmark.md").write_text(render_benchmark_markdown(report), encoding="utf-8")
    return {"report": report, "benchmark_dir": benchmark_dir}


def yesterday_china() -> date:
    return datetime.now(ZoneInfo("Asia/Shanghai")).date() - timedelta(days=1)


def discover_articles(source_key: str, config: dict[str, Any], target: date, *, per_source: int) -> list[BenchmarkArticle]:
    kind = config["kind"]
    if kind == "wordpress":
        return discover_wordpress_articles(source_key, config, target, per_source=per_source)
    if kind == "html":
        return discover_html_articles(source_key, config, target, per_source=per_source)
    raise ValueError(f"unsupported source kind: {kind}")


def discover_wordpress_articles(source_key: str, config: dict[str, Any], target: date, *, per_source: int) -> list[BenchmarkArticle]:
    params = {
        "per_page": max(10, per_source * 5),
        "after": f"{target.isoformat()}T00:00:00",
        "before": f"{target.isoformat()}T23:59:59",
    }
    with httpx.Client(headers=_BROWSER_HEADERS, timeout=30.0, follow_redirects=True) as client:
        resp = client.get(config["api_url"], params=params)
        resp.raise_for_status()
        items = resp.json()
    return wordpress_items_to_articles(source_key, config["name"], items, per_source=per_source)


def wordpress_items_to_articles(source_key: str, source_name: str, items: list[dict[str, Any]], *, per_source: int) -> list[BenchmarkArticle]:
    articles: list[BenchmarkArticle] = []
    for item in items[:per_source]:
        rendered = item.get("content", {}).get("rendered", "") or ""
        title = _clean_html(item.get("title", {}).get("rendered", "") or "")
        articles.append(
            BenchmarkArticle(
                source_key=source_key,
                source_name=source_name,
                title=title or "未命名文章",
                url=item.get("link", ""),
                published_at=item.get("date", ""),
                markdown=html_to_markdownish(rendered),
                html=rendered,
                discovery="wordpress_api",
            )
        )
    return articles


def discover_html_articles(source_key: str, config: dict[str, Any], target: date, *, per_source: int) -> list[BenchmarkArticle]:
    with httpx.Client(headers=_BROWSER_HEADERS, timeout=30.0, follow_redirects=True) as client:
        for listing_url in config.get("listing_urls", []):
            resp = client.get(listing_url)
            resp.raise_for_status()
            text = resp.text
            marker = config.get("blocked_marker")
            if marker and marker in text:
                raise RuntimeError(f"{config['name']}公开列表页返回数据服务页，无法稳定自动抓取；请用 --manual-url 补充样本")
            links = _extract_candidate_links(text, base=listing_url)
            articles = []
            for link in links:
                fetched = fetch_url_article(link, source_key=source_key, source_name=config["name"], discovery="html_listing")
                if fetched and _same_day(fetched.published_at, target):
                    articles.append(fetched)
                if len(articles) >= per_source:
                    return articles
    return []


def fetch_manual_article(raw: str) -> BenchmarkArticle:
    source_key, url = _parse_manual_url(raw)
    config = SOURCE_CONFIGS.get(source_key, {"name": source_key, "kind": "manual"})
    article = fetch_url_article(url, source_key=source_key, source_name=config["name"], discovery="manual")
    if not article:
        raise RuntimeError("无法抓取正文")
    return article


def fetch_url_article(url: str, *, source_key: str, source_name: str, discovery: str) -> BenchmarkArticle | None:
    with httpx.Client(headers=_BROWSER_HEADERS, timeout=30.0, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        html_text = resp.text
    title = _meta_content(html_text, "og:title") or _title_tag(html_text) or "未命名文章"
    published = _meta_content(html_text, "article:published_time") or _json_ld_date(html_text)
    markdown = html_to_markdownish(html_text)
    if len(_strip_markdown(markdown)) < 200:
        return None
    return BenchmarkArticle(
        source_key=source_key,
        source_name=source_name,
        title=_clean_html(title),
        url=url,
        published_at=published,
        markdown=markdown,
        html=html_text,
        discovery=discovery,
    )


def load_local_article(source: str | Path) -> BenchmarkArticle:
    source_path = Path(source)
    if source_path.is_dir():
        md = _prefer_existing(source_path, ("article-pro.md", "article.md"))
        html_path = _prefer_existing(source_path, ("article-pro.html", "article.html"))
    else:
        md = source_path
        html_path = source_path.with_suffix(".html") if source_path.with_suffix(".html").exists() else None
    if not md or not md.exists():
        raise FileNotFoundError(f"no markdown found: {source}")
    markdown = md.read_text(encoding="utf-8")
    html_text = html_path.read_text(encoding="utf-8") if html_path else ""
    return BenchmarkArticle(
        source_key="agi",
        source_name="AGI通识",
        title=_extract_title(markdown) or md.stem,
        url=str(source_path),
        published_at="",
        markdown=markdown,
        html=html_text,
        discovery="local",
    )


def score_benchmark_article(article: BenchmarkArticle, *, source_label: str | None = None) -> dict:
    text = article.markdown
    html_text = article.html
    plain = _strip_markdown(html_to_markdownish(html_text) if html_text else text)
    image_refs = _extract_image_refs(text) + _html_image_refs(html_text)
    image_set = set(image_refs)
    links = [link for link in LINK_RE.findall(text) + _html_links(html_text) if link not in image_set]
    headings = len(re.findall(r"^#{1,3}\s+", text, flags=re.M)) + len(re.findall(r"<h[1-3]\b", html_text, flags=re.I))
    captions = _caption_count(text, html_text)
    number_facts = _number_fact_count(text + "\n" + html_to_markdownish(html_text))
    checks = benchmark_checks(
        title=article.title,
        text=text,
        plain=plain,
        image_count=len(set(image_refs)),
        captions=captions,
        links=links,
        headings=headings,
        number_facts=number_facts,
    )
    score, max_score, pct = _score_checks(checks)
    return {
        "source": source_label or article.source_name,
        "source_key": article.source_key,
        "title": article.title,
        "url": article.url,
        "published_at": article.published_at,
        "score": score,
        "max_score": max_score,
        "score_pct": pct,
        "eligible_for_average": len(plain) >= 1000,
        "checks": checks,
        "metrics": {
            "chars": len(plain),
            "headings": headings,
            "images": len(set(image_refs)),
            "captions": captions,
            "links": len(set(links)),
            "unique_source_domains": len(_source_domains(links)),
            "number_facts": number_facts,
        },
        "discovery": article.discovery,
    }


def benchmark_checks(
    *,
    title: str,
    text: str,
    plain: str,
    image_count: int,
    captions: int,
    links: list[str],
    headings: int,
    number_facts: int,
) -> list[dict]:
    opening = text[:700]
    return [
        _check("title_hook", any(k in title for k in ("！", "？", "：", "但", "像", "首", "新", "刚刚", "一夜", "万", "亿")), 10, "标题有新闻钩子/冲突/强信号"),
        _check("opening_facts", number_facts >= 2 and _has_news_opening(opening), 12, "开头有硬事实或明确冲突"),
        _check("length", 1800 <= len(plain) <= 9000, 8, "篇幅适合公众号深度图文"),
        _check("structure", headings >= 3, 8, "有清晰章节结构"),
        _check("image_density", image_count >= 3, 12, "有足够图像/截图/配图承载阅读节奏"),
        _check("caption_payload", captions >= max(2, min(6, image_count // 2)), 10, "图注或图片上下文能解释图片价值"),
        _check("specifics", number_facts >= 5, 10, "有足够数字、时间、规模事实"),
        _check("people_or_case", _has_people_or_case(text), 10, "有具体人物、机构或案例现场"),
        _check("source_signal", len(_source_domains(links)) >= 2 or len(links) >= 3, 8, "有外部链接/来源信号"),
        _check("mobile_rhythm", _wechat_readability_ok(text), 6, "段落节奏适合移动端阅读"),
        _check("takeaway", _has_takeaway(text), 6, "结尾或正文有可传播判断"),
    ]


def render_benchmark_markdown(report: dict) -> str:
    lines = [
        f"# 公众号媒体基准评分：{report['target_date']}",
        "",
        f"- 有效媒体样本均分：{report['media_average']}/100",
        f"- 全量媒体样本均分：{report.get('media_average_all', report['media_average'])}/100",
        f"- 有效样本：{report.get('media_effective_sample_count', 0)}/{report.get('media_total_sample_count', 0)}",
        f"- 缺失样本来源：{', '.join(report.get('missing_sample_sources') or []) or '无'}",
        f"- 无有效深度样本来源：{', '.join(report.get('missing_effective_sources') or []) or '无'}",
        f"- 媒体最高分：{report.get('media_top_score') if report.get('media_top_score') is not None else '样本不足'}/100",
    ]
    if report.get("own_score") is not None:
        lines.append(f"- AGI通识分数：{report['own_score']}/100")
        delta = report.get("own_delta_vs_media_avg")
        lines.append(f"- 相对媒体均值：{delta:+.1f}" if delta is not None else "- 相对媒体均值：样本不足")
        top_delta = report.get("own_delta_vs_media_top")
        lines.append(f"- 相对媒体最高分：{top_delta:+.1f}" if top_delta is not None else "- 相对媒体最高分：样本不足")
        lines.append(f"- 是否高于媒体最高分：{'是' if report.get('own_beats_media_top') else '否'}")
    if report.get("notes"):
        lines.append("")
        lines.append("## 抓取备注")
        for note in report["notes"]:
            lines.append(f"- {note['source']}：{note['message']}")
    lines.extend([
        "",
        "## 排名",
        "",
        "| 排名 | 来源 | 分数 | 有效 | 标题 | 字数 | 图 | 数字事实 |",
        "|---:|---|---:|---|---|---:|---:|---:|",
    ])
    for idx, row in enumerate(report["articles"], start=1):
        title = row["title"].replace("|", "\\|")
        url = row.get("url") or ""
        linked = f"[{title}]({url})" if url.startswith("http") else title
        metrics = row["metrics"]
        lines.append(
            f"| {idx} | {row['source']} | {row['score_pct']} | {'是' if row.get('eligible_for_average') else '否'} | {linked} | "
            f"{metrics['chars']} | {metrics['images']} | {metrics['number_facts']} |"
        )
    lines.append("")
    lines.append("## 明细")
    for row in report["articles"]:
        failed = [c for c in row["checks"] if not c["passed"]]
        lines.append("")
        lines.append(f"### {row['source']}：{row['title']}")
        lines.append(f"- 分数：{row['score_pct']}/100")
        lines.append(f"- 指标：{row['metrics']}")
        if failed:
            lines.append("- 扣分项：" + "；".join(f"{c['label']}(-{c['points']})" for c in failed))
        else:
            lines.append("- 扣分项：无")
    lines.append("")
    return "\n".join(lines)


def html_to_markdownish(html_text: str) -> str:
    if not html_text:
        return ""
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", "", html_text)
    text = re.sub(r"(?is)<figcaption[^>]*>(.*?)</figcaption>", lambda m: "\n图注：" + _clean_html(m.group(1)) + "\n", text)
    text = re.sub(r"(?is)<h([1-3])[^>]*>(.*?)</h\1>", lambda m: "\n" + "#" * int(m.group(1)) + " " + _clean_html(m.group(2)) + "\n", text)
    text = re.sub(r"(?is)<img[^>]*src=[\"']([^\"']+)[\"'][^>]*>", lambda m: f"\n![图]({m.group(1)})\n", text)
    text = re.sub(r"(?is)</p>|<br\s*/?>|</div>|</li>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", "", text)
    text = html.unescape(text)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _html_image_refs(html_text: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r"<img[^>]*src=[\"']([^\"']+)[\"']", html_text or "", flags=re.I)]


def _html_links(html_text: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r"<a[^>]*href=[\"']([^\"']+)[\"']", html_text or "", flags=re.I) if m.group(1).startswith("http")]


def _caption_count(text: str, html_text: str) -> int:
    markdown_count = len(re.findall(r"^图注[:：]", text, flags=re.M))
    figcaption_count = len(re.findall(r"<figcaption\b|pgc-img-caption|wp-block-image.*?<em>图[:：]", html_text or "", flags=re.I | re.S))
    return markdown_count + figcaption_count


def _has_news_opening(text: str) -> bool:
    return any(k in text for k in ("据", "宣布", "发布", "显示", "称", "首次", "已经", "最新", "但", "问题"))


def _has_people_or_case(text: str) -> bool:
    return any(k in text for k in ("创始人", "CEO", "CTO", "团队", "公司", "研究员", "用户", "开发者", "案例", "现场", "表示"))


def _has_takeaway(text: str) -> bool:
    ending = text[-1600:]
    return any(k in ending for k in ("这意味着", "所以", "一句话", "结论", "核心", "真正", "接下来", "未来", "建议", "竞争层"))


def _clean_html(text: str) -> str:
    text = re.sub(r"(?is)<[^>]+>", "", text)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def _extract_candidate_links(html_text: str, *, base: str) -> list[str]:
    host = urlparse(base).netloc
    links = []
    for match in re.finditer(r"<a[^>]*href=[\"']([^\"']+)[\"']", html_text, flags=re.I):
        href = match.group(1)
        if href.startswith("/"):
            href = f"https://{host}{href}"
        if host in urlparse(href).netloc and href not in links:
            links.append(href)
    return links


def _parse_manual_url(raw: str) -> tuple[str, str]:
    if "=" in raw:
        source, url = raw.split("=", 1)
        return source.strip(), url.strip()
    host = urlparse(raw).netloc
    if "qbitai" in host:
        return "qbitai", raw
    if "jiqizhixin" in host:
        return "jiqizhixin", raw
    if "aiera" in host or "aixinzhijie" in host:
        return "aiera", raw
    return _slugify(host), raw


def _same_day(value: str, target: date) -> bool:
    if not value:
        return False
    match = re.search(r"\d{4}-\d{2}-\d{2}", value)
    return bool(match and match.group(0) == target.isoformat())


def _prefer_existing(source_path: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        path = source_path / name
        if path.exists():
            return path
    return None


def _meta_content(html_text: str, prop: str) -> str:
    patterns = [
        rf"<meta[^>]+property=[\"']{re.escape(prop)}[\"'][^>]+content=[\"']([^\"']+)[\"']",
        rf"<meta[^>]+content=[\"']([^\"']+)[\"'][^>]+property=[\"']{re.escape(prop)}[\"']",
        rf"<meta[^>]+name=[\"']{re.escape(prop)}[\"'][^>]+content=[\"']([^\"']+)[\"']",
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text, flags=re.I)
        if match:
            return html.unescape(match.group(1)).strip()
    return ""


def _title_tag(html_text: str) -> str:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html_text)
    return _clean_html(match.group(1)) if match else ""


def _json_ld_date(html_text: str) -> str:
    match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html_text)
    return match.group(1) if match else ""
