"""网页截图/录屏质量过滤。

用于在自动采图与网页截图前，拦截以下低价值页面：
1. 反爬/错误页
2. 登录墙 / 注册页 / 账号引导页
3. 信息密度过低的空壳首屏
"""

from __future__ import annotations

from urllib.parse import urlparse


BLOCK_SIGNALS = (
    "security verification",
    "verifies you are not a bot",
    "checking your browser",
    "just a moment",
    "enable javascript",
    "captcha",
    "请完成安全验证",
    "page not found",
    "404 not found",
    "the requested page could not be found",
    "this page doesn't exist",
    "page does not exist",
    "404 error",
    "500 internal server error",
)

AUTH_STRONG_SIGNALS = (
    "sign up",
    "create account",
    "join now",
    "continue with google",
    "continue with apple",
    "continue with github",
    "forgot password",
    "现在就加入",
    "立即注册",
    "创建账号",
    "已有账号",
    "没有账号",
    "忘记密码",
)

AUTH_SOFT_SIGNALS = (
    "log in",
    "login",
    "登录",
    "注册",
    "加入",
    "开始使用",
    "already have an account",
    "discover more",
    "discover what's happening",
    "正在发生",
    "发现更多",
    "grok",
)

AUTH_RISK_HOSTS = {
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
    "linkedin.com",
    "www.linkedin.com",
    "instagram.com",
    "www.instagram.com",
    "facebook.com",
    "www.facebook.com",
}


def is_auth_risk_host(url: str) -> bool:
    """判断 URL 是否属于高概率登录墙站点。"""
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return host in AUTH_RISK_HOSTS


def collect_page_snapshot(page) -> dict:
    """从 Playwright page 收集轻量质量评估信息。"""
    try:
        snapshot = page.evaluate(
            """() => {
                const text = (document.body?.innerText || "").replace(/\\s+/g, " ").trim();
                const count = (sel) => document.querySelectorAll(sel).length;
                return {
                    url: window.location.href || "",
                    title: document.title || "",
                    text: text.slice(0, 8000),
                    text_length: text.length,
                    heading_count: count("h1,h2,h3"),
                    paragraph_count: count("p,li"),
                    link_count: count("a"),
                    button_count: count("button,[role='button']"),
                    input_count: count("input,textarea,[contenteditable='true']"),
                    code_count: count("pre,code"),
                    image_count: count("img,video,svg,canvas"),
                    article_count: count("main,article,[role='main'],.markdown-body,.application-main,.docs-story"),
                };
            }"""
        )
        if isinstance(snapshot, dict):
            return snapshot
    except Exception:
        pass
    return {
        "url": "",
        "title": "",
        "text": "",
        "text_length": 0,
        "heading_count": 0,
        "paragraph_count": 0,
        "link_count": 0,
        "button_count": 0,
        "input_count": 0,
        "code_count": 0,
        "image_count": 0,
        "article_count": 0,
    }


def assess_page_snapshot(snapshot: dict, url: str = "") -> tuple[bool, str]:
    """评估页面是否适合截图/录屏。"""
    text = str(snapshot.get("text") or "")
    title = str(snapshot.get("title") or "")
    corpus = f"{title}\n{text}".lower()
    source_url = url or str(snapshot.get("url") or "")
    host = ""
    try:
        host = urlparse(source_url).netloc.lower()
    except Exception:
        host = ""

    if any(signal in corpus for signal in BLOCK_SIGNALS):
        return False, "blocked"

    strong_hits = sum(1 for signal in AUTH_STRONG_SIGNALS if signal in corpus)
    soft_hits = sum(1 for signal in AUTH_SOFT_SIGNALS if signal in corpus)
    has_form = int(snapshot.get("input_count") or 0) > 0
    has_cta = int(snapshot.get("button_count") or 0) > 0
    auth_score = strong_hits * 2 + soft_hits

    if strong_hits >= 1 and (has_form or has_cta):
        return False, "auth_wall"
    if auth_score >= 3 and (has_form or has_cta):
        return False, "auth_wall"
    if host in AUTH_RISK_HOSTS and auth_score >= 1:
        return False, "auth_wall"

    text_length = int(snapshot.get("text_length") or 0)
    heading_count = int(snapshot.get("heading_count") or 0)
    paragraph_count = int(snapshot.get("paragraph_count") or 0)
    link_count = int(snapshot.get("link_count") or 0)
    code_count = int(snapshot.get("code_count") or 0)
    image_count = int(snapshot.get("image_count") or 0)
    article_count = int(snapshot.get("article_count") or 0)

    content_score = (
        heading_count * 2
        + paragraph_count
        + code_count * 3
        + min(image_count, 4)
        + article_count * 2
    )
    is_dense = (
        text_length >= 260
        or content_score >= 10
        or (code_count >= 1 and text_length >= 120)
        or (heading_count >= 2 and paragraph_count >= 4)
        or (article_count >= 1 and text_length >= 160)
    )
    if not is_dense and text_length < 160 and content_score < 8 and link_count < 24:
        return False, "low_density"

    return True, "ok"
