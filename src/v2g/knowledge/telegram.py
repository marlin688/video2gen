"""Telegram Bot 通知（HTML parse_mode）。"""

import click


def send_telegram(
    bot_token: str,
    chat_id: str,
    text: str,
    parse_mode: str = "HTML",
) -> bool:
    """发送 Telegram 消息。失败仅 log 不抛异常。"""
    if not bot_token or not chat_id:
        return False

    import httpx

    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text[:4096],  # Telegram 消息长度限制
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            },
            timeout=15.0,
        )
        if resp.status_code != 200:
            click.echo(f"   ⚠️ Telegram 发送失败: {resp.status_code}")
            return False
        return True
    except Exception as e:
        click.echo(f"   ⚠️ Telegram 发送异常: {e}")
        return False


def format_tweet_digest(tweets: list[dict]) -> str:
    """格式化推文摘要为 Telegram HTML。"""
    lines = ["<b>🐦 Twitter AI 精选</b>\n"]
    for i, t in enumerate(tweets[:10], 1):
        author = t.get("author", t.get("user", {}).get("screen_name", "unknown"))
        text = t.get("text", t.get("full_text", ""))[:150]
        likes = t.get("likes", t.get("favorite_count", 0))
        score = t.get("total_score", 0)
        url = t.get("url", "")
        lines.append(f"<b>{i}. @{_escape_html(author)}</b> (score:{score:.1f} ❤️{likes})")
        lines.append(f"{_escape_html(text)}")
        if url:
            lines.append(f'<a href="{url}">查看原文</a>')
        lines.append("")
    return "\n".join(lines)


def format_github_digest(repos: list[dict]) -> str:
    """格式化 GitHub 仓库摘要为 Telegram HTML。"""
    lines = ["<b>🔥 GitHub AI 趋势</b>\n"]
    for i, r in enumerate(repos[:10], 1):
        name = r.get("full_name", r.get("name", "unknown"))
        stars = r.get("stargazers_count", r.get("stars", 0))
        desc = (r.get("description", "") or "")[:100]
        url = r.get("html_url", r.get("url", ""))
        lines.append(f'<b>{i}. <a href="{url}">{_escape_html(name)}</a></b> ⭐{stars}')
        lines.append(f"{_escape_html(desc)}")
        lines.append("")
    return "\n".join(lines)


def _escape_html(text: str) -> str:
    """转义 HTML 特殊字符。"""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
