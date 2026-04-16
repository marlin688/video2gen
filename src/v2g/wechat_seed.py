"""微信公众号文章图片入库（Local-first 素材库种子构建）。"""

from __future__ import annotations

import hashlib
import html
import json
import re
import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import httpx

from v2g.asset_store import AssetMeta, AssetStore
from v2g.config import Config

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

_IMAGE_HEADERS = {
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}

_SOF_MARKERS = {
    0xC0, 0xC1, 0xC2, 0xC3,
    0xC5, 0xC6, 0xC7,
    0xC9, 0xCA, 0xCB,
    0xCD, 0xCE, 0xCF,
}

_PRODUCT_HINTS = {
    "openai": {"openai", "chatgpt", "gpt", "codex"},
    "claude-code": {"claude code", "claude-code"},
    "claude": {"claude", "anthropic"},
    "google": {"google"},
    "gemini": {"gemini"},
    "deepseek": {"deepseek"},
    "github": {"github"},
    "cursor": {"cursor"},
    "vscode": {"vscode", "vs code"},
}

_DIAGRAM_HINTS = ("架构", "框架", "流程", "图解", "结构图", "拓扑")
_WARNING_HINTS = ("封禁", "风险", "漏洞", "事故", "泄露", "崩溃")
_COMPARE_HINTS = ("对比", "横评", "vs", "PK")
_DEMO_HINTS = ("实测", "上手", "体验", "演示", "教程")
_SUMMARY_HINTS = ("盘点", "总结", "周报", "日报", "趋势", "报告")


@dataclass
class _ArticleMeta:
    url: str
    title: str
    account: str
    image_urls: list[str]


