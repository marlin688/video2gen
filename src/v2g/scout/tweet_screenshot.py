"""推文截图：Playwright 截取 Twitter/X 推文卡片，供 image-overlay 组件使用。"""

import re
from pathlib import Path

import click


def _extract_tweet_id(url: str) -> str | None:
    m = re.search(r"/status/(\d+)", url)
    return m.group(1) if m else None


def _is_blocked_page(page) -> bool:
    try:
        text = (page.text_content("body") or "").lower()
        signals = [
            "security verification", "verifies you are not a bot",
            "checking your browser", "just a moment", "captcha",
            "page not found", "404 not found", "this page doesn't exist",
        ]
        return any(s in text for s in signals)
    except Exception:
        return False


def capture_tweet_screenshots(
    tweets: list[dict],
    images_dir: Path,
    max_tweets: int = 5,
) -> dict[str, Path]:
    """截取推文为 PNG 图片。

    Args:
        tweets: 推文列表（需含 url 或 tweet_id 字段），按 total_score 降序。
        images_dir: 输出目录，如 output/{pid}/images/。
        max_tweets: 最多截取条数。

    Returns:
        {tweet_url: saved_png_path} 成功截取的映射。
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        click.echo("   ⚠️ Playwright 未安装，跳过推文截图")
        return {}

    images_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, Path] = {}

    # 筛选有效推文
    candidates = []
    for t in tweets[:max_tweets]:
        url = t.get("url", "")
        tid = t.get("tweet_id") or _extract_tweet_id(url)
        if tid:
            candidates.append((tid, url, t))

    if not candidates:
        return results

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            page = browser.new_page(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )

            for tid, url, tweet in candidates:
                try:
                    embed_url = f"https://fxtwitter.com/x/status/{tid}"
                    click.echo(f"   🐦 截图: @{tweet.get('author', '?')} ({tid[:8]}...)")
                    page.goto(embed_url, timeout=15000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2500)

                    if _is_blocked_page(page):
                        # fallback: 原始 URL
                        if url:
                            page.goto(url, timeout=15000, wait_until="domcontentloaded")
                            page.wait_for_timeout(2500)

                    # 找推文主体元素
                    element = None
                    for selector in ["article", '[data-testid="tweet"]', ".tweet-card", "main"]:
                        try:
                            element = page.query_selector(selector)
                            if element:
                                break
                        except Exception:
                            pass

                    out_path = images_dir / f"tweet_{tid}.png"
                    if element:
                        element.screenshot(path=str(out_path), type="png")
                    else:
                        page.screenshot(path=str(out_path), type="png")

                    results[url or f"https://x.com/i/status/{tid}"] = out_path
                    click.echo(f"   ✅ {out_path.name}")

                except Exception as e:
                    click.echo(f"   ⚠️ 推文截图失败 ({tid[:8]}): {e}")

            browser.close()

    except Exception as e:
        click.echo(f"   ⚠️ 浏览器启动失败: {e}")

    return results
