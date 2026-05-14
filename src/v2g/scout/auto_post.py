"""自动热点发帖: 发现热点 → 选话题 → waterfall → 发到 X"""

import json
import os
from datetime import date
from pathlib import Path


def _generate_daily_digest(cfg, vault: Path, today: date) -> None:
    """从当日各源报告生成 daily digest（与 scout all 相同逻辑）。"""
    import click
    from v2g.llm import call_llm
    from v2g.scout import _load_prompt
    from v2g.scout.obsidian import ObsidianWriter

    # 检查 digest 是否已存在
    writer = ObsidianWriter(cfg.obsidian_vault_path)
    digest_path = writer.vault / "daily" / f"{today}.md"
    if digest_path.exists():
        return

    source_files = {
        "github":   vault / "scout" / "github"  / f"{today}-trending.md",
        "hn":       vault / "scout" / "hn"       / f"{today}-hn.md",
        "arxiv":    vault / "scout" / "arxiv"    / f"{today}-arxiv.md",
        "twitter":  vault / "scout" / "twitter"  / f"{today}-curated.md",
        "articles": vault / "scout" / "articles" / f"{today}-articles.md",
    }
    sections: dict[str, str] = {}
    for name, path in source_files.items():
        if path.exists():
            sections[name] = path.read_text(encoding="utf-8")[:4000]

    if not sections:
        click.echo("   ℹ️ 无源报告，跳过 daily digest")
        return

    click.echo("   📋 生成 daily digest...")
    system_prompt = _load_prompt("scout_daily.md")
    user_msg = "\n\n---\n\n".join(f"## {k}\n{v}" for k, v in sections.items())
    digest = call_llm(system_prompt, user_msg, cfg.scout_model, temperature=0.3, max_tokens=1000)

    bad = ("无法生成", "需要完整", "没有可用")
    if len(digest.strip()) < 80 or any(s in digest[:200] for s in bad):
        click.echo("   ⚠️ digest 内容质量不佳，跳过写入")
        return

    out = writer.write_daily_digest(today, {"汇总": digest})
    click.echo(f"   📝 daily digest: {out}")


def _get_posted_slugs_today(cfg, today: date) -> set[str]:
    """获取今日已发布的话题 slug 集合（从 ScoutStore）。"""
    from v2g.scout.store import ScoutStore

    posted: set[str] = set()
    with ScoutStore(cfg.scout_db_path) as store:
        cur = store._conn.execute(
            "SELECT data FROM seen_items WHERE source='x_publish' AND fetched_at LIKE ?",
            (f"{today}%",),
        )
        for row in cur.fetchall():
            try:
                data = json.loads(row[0])
                src = data.get("source_file", "")
                prefix = f"{today}-waterfall-"
                if src.startswith(prefix):
                    posted.add(src[len(prefix):].removesuffix(".md"))
            except (json.JSONDecodeError, KeyError):
                pass
    return posted


def _ensure_scout_done(cfg, vault: Path, today: date) -> None:
    """今日 ideation 文件不存在时自动运行 scout all。"""
    import click

    ideation_dir = vault / "scout" / "ideation"
    today_files = list(ideation_dir.glob(f"{today}-*.md")) if ideation_dir.exists() else []
    if today_files:
        click.echo(f"   ✓ 今日已有 {len(today_files)} 个 ideation 话题，跳过 scout")
        return

    click.echo("   📡 运行 scout all 发现今日热点...")

    from v2g.scout.github_trending import run_github_trending
    from v2g.scout.hn_monitor import run_hn_monitor
    from v2g.scout.article_monitor import run_article_monitor
    from v2g.scout.ideation import run_ideation

    for name, fn in [("GitHub", run_github_trending), ("HN", run_hn_monitor),
                     ("文章", run_article_monitor)]:
        try:
            fn(cfg)
        except Exception as e:
            click.echo(f"   ⚠️ {name} 失败: {e}")

    # Twitter 热点（需要 APIFY_TOKEN 或 TWITTER_API_IO_KEY）
    if os.environ.get("APIFY_TOKEN") or os.environ.get("TWITTER_API_IO_KEY"):
        try:
            from v2g.scout.twitter_monitor import run_twitter_monitor
            run_twitter_monitor(cfg)
        except Exception as e:
            click.echo(f"   ⚠️ Twitter 失败: {e}")
    else:
        click.echo("   ℹ️  未配置 APIFY_TOKEN，跳过 Twitter 热点")

    # 生成 daily digest（ideation 依赖它）
    try:
        _generate_daily_digest(cfg, vault, today)
    except Exception as e:
        click.echo(f"   ⚠️ daily digest 失败: {e}")

    # 从今日 digest 自动选题并生成 ideation
    try:
        run_ideation(cfg, from_daily=True)
    except Exception as e:
        click.echo(f"   ⚠️ ideation 失败: {e}")