def ingest_wechat_seed(
    cfg: Config,
    *,
    article_urls: list[str],
    seed_id: str,
    allow_accounts: list[str] | None = None,
    target_total: int = 100,
    per_article_limit: int = 8,
    min_width: int = 960,
    min_height: int = 540,
    min_bytes: int = 30_000,
    timeout: float = 25.0,
    dry_run: bool = False,
) -> dict:
    """从公众号文章批量抓图并写入 assets.db。"""
    urls = _dedupe_urls(article_urls)
    if not urls:
        return {
            "seed_id": seed_id,
            "target_total": target_total,
            "added_this_run": 0,
            "skip_reason_count": {"empty_urls": 1},
            "items": [],
        }

    image_dir = cfg.output_dir / "asset_library" / "images" / _safe_slug(seed_id)
    seed_dir = cfg.output_dir / "asset_library" / "seeds"
    if not dry_run:
        image_dir.mkdir(parents=True, exist_ok=True)
        seed_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    added = 0
    fetched_articles = 0
    scanned_images = 0
    skip_reason_count: dict[str, int] = {}
    by_visual_type: dict[str, int] = {}
    items: list[dict] = []
    seen_hashes: set[str] = set()

    with httpx.Client(
        headers={**_BROWSER_HEADERS, **_IMAGE_HEADERS},
        follow_redirects=True,
        timeout=timeout,
        trust_env=False,
    ) as client, AssetStore(cfg.output_dir / "assets.db") as store:
        next_seq = _next_sequence(store, seed_id)
        for article_url in urls:
            if added >= target_total:
                break
            article = _fetch_article_meta(client, article_url)
            if article is None:
                _inc(skip_reason_count, "article_fetch_failed")
                continue
            if allow_accounts and not _account_allowed(article.account, allow_accounts):
                _inc(skip_reason_count, "account_not_whitelisted")
                continue
            fetched_articles += 1

            taken = 0
            for raw_img_url in article.image_urls:
                if added >= target_total or taken >= per_article_limit:
                    break
                scanned_images += 1

                candidates = _image_candidates(raw_img_url)
                result = _download_best_image(
                    client,
                    article_url=article.url,
                    candidates=candidates,
                    min_bytes=min_bytes,
                    min_width=min_width,
                    min_height=min_height,
                )
                if result is None:
                    _inc(skip_reason_count, "quality_or_download_failed")
                    continue

                img_bytes, final_url, ext, width, height, digest = result
                if digest in seen_hashes:
                    _inc(skip_reason_count, "duplicate_in_run")
                    continue
                seen_hashes.add(digest)

                existing = store.get_by_hash(digest)
                if existing and existing.file_path and Path(existing.file_path).exists():
                    _inc(skip_reason_count, "duplicate_existing")
                    continue

                visual_type = _infer_visual_type(article.title)
                mood = _infer_mood(article.title)
                tags = _make_tags(article, final_url)
                products = _infer_products(article.title, tags)
                clip_id = f"{seed_id}-{next_seq:03d}"
                next_seq += 1
                filename = (
                    f"{_safe_slug(article.account or 'wechat')}_"
                    f"{_safe_slug(article.title)[:48]}_{digest[:10]}{ext}"
                )
                file_path = image_dir / filename

                if not dry_run:
                    file_path.write_bytes(img_bytes)

                meta = AssetMeta(
                    clip_id=clip_id,
                    source_video=seed_id,
                    time_range_start=0.0,
                    time_range_end=0.0,
                    duration=0.0,
                    captured_date=today,
                    visual_type=visual_type,
                    tags=tags,
                    product=products,
                    mood=mood,
                    has_text_overlay=True,
                    has_useful_audio=False,
                    reusable=True,
                    freshness="current",
                    engagement_score=None,
                    file_path=str(file_path),
                    notes=(
                        f"wechat seed | account={article.account or '-'} "
                        f"| title={article.title[:120]}"
                    ),
                    source_kind="search_download",
                    source_url=article.url,
                    asset_hash=digest,
                    rights_status="unknown",
                    license_type="wechat_unknown",
                    license_scope="review_required",
                    expires_at="",
                )
                if not dry_run:
                    store.insert(meta)

                added += 1
                taken += 1
                by_visual_type[visual_type] = by_visual_type.get(visual_type, 0) + 1
                items.append(
                    {
                        "clip_id": clip_id,
                        "visual_type": visual_type,
                        "mood": mood,
                        "title": article.title,
                        "account": article.account,
                        "article_url": article.url,
                        "image_url": final_url,
                        "file_path": str(file_path),
                        "width": width,
                        "height": height,
                        "license_type": "wechat_unknown",
                    }
                )

    manifest = {
        "seed_id": seed_id,
        "target_total": target_total,
        "added_this_run": added,
        "article_count": fetched_articles,
        "scanned_images": scanned_images,
        "by_visual_type": by_visual_type,
        "skip_reason_count": skip_reason_count,
        "items": items,
    }
    manifest_path = cfg.output_dir / "asset_library" / "seeds" / f"{seed_id}.json"
    manifest["manifest_path"] = str(manifest_path)
    if not dry_run:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return manifest


def _fetch_article_meta(client: httpx.Client, article_url: str) -> _ArticleMeta | None:
    try:
        resp = client.get(article_url, headers={"Referer": "https://mp.weixin.qq.com/"})
        resp.raise_for_status()
    except Exception:
        return None

    html_text = resp.text
    title = _extract_title(html_text)
    account = _extract_account(html_text)
    image_urls = _extract_image_urls(html_text, article_url)
    if not image_urls:
        return None
    return _ArticleMeta(url=article_url, title=title, account=account, image_urls=image_urls)


def _extract_title(html_text: str) -> str:
    for pattern in (
        r'<meta\s+property="og:title"\s+content="([^"]+)"',
        r"<title>(.*?)</title>",
    ):
        m = re.search(pattern, html_text, flags=re.IGNORECASE | re.S)
        if m:
            t = html.unescape(m.group(1)).strip()
            t = re.sub(r"\s+", " ", t)
            if t:
                return t
    return "公众号图片"


