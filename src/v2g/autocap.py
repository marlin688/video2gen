"""B 类素材自动截图：解析 recording_instruction，用 Playwright 截图。

三级 fallback：
  L1: 素材库匹配 → 直接复用已有素材
  L2: Playwright 截图 → 从 instruction 中提取 URL 自动截图
  L3: 跳过 → 渲染时由 Remotion TerminalDemoSegment 降级处理

支持的截图类型：
  - 普通网页（GitHub, npm, 文档等）：智能定位页面焦点区域
  - 推特/X 帖子：截取推文卡片，可拼接多条
  - GitHub 文件：直接导航到具体文件路径
"""

import json
import re
import shutil
from pathlib import Path

import click

from v2g.config import Config
from v2g.material_library import MaterialLibrary, MaterialEntry


def run_capture(cfg: Config, project_id: str) -> int:
    """对脚本中所有 B 类 segment 自动采集素材。返回成功数。"""
    output_dir = cfg.output_dir / project_id
    script_path = output_dir / "script.json"
    if not script_path.exists():
        raise click.ClickException("脚本不存在，请先生成 script.json")

    script_data = json.loads(script_path.read_text(encoding="utf-8"))
    b_segments = [s for s in script_data.get("segments", []) if s.get("material") == "B"]

    if not b_segments:
        click.echo("ℹ️ 脚本中无 B 类素材段")
        return 0

    library = MaterialLibrary(db_path=cfg.output_dir / "assets.db")
    recordings_dir = output_dir / "recordings"
    recordings_dir.mkdir(exist_ok=True)

    click.echo(f"🖥️ 自动素材采集: {len(b_segments)} 段 B 类素材\n")
    success = 0

    for seg in b_segments:
        seg_id = seg.get("id", 0)
        instruction = seg.get("recording_instruction", "")
        narration = seg.get("narration_zh", "")
        rec_path = recordings_dir / f"seg_{seg_id}.mp4"

        if rec_path.exists():
            click.echo(f"   ⏭️ Segment {seg_id}: 录屏已存在")
            success += 1
            continue

        click.echo(f"   📹 Segment {seg_id}: {instruction[:50]}...")

        # L1: 素材库检索
        matched = library.search(instruction, top_k=1)
        if matched:
            entry = matched[0]
            src = Path(entry.path)
            if src.exists():
                shutil.copy2(src, rec_path)
                click.echo(f"      ✅ L1 素材库命中: {entry.description[:40]}")
                success += 1
                continue

        # L1.5: 动态录屏（有 URL 时）
        urls = _extract_urls(instruction)
        if urls and _dynamic_record(instruction, narration, rec_path, duration=15.0):
            click.echo(f"      ✅ L1.5 动态录屏成功")
            library.add(MaterialEntry(
                type="capture",
                path=str(rec_path),
                keywords=_extract_keywords(instruction),
                description=instruction[:80],
                source_project=project_id,
            ))
            success += 1
            continue

        # L2: Playwright 自动截图
        screenshots_dir = output_dir / "screenshots" / f"seg_{seg_id}"
        captured = _smart_capture(instruction, narration, screenshots_dir)
        if captured:
            from v2g.recorder import screenshots_to_video
            screenshots_to_video(screenshots_dir, rec_path, duration=15.0)
            if rec_path.exists():
                click.echo(f"      ✅ L2 截图成功 ({captured} 张)")
                library.add(MaterialEntry(
                    type="capture",
                    path=str(rec_path),
                    keywords=_extract_keywords(instruction),
                    description=instruction[:80],
                    source_project=project_id,
                ))
                success += 1
                continue

        # L3: 跳过
        click.echo(f"      ⬜ L3 跳过 → 渲染时使用终端模拟动画")

    click.echo(f"\n📊 素材采集完成: {success}/{len(b_segments)}")
    return success


# ---------------------------------------------------------------------------
# Smart capture: 根据 URL 类型选择截图策略
# ---------------------------------------------------------------------------

