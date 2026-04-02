"""Twitter/X 监控：Apify 抓取 + 规则粗筛 + LLM 精评 + softmax 选择。"""

import math
import random
import time

import click


def fetch_tweets_apify(
    token: str,
    keywords: list[str],
    authors: list[str],
    max_tweets: int = 100,
    poll_interval: int = 5,
    timeout: int = 300,
) -> list[dict]:
    """通过 Apify Twitter Scraper 抓取推文（异步轮询模型）。"""
    import httpx

    if not token:
        raise click.ClickException("APIFY_TOKEN 未设置")

    # 构造搜索 query
    search_terms = []
    if keywords:
        search_terms.extend(keywords)
    if authors:
        search_terms.extend([f"from:{a}" for a in authors])

    if not search_terms:
        raise click.ClickException("TWITTER_KEYWORDS 和 TWITTER_AUTHORS 均未设置")

    search_query = " OR ".join(search_terms)
    click.echo(f"   🐦 Twitter 搜索: {search_query[:80]}...")

    # 构造搜索 URL（apidojo/tweet-scraper 使用 startUrls 方式）
    search_url = f"https://x.com/search?q={search_query}&f=live"

    # 启动 Apify Actor run
    try:
        resp = httpx.post(
            "https://api.apify.com/v2/acts/apidojo~tweet-scraper/runs",
            params={"token": token},
            json={
                "startUrls": [{"url": search_url}],
                "maxItems": max_tweets,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        run_data = resp.json().get("data", {})
        run_id = run_data.get("id")
        if not run_id:
            click.echo("   ⚠️ Apify 启动失败: 无 run ID")
            return []
    except Exception as e:
        click.echo(f"   ⚠️ Apify 启动失败: {e}")
        return []

    click.echo(f"   ⏳ Apify run {run_id[:8]}... 等待完成")

    # 轮询等待完成
    elapsed = 0
    while elapsed < timeout:
        time.sleep(poll_interval)
        elapsed += poll_interval
        try:
            status_resp = httpx.get(
                f"https://api.apify.com/v2/actor-runs/{run_id}",
                params={"token": token},
                timeout=15.0,
            )
            status = status_resp.json().get("data", {}).get("status", "")
            if status == "SUCCEEDED":
                break
            if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                click.echo(f"   ⚠️ Apify run 失败: {status}")
                return []
        except Exception as e:
            click.echo(f"   ⚠️ 状态查询失败: {e}")
    else:
        click.echo(f"   ⚠️ Apify 超时 ({timeout}s)")
        return []

    # 获取结果
    try:
        dataset_id = run_data.get("defaultDatasetId")
        items_resp = httpx.get(
            f"https://api.apify.com/v2/datasets/{dataset_id}/items",
            params={"token": token, "format": "json"},
            timeout=30.0,
        )
        items_resp.raise_for_status()
        tweets = items_resp.json()
        click.echo(f"   ✅ 抓取 {len(tweets)} 条推文")
        return tweets
    except Exception as e:
        click.echo(f"   ⚠️ 获取推文数据失败: {e}")
        return []


def _normalize_tweet(raw: dict) -> dict:
    """统一 Apify 返回的推文字段。"""
    return {
        "tweet_id": raw.get("id") or raw.get("id_str", ""),
        "author": raw.get("author", {}).get("userName", "") or raw.get("user", {}).get("screen_name", ""),
        "text": raw.get("text") or raw.get("full_text", ""),
        "created_at": raw.get("createdAt") or raw.get("created_at", ""),
        "likes": raw.get("likeCount") or raw.get("favorite_count", 0),
        "retweets": raw.get("retweetCount") or raw.get("retweet_count", 0),
        "replies": raw.get("replyCount") or raw.get("reply_count", 0),
        "url": raw.get("url", ""),
    }


def rule_filter(tweets: list[dict], min_likes: int = 10) -> list[dict]:
    """规则粗筛：likes 阈值 + 排除纯 RT。"""
    result = []
    for t in tweets:
        if t.get("likes", 0) < min_likes:
            continue
        text = t.get("text", "")
        if text.startswith("RT @"):
            continue
        result.append(t)
    return result


def score_tweets_with_llm(tweets: list[dict], model: str) -> list[dict]:
    """LLM 精评推文，返回带分数的推文列表。"""
    import json as json_mod
    from v2g.llm import call_llm
    from v2g.knowledge import _load_prompt

    if not tweets:
        return []

    system_prompt = _load_prompt("knowledge_twitter.md")

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
    from v2g.knowledge.store import KnowledgeStore
    from v2g.knowledge.obsidian import ObsidianWriter
    from v2g.knowledge.telegram import send_telegram, format_tweet_digest

    click.echo("🐦 Twitter 监控")

    if not cfg.apify_token:
        click.echo("   ⚠️ APIFY_TOKEN 未设置，跳过 Twitter 监控")
        return None

    keywords = [k.strip() for k in cfg.twitter_keywords.split(",") if k.strip()]
    authors = [a.strip() for a in cfg.twitter_authors.split(",") if a.strip()]

    # 抓取
    raw_tweets = fetch_tweets_apify(
        cfg.apify_token, keywords, authors, max_tweets=max_tweets
    )
    if not raw_tweets:
        click.echo("   ℹ️ 未抓取到推文")
        return None

    # 标准化
    tweets = [_normalize_tweet(t) for t in raw_tweets]

    # 去重
    with KnowledgeStore(cfg.knowledge_db_path) as store:
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
            scored = score_tweets_with_llm(filtered, cfg.knowledge_model)
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
