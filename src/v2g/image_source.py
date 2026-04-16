"""自动配图：网页截图 + 搜图 + AI 生图。

三种图片获取方式，统一接口：
  source_image(query, method, output_dir) -> Path | None

方式:
  screenshot — Playwright 截取网页（复用 tweet_screenshot 的反爬逻辑）
  search     — Bing Image Search API（免费 1000 次/月）
  generate   — DALL-E 3 via OpenAI SDK / Gemini Imagen
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

import click
import httpx
from v2g.page_quality import assess_page_snapshot, collect_page_snapshot

log = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


# ── 统一入口 ─────────────────────────────────────────────

def source_image(
    query: str,
    method: str,
    output_dir: Path,
    **kwargs,
) -> Path | None:
    """统一配图入口。

    Args:
        query: URL（screenshot）/ 关键词（search）/ prompt（generate）
        method: "screenshot" | "search" | "generate"
        output_dir: 图片输出目录（如 output/{pid}/images/）
        **kwargs: 透传给具体方法

    Returns:
        本地图片路径，失败返回 None
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if method == "screenshot":
        return screenshot_url(query, output_dir, **kwargs)
    elif method == "search":
        return search_image(query, output_dir, **kwargs)
    elif method == "generate":
        return generate_image(query, output_dir, **kwargs)
    else:
        click.echo(f"   ⚠️ 未知配图方式: {method}")
        return None


# ── 方式 1: 网页截图 ─────────────────────────────────────

def screenshot_url(
    url: str,
    output_dir: Path,
    selector: str | None = None,
    wait_ms: int = 3000,
) -> Path | None:
    """用 Playwright 截取网页。

    Args:
        url: 目标 URL
        output_dir: 输出目录
        selector: CSS 选择器（截取特定元素，None = 全页可视区域）
        wait_ms: 页面加载等待时间（毫秒）
    """
    slug = _url_slug(url)
    out_path = output_dir / f"screenshot_{slug}.png"

    if out_path.exists() and out_path.stat().st_size > 1024:
        click.echo(f"   ⏭️ 截图已存在: {out_path.name}")
        return out_path

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        click.echo("   ⚠️ 需要安装 playwright: pip install playwright && playwright install chromium")
        return None

    click.echo(f"   📸 截图: {url}")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(wait_ms)

            ok, reason = _is_captureworthy(page, url)
            if not ok:
                click.echo(f"   ⚠️ 页面不适合截图({reason}): {url}")
                browser.close()
                return None

            if selector:
                element = page.query_selector(selector)
                if element:
                    element.screenshot(path=str(out_path))
                else:
                    click.echo(f"   ⚠️ 选择器未匹配: {selector}")
                    page.screenshot(path=str(out_path))
            else:
                page.screenshot(path=str(out_path))

            browser.close()

        click.echo(f"   ✅ 截图完成: {out_path.name}")
        return out_path
    except Exception as e:
        click.echo(f"   ⚠️ 截图失败: {e}")
        return None


def _is_captureworthy(page, url: str) -> tuple[bool, str]:
    """检测页面是否适合截图。低信息页面尝试向下滚动后重试一次。"""
    snapshot = collect_page_snapshot(page)
    ok, reason = assess_page_snapshot(snapshot, url=url)
    if ok:
        return True, "ok"
    if reason == "low_density":
        try:
            page.evaluate("window.scrollBy(0, Math.max(window.innerHeight * 0.9, 640))")
            page.wait_for_timeout(800)
        except Exception:
            return False, reason
        snapshot = collect_page_snapshot(page)
        ok, reason = assess_page_snapshot(snapshot, url=url)
        if ok:
            return True, "ok"
    return False, reason


# ── 方式 2: 搜图 (DuckDuckGo 免费，Bing 备选) ──────────


def search_image(
    query: str,
    output_dir: Path,
    api_key: str = "",
) -> Path | None:
    """搜索并下载图片。

    优先 DuckDuckGo（免费，无需 Key），fallback 到 Bing Image Search。
    """
    slug = _text_slug(query)
    out_path = output_dir / f"search_{slug}.jpg"

    if out_path.exists() and out_path.stat().st_size > 1024:
        click.echo(f"   ⏭️ 搜图已存在: {out_path.name}")
        return out_path

    # 优先 DuckDuckGo
    result = _search_ddg(query, out_path)
    if result:
        return result

    # Fallback: Bing（需要 Key）
    import os
    bing_key = api_key or os.environ.get("BING_IMAGE_API_KEY", "")
    if bing_key:
        return _search_bing(query, out_path, bing_key)

    click.echo(f"   ⚠️ DuckDuckGo 搜图失败且无 BING_IMAGE_API_KEY")
    return None


def _search_ddg(query: str, out_path: Path) -> Path | None:
    """DuckDuckGo 图片搜索（免费，无需 API Key）。"""
    click.echo(f"   🔍 搜图 (DuckDuckGo): {query}")
    try:
        from ddgs import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.images(query, max_results=3, size="Large"))

        if not results:
            click.echo(f"   ⚠️ DuckDuckGo 无结果: {query}")
            return None

        # 尝试下载前 3 张（有些 URL 可能失效）
        for r in results:
            img_url = r.get("image", "")
            if not img_url:
                continue
            try:
                img_resp = httpx.get(
                    img_url,
                    headers={"User-Agent": _UA},
                    timeout=10.0,
                    follow_redirects=True,
                )
                if img_resp.status_code == 200 and len(img_resp.content) > 5000:
                    out_path.write_bytes(img_resp.content)
                    click.echo(f"   ✅ 搜图完成: {out_path.name}")
                    return out_path
            except Exception:
                continue

        click.echo(f"   ⚠️ DuckDuckGo 结果均无法下载")
        return None
    except ImportError:
        click.echo("   ⚠️ 需要安装: pip install duckduckgo-search")
        return None
    except Exception as e:
        click.echo(f"   ⚠️ DuckDuckGo 搜图失败: {e}")
        return None


