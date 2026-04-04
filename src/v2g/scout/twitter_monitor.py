"""Twitter/X 监控：TwitterAPI.io 搜索 + 规则粗筛 + LLM 精评 + softmax 选择。"""

import math
import random
import time

import click


def _search_one_query(
    api_key: str, query: str, query_type: str = "Top",
    max_items: int = 40, max_pages: int = 2,
) -> list[dict]:
    """单个查询的分页抓取，带 429 重试。"""
    import httpx

    tweets = []
    cursor = None

    for _ in range(max_pages):
        if len(tweets) >= max_items:
            break

        params = {"query": query, "queryType": query_type}
        if cursor:
            params["cursor"] = cursor

        # 带重试的请求
        for retry in range(3):
            try:
                resp = httpx.get(
                    "https://api.twitterapi.io/twitter/tweet/advanced_search",
                    headers={"X-API-Key": api_key},
                    params=params,
                    timeout=30.0,
                )
                if resp.status_code == 429:
                    wait = 2 ** retry + 1
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                break
            except Exception as e:
                if retry == 2:
                    click.echo(f"   ⚠️ 查询失败: {e}")
                    return tweets
                time.sleep(2)

        data = resp.json()
        page_tweets = data.get("tweets", [])
        if not page_tweets:
            break

        tweets.extend(page_tweets)

        cursor = data.get("next_cursor") or data.get("cursor")
        if not cursor or not data.get("has_next_page", False):
            break
        time.sleep(1.5)

    return tweets[:max_items]


