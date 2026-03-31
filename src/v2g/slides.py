"""Stage 5a: AI 生成 PPT 图文卡片 (素材 A)。"""

import json
import os
import re
import subprocess
from pathlib import Path

import click

from v2g.config import Config
from v2g.checkpoint import PipelineState


def _create_text_image(text: str, output_path: Path, width: int, height: int,
                       bg_color: tuple = (0, 0, 0), text_color: tuple = (255, 255, 255)):
    """生成简单的文字卡片图片（供 editor.py 占位用）。"""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    font_candidates = [
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    font_path = None
    for f in font_candidates:
        if Path(f).exists():
            font_path = f
            break

    try:
        font = ImageFont.truetype(font_path, 40) if font_path else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    # 居中绘制（处理多行）
    lines = [text[i:i+30] for i in range(0, len(text), 30)]
    y = height // 2 - len(lines) * 25
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((width - tw) // 2, y), line, fill=text_color, font=font)
        y += 55

    img.save(str(output_path), "PNG")


def _generate_slide_html(slide_content: dict, seg_id: int, width: int, height: int) -> str:
    """生成单张卡片的 HTML — B站知识区风格。"""
    title = slide_content.get("title", "")
    bullets = slide_content.get("bullet_points", [])
    chart_hint = slide_content.get("chart_hint", "")

    # 过滤 emoji
    def clean(text: str) -> str:
        return re.sub(
            r'[^\u4e00-\u9fff\u3000-\u303f\uff00-\uffef'
            r'a-zA-Z0-9\s.,;:!?\-+=/()（）【】《》、。，；：！？""''…—<>]',
            '', text)

    bullet_html = ""
    for i, bp in enumerate(bullets):
        num = f'{i + 1:02d}'
        bullet_html += f'<li><span class="num">{num}</span><span class="text">{clean(bp)}</span></li>\n'

    chart_html = ""
    if chart_hint:
        chart_html = f'<div class="chart-hint">{clean(chart_hint)}</div>'

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    width: {width}px;
    height: {height}px;
    background: #0b0f1a;
    background-image:
        radial-gradient(ellipse at 15% 80%, rgba(0, 120, 255, 0.08) 0%, transparent 50%),
        radial-gradient(ellipse at 85% 20%, rgba(0, 212, 255, 0.06) 0%, transparent 50%);
    font-family: "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", sans-serif;
    color: #e0e0e0;
    padding: 70px 100px;
    overflow: hidden;
    position: relative;
}}
/* 顶部装饰线 */
body::before {{
    content: "";
    position: absolute;
    top: 0; left: 80px; right: 80px;
    height: 3px;
    background: linear-gradient(90deg, transparent, #00d4ff, #00ff88, transparent);
    border-radius: 2px;
}}
.title {{
    font-size: 58px;
    font-weight: 800;
    color: #ffffff;
    margin-bottom: 50px;
    line-height: 1.3;
    letter-spacing: 2px;
    position: relative;
    padding-left: 24px;
}}
.title::before {{
    content: "";
    position: absolute;
    left: 0;
    top: 8px;
    bottom: 8px;
    width: 5px;
    background: linear-gradient(180deg, #00d4ff, #00ff88);
    border-radius: 3px;
}}
.bullets {{
    list-style: none;
    margin-top: 10px;
}}
.bullets li {{
    display: flex;
    align-items: flex-start;
    margin-bottom: 24px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
    padding: 20px 28px;
    transition: all 0.3s;
}}
.bullets li .num {{
    flex-shrink: 0;
    width: 44px;
    height: 44px;
    background: linear-gradient(135deg, #00d4ff, #0088cc);
    color: #fff;
    font-size: 22px;
    font-weight: 700;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-right: 22px;
    margin-top: 2px;
}}
.bullets li .text {{
    font-size: 36px;
    line-height: 1.6;
    color: #d0d0d0;
}}
.chart-hint {{
    margin-top: 36px;
    font-size: 28px;
    color: #666;
    font-style: italic;
    padding-left: 24px;
    border-left: 2px solid #333;
}}
</style>
</head>
<body>
<div class="title">{clean(title)}</div>
<ul class="bullets">
{bullet_html}
</ul>
{chart_html}
</body>
</html>"""


def _html_to_png_playwright(html_content: str, output_path: Path, width: int, height: int):
    """用 Playwright 将 HTML 渲染为 PNG。"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height})
        page.set_content(html_content)
        page.screenshot(path=str(output_path), type="png")
        browser.close()


def _html_to_png_simple(html_content: str, output_path: Path, width: int, height: int):
    """用 Pillow 生成图文卡片。"""
    import re
    from PIL import Image, ImageDraw, ImageFont

    title_match = re.search(r'<div class="title">(.*?)</div>', html_content)
    title = title_match.group(1) if title_match else "Info Card"
    bullets = re.findall(r'<li>(.*?)</li>', html_content)

    # 创建深色背景
    img = Image.new("RGB", (width, height), color=(10, 14, 39))
    draw = ImageDraw.Draw(img)

    # 查找 CJK 字体
    font_candidates = [
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    font_path = None
    for f in font_candidates:
        if Path(f).exists():
            font_path = f
            break

    try:
        title_font = ImageFont.truetype(font_path, 60) if font_path else ImageFont.load_default()
        body_font = ImageFont.truetype(font_path, 38) if font_path else ImageFont.load_default()
    except Exception:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()

    # 绘制标题
    title_color = (0, 212, 255)  # 荧光蓝
    # 居中标题
    bbox = draw.textbbox((0, 0), title, font=title_font)
    title_w = bbox[2] - bbox[0]
    draw.text(((width - title_w) // 2, int(height * 0.12)), title, fill=title_color, font=title_font)

    # 绘制要点（过滤 emoji，保留中英文和基础标点）
    bullet_color = (230, 230, 230)
    accent_color = (0, 255, 136)  # 荧光绿
    y = int(height * 0.30)
    for bp in bullets[:6]:
        clean_bp = re.sub(
            r'[^\u4e00-\u9fff\u3000-\u303f\uff00-\uffef'
            r'a-zA-Z0-9\s.,;:!?\-+=/()（）【】《》、。，；：！？""''…—]',
            '', bp
        ).strip()[:50]
        draw.text((int(width * 0.08), y), "-", fill=accent_color, font=body_font)
        draw.text((int(width * 0.08) + 40, y), clean_bp, fill=bullet_color, font=body_font)
        y += 80

    img.save(str(output_path), "PNG")


def generate_slide_image(slide_content: dict, seg_id: int, output_path: Path,
                         width: int = 1920, height: int = 1080):
    """生成单张图文卡片 PNG（供 editor.py 降级调用）。"""
    html = _generate_slide_html(slide_content, seg_id, width, height)
    try:
        import playwright  # noqa: F401
        _html_to_png_playwright(html, output_path, width, height)
    except (ImportError, Exception):
        _html_to_png_simple(html, output_path, width, height)


def run_slides(cfg: Config, video_id: str, model: str) -> PipelineState:
    """执行 Stage 5a: 生成 PPT 图文卡片。"""
    state = PipelineState.load(cfg.output_dir, video_id)
    if not state.tts_done:
        raise click.ClickException("TTS 尚未完成，请先运行 v2g tts")

    if state.slides_done:
        click.echo("⏭️  图���卡片已生成，跳过")
        return state

    output_dir = cfg.output_dir / video_id
    slides_dir = output_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    # 读取脚本
    script_path = Path(state.script_json)
    script_data = json.loads(script_path.read_text(encoding="utf-8"))

    a_segments = [s for s in script_data.get("segments", []) if s.get("material") == "A"]

    if not a_segments:
        click.echo("   ℹ️ 无素材 A 段，跳过图文卡片生成")
        state.slides_done = True
        state.save(cfg.output_dir)
        return state

    click.echo(f"📊 生成图文卡片: {len(a_segments)} 张")

    # 检测 Playwright 是否可用
    has_playwright = False
    try:
        import playwright
        has_playwright = True
    except ImportError:
        click.echo("   ℹ️ Playwright 未安装，使用 FFmpeg 简易卡片模式")
        click.echo("   提示: pip install playwright && playwright install chromium")

    for seg in a_segments:
        seg_id = seg.get("id", 0)
        slide_content = seg.get("slide_content", {})
        if not slide_content:
            continue

        output_path = slides_dir / f"slide_{seg_id}.png"
        click.echo(f"   Slide {seg_id}: {slide_content.get('title', '?')}")

        html = _generate_slide_html(slide_content, seg_id, cfg.video_width, cfg.video_height)

        try:
            if has_playwright:
                _html_to_png_playwright(html, output_path, cfg.video_width, cfg.video_height)
            else:
                _html_to_png_simple(html, output_path, cfg.video_width, cfg.video_height)

            if output_path.exists():
                click.echo(f"   ✅ {output_path.name}")
            else:
                click.echo(f"   ⚠️ 生成失败: {output_path.name}")
        except Exception as e:
            click.echo(f"   ⚠️ Slide {seg_id} 生成失败: {e}")
            # 生成占位卡片
            _html_to_png_simple(html, output_path, cfg.video_width, cfg.video_height)

    state.slides_done = True
    state.last_error = ""
    state.save(cfg.output_dir)
    return state