def _smart_capture(instruction: str, narration: str, screenshots_dir: Path) -> int:
    """智能截图：根据 URL 类型选择不同的截图策略。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        click.echo("      ⚠️ Playwright 未安装")
        return 0

    urls = _extract_urls(instruction)
    tweet_urls = [u for u in urls if _is_tweet_url(u)]
    regular_urls = [u for u in urls if not _is_tweet_url(u)]

    if not urls:
        return 0

    screenshots_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    # 从 instruction 中提取焦点关键词（用于页面内定位）
    focus_hints = _extract_focus_hints(instruction)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                ),
                locale="zh-CN",
            )
            page = context.new_page()
            page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            # 推特截图（特殊处理）
            if tweet_urls:
                count += _capture_tweets(page, tweet_urls, screenshots_dir, count)

            # 普通网页截图（带焦点定位）
            for url in regular_urls:
                count += _capture_webpage(page, url, screenshots_dir, count, focus_hints)

            browser.close()
    except Exception as e:
        click.echo(f"      ⚠️ Playwright 错误: {e}")

    return count


def _capture_webpage(page, url: str, screenshots_dir: Path, start_idx: int,
                     focus_hints: list[str]) -> int:
    """截取网页，带焦点定位。"""
    count = 0
    try:
        click.echo(f"      🌐 访问: {url[:60]}")
        resp = page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # HTTP 状态码检测
        if resp and resp.status >= 400:
            click.echo(f"      ❌ HTTP {resp.status}，跳过")
            return 0

        if _is_blocked_page(page):
            page.wait_for_timeout(5000)
            if _is_blocked_page(page):
                click.echo(f"      ❌ 被反爬拦截或错误页面，跳过")
                return 0

        # GitHub 文件路径：直接导航到具体文件
        if "github.com" in url and not url.rstrip("/").endswith(url.split("/")[-1].split(".")[0]):
            # 已经是具体文件 URL，直接截图
            pass
        elif "github.com" in url and focus_hints:
            # 尝试导航到 GitHub 仓库里的具体文件
            navigated = _github_navigate_to_file(page, focus_hints)
            if navigated:
                page.wait_for_timeout(2000)

        # 尝试滚动到焦点区域
        if focus_hints:
            _scroll_to_focus(page, focus_hints)
            page.wait_for_timeout(500)

        # 截图当前视口
        path = screenshots_dir / f"{start_idx + count:03d}.png"
        page.screenshot(path=str(path), type="png")
        count += 1

        # 再截 1-2 张（滚动不同区域）
        for _ in range(2):
            page.evaluate("window.scrollBy(0, window.innerHeight * 0.6)")
            page.wait_for_timeout(600)
            path = screenshots_dir / f"{start_idx + count:03d}.png"
            page.screenshot(path=str(path), type="png")
            count += 1

    except Exception as e:
        click.echo(f"      ⚠️ 截图失败 {url[:40]}: {e}")

    return count


def _capture_tweets(page, tweet_urls: list[str], screenshots_dir: Path,
                    start_idx: int) -> int:
    """截取推特/X 帖子。使用 embed 页面获取干净的推文卡片。"""
    count = 0

    for url in tweet_urls:
        try:
            # 将推特 URL 转为 embed URL（更干净的卡片样式）
            tweet_id = _extract_tweet_id(url)
            if not tweet_id:
                continue

            # 方案 1: 用 publish.twitter.com 的 embed
            # 方案 2: 直接访问推文页面截图
            click.echo(f"      🐦 推文: {url[:50]}")

            # 用 fxtwitter/vxtwitter 获取更好的预览（不需要登录）
            embed_url = f"https://fxtwitter.com/x/status/{tweet_id}"
            page.goto(embed_url, timeout=15000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)

            if _is_blocked_page(page):
                # fallback: 直接访问原始 URL
                page.goto(url, timeout=15000, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)

            # 尝试找到推文主体元素并截图（比全页面截图更干净）
            tweet_element = None
            for selector in ['article', '[data-testid="tweet"]', '.tweet-card', 'main']:
                try:
                    tweet_element = page.query_selector(selector)
                    if tweet_element:
                        break
                except Exception:
                    pass

            path = screenshots_dir / f"{start_idx + count:03d}.png"
            if tweet_element:
                tweet_element.screenshot(path=str(path), type="png")
            else:
                page.screenshot(path=str(path), type="png")
            count += 1

        except Exception as e:
            click.echo(f"      ⚠️ 推文截图失败: {e}")

    return count


# ---------------------------------------------------------------------------
# GitHub 智能导航
# ---------------------------------------------------------------------------

def _github_navigate_to_file(page, focus_hints: list[str]) -> bool:
    """在 GitHub 仓库页面中尝试导航到具体文件。"""
    for hint in focus_hints:
        # 如果 hint 看起来像文件路径
        if "/" in hint or hint.endswith((".ts", ".js", ".py", ".json", ".md")):
            try:
                # 点击文件树中的链接
                link = page.query_selector(f'a[href*="{hint}"]')
                if link:
                    link.click()
                    page.wait_for_timeout(2000)
                    click.echo(f"      📂 导航到: {hint}")
                    return True
            except Exception:
                pass
    return False


def _scroll_to_focus(page, focus_hints: list[str]):
    """尝试滚动到包含焦点关键词的页面区域。"""
    for hint in focus_hints:
        try:
            # 用 XPath 查找包含关键词的元素
            elements = page.query_selector_all(f'//*[contains(text(), "{hint}")]')
            if elements:
                elements[0].scroll_into_view_if_needed()
                click.echo(f"      🎯 定位到: {hint}")
                return
        except Exception:
            pass


# ---------------------------------------------------------------------------
# URL 和内容解析
# ---------------------------------------------------------------------------

def _extract_urls(instruction: str) -> list[str]:
    """从 instruction 中提取 URL。"""
    urls = re.findall(r'https?://[^\s,，。、\)）\]]+', instruction)

    site_patterns = [
        (r'(?:打开|访问|进入)\s*(?:npm|npmjs)', 'https://www.npmjs.com'),
        (r'(?:打开|访问|进入)\s*(?:GitHub|github)', 'https://github.com'),
    ]
    for pattern, url in site_patterns:
        if url and re.search(pattern, instruction, re.IGNORECASE) and url not in urls:
            pkg_match = re.search(r'(?:搜索|查找)\s+(@?[\w\-/]+)', instruction)
            if pkg_match and 'npm' in (url or ''):
                urls.append(f"https://www.npmjs.com/package/{pkg_match.group(1)}")
            elif url:
                urls.append(url)

    return urls


def _extract_focus_hints(instruction: str) -> list[str]:
    """从 instruction 中提取焦点关键词/文件路径。

    用于页面内定位——告诉 Playwright 应该滚动到哪个区域。
    """
    hints = []

    # 提取文件路径 (src/xxx/yyy.ts)
    file_paths = re.findall(r'[\w\-]+/[\w\-/]+\.(?:ts|js|py|json|md|tsx|jsx)', instruction)
    hints.extend(file_paths)

    # 提取"展示/高亮/定位到"后面的关键词
    focus_patterns = [
        r'(?:展示|高亮|显示|定位到|滚动到|找到)\s*[「「]?(.+?)[」」]?(?:[,，。;；]|$)',
        r'(?:highlight|show|scroll to)\s+(.+?)(?:[,.]|$)',
    ]
    for pattern in focus_patterns:
        matches = re.findall(pattern, instruction, re.IGNORECASE)
        for m in matches:
            cleaned = m.strip()[:50]
            if cleaned:
                hints.append(cleaned)

    # 提取技术关键词（驼峰命名、带点号的标识符）
    tech_terms = re.findall(r'[a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9]*)+', instruction)
    hints.extend(tech_terms)

    # 提取目录名
    dir_patterns = re.findall(r'(\w+/)\s*目录', instruction)
    hints.extend(dir_patterns)

    return hints[:5]  # 最多 5 个焦点


def _is_tweet_url(url: str) -> bool:
    """判断是否是推特/X 帖子 URL。"""
    return bool(re.match(
        r'https?://(?:twitter\.com|x\.com|fxtwitter\.com|vxtwitter\.com)/\w+/status/\d+',
        url
    ))


def _extract_tweet_id(url: str) -> str | None:
    """从推特 URL 中提取推文 ID。"""
    m = re.search(r'/status/(\d+)', url)
    return m.group(1) if m else None


def _is_blocked_page(page) -> bool:
    """检测页面是否被拦截或为错误页面（404/500 等）。"""
    try:
        text = page.text_content("body") or ""
        block_signals = [
            "security verification",
            "verifies you are not a bot",
            "checking your browser",
            "just a moment",
            "enable javascript",
            "captcha",
            "请完成安全验证",
            # 错误页面检测
            "page not found",
            "404 not found",
            "the requested page could not be found",
            "this page doesn't exist",
            "page does not exist",
            "404 error",
            "500 internal server error",
        ]
        text_lower = text.lower()
        return any(signal in text_lower for signal in block_signals)
    except Exception:
        return False


def _extract_highlight_keywords(narration: str) -> list[str]:
    """从 narration 中提取高亮关键词：英文术语 + 引号内容。"""
    keywords: list[str] = []

    # 引号内容
    quoted = re.findall(r"""[''""](.+?)[''""]""", narration)
    keywords.extend(quoted)

    # 英文术语（连续英文字母序列 >= 3 字符）
    english_terms = re.findall(r'[A-Za-z][A-Za-z0-9]{2,}(?:\s+[A-Za-z][A-Za-z0-9]{2,})*', narration)
    keywords.extend(english_terms)

    # 去重，取最长的 top 5
    seen: set[str] = set()
    unique: list[str] = []
    for kw in keywords:
        lower = kw.lower()
        if lower not in seen:
            seen.add(lower)
            unique.append(kw)
    unique.sort(key=len, reverse=True)
    return unique[:5]


def _dynamic_record(
    instruction: str,
    narration: str,
    output_path: Path,
    duration: float = 15.0,
) -> bool:
    """L1.5: Playwright 动态录屏 — 打开 URL、高亮关键词、平滑滚动。

    返回 True 如果录屏成功生成。
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False

    urls = _extract_urls(instruction)
    if not urls:
        return False

    url = urls[0]  # 取第一个 URL
    highlight_keywords = _extract_highlight_keywords(narration)

    import tempfile
    import time

    temp_dir = tempfile.mkdtemp(prefix="v2g_dynrec_")
    temp_path = Path(temp_dir)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            ctx = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                record_video_dir=str(temp_path),
                record_video_size={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                ),
                locale="zh-CN",
            )
            page = ctx.new_page()
            page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            record_start = time.time()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                click.echo(f"      ⚠️ 动态录屏导航失败: {e}")
                ctx.close()
                browser.close()
                return False

            page.wait_for_timeout(2000)

            # 记录内容就绪时间（用于后续裁掉加载阶段）
            content_ready = time.time() - record_start

            # 关闭 cookie banner（尝试多个常见 selector）
            cookie_selectors = [
                "button:has-text('Accept')",
                "button:has-text('accept')",
                "button:has-text('同意')",
                "button:has-text('OK')",
                "button:has-text('Got it')",
                "[id*='cookie'] button",
                "[class*='cookie'] button",
                "[class*='consent'] button",
            ]
            for sel in cookie_selectors:
                try:
                    btn = page.query_selector(sel)
                    if btn and btn.is_visible():
                        btn.click()
                        page.wait_for_timeout(500)
                        break
                except Exception:
                    pass

            # JS 注入高亮关键词
            if highlight_keywords:
                # 转义 JS 字符串
                kw_js = json.dumps(highlight_keywords, ensure_ascii=False)
                page.evaluate(f"""(() => {{
                    const keywords = {kw_js};
                    const style = document.createElement('style');
                    style.textContent = `
                        .v2g-highlight {{
                            background: linear-gradient(120deg, rgba(255,215,0,0.3) 0%, rgba(255,215,0,0.5) 100%);
                            padding: 2px 4px;
                            border-radius: 3px;
                            transition: background 0.3s;
                        }}
                    `;
                    document.head.appendChild(style);

                    const walker = document.createTreeWalker(
                        document.body, NodeFilter.SHOW_TEXT
                    );
                    const nodes = [];
                    while (walker.nextNode()) nodes.push(walker.currentNode);

                    for (const node of nodes) {{
                        let text = node.textContent;
                        let replaced = false;
                        for (const kw of keywords) {{
                            const regex = new RegExp('(' + kw.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&') + ')', 'gi');
                            if (regex.test(text)) {{
                                replaced = true;
                                const span = document.createElement('span');
                                span.innerHTML = text.replace(regex, '<mark class="v2g-highlight">$1</mark>');
                                node.parentNode.replaceChild(span, node);
                                break;
                            }}
                        }}
                    }}
                }})()""")
                page.wait_for_timeout(500)

            # 平滑滚动
            total_scroll_time = max(2.0, duration - content_ready - 2)
            scroll_steps = int(total_scroll_time / 0.5)
            for _ in range(min(scroll_steps, 20)):
                page.evaluate("window.scrollBy({top: window.innerHeight * 0.3, behavior: 'smooth'})")
                page.wait_for_timeout(500)

            # 等一下让最后的内容稳定
            page.wait_for_timeout(1000)

            ctx.close()
            browser.close()

        # 找到录制的 webm 文件
        webm_files = list(temp_path.glob("*.webm"))
        if not webm_files:
            return False

        webm_file = webm_files[0]

        # webm → mp4，裁掉 content_ready 秒
        from v2g.recorder import webm_to_mp4
        return webm_to_mp4(
            webm_file,
            output_path,
            trim_start=content_ready,
            max_duration=duration,
        )

    except Exception as e:
        click.echo(f"      ⚠️ 动态录屏失败: {e}")
        return False
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


def _extract_keywords(instruction: str) -> list[str]:
    """从 instruction 中提取关键词（用于素材库索引）。"""
    keywords = []
    tech_words = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*|[a-z]+(?:-[a-z]+)+|[A-Z]{2,}', instruction)
    keywords.extend(w.lower() for w in tech_words)
    chinese = re.findall(r'[\u4e00-\u9fff]{2,4}', instruction)
    keywords.extend(chinese[:5])
    return list(set(keywords))