def _pick_next_topic(cfg, vault: Path, today: date) -> tuple[str, Path] | tuple[None, None]:
    """从今日 ideation 选出下一个未发布的话题，返回 (topic, ideation_file)。"""
    from v2g.scout.url_extractor import list_ideation_topics
    from v2g.scout.ideation import _topic_slug

    topics = list_ideation_topics(vault, today)
    if not topics:
        return None, None

    posted = _get_posted_slugs_today(cfg, today)
    for t in topics:
        if _topic_slug(t["title"]) not in posted:
            return t["title"], t["source_path"]
    return None, None


def run_auto_post(cfg, dry_run: bool = False, force: bool = False) -> None:
    """自动热点发帖主流程。"""
    import click
    from v2g.scout.obsidian import ObsidianWriter
    from v2g.scout.waterfall import run_waterfall
    from v2g.scout.x_publisher import run_publish

    click.echo("🤖 自动热点发帖")

    writer = ObsidianWriter(cfg.obsidian_vault_path)
    vault = writer.vault
    today = date.today()

    # 1. 确保今日 scout 已完成
    _ensure_scout_done(cfg, vault, today)

    # 2. 选下一个未发布的话题
    topic, ideation_file = _pick_next_topic(cfg, vault, today)
    if not topic:
        from v2g.scout.url_extractor import list_ideation_topics
        if not list_ideation_topics(vault, today):
            click.echo("   ⚠️ 今日 ideation 为空（scout 可能未完成），无话题可发")
            click.echo("   💡 提示: LLM 连接失败会导致 daily digest 和 ideation 无法生成")
            click.echo("        检查 ANTHROPIC_API_KEY 或 GPT_API_KEY 是否正确配置")
        else:
            click.echo("   ✅ 今日所有话题已全部发布")
        return

    click.echo(f"   🎯 话题: {topic}\n")

    # 3. 生成 waterfall（以 ideation 文件为内容输入）
    waterfall_path = run_waterfall(cfg, topic, file_path=str(ideation_file) if ideation_file else None)
    if not waterfall_path:
        click.echo("   ⚠️ waterfall 生成失败")
        return

    # 4. 发布短版 3 条
    click.echo()
    run_publish(cfg, str(waterfall_path), version="short", dry_run=dry_run, force=force)


# ──────────────────────────────────────────────────────────────
# launchd 定时任务安装
# ──────────────────────────────────────────────────────────────

PLIST_LABEL = "com.v2g.auto-post"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"
LOG_DIR = Path.home() / ".v2g"


def _build_plist(v2g_bin: str, project_dir: str, hours: list[int]) -> str:
    intervals = "\n".join(
        f"        <dict>\n"
        f"            <key>Hour</key><integer>{h}</integer>\n"
        f"            <key>Minute</key><integer>0</integer>\n"
        f"        </dict>"
        for h in hours
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>{v2g_bin}</string>
        <string>scout</string>
        <string>auto-post</string>
    </array>

    <key>WorkingDirectory</key>
    <string>{project_dir}</string>

    <key>StartCalendarInterval</key>
    <array>
{intervals}
    </array>

    <key>StandardOutPath</key>
    <string>{LOG_DIR}/auto-post.log</string>
    <key>StandardErrorPath</key>
    <string>{LOG_DIR}/auto-post-error.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>HOME</key>
        <string>{Path.home()}</string>
    </dict>

    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>"""


def _hours_for_interval(interval: int, start: int = 9, end: int = 21) -> list[int]:
    """按间隔小时数生成触发时间列表（本地时间）。"""
    return list(range(start, end + 1, interval))


def setup_cron(interval: int, start: int, end: int, uninstall: bool) -> None:
    """安装或卸载 launchd 定时任务。"""
    import shutil
    import subprocess
    import click

    if uninstall:
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
        PLIST_PATH.unlink(missing_ok=True)
        click.echo(f"✅ 已卸载 {PLIST_LABEL}")
        return

    v2g_bin = shutil.which("v2g")
    if not v2g_bin:
        raise click.ClickException("找不到 v2g 命令，请先 pip install -e .")

    project_dir = str(Path(__file__).parents[3])  # src/v2g/scout/ → repo root
    hours = _hours_for_interval(interval, start, end)
    plist_content = _build_plist(v2g_bin, project_dir, hours)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(plist_content, encoding="utf-8")

    # 如果已加载先卸载再重新加载
    subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
    result = subprocess.run(["launchctl", "load", str(PLIST_PATH)], capture_output=True, text=True)

    if result.returncode != 0:
        click.echo(f"⚠️ launchctl load 失败: {result.stderr}")
        return

    times_str = "、".join(f"{h}:00" for h in hours)
    click.echo(f"✅ 已安装定时任务 (每天 {times_str})")
    click.echo(f"   plist: {PLIST_PATH}")
    click.echo(f"   日志:  {LOG_DIR}/auto-post.log")
    click.echo(f"\n   查看日志: tail -f {LOG_DIR}/auto-post.log")
    click.echo(f"   手动触发: v2g scout auto-post --dry-run")
    click.echo(f"   卸载:     v2g scout cron-setup --uninstall")