def _search_bing(query: str, out_path: Path, api_key: str) -> Path | None:
    """Bing Image Search API（备选，需 API Key）。"""
    click.echo(f"   🔍 搜图 (Bing fallback): {query}")
    try:
        resp = httpx.get(
            "https://api.bing.microsoft.com/v7.0/images/search",
            params={"q": query, "count": 1, "imageType": "Photo", "size": "Large"},
            headers={"Ocp-Apim-Subscription-Key": api_key, "User-Agent": _UA},
            timeout=15.0,
        )
        resp.raise_for_status()
        images = resp.json().get("value", [])
        if not images:
            return None

        img_url = images[0].get("contentUrl", "")
        if not img_url:
            return None

        img_resp = httpx.get(img_url, headers={"User-Agent": _UA}, timeout=15.0, follow_redirects=True)
        img_resp.raise_for_status()
        out_path.write_bytes(img_resp.content)
        click.echo(f"   ✅ 搜图完成: {out_path.name}")
        return out_path
    except Exception as e:
        click.echo(f"   ⚠️ Bing 搜图失败: {e}")
        return None


# ── 方式 3: AI 生图 ──────────────────────────────────────

def generate_image(
    prompt: str,
    output_dir: Path,
    model: str = "",
    api_key: str = "",
    base_url: str = "",
) -> Path | None:
    """用 DALL-E 3 / Gemini Imagen 生成图片。

    优先走 GPT proxy (DALL-E 3)，fallback 到 Gemini Imagen。
    """
    import os

    # 尝试 DALL-E 3 (OpenAI SDK)
    gpt_key = api_key or os.environ.get("GPT_API_KEY", "")
    gpt_base = base_url or os.environ.get("GPT_BASE_URL", "")
    if gpt_key:
        result = _generate_dalle(prompt, output_dir, gpt_key, gpt_base, model)
        if result:
            return result

    # Fallback: Gemini Imagen
    gemini_key = os.environ.get("GEMINI_IMAGE_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
    if gemini_key:
        return _generate_gemini(prompt, output_dir, gemini_key)

    click.echo("   ⚠️ 生图需要 GPT_API_KEY (DALL-E) 或 GEMINI_IMAGE_API_KEY")
    return None


def _generate_dalle(
    prompt: str,
    output_dir: Path,
    api_key: str,
    base_url: str,
    model: str = "",
) -> Path | None:
    """DALL-E 3 via OpenAI SDK。"""
    slug = _text_slug(prompt)
    out_path = output_dir / f"generated_{slug}.png"

    if out_path.exists() and out_path.stat().st_size > 1024:
        click.echo(f"   ⏭️ 生图已存在: {out_path.name}")
        return out_path

    click.echo(f"   🎨 AI 生图 (DALL-E): {prompt[:60]}...")
    try:
        from openai import OpenAI

        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        client = OpenAI(**client_kwargs)

        response = client.images.generate(
            model=model or "dall-e-3",
            prompt=prompt,
            size="1792x1024",
            quality="standard",
            n=1,
        )
        img_url = response.data[0].url
        if not img_url:
            return None

        img_resp = httpx.get(img_url, timeout=30.0, follow_redirects=True)
        img_resp.raise_for_status()
        out_path.write_bytes(img_resp.content)

        click.echo(f"   ✅ 生图完成: {out_path.name}")
        return out_path
    except Exception as e:
        click.echo(f"   ⚠️ DALL-E 生图失败: {e}")
        return None


def _generate_gemini(
    prompt: str,
    output_dir: Path,
    api_key: str,
) -> Path | None:
    """Gemini Imagen API。"""
    slug = _text_slug(prompt)
    out_path = output_dir / f"generated_{slug}.png"

    if out_path.exists() and out_path.stat().st_size > 1024:
        click.echo(f"   ⏭️ 生图已存在: {out_path.name}")
        return out_path

    click.echo(f"   🎨 AI 生图 (Gemini): {prompt[:60]}...")
    try:
        import google.generativeai as genai
        import base64

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash-exp")

        response = model.generate_content(
            f"Generate a high-quality photo-realistic image: {prompt}",
            generation_config={"response_mime_type": "image/png"},
        )

        # Gemini 返回的图片在 response.candidates[0].content.parts[0].inline_data
        for part in response.candidates[0].content.parts:
            if hasattr(part, "inline_data") and part.inline_data:
                img_data = base64.b64decode(part.inline_data.data)
                out_path.write_bytes(img_data)
                click.echo(f"   ✅ 生图完成: {out_path.name}")
                return out_path

        click.echo("   ⚠️ Gemini 未返回图片数据")
        return None
    except Exception as e:
        click.echo(f"   ⚠️ Gemini 生图失败: {e}")
        return None


# ── 工具函数 ─────────────────────────────────────────────

def _url_slug(url: str) -> str:
    """URL → 短 slug（用于文件名）。"""
    h = hashlib.md5(url.encode()).hexdigest()[:8]
    # 提取域名+路径关键部分
    clean = re.sub(r"https?://", "", url)
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", clean)[:40]
    return f"{clean}_{h}"


def _text_slug(text: str) -> str:
    """文本 → 短 slug（用于文件名）。"""
    h = hashlib.md5(text.encode()).hexdigest()[:8]
    clean = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "_", text)[:30]
    return f"{clean}_{h}"