def _extract_account(html_text: str) -> str:
    for pattern in (
        r'nickname\s*=\s*htmlDecode\("([^"]+)"\)',
        r'"nickname"\s*:\s*"([^"]+)"',
        r'<meta\s+property="og:site_name"\s+content="([^"]+)"',
    ):
        m = re.search(pattern, html_text, flags=re.IGNORECASE)
        if m:
            name = html.unescape(m.group(1)).strip()
            name = re.sub(r"\s+", " ", name)
            if name:
                return name
    return ""


def _extract_image_urls(html_text: str, article_url: str) -> list[str]:
    patterns = (
        r'data-src=["\'](https://mmbiz\.qpic\.cn[^"\']+)["\']',
        r'src=["\'](https://mmbiz\.qpic\.cn[^"\']+)["\']',
        r'cdn_url:\s*"((?:https:)?//mmbiz\.qpic\.cn[^"]+)"',
    )
    urls: list[str] = []
    for pattern in patterns:
        for raw in re.findall(pattern, html_text, flags=re.IGNORECASE):
            u = html.unescape(raw).replace("\\/", "/").strip()
            if u.startswith("//"):
                u = "https:" + u
            if not u.startswith("http"):
                continue
            if "wx_fmt=gif" in u.lower() or u.lower().endswith(".gif"):
                continue
            urls.append(_canonical_url(u))
    return _dedupe_urls(urls)


def _download_best_image(
    client: httpx.Client,
    *,
    article_url: str,
    candidates: list[str],
    min_bytes: int,
    min_width: int,
    min_height: int,
) -> tuple[bytes, str, str, int, int, str] | None:
    for img_url in candidates:
        try:
            resp = client.get(
                img_url,
                headers={"Referer": article_url},
            )
            resp.raise_for_status()
        except Exception:
            continue

        ctype = (resp.headers.get("content-type") or "").lower()
        data = resp.content
        if len(data) < max(1024, min_bytes):
            continue
        if ctype and "image" not in ctype:
            continue

        dims = _parse_image_size(data)
        if dims is None:
            continue
        width, height = dims
        if width < min_width or height < min_height:
            continue

        ext = _guess_extension(ctype, img_url)
        digest = hashlib.sha1(data).hexdigest()
        return data, img_url, ext, width, height, digest
    return None


def _image_candidates(img_url: str) -> list[str]:
    candidates = [_canonical_url(img_url)]
    parsed = urlparse(img_url)
    if parsed.netloc.endswith("mmbiz.qpic.cn"):
        parts = parsed.path.split("/")
        if parts and parts[-1].isdigit():
            upgraded = parts[:]
            upgraded[-1] = "0"
            up_path = "/".join(upgraded)
            high_res = urlunparse(parsed._replace(path=up_path))
            candidates.insert(0, _canonical_url(high_res))
    return _dedupe_urls(candidates)


def _guess_extension(content_type: str, url: str) -> str:
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    for key, ext in mapping.items():
        if key in content_type:
            return ext
    path = urlparse(url).path.lower()
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return ".jpg"


def _parse_image_size(data: bytes) -> tuple[int, int] | None:
    if len(data) < 24:
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        width, height = struct.unpack(">II", data[16:24])
        return int(width), int(height)
    if data.startswith((b"GIF87a", b"GIF89a")):
        width, height = struct.unpack("<HH", data[6:10])
        return int(width), int(height)
    if data[:2] == b"\xff\xd8":
        return _parse_jpeg_size(data)
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return _parse_webp_size(data)
    return None


