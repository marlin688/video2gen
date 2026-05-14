"""公众号内容生产流水线：打包、评分、发布准备。

这个模块刻意把“发布”拆成安全的两级：
1. 生成可审阅的 package + score；
2. 默认 dry-run 或写入草稿箱，只有显式 execute/free-publish 才会继续发布。
"""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx


IMAGE_RE = re.compile(r"!\[[^\]]*]\(([^)]+)\)|<img\s+[^>]*src=[\"']([^\"']+)[\"']", re.I)
LINK_RE = re.compile(r"https?://[^\s)\"']+")
HEADING_RE = re.compile(r"^#{1,3}\s+", re.M)


@dataclass
class WechatArticlePackage:
    package_id: str
    package_dir: Path
    title: str
    markdown_path: Path
    html_path: Path | None
    images: list[Path]
    source_path: Path


def make_package(
    output_dir: Path,
    source: str | Path,
    *,
    package_id: str | None = None,
    title: str | None = None,
) -> WechatArticlePackage:
    """把现有 Markdown/HTML/文章目录打成公众号生产包。"""
    source_path = Path(source)
    if not source_path.exists():
        raise FileNotFoundError(f"source not found: {source}")

    if source_path.is_dir():
        md_candidates = sorted(source_path.glob("*.md"))
        html_candidates = sorted(source_path.glob("*.html"))
        markdown_path = _prefer_named(md_candidates, ("article-pro.md", "article.md")) or (md_candidates[0] if md_candidates else None)
        html_path = _prefer_named(html_candidates, ("article-pro.html", "article-real.html", "article.html"))
        if markdown_path is None:
            raise FileNotFoundError(f"no markdown file found in {source_path}")
    else:
        markdown_path = source_path
        html_guess = source_path.with_suffix(".html")
        html_path = html_guess if html_guess.exists() else None

    text = markdown_path.read_text(encoding="utf-8")
    resolved_title = title or _extract_title(text) or markdown_path.stem
    resolved_id = package_id or _slugify(resolved_title)
    package_dir = output_dir / "wechat" / resolved_id
    assets_dir = package_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    packaged_md = package_dir / "article.md"
    packaged_md.write_text(text, encoding="utf-8")
    packaged_html: Path | None = None
    if html_path and html_path.exists():
        packaged_html = package_dir / "article.html"
        packaged_html.write_text(html_path.read_text(encoding="utf-8"), encoding="utf-8")

    images = _resolve_images(text, markdown_path.parent)
    copied_images: list[Path] = []
    for image in images:
        if not image.exists() or not image.is_file():
            continue
        target = assets_dir / image.name
        if image.resolve() != target.resolve():
            shutil.copy2(image, target)
        copied_images.append(target)

    manifest = {
        "package_id": resolved_id,
        "title": resolved_title,
        "source_path": str(source_path),
        "markdown_path": str(packaged_md),
        "html_path": str(packaged_html) if packaged_html else "",
        "images": [str(p) for p in copied_images],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "packaged",
    }
    (package_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return WechatArticlePackage(
        package_id=resolved_id,
        package_dir=package_dir,
        title=resolved_title,
        markdown_path=packaged_md,
        html_path=packaged_html,
        images=copied_images,
        source_path=source_path,
    )


def score_package(package_dir: Path, *, min_score: int = 85) -> dict:
    """规则化打分，目标是先做稳定门禁，不消耗 LLM。"""
    manifest_path = package_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    md_path = Path(manifest["markdown_path"])
    text = md_path.read_text(encoding="utf-8")

    plain = _strip_markdown(text)
    images = [Path(p) for p in manifest.get("images", [])]
    image_refs = _extract_image_refs(text)
    real_screenshots = [p for p in images if p.name.startswith("real-")]
    pro_assets = [p for p in images if p.name.startswith("pro-")]
    refs = re.findall(r"^\[\d+]\s+|\[\d+]\s+\[|^\[\d+]", text, flags=re.M)
    links = LINK_RE.findall(text)
    headings = HEADING_RE.findall(text)

    gate_checks = [
        _check("title", bool(_extract_title(text)), 8, "有明确标题"),
        _range_check("length", len(plain), 2200, 6500, 14, "正文长度适合公众号深度短文"),
        _check("opening", _has_strong_opening(text), 10, "开头 400 字内有核心判断/冲突"),
        _check("structure", len(headings) >= 5, 10, "有清晰小标题结构"),
        _check("image_count", len(image_refs) >= 6, 12, "至少 6 张图文素材"),
        _check("real_screenshots", len(real_screenshots) >= 3, 12, "至少 3 张真实网络截图"),
        _check("original_visuals", len(pro_assets) >= 3, 8, "至少 3 张原创信息图/结构图"),
        _check("sources", len(refs) >= 4 or len(links) >= 5, 10, "有参考资料/链接来源"),
        _check("wechat_readability", _wechat_readability_ok(text), 8, "段落短、适合手机阅读"),
        _check("takeaway", "MCP 是接口层" in text or "上下文工程" in text[-600:], 8, "结尾有可传播金句"),
    ]
    gate_score, gate_max_score, gate_pct = _score_checks(gate_checks)
    checks = _editorial_checks(
        text=text,
        plain=plain,
        images=images,
        image_refs=image_refs,
        real_screenshots=real_screenshots,
        links=links,
    )
    score, max_score, pct = _score_checks(checks)
    passed = pct >= min_score

    result = {
        "package_id": manifest.get("package_id", package_dir.name),
        "title": manifest.get("title", ""),
        "score": score,
        "max_score": max_score,
        "score_pct": pct,
        "score_type": "media_competitiveness",
        "gate_score": gate_score,
        "gate_max_score": gate_max_score,
        "gate_score_pct": gate_pct,
        "gate_checks": gate_checks,
        "min_score": min_score,
        "passed": passed,
        "checks": checks,
        "metrics": {
            "chars": len(plain),
            "headings": len(headings),
            "image_refs": len(image_refs),
            "packaged_images": len(images),
            "real_screenshots": len(real_screenshots),
            "original_visuals": len(pro_assets),
            "links": len(links),
            "unique_source_domains": len(_source_domains(links)),
            "image_captions": _caption_count(text),
            "number_facts": _number_fact_count(text),
        },
        "scored_at": datetime.now(timezone.utc).isoformat(),
    }
    (package_dir / "score.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def build_publish_plan(package_dir: Path, *, min_score: int = 85, allow_below_threshold: bool = False) -> dict:
    """生成发布计划，不触网。"""
    manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
    score_path = package_dir / "score.json"
    score = json.loads(score_path.read_text(encoding="utf-8")) if score_path.exists() else score_package(package_dir, min_score=min_score)
    if not score.get("passed") and not allow_below_threshold:
        plan = {
            "ready": False,
            "reason": "score_below_threshold",
            "score_pct": score.get("score_pct"),
            "gate_score_pct": score.get("gate_score_pct"),
            "min_score": min_score,
            "package_dir": str(package_dir),
        }
        (package_dir / "publish_plan.json").write_text(
            json.dumps(plan, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return plan

    images = [Path(p) for p in manifest.get("images", [])]
    cover = _choose_cover(images)
    plan = {
        "ready": True,
        "package_id": manifest.get("package_id"),
        "title": manifest.get("title"),
        "package_dir": str(package_dir),
        "markdown_path": manifest.get("markdown_path"),
        "html_path": manifest.get("html_path"),
        "cover_image": str(cover) if cover else "",
        "image_count": len(images),
        "score_pct": score.get("score_pct"),
        "gate_score_pct": score.get("gate_score_pct"),
        "publish_steps": [
            "get_access_token",
            "upload_inline_images",
            "upload_cover_thumb",
            "create_draft",
            "optional_freepublish_submit",
        ],
    }
    (package_dir / "publish_plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return plan


def publish_to_wechat(
    package_dir: Path,
    *,
    app_id: str,
    app_secret: str,
    author: str = "AGI通识",
    digest: str = "",
    dry_run: bool = True,
    free_publish: bool = False,
    min_score: int = 85,
) -> dict:
    """发布到微信公众号草稿箱；默认 dry-run。

    真正发布需要公众号已开通 API 权限，并配置 IP 白名单。
    """
    plan = build_publish_plan(package_dir, min_score=min_score)
    if not plan.get("ready"):
        return plan
    if dry_run:
        return {"dry_run": True, **plan}
    if not app_id or not app_secret:
        raise ValueError("WECHAT_APP_ID / WECHAT_APP_SECRET required")

    manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
    md_path = Path(manifest["markdown_path"])
    html_path = Path(manifest.get("html_path") or "")
    content = html_path.read_text(encoding="utf-8") if html_path.exists() else _markdown_to_basic_html(md_path.read_text(encoding="utf-8"))

    with httpx.Client(timeout=30.0) as client:
        token = _wechat_access_token(client, app_id, app_secret)
        image_map = _upload_inline_images(client, token, [Path(p) for p in manifest.get("images", [])])
        for local, remote in image_map.items():
            content = content.replace(str(local), remote).replace(f"./assets/{Path(local).name}", remote)
        thumb_media_id = _upload_thumb(client, token, Path(plan["cover_image"]))
        draft = _create_draft(
            client,
            token,
            title=manifest["title"],
            author=author,
            digest=digest or _make_digest(md_path.read_text(encoding="utf-8")),
            content=content,
            thumb_media_id=thumb_media_id,
        )
        result = {"draft": draft, "free_publish": None}
        if free_publish:
            result["free_publish"] = _submit_freepublish(client, token, draft["media_id"])
        (package_dir / "publish_result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return result


def _wechat_access_token(client: httpx.Client, app_id: str, app_secret: str) -> str:
    resp = client.get(
        "https://api.weixin.qq.com/cgi-bin/token",
        params={"grant_type": "client_credential", "appid": app_id, "secret": app_secret},
    )
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(f"wechat token failed: {data}")
    return str(data["access_token"])


def _upload_inline_images(client: httpx.Client, token: str, images: list[Path]) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in images:
        if not path.exists():
            continue
        with path.open("rb") as f:
            resp = client.post(
                "https://api.weixin.qq.com/cgi-bin/media/uploadimg",
                params={"access_token": token},
                files={"media": (path.name, f, _mime(path))},
            )
        data = resp.json()
        if "url" in data:
            out[str(path)] = str(data["url"])
    return out


def _upload_thumb(client: httpx.Client, token: str, path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"cover image not found: {path}")
    with path.open("rb") as f:
        resp = client.post(
            "https://api.weixin.qq.com/cgi-bin/material/add_material",
            params={"access_token": token, "type": "thumb"},
            files={"media": (path.name, f, _mime(path))},
        )
    data = resp.json()
    media_id = data.get("media_id")
    if not media_id:
        raise RuntimeError(f"wechat thumb upload failed: {data}")
    return str(media_id)


def _create_draft(
    client: httpx.Client,
    token: str,
    *,
    title: str,
    author: str,
    digest: str,
    content: str,
    thumb_media_id: str,
) -> dict:
    resp = client.post(
        "https://api.weixin.qq.com/cgi-bin/draft/add",
        params={"access_token": token},
        json={
            "articles": [
                {
                    "title": title[:64],
                    "author": author[:8],
                    "digest": digest[:120],
                    "content": content,
                    "thumb_media_id": thumb_media_id,
                    "need_open_comment": 0,
                    "only_fans_can_comment": 0,
                }
            ]
        },
    )
    data = resp.json()
    if "media_id" not in data:
        raise RuntimeError(f"wechat draft failed: {data}")
    return data


def _submit_freepublish(client: httpx.Client, token: str, media_id: str) -> dict:
    resp = client.post(
        "https://api.weixin.qq.com/cgi-bin/freepublish/submit",
        params={"access_token": token},
        json={"media_id": media_id},
    )
    return resp.json()


def _extract_title(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _strip_markdown(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"!\[[^\]]*]\([^)]+\)", "", text)
    text = re.sub(r"\[[^\]]+]\([^)]+\)", "", text)
    text = re.sub(r"[#>*_`~-]", "", text)
    return re.sub(r"\s+", "", text)


def _extract_image_refs(text: str) -> list[str]:
    refs = []
    for match in IMAGE_RE.finditer(text):
        ref = match.group(1) or match.group(2)
        if ref:
            refs.append(ref)
    return refs


def _resolve_images(text: str, base_dir: Path) -> list[Path]:
    images = []
    for ref in _extract_image_refs(text):
        if ref.startswith(("http://", "https://", "data:")):
            continue
        path = (base_dir / ref).resolve()
        images.append(path)
    return _dedupe_paths(images)


def _prefer_named(paths: list[Path], names: tuple[str, ...]) -> Path | None:
    by_name = {p.name: p for p in paths}
    for name in names:
        if name in by_name:
            return by_name[name]
    return None


def _check(name: str, passed: bool, points: int, label: str) -> dict:
    return {"name": name, "label": label, "points": points, "passed": bool(passed)}


def _range_check(name: str, value: int, low: int, high: int, points: int, label: str) -> dict:
    return _check(name, low <= value <= high, points, f"{label} ({value}/{low}-{high})")


def _score_checks(checks: list[dict]) -> tuple[int, int, float]:
    score = sum(c["points"] for c in checks if c["passed"])
    max_score = sum(c["points"] for c in checks)
    pct = round(score / max_score * 100, 1) if max_score else 0.0
    return score, max_score, pct


def _editorial_checks(
    *,
    text: str,
    plain: str,
    images: list[Path],
    image_refs: list[str],
    real_screenshots: list[Path],
    links: list[str],
) -> list[dict]:
    """更接近媒体成品稿的竞争力评分，而不是发布前素材门禁。"""
    title = _extract_title(text)
    opening = text[:700]
    caption_count = _caption_count(text)
    source_domains = _source_domains(links)
    number_facts = _number_fact_count(text)
    caption_ratio = caption_count / max(1, len(image_refs))

    return [
        _check(
            "topic_tension",
            bool(title) and any(k in title for k in ("但", "为什么", "刚刚", "首次", "官方", "一夜", "背后")),
            10,
            "标题有明确冲突/新闻钩子，不只是陈述主题",
        ),
        _check(
            "opening_newsroom",
            _has_strong_opening(opening) and any(k in opening for k in ("但", "因为", "同时", "真正", "问题")),
            10,
            "开头能在手机首屏建立冲突和判断",
        ),
        _check(
            "source_diversity",
            len(source_domains) >= 4,
            12,
            "至少 4 个独立信源域名，避免只复述同一组官方文档",
        ),
        _check(
            "evidence_visuals",
            len(real_screenshots) >= 4 and caption_count >= 4,
            12,
            "真实截图足够多，并且有图注解释截图价值",
        ),
        _check(
            "visual_payload",
            caption_ratio >= 0.6 and len(images) >= 8,
            12,
            "多数图片承担信息增量，而不是装饰性配图",
        ),
        _check(
            "reported_specifics",
            number_facts >= 3,
            8,
            "正文包含足够具体的数字/时间/规模事实",
        ),
        _check(
            "scene_or_case",
            any(k in text for k in ("第一周", "第二周", "真实团队", "用户", "开发者", "工程师", "案例", "现场")),
            10,
            "有场景、人物或案例，不只是抽象判断",
        ),
        _check(
            "contrarian_analysis",
            any(k in text for k in ("不是", "但", "然而", "反而", "真正"))
            and any(k in text for k in ("因为", "所以", "这就是为什么", "意味着")),
            10,
            "有反直觉分析和因果解释",
        ),
        _check(
            "actionable_takeaway",
            any(k in text for k in ("第一步", "第二步", "落地顺序", "更靠谱的顺序", "怎么做"))
            and len(plain) >= 2200,
            8,
            "读者能带走可执行的判断或方法",
        ),
        _check(
            "mobile_rhythm",
            _wechat_readability_ok(text),
            8,
            "段落节奏适合公众号移动端阅读",
        ),
    ]


def _has_strong_opening(text: str) -> bool:
    opening = text[:600]
    return any(key in opening for key in ("结论", "判断", "问题", "不是", "真正", "核心"))


def _wechat_readability_ok(text: str) -> bool:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip() and not p.strip().startswith("!")]
    if not paragraphs:
        return False
    long_count = sum(1 for p in paragraphs if len(_strip_markdown(p)) > 220)
    return long_count / len(paragraphs) <= 0.18


def _choose_cover(images: list[Path]) -> Path | None:
    for prefix in ("pro-cover", "cover-final", "cover"):
        for image in images:
            if image.stem.startswith(prefix):
                return image
    return images[0] if images else None


def _make_digest(text: str) -> str:
    plain = _strip_markdown(text)
    return plain[:110]


def _source_domains(links: list[str]) -> set[str]:
    domains = set()
    for link in links:
        host = urlparse(link).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        if host:
            domains.add(host)
    return domains


def _caption_count(text: str) -> int:
    return len(re.findall(r"^图注[:：]", text, flags=re.M))


def _number_fact_count(text: str) -> int:
    body = re.sub(r"https?://\S+", "", text)
    body = "\n".join(
        line
        for line in body.splitlines()
        if not line.lstrip().startswith(("!", "["))
    )
    units = (
        "%|倍|年|月|日|小时|分钟|秒|个|项|次|美元|亿元|万|亿|"
        "GB|MB|KB|tokens?|Token|fps|岁|人|家|款|层|步|张|字"
    )
    return len(re.findall(rf"\d+(?:\.\d+)?\s*(?:{units})", body, flags=re.I))


def _markdown_to_basic_html(text: str) -> str:
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("# "):
            lines.append(f"<h1>{_escape(line[2:])}</h1>")
        elif line.startswith("## "):
            lines.append(f"<h2>{_escape(line[3:])}</h2>")
        elif line.startswith("### "):
            lines.append(f"<h3>{_escape(line[4:])}</h3>")
        elif line.startswith("!"):
            m = re.match(r"!\[[^\]]*]\(([^)]+)\)", line)
            if m:
                lines.append(f'<p><img src="{_escape(m.group(1))}" /></p>')
        else:
            lines.append(f"<p>{_escape(line)}</p>")
    return "\n".join(lines)


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _mime(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    if ext == ".webp":
        return "image/webp"
    return "application/octet-stream"


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", text.lower()).strip("-")
    return slug[:60] or "wechat-article"


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen = set()
    out = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def env_wechat_credentials() -> tuple[str, str, str]:
    return (
        os.environ.get("WECHAT_APP_ID", ""),
        os.environ.get("WECHAT_APP_SECRET", ""),
        os.environ.get("WECHAT_AUTHOR", "AGI通识"),
    )