def fetch_tweets_twitterapi(
    api_key: str,
    keywords: list[str],
    authors: list[str],
    max_tweets: int = 100,
) -> list[dict]:
    """通过 TwitterAPI.io Advanced Search 抓取推文。

    策略：分关键词多次查询 + Top 排序获取高质量推文 + 合并去重。
    Docs: https://docs.twitterapi.io/api-reference/endpoint/tweet_advanced_search
    """
    import httpx

    if not api_key:
        raise click.ClickException("TWITTER_API_IO_KEY 未设置")

    if not keywords and not authors:
        raise click.ClickException("TWITTER_KEYWORDS 和 TWITTER_AUTHORS 均未设置")

    all_tweets = {}  # tweet_id → tweet，自动去重
    per_query = max(20, max_tweets // max(len(keywords) + len(authors), 1))

    # 按关键词分别查询（Top 排序拿高互动推文）
    for kw in keywords:
        query = f"{kw} min_faves:5"  # 过滤零互动噪音
        click.echo(f"   🔍 \"{kw}\"...")
        results = _search_one_query(api_key, query, "Top", per_query)
        for t in results:
            tid = t.get("id", "")
            if tid and tid not in all_tweets:
                all_tweets[tid] = t

    # 按作者查询
    for author in authors:
        query = f"from:{author}"
        click.echo(f"   🔍 @{author}...")
        results = _search_one_query(api_key, query, "Latest", per_query)
        for t in results:
            tid = t.get("id", "")
            if tid and tid not in all_tweets:
                all_tweets[tid] = t

    tweets = list(all_tweets.values())
    click.echo(f"   ✅ 抓取 {len(tweets)} 条推文（去重后）")
    return tweets[:max_tweets]


def _normalize_tweet(raw: dict) -> dict:
    """统一 TwitterAPI.io 返回的推文字段。"""
    author = raw.get("author", {})
    return {
        "tweet_id": raw.get("id", ""),
        "author": author.get("userName", "") or author.get("name", ""),
        "text": raw.get("text", ""),
        "created_at": raw.get("createdAt", ""),
        "likes": raw.get("likeCount", 0) or 0,
        "retweets": raw.get("retweetCount", 0) or 0,
        "replies": raw.get("replyCount", 0) or 0,
        "url": raw.get("url", ""),
    }


def rule_filter(tweets: list[dict], min_likes: int = 0) -> list[dict]:
    """规则粗筛：排除纯 RT、spam、空内容。"""
    result = []
    for t in tweets:
        text = t.get("text", "")
        if not text or len(text) < 20:
            continue
        if text.startswith("RT @"):
            continue
        # 排除明显的 spam（加密货币 pump、过多 emoji）
        spam_signals = ("CA:", "Quick Buy", "TXs/Vol", "pump", "🐋 Whale")
        if any(s in text for s in spam_signals):
            continue
        if t.get("likes", 0) < min_likes:
            continue
        result.append(t)
    return result


def score_tweets_with_llm(tweets: list[dict], model: str) -> list[dict]:
    """LLM 精评推文，返回带分数的推文列表。"""
    import json as json_mod
    from v2g.llm import call_llm
    from v2g.scout import _load_prompt

    if not tweets:
        return []

    system_prompt = _load_prompt("scout_twitter.md")

    # 构造推文摘要
    tweet_lines = []
    for i, t in enumerate(tweets[:30]):  # 限制 30 条避免 prompt 过长
        tweet_lines.append(
            f"[{i}] @{t['author']} (❤️{t['likes']} 🔄{t['retweets']})\n{t['text'][:200]}"
        )
    user_message = "\n\n".join(tweet_lines)

    try:
        result = call_llm(system_prompt, user_message, model, temperature=0.2, max_tokens=3000)
        # 解析 JSON 数组
        # LLM 可能用 ```json 包裹
        result = result.strip()
        if result.startswith("```"):
            result = result.split("\n", 1)[1]
            result = result.rsplit("```", 1)[0]
        scores = json_mod.loads(result)

        # 合并分数到推文
        for score_item in scores:
            idx = score_item.get("index", -1)
            if 0 <= idx < len(tweets):
                tweets[idx]["virality"] = score_item.get("virality", 0.5)
                tweets[idx]["authority"] = score_item.get("authority", 0.5)
                tweets[idx]["timeliness"] = score_item.get("timeliness", 0.5)
                tweets[idx]["opportunity"] = score_item.get("opportunity", 0.5)
                tweets[idx]["total_score"] = (
                    tweets[idx]["virality"] * 0.2
                    + tweets[idx]["authority"] * 0.3
                    + tweets[idx]["timeliness"] * 0.25
                    + tweets[idx]["opportunity"] * 0.25
                )
        return tweets
    except Exception as e:
        click.echo(f"   ⚠️ LLM 评分失败: {e}")
        # fallback: 用 likes 作为分数
        for t in tweets:
            t["total_score"] = min(t.get("likes", 0) / 100.0, 1.0)
        return tweets


def softmax_select(
    tweets: list[dict], k: int = 10, temperature: float = 0.5
) -> list[dict]:
    """Softmax 概率采样选择 top-k 推文。"""
    if len(tweets) <= k:
        return tweets

    scores = [t.get("total_score", 0.5) for t in tweets]
    # softmax with temperature
    max_s = max(scores) if scores else 0
    exps = [math.exp((s - max_s) / max(temperature, 0.01)) for s in scores]
    total = sum(exps)
    probs = [e / total for e in exps]

    # 加权无放回采样
    selected = []
    indices = list(range(len(tweets)))
    remaining_probs = list(probs)

    for _ in range(min(k, len(tweets))):
        total_p = sum(remaining_probs)
        if total_p <= 0:
            break
        normalized = [p / total_p for p in remaining_probs]
        r = random.random()
        cumulative = 0.0
        chosen_idx = 0
        for i, p in enumerate(normalized):
            cumulative += p
            if r <= cumulative:
                chosen_idx = i
                break
        selected.append(tweets[indices[chosen_idx]])
        indices.pop(chosen_idx)
        remaining_probs.pop(chosen_idx)

    return selected


def run_twitter_monitor(cfg, temperature: float = 0.5, max_tweets: int = 100) -> "Path | None":
    """Twitter 监控主流程。"""
    from datetime import date
    from v2g.scout.store import ScoutStore
    from v2g.scout.obsidian import ObsidianWriter
    from v2g.scout.telegram import send_telegram, format_tweet_digest

    click.echo("🐦 Twitter 监控")

    import os
    twitter_api_key = os.environ.get("TWITTER_API_IO_KEY", "")
    if not twitter_api_key:
        click.echo("   ⚠️ TWITTER_API_IO_KEY 未设置，跳过 Twitter 监控")
        return None

    keywords = [k.strip() for k in cfg.twitter_keywords.split(",") if k.strip()]
    authors = [a.strip() for a in cfg.twitter_authors.split(",") if a.strip()]

    # 抓取
    raw_tweets = fetch_tweets_twitterapi(
        twitter_api_key, keywords, authors, max_tweets=max_tweets
    )
    if not raw_tweets:
        click.echo("   ℹ️ 未抓取到推文")
        return None

    # 标准化
    tweets = [_normalize_tweet(t) for t in raw_tweets]

    # 去重
    with ScoutStore(cfg.scout_db_path) as store:
        new_tweets = store.filter_new("twitter", tweets, lambda t: t["tweet_id"])
        click.echo(f"   📊 新推文: {len(new_tweets)} / {len(tweets)}")

        if not new_tweets:
            click.echo("   ℹ️ 无新推文")
            return None

        # 规则粗筛
        filtered = rule_filter(new_tweets, min_likes=10)
        click.echo(f"   🎯 粗筛后: {len(filtered)}")

        # LLM 精评
        if filtered:
            click.echo("   🤖 LLM 评分中...")
            scored = score_tweets_with_llm(filtered, cfg.scout_model)
        else:
            scored = new_tweets

        # softmax 选择
        selected = softmax_select(scored, k=10, temperature=temperature)
        click.echo(f"   ✨ 精选: {len(selected)} 条")

        # 标记已见
        store.mark_seen_batch("twitter", new_tweets, lambda t: t["tweet_id"])

    # 写入 Obsidian
    writer = ObsidianWriter(cfg.obsidian_vault_path)
    today = date.today()
    path = writer.write_twitter_report(today, selected, "")
    click.echo(f"   📝 已写入: {path}")

    # Telegram 通知
    if selected and cfg.telegram_bot_token:
        msg = format_tweet_digest(selected)
        send_telegram(cfg.telegram_bot_token, cfg.telegram_chat_id, msg)
        click.echo("   📬 Telegram 已通知")

    return path
