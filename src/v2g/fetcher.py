"""网页/公众号文章抓取，提取正文为 markdown。"""

import os
import re
from urllib.parse import urlparse

import click


_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def fetch_article(url: str) -> dict:
    """抓取 URL 文章内容，返回结构化结果。

    Returns:
        {
            "title": str,
            "author": str,
            "content": str,       # markdown 格式正文
            "source_url": str,
            "word_count": int,
        }
    """
    try:
        import trafilatura
    except ImportError:
        raise click.ClickException(
            "需要安装 trafilatura: pip install trafilatura"
        )

    click.echo(f"   🌐 抓取: {_truncate_url(url)}")

    # 先用 httpx 自己下载 HTML（绕过 trafilatura 默认下载的问题）
    # 特别是公众号需要浏览器 UA 头
    html = _download_html(url)
    if not html:
        raise click.ClickException(f"无法下载页面: {url}")

    # 提取正文 (markdown 格式)
    content = trafilatura.extract(
        html,
        output_format="markdown",
        include_links=False,
        include_images=False,
        include_tables=True,
    )
    if not content:
        raise click.ClickException(f"无法提取正文: {url}")

    # 提取元数据
    metadata = trafilatura.extract_metadata(html)
    title = metadata.title if metadata and metadata.title else _guess_title(content)
    author = metadata.author if metadata and metadata.author else ""

    # 清理公众号文章常见噪声
    content = _clean_wechat_noise(content)

    return {
        "title": title,
        "author": author,
        "content": content,
        "source_url": url,
        "word_count": len(content),
    }


def _download_html(url: str) -> str | None:
    """用 httpx 下载 HTML，带浏览器 UA 头，临时清理有问题的代理变量。"""
    import httpx

    # 临时清理非法代理变量（如 all_proxy=socks5://...~）
    cleaned = {}
    for key in list(os.environ):
        if "proxy" in key.lower():
            val = os.environ[key]
            if val and val.rstrip("/").endswith("~"):
                cleaned[key] = os.environ.pop(key)

    try:
        resp = httpx.get(
            url,
            headers=_BROWSER_HEADERS,
            follow_redirects=True,
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        click.echo(f"   ⚠️ 下载失败: {e}")
        return None
    finally:
        os.environ.update(cleaned)


def _clean_wechat_noise(text: str) -> str:
    """清理公众号文章的广告尾巴和引导关注。"""
    noise_patterns = [
        r"(?:点击|长按).*?关注.*$",
        r"(?:扫码|识别).*?二维码.*$",
        r"(?:转发|分享).*?朋友圈.*$",
        r"▼.*?往期.*?推荐.*$",
        r"阅读原文.*$",
    ]
    for pattern in noise_patterns:
        text = re.sub(pattern, "", text, flags=re.MULTILINE | re.DOTALL)
    return text.rstrip()


def _guess_title(content: str) -> str:
    """从正文首行猜测标题。"""
    first_line = content.strip().split("\n")[0]
    title = re.sub(r"^#+\s*", "", first_line).strip()
    return title[:60] if title else "未知标题"


def _truncate_url(url: str, max_len: int = 60) -> str:
    parsed = urlparse(url)
    short = f"{parsed.netloc}{parsed.path}"
    if len(short) > max_len:
        short = short[:max_len - 3] + "..."
    return short
