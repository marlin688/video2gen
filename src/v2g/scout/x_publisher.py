"""X (Twitter) 发帖模块 - OAuth 1.0a，发单推或帖串。"""

import hashlib
import os
import re
from pathlib import Path


def _get_client():
    try:
        import tweepy
    except ImportError:
        raise ImportError("请先安装: pip install 'video2gen[x]'")

    missing = [k for k in ("X_CONSUMER_KEY", "X_CONSUMER_SECRET",
                            "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")
               if not os.environ.get(k)]
    if missing:
        raise ValueError(f"缺少环境变量: {', '.join(missing)}")

    return tweepy.Client(
        consumer_key=os.environ["X_CONSUMER_KEY"],
        consumer_secret=os.environ["X_CONSUMER_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )


def post_thread(tweets: list[str], dry_run: bool = False) -> list[str]:
    """发布帖串，返回 tweet ID 列表。dry_run=True 只打印不发。"""
    if not tweets:
        raise ValueError("推文列表为空")

    if dry_run:
        for i, t in enumerate(tweets, 1):
            print(f"[DRY RUN] 推文 {i}/{len(tweets)}:\n{t}\n{'─'*40}")
        return [f"dry_run_{i}" for i in range(len(tweets))]

    client = _get_client()
    tweet_ids: list[str] = []
    reply_to: str | None = None

    for tweet in tweets:
        kwargs: dict = {"text": tweet}
        if reply_to:
            kwargs["in_reply_to_tweet_id"] = reply_to
        resp = client.create_tweet(**kwargs)
        tid = str(resp.data["id"])
        tweet_ids.append(tid)
        reply_to = tid

    return tweet_ids


def parse_waterfall_tweets(content: str, version: str = "short") -> list[str]:
    """从 waterfall markdown 提取推文。version: 'short' | 'long'"""
    if version == "short":
        pat = r"###\s*短版.*?(?=###\s*长版|^---|\Z)"
    else:
        pat = r"###\s*长版.*?(?=^---|\Z)"

    m = re.search(pat, content, re.DOTALL | re.MULTILINE)
    if not m:
        return []

    section = m.group(0)
    # 按 **推文 N** 行分割，每块提取 blockquote 内容
    chunks = re.split(r'\n(?=\*\*推文)', section)

    tweets = []
    for chunk in chunks:
        lines = [ln.strip()[1:].strip()
                 for ln in chunk.split('\n')
                 if ln.strip().startswith('>')]
        if lines:
            text = '\n'.join(lines).strip()
            if text and text != '...':
                tweets.append(text)

    return tweets


def _content_hash(tweets: list[str]) -> str:
    return hashlib.md5("\n---\n".join(tweets).encode()).hexdigest()[:12]


def run_publish(cfg, file_path: str | None, version: str,
                dry_run: bool, force: bool) -> None:
    import click
    from v2g.scout.store import ScoutStore
    from v2g.scout.obsidian import ObsidianWriter

    click.echo("🐦 X 发布")

    # 定位 waterfall 文件
    if file_path:
        target = Path(file_path)
    else:
        writer = ObsidianWriter(cfg.obsidian_vault_path)
        dist_dir = writer.vault / "scout" / "distribution"
        files = sorted(dist_dir.glob("*-waterfall-*.md"), reverse=True)
        if not files:
            click.echo("   ⚠️ 未找到 waterfall 文件，请先运行 v2g scout waterfall")
            return
        target = files[0]
        click.echo(f"   📄 使用最新文件: {target.name}")

    if not target.exists():
        click.echo(f"   ⚠️ 文件不存在: {target}")
        return

    content = target.read_text(encoding="utf-8")
    tweets = parse_waterfall_tweets(content, version)

    if not tweets:
        click.echo(f"   ⚠️ 未解析到推文 (version={version})，请检查文件格式")
        return

    item_id = _content_hash(tweets)

    with ScoutStore(cfg.scout_db_path) as store:
        if store.is_seen("x_publish", item_id) and not force:
            click.echo(f"   ⏭️  已发布过（hash={item_id}），用 --force 强制重发")
            return

        click.echo(f"\n   📋 {version}版，共 {len(tweets)} 条:\n")
        for i, t in enumerate(tweets, 1):
            preview = t[:80] + ('…' if len(t) > 80 else '')
            click.echo(f"   [{i}] {preview}")

        if not dry_run and not click.confirm("\n   确认发布?"):
            click.echo("   ❌ 已取消")
            return

        tweet_ids = post_thread(tweets, dry_run=dry_run)

        if not dry_run:
            store.mark_seen("x_publish", item_id, {
                "tweet_ids": tweet_ids,
                "version": version,
                "source_file": target.name,
                "first_tweet": tweets[0][:100],
            })
            click.echo(f"\n   ✅ 发布成功！首推: https://x.com/i/web/status/{tweet_ids[0]}")
        else:
            click.echo("\n   ✅ Dry run 完成，未实际发布")
