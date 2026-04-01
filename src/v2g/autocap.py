"""B 类素材自动截图：解析 recording_instruction，用 Playwright 截图。

三级 fallback：
  L1: 素材库匹配 → 直接复用已有素材
  L2: Playwright 截图 → 从 instruction 中提取 URL 自动截图
  L3: 跳过 → 渲染时由 Remotion TerminalDemoSegment 降级处理
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

    library = MaterialLibrary()
    recordings_dir = output_dir / "recordings"
    recordings_dir.mkdir(exist_ok=True)

    click.echo(f"🖥️ 自动素材采集: {len(b_segments)} 段 B 类素材\n")
    success = 0

    for seg in b_segments:
        seg_id = seg.get("id", 0)
        instruction = seg.get("recording_instruction", "")
        rec_path = recordings_dir / f"seg_{seg_id}.mp4"

        # 已有录屏则跳过
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

        # L2: Playwright 自动截图
        screenshots_dir = output_dir / "screenshots" / f"seg_{seg_id}"
        captured = _playwright_capture(instruction, screenshots_dir)
        if captured:
            # 用 recorder.py 合成视频
            from v2g.recorder import screenshots_to_video
            screenshots_to_video(screenshots_dir, rec_path, duration=15.0)
            if rec_path.exists():
                click.echo(f"      ✅ L2 Playwright 截图成功 ({captured} 张)")
                # 存入素材库
                library.add(MaterialEntry(
                    type="capture",
                    path=str(rec_path),
                    keywords=_extract_keywords(instruction),
                    description=instruction[:80],
                    source_project=project_id,
                ))
                success += 1
                continue

        # L3: 跳过，由 Remotion fallback 处理
        click.echo(f"      ⬜ L3 跳过 → 渲染时使用终端模拟动画")

    click.echo(f"\n📊 素材采集完成: {success}/{len(b_segments)}")
    return success


def _playwright_capture(instruction: str, screenshots_dir: Path) -> int:
    """从 instruction 中提取 URL 并用 Playwright 截图。

    返回截图数量，0 表示失败或无 URL。
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        click.echo("      ⚠️ Playwright 未安装，跳过自动截图")
        click.echo("      提示: pip install playwright && playwright install chromium")
        return 0

    urls = _extract_urls(instruction)
    if not urls:
        # 没有 URL 的 instruction（如"打开终端执行命令"）无法用 Playwright 处理
        return 0

    screenshots_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    try:
        with sync_playwright() as p:
            # 使用更真实的浏览器配置减少反爬检测
            browser = p.chromium.launch(
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ]
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
            # 覆盖 navigator.webdriver 标记
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            for url in urls:
                try:
                    click.echo(f"      🌐 访问: {url[:60]}")
                    page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)  # 等待 JS 渲染 + 可能的验证

                    # 检测是否被 Cloudflare 等拦截
                    if _is_blocked_page(page):
                        click.echo(f"      ⚠️ 被反爬拦截，等待验证通过...")
                        page.wait_for_timeout(5000)  # 再等一会
                        if _is_blocked_page(page):
                            click.echo(f"      ❌ 无法通过验证，跳过此 URL")
                            continue

                    # 首屏截图
                    path = screenshots_dir / f"{count:03d}.png"
                    page.screenshot(path=str(path), type="png")
                    count += 1

                    # 滚动截图（捕获页面不同区域）
                    for scroll_step in range(2):
                        page.evaluate("window.scrollBy(0, window.innerHeight * 0.7)")
                        page.wait_for_timeout(800)
                        path = screenshots_dir / f"{count:03d}.png"
                        page.screenshot(path=str(path), type="png")
                        count += 1

                except Exception as e:
                    click.echo(f"      ⚠️ 截图失败 {url[:40]}: {e}")

            browser.close()
    except Exception as e:
        click.echo(f"      ⚠️ Playwright 错误: {e}")

    return count


def _is_blocked_page(page) -> bool:
    """检测页面是否被 Cloudflare/Captcha 等拦截。"""
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
        ]
        text_lower = text.lower()
        return any(signal in text_lower for signal in block_signals)
    except Exception:
        return False


def _extract_urls(instruction: str) -> list[str]:
    """从 instruction 文本中提取 URL。"""
    # 匹配 http/https URL
    urls = re.findall(r'https?://[^\s,，。、\)）]+', instruction)

    # 常见网站名 → URL 映射
    site_patterns = [
        (r'(?:打开|访问|进入)\s*(?:npm|npmjs)', 'https://www.npmjs.com'),
        (r'(?:打开|访问|进入)\s*(?:GitHub|github)', 'https://github.com'),
        (r'(?:打开|访问|进入)\s*(?:VS\s*Code|vscode)', None),  # 本地应用，不处理
    ]
    for pattern, url in site_patterns:
        if url and re.search(pattern, instruction, re.IGNORECASE) and url not in urls:
            # 尝试从 instruction 中提取更具体的路径
            pkg_match = re.search(r'(?:搜索|查找)\s+(@?[\w\-/]+)', instruction)
            if pkg_match and 'npm' in (url or ''):
                urls.append(f"https://www.npmjs.com/package/{pkg_match.group(1)}")
            elif url:
                urls.append(url)

    return urls


def _extract_keywords(instruction: str) -> list[str]:
    """从 instruction 中提取关键词（用于素材库索引）。"""
    keywords = []
    # 提取英文技术词
    tech_words = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*|[a-z]+(?:-[a-z]+)+|[A-Z]{2,}', instruction)
    keywords.extend(w.lower() for w in tech_words)
    # 提取中文关键短语（2-4字）
    chinese = re.findall(r'[\u4e00-\u9fff]{2,4}', instruction)
    keywords.extend(chinese[:5])
    return list(set(keywords))
