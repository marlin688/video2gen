"""GitHub 趋势监控：REST API 查询 + LLM 分析。"""

import os
from datetime import date, timedelta

import click

# 清理系统中可能携带非法字符的 proxy 环境变量（如 all_proxy=socks5://127.0.0.1:7890~）
for _k in list(os.environ):
    if "proxy" in _k.lower():
        _v = os.environ[_k]
        if _v and _v.rstrip("/").endswith("~"):
            os.environ[_k] = _v.rstrip("~")


def search_trending_repos(
    topics: list[str],
    since_days: int = 7,
    min_stars: int = 50,
    per_topic: int = 10,
) -> list[dict]:
    """通过 GitHub REST API 搜索近期热门 AI 仓库。

    对每个 topic 单独查询再合并去重（避免 OR 过多导致 422）。
    不需要 token（匿名 60 req/hour 足够）。
    """
    import httpx

    cutoff = (date.today() - timedelta(days=since_days)).isoformat()
    if not topics:
        topics = ["ai"]

    click.echo(f"   🔍 GitHub 搜索: stars>{min_stars}, 最近 {since_days} 天, {len(topics)} 个主题")

    all_repos = []
    for topic in topics:
        query = f"{topic} stars:>{min_stars} created:>{cutoff}"
        try:
            resp = httpx.get(
                "https://api.github.com/search/repositories",
                params={
                    "q": query,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": per_topic,
                },
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "video2gen-knowledge",
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            all_repos.extend(items)
        except Exception as e:
            click.echo(f"   ⚠️ GitHub [{topic}] 请求失败: {e}")

    # 按 full_name 去重，按 stars 降序
    seen = set()
    unique = []
    for r in all_repos:
        name = r.get("full_name", "")
        if name not in seen:
            seen.add(name)
            unique.append(r)
    unique.sort(key=lambda r: r.get("stargazers_count", 0), reverse=True)

    click.echo(f"   ✅ 找到 {len(unique)} 个仓库 (合并去重)")
    return unique


def filter_ai_repos(repos: list[dict], topic_keywords: list[str]) -> list[dict]:
    """关键词粗筛：description 或 topics 命中则保留。"""
    if not topic_keywords:
        return repos

    kw_set = {kw.lower() for kw in topic_keywords}
    result = []
    for repo in repos:
        desc = (repo.get("description") or "").lower()
        repo_topics = [t.lower() for t in repo.get("topics", [])]
        name = repo.get("full_name", "").lower()
        # 任一关键词命中 description / topics / repo name
        if any(kw in desc or kw in name or kw in repo_topics for kw in kw_set):
            result.append(repo)
    return result


def analyze_repos_with_llm(repos: list[dict], model: str) -> str:
    """用 LLM 分析 GitHub 仓库列表，返回 Markdown 分析报告。"""
    from v2g.llm import call_llm
    from v2g.knowledge import _load_prompt

    if not repos:
        return "*今日无新仓库*"

    # 构造仓库摘要给 LLM
    repo_lines = []
    for r in repos[:20]:  # 限制 20 个避免 prompt 过长
        name = r.get("full_name", "")
        stars = r.get("stargazers_count", 0)
        lang = r.get("language", "")
        desc = (r.get("description") or "")[:200]
        created = r.get("created_at", "")[:10]
        topics = ", ".join(r.get("topics", [])[:5])
        repo_lines.append(
            f"- **{name}** ⭐{stars} ({lang}) [{created}]\n"
            f"  Topics: {topics}\n"
            f"  {desc}"
        )

    system_prompt = _load_prompt("knowledge_github.md")
    user_message = "以下是本周 GitHub AI 领域热门新仓库：\n\n" + "\n\n".join(repo_lines)

    try:
        return call_llm(system_prompt, user_message, model, temperature=0.3, max_tokens=2000)
    except Exception as e:
        click.echo(f"   ⚠️ LLM 分析失败: {e}")
        return ""


def run_github_trending(cfg) -> "Path | None":
    """GitHub 趋势监控主流程。"""
    from datetime import date as date_cls
    from v2g.knowledge.store import KnowledgeStore
    from v2g.knowledge.obsidian import ObsidianWriter
    from v2g.knowledge.telegram import send_telegram, format_github_digest

    click.echo("📦 GitHub 趋势监控")

    topics = [t.strip() for t in cfg.github_topics.split(",") if t.strip()]

    # 搜索
    repos = search_trending_repos(topics, since_days=7, min_stars=50)
    if not repos:
        click.echo("   ℹ️ 未找到新仓库")

    # 去重
    store = KnowledgeStore(cfg.knowledge_db_path)
    new_repos = store.filter_new("github", repos, lambda r: r.get("full_name", ""))
    click.echo(f"   📊 新仓库: {len(new_repos)} / {len(repos)}")

    # 关键词过滤
    filtered = filter_ai_repos(new_repos, topics) if new_repos else []
    click.echo(f"   🎯 AI 相关: {len(filtered)}")

    # LLM 分析
    analysis = ""
    if filtered:
        click.echo("   🤖 LLM 分析中...")
        analysis = analyze_repos_with_llm(filtered, cfg.knowledge_model)

    # 标记已见
    if new_repos:
        store.mark_seen_batch("github", new_repos, lambda r: r.get("full_name", ""))
    store.close()

    # 写入 Obsidian
    writer = ObsidianWriter(cfg.obsidian_vault_path)
    today = date_cls.today()
    # 写入所有新仓库（包含过滤前），分析只针对 AI 相关的
    path = writer.write_github_report(today, filtered or new_repos, analysis)
    click.echo(f"   📝 已写入: {path}")

    # Telegram 通知
    if filtered and cfg.telegram_bot_token:
        msg = format_github_digest(filtered[:10])
        send_telegram(cfg.telegram_bot_token, cfg.telegram_chat_id, msg)
        click.echo("   📬 Telegram 已通知")

    return path
