"""
素材预取管线 — Twitter 头像 / 科技人物照片 / Meme 模板

用法:
    v2g assets prefetch              # 用内置清单下载全部
    v2g assets prefetch --refresh    # 强制重新下载

本地目录:
    output/prefetch/
      avatars/twitter_{username}.jpg
      persons/{slug}.jpg
      memes/{slug}.jpg

去重: 文件已存在且 >1KB 则跳过（--refresh 强制覆盖）
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

# ═══════════════ HTTP 客户端 ═══════════════

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
}

_TIMEOUT = 20.0


def _get_proxy() -> str | None:
    """读取系统代理，清理 all_proxy 末尾的 ~ 等异常字符。"""
    import os
    for key in ("https_proxy", "HTTPS_PROXY", "http_proxy", "HTTP_PROXY"):
        val = os.environ.get(key, "").strip()
        if val:
            return val.rstrip("~")
    return None


def _make_client() -> httpx.Client:
    """构造 httpx 客户端，显式传入代理以绕过 trust_env 的 SSL 问题。"""
    proxy = _get_proxy()
    return httpx.Client(
        headers=_HEADERS,
        follow_redirects=True,
        timeout=_TIMEOUT,
        trust_env=False,
        proxy=proxy,
    )


def _download(url: str, dest: Path, refresh: bool = False) -> Path | None:
    """下载 URL 到本地文件，带去重和错误处理。"""
    if not refresh and dest.exists() and dest.stat().st_size > 1024:
        log.debug("skip (cached): %s", dest.name)
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with _make_client() as client:
            resp = client.get(url)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            log.info("  ✅ %s (%dKB)", dest.name, len(resp.content) // 1024)
            return dest
    except Exception as e:
        log.warning("  ❌ %s — %s", dest.name, e)
        return None


# ═══════════════ 三类下载器 ═══════════════


def download_twitter_avatar(
    username: str, out_dir: Path, refresh: bool = False,
) -> Path | None:
    """通过 unavatar.io 下载 Twitter 头像（免费，无需 API key）。"""
    url = f"https://unavatar.io/twitter/{username}"
    dest = out_dir / "avatars" / f"twitter_{username}.jpg"
    return _download(url, dest, refresh)


def download_person_photo(
    name: str, out_dir: Path, refresh: bool = False,
    twitter_username: str | None = None,
) -> Path | None:
    """下载人物照片。

    优先级:
      1. Twitter 头像（通过 unavatar.io/twitter/{username}），最可靠
      2. GitHub 头像（通过 unavatar.io/github/{username}）
      3. Wikipedia REST API（可能被 rate limit）
    """
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    dest = out_dir / "persons" / f"{slug}.jpg"

    if not refresh and dest.exists() and dest.stat().st_size > 1024:
        log.debug("skip (cached): %s", dest.name)
        return dest

    # ── 方案 1: 通过 Twitter 用户名拉照片（最可靠） ──
    if twitter_username:
        url = f"https://unavatar.io/twitter/{twitter_username}"
        result = _download(url, dest, refresh=True)
        if result:
            return result

    # ── 方案 2: Wikipedia REST API ──
    wiki_name = name.replace(" ", "_")
    api_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{wiki_name}"
    try:
        wiki_headers = {
            **_HEADERS,
            "Api-User-Agent": "video2gen/1.0 (https://github.com/video2gen)",
        }
        with httpx.Client(
            headers=wiki_headers, follow_redirects=True, timeout=_TIMEOUT,
            trust_env=False, proxy=_get_proxy(),
        ) as client:
            resp = client.get(api_url)
            resp.raise_for_status()
            data = resp.json()
            thumb_url = data.get("thumbnail", {}).get("source")
            if not thumb_url:
                log.warning("  ⚠️ No photo for %s", name)
                return None
    except Exception as e:
        log.warning("  ❌ Wikipedia fallback failed for %s — %s", name, e)
        return None

    return _download(thumb_url, dest, refresh=True)


def download_meme(
    slug: str, url: str, out_dir: Path, refresh: bool = False,
) -> Path | None:
    """下载 meme 模板图片。"""
    ext = Path(url).suffix or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
        ext = ".jpg"
    dest = out_dir / "memes" / f"{slug}{ext}"
    return _download(url, dest, refresh)


# ═══════════════ 内置清单 ═══════════════

DEFAULT_TWITTER_USERS = [
    # AI 公司创始人/CEO
    "sama",            # Sam Altman (OpenAI)
    "DarioAmodei",     # Dario Amodei (Anthropic)
    "elonmusk",        # Elon Musk (xAI/Tesla)
    # AI 工程/研究
    "karpathy",        # Andrej Karpathy
    "jimfan",          # Jim Fan (NVIDIA)
    "ylecun",          # Yann LeCun (Meta AI)
    # 开发者/内容创作者
    "fireship_dev",    # Fireship
    "theo",            # Theo (t3.gg)
    "levelsio",        # Pieter Levels
    "swyx",            # swyx
    # 科技公司高管
    "satyanadella",    # Satya Nadella (Microsoft)
    "sundarpichai",    # Sundar Pichai (Google)
    "tim_cook",        # Tim Cook (Apple)
]

# {显示名: Twitter 用户名} — 用 Twitter 头像作为人物照片源
DEFAULT_PERSONS: dict[str, str] = {
    "Elon Musk": "elonmusk",
    "Sam Altman": "sama",
    "Dario Amodei": "DarioAmodei",
    "Satya Nadella": "satyanadella",
    "Sundar Pichai": "sundarpichai",
    "Jensen Huang": "nvidia",           # Jensen 没有个人 Twitter，用 NVIDIA 官方
    "Andrej Karpathy": "karpathy",
    "Yann LeCun": "ylecun",
    "Tim Cook": "tim_cook",
    "Jim Fan": "jimfan",
}

DEFAULT_MEMES: dict[str, str] = {
    "this_is_fine": "https://i.imgflip.com/1nhqil.jpg",
    "surprised_pikachu": "https://i.imgflip.com/2kbn1e.jpg",
    "trust_nobody": "https://i.imgflip.com/1otk96.jpg",
    "disaster_girl": "https://i.imgflip.com/28j0te.jpg",
    "drake_hotline": "https://i.imgflip.com/30b1gx.jpg",
    "expanding_brain": "https://i.imgflip.com/1jwhww.jpg",
    "one_does_not_simply": "https://i.imgflip.com/1bij.jpg",
    "change_my_mind": "https://i.imgflip.com/24y43o.jpg",
    "distracted_boyfriend": "https://i.imgflip.com/1ur9b0.jpg",
    "two_buttons": "https://i.imgflip.com/1g8my4.jpg",
    "is_this_a_pigeon": "https://i.imgflip.com/1o00in.jpg",
    "monkey_puppet": "https://i.imgflip.com/2gnnjh.jpg",
    "always_has_been": "https://i.imgflip.com/46e43q.png",
}


# ═══════════════ 统一入口 ═══════════════


def prefetch_all(
    out_dir: Path,
    *,
    twitter_users: list[str] | None = None,
    persons: dict[str, str] | list[str] | None = None,
    memes: dict[str, str] | None = None,
    refresh: bool = False,
) -> dict[str, Path]:
    """批量预取所有素材，返回 {标识符: 本地路径} 映射。

    persons 参数:
      - dict[str, str]: {显示名: Twitter用户名} 映射
      - list[str]: 显示名列表（从 DEFAULT_PERSONS 查找 Twitter 用户名）
      - None: 使用 DEFAULT_PERSONS
    """
    results: dict[str, Path] = {}
    users = twitter_users or DEFAULT_TWITTER_USERS
    meme_map = memes or DEFAULT_MEMES

    # 规范化 persons 为 {name: twitter_username} 映射
    if persons is None:
        person_map = DEFAULT_PERSONS
    elif isinstance(persons, list):
        person_map = {}
        for name in persons:
            name = name.strip()
            if name in DEFAULT_PERSONS:
                person_map[name] = DEFAULT_PERSONS[name]
            else:
                person_map[name] = ""  # 无 Twitter 用户名，走 Wikipedia fallback
    else:
        person_map = persons

    # ── Twitter 头像 ──
    log.info("📥 Twitter 头像 (%d 个)...", len(users))
    for username in users:
        username = username.strip().lstrip("@")
        if not username:
            continue
        path = download_twitter_avatar(username, out_dir, refresh)
        if path:
            results[f"avatar:{username}"] = path
        time.sleep(0.3)  # 礼貌限速

    # ── 人物照片 ──
    log.info("📥 人物照片 (%d 个)...", len(person_map))
    for name, twitter in person_map.items():
        name = name.strip()
        if not name:
            continue
        path = download_person_photo(name, out_dir, refresh, twitter_username=twitter or None)
        if path:
            slug = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
            results[f"person:{slug}"] = path
        time.sleep(0.3)

    # ── Meme 模板 ──
    log.info("📥 Meme 模板 (%d 个)...", len(meme_map))
    for slug, url in meme_map.items():
        path = download_meme(slug, url, out_dir, refresh)
        if path:
            results[f"meme:{slug}"] = path
        time.sleep(0.2)

    total_expected = len(users) + len(person_map) + len(meme_map)
    log.info("✅ 预取完成: %d/%d 成功", len(results), total_expected)
    return results
