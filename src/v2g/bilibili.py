"""B站数据采集：公开 stats + 创作中心诊断数据。

公开 API（无需认证）：
  https://api.bilibili.com/x/web-interface/view?bvid=BVxxx
  → 播放量、点赞、投币、收藏、分享、弹幕、评论

创作中心 API（需 SESSDATA + bili_jct cookie）：
  play_analyze: 互动率、流失率、播转粉率、受众标签
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

import click
import httpx

# ── 数据模型 ─────────────────────────────────────────────

@dataclass
class VideoStats:
    bvid: str
    aid: int = 0
    title: str = ""
    view_count: int = 0
    like_count: int = 0
    coin_count: int = 0
    fav_count: int = 0
    share_count: int = 0
    danmaku_count: int = 0
    reply_count: int = 0
    duration: int = 0  # 秒


@dataclass
class PlayDiagnosis:
    """创作中心 play_analyze 诊断数据（万分比单位）。"""
    bvid: str
    # 互动率 (万分比，854 = 8.54%)
    interact_rate: int = 0
    interact_pass_rate: int = 0      # 超过同类视频百分比
    # 流失率
    crash_rate: int = 0
    crash_pass_rate: int = 0
    # 弹幕率
    tm_rate: int = 0
    tm_pass_rate: int = 0
    # 播转粉率
    play_trans_fan_rate: int = 0
    play_trans_fan_pass_rate: int = 0
    # 受众标签
    viewer_tags: list[str] = field(default_factory=list)
    fans_tags: list[str] = field(default_factory=list)
    # 诊断建议
    tip: str = ""


# ── BV 号提取 ────────────────────────────────────────────

_BV_RE = re.compile(r"(BV[a-zA-Z0-9]{10})")


def extract_bvid(url_or_bvid: str) -> str | None:
    """从 URL 或字符串中提取 BV 号。"""
    m = _BV_RE.search(url_or_bvid)
    return m.group(1) if m else None


# ── 公开 API：视频基础数据 ────────────────────────────────

_VIEW_API = "https://api.bilibili.com/x/web-interface/view"
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def fetch_video_stats(bvid: str) -> VideoStats | None:
    """通过公开 API 获取视频基础数据（无需认证）。"""
    try:
        resp = httpx.get(
            _VIEW_API,
            params={"bvid": bvid},
            headers={"User-Agent": _UA},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            click.echo(f"   ⚠️ B站 API 返回错误: {data.get('message', 'unknown')}")
            return None

        info = data["data"]
        stat = info.get("stat", {})
        return VideoStats(
            bvid=bvid,
            aid=info.get("aid", 0),
            title=info.get("title", ""),
            view_count=stat.get("view", 0),
            like_count=stat.get("like", 0),
            coin_count=stat.get("coin", 0),
            fav_count=stat.get("favorite", 0),
            share_count=stat.get("share", 0),
            danmaku_count=stat.get("danmaku", 0),
            reply_count=stat.get("reply", 0),
            duration=info.get("duration", 0),
        )
    except Exception as e:
        click.echo(f"   ⚠️ 获取视频数据失败: {e}")
        return None


# ── 创作中心 API：播放诊断（需认证） ─────────────────────

_PLAY_ANALYZE_API = (
    "https://member.bilibili.com/x/web/data/archive_diagnose/play_analyze"
)


def fetch_play_diagnosis(
    bvid: str,
    sessdata: str,
    bili_jct: str,
) -> PlayDiagnosis | None:
    """通过创作中心 play_analyze 接口获取播放诊断数据。

    包含互动率、流失率、播转粉率、受众标签等。
    数值单位为万分比（如 854 = 8.54%）。
    """
    if not sessdata or not bili_jct:
        return None

    cookies = {"SESSDATA": sessdata, "bili_jct": bili_jct}

    try:
        resp = httpx.get(
            _PLAY_ANALYZE_API,
            params={"bvid": bvid},
            cookies=cookies,
            headers={
                "User-Agent": _UA,
                "Referer": "https://member.bilibili.com/",
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            click.echo(f"   ⚠️ 播放诊断 API 错误: {data.get('message', 'unknown')}")
            return None

        return _parse_play_diagnosis(bvid, data.get("data", {}))

    except Exception as e:
        click.echo(f"   ⚠️ 播放诊断获取失败: {e}")
        return None


def _parse_play_diagnosis(bvid: str, data: dict) -> PlayDiagnosis | None:
    """解析 play_analyze 响应。"""
    if not data:
        return None

    interact = data.get("guest_interact", {})
    audience = data.get("arc_audience", {})
    improve = data.get("improve_idea", {})

    viewer_tags = []
    if improve.get("viewer_tags_main"):
        viewer_tags = [t.strip() for t in improve["viewer_tags_main"].split(",") if t.strip()]

    fans_tags = []
    if improve.get("fans_tags_main"):
        fans_tags = [t.strip() for t in improve["fans_tags_main"].split(",") if t.strip()]

    return PlayDiagnosis(
        bvid=bvid,
        interact_rate=interact.get("interact_rate", 0),
        interact_pass_rate=interact.get("interact_pass_rate", 0),
        crash_rate=interact.get("crash_rate", 0),
        crash_pass_rate=interact.get("crash_pass_rate", 0),
        tm_rate=interact.get("tm_rate", 0),
        tm_pass_rate=interact.get("tm_pass_rate", 0),
        play_trans_fan_rate=interact.get("play_trans_fan_rate", 0),
        play_trans_fan_pass_rate=interact.get("play_trans_fan_pass_rate", 0),
        viewer_tags=viewer_tags[:10],
        fans_tags=fans_tags[:10],
        tip=audience.get("tip", ""),
    )


# ── 批量获取 ─────────────────────────────────────────────

def fetch_batch_stats(
    bvids: list[str],
    delay: float = 1.0,
) -> dict[str, VideoStats]:
    """批量获取多个视频的基础数据。

    Args:
        bvids: BV 号列表
        delay: 请求间隔（秒），避免触发频率限制
    """
    results = {}
    for i, bvid in enumerate(bvids):
        if i > 0:
            time.sleep(delay)
        stats = fetch_video_stats(bvid)
        if stats:
            results[bvid] = stats
    return results