def _parse_jpeg_size(data: bytes) -> tuple[int, int] | None:
    i = 2
    n = len(data)
    while i + 9 <= n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        i += 2
        if marker in (0x01, 0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        if i + 2 > n:
            break
        seg_len = struct.unpack(">H", data[i:i + 2])[0]
        if seg_len < 2 or i + seg_len > n:
            break
        if marker in _SOF_MARKERS and i + 7 <= n:
            h = struct.unpack(">H", data[i + 3:i + 5])[0]
            w = struct.unpack(">H", data[i + 5:i + 7])[0]
            if w > 0 and h > 0:
                return int(w), int(h)
        i += seg_len
    return None


def _parse_webp_size(data: bytes) -> tuple[int, int] | None:
    if len(data) < 30:
        return None
    chunk = data[12:16]
    if chunk == b"VP8X" and len(data) >= 30:
        w = 1 + int.from_bytes(data[24:27], "little")
        h = 1 + int.from_bytes(data[27:30], "little")
        return w, h
    if chunk == b"VP8 " and len(data) >= 30:
        # 参考 VP8 帧头结构：宽高位于起始码后的 4 字节（小端，低 14 bit）。
        w = struct.unpack("<H", data[26:28])[0] & 0x3FFF
        h = struct.unpack("<H", data[28:30])[0] & 0x3FFF
        if w > 0 and h > 0:
            return int(w), int(h)
    return None


def _infer_visual_type(title: str) -> str:
    low = title.lower()
    if any(key in title for key in _DIAGRAM_HINTS) or "diagram" in low:
        return "diagram"
    if any(k in low for k in ("ui", "dashboard", "界面", "截图", "产品", "发布", "实测", "评测")):
        return "product_ui"
    return "image_overlay"


def _infer_mood(title: str) -> str:
    low = title.lower()
    if any(k in title for k in _WARNING_HINTS):
        return "warning"
    if any(k in title for k in _COMPARE_HINTS) or " vs " in low:
        return "compare"
    if any(k in title for k in _DEMO_HINTS):
        return "demo"
    if any(k in title for k in _SUMMARY_HINTS):
        return "summary"
    return "explain"


def _infer_products(title: str, tags: list[str]) -> list[str]:
    text = f"{title} {' '.join(tags)}".lower()
    products: list[str] = []
    for product, hints in _PRODUCT_HINTS.items():
        if any(hint in text for hint in hints):
            products.append(product)
    if not products:
        products.append("other")
    return _dedupe_urls(products)


def _make_tags(article: _ArticleMeta, image_url: str) -> list[str]:
    tags = []
    if article.account:
        tags.append(article.account)
    if article.title:
        tags.extend(_tokenize_cn_en(article.title))
    host = urlparse(image_url).netloc
    if host:
        tags.append(host)
    tags.append("wechat")
    return _dedupe_urls(tags)[:16]


def _tokenize_cn_en(text: str) -> list[str]:
    if not text:
        return []
    raw = re.split(r"[\s,，。！？!?:：;；、()（）【】\\|/]+", text)
    out = []
    for tok in raw:
        t = tok.strip()
        if len(t) < 2:
            continue
        out.append(t[:30])
    return out


def _next_sequence(store: AssetStore, seed_id: str) -> int:
    rows = store.list_assets(reusable_only=False, limit=None)
    max_seq = 0
    prefix = f"{seed_id}-"
    for asset in rows:
        cid = asset.clip_id or ""
        if not cid.startswith(prefix):
            continue
        tail = cid[len(prefix):]
        if tail.isdigit():
            max_seq = max(max_seq, int(tail))
    return max_seq + 1


def _safe_slug(text: str) -> str:
    t = (text or "").strip().lower()
    t = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", t)
    t = re.sub(r"_+", "_", t).strip("_")
    return t or "seed"


def _canonical_url(url: str) -> str:
    p = urlparse(url)
    clean = p._replace(fragment="")
    return urlunparse(clean)


def _dedupe_urls(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        v = (value or "").strip()
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def _inc(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


def _account_allowed(account: str, allow_accounts: list[str]) -> bool:
    name = (account or "").strip()
    if not name:
        return False
    for expected in allow_accounts:
        token = (expected or "").strip()
        if token and token in name:
            return True
    return False
