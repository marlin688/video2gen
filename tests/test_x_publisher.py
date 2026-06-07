import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import click
import pytest

import v2g.scout.x_publisher as xp
from v2g.scout.x_publisher import (
    CHAIN_DISCLAIMER,
    TweetDraft,
    build_chain_draft,
    build_waterfall_draft,
    run_draft_publish,
    validate_draft,
)


def test_build_waterfall_draft_extracts_short_tweets_and_topic(tmp_path: Path):
    path = tmp_path / "2026-06-07-waterfall-demo.md"
    path.write_text(
        "---\n"
        "date: 2026-06-07\n"
        "type: waterfall\n"
        "topic: AI Agent Runtime\n"
        "---\n\n"
        "## 二、Twitter 内容\n\n"
        "### 短版（3 条，日常发帖用）\n\n"
        "**推文 1**：\n"
        "> 第一条观点\n\n"
        "**推文 2**：\n"
        "> 第二条事实\n\n"
        "### 长版（7 条，发视频时配套用）\n\n"
        "**推文 1**：\n"
        "> 长版第一条\n",
        encoding="utf-8",
    )

    draft = build_waterfall_draft(path, "short")

    assert draft.source_type == "waterfall"
    assert draft.topic == "AI Agent Runtime"
    assert draft.tweets == ["第一条观点", "第二条事实"]


def test_validate_draft_blocks_publish_risks():
    draft = TweetDraft(
        source_type="waterfall",
        tweets=[
            "这条里面还有 [link] 占位",
            "建议买入 $NVDA，目标价 999。",
            "重复内容",
            "重复内容",
            "x" * 281,
        ],
    )

    codes = {issue.code for issue in validate_draft(draft)}

    assert "placeholder" in codes
    assert "investment_advice" in codes
    assert "duplicate_tweet" in codes
    assert "tweet_too_long" in codes


def test_build_chain_draft_short_appends_disclaimer_and_passes_policy(tmp_path: Path):
    path = tmp_path / "2026-06-07-ai-chain.json"
    path.write_text(
        json.dumps(
            {
                "topic": "AI 存储产业链",
                "short_tweet": "AI 这轮不是只看模型，资金在沿基础设施往下挖。",
                "long_tweet": "AI 这轮不是只看模型。\n\n" + CHAIN_DISCLAIMER,
                "disclaimer": CHAIN_DISCLAIMER,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    draft = build_chain_draft(path, "short")

    assert draft.source_type == "chain"
    assert draft.topic == "AI 存储产业链"
    assert CHAIN_DISCLAIMER in draft.tweets[0]
    assert validate_draft(draft) == []


def test_chain_policy_blocks_review_marker():
    draft = TweetDraft(
        source_type="chain",
        tweets=[f"AI 产业链开始扩散，$NVDA $AMD $XYZ ⚠️\n\n{CHAIN_DISCLAIMER}"],
    )

    codes = {issue.code for issue in validate_draft(draft)}

    assert "unverified_ticker" in codes


def test_build_chain_draft_long_splits_to_api_sized_tweets(tmp_path: Path):
    path = tmp_path / "2026-06-07-ai-chain.json"
    long_text = (
        "第一段：" + "工程落地需要基础设施。" * 20 + "\n\n"
        "第二段：" + "模型决定上限，系统决定落地。" * 18 + "\n\n"
        + CHAIN_DISCLAIMER
    )
    path.write_text(
        json.dumps(
            {
                "topic": "AI Agent",
                "short_tweet": "短推。",
                "long_tweet": long_text,
                "disclaimer": CHAIN_DISCLAIMER,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    draft = build_chain_draft(path, "long")

    assert len(draft.tweets) > 1
    assert all(len(tweet) <= 280 for tweet in draft.tweets)
    assert validate_draft(draft) == []


def test_run_draft_publish_records_partial_failure(monkeypatch, tmp_path: Path):
    cfg = SimpleNamespace(scout_db_path=tmp_path / "scout.db")
    draft = TweetDraft(source_type="waterfall", tweets=["第一条", "第二条"])

    def fake_post_thread(tweets, dry_run=False, after_post=None):
        assert dry_run is False
        assert after_post is not None
        after_post(1, "111", ["111"])
        raise RuntimeError("api down")

    monkeypatch.setattr(xp, "post_thread", fake_post_thread)

    with pytest.raises(click.ClickException):
        run_draft_publish(cfg, draft, dry_run=False, force=False, yes=True)

    conn = sqlite3.connect(str(cfg.scout_db_path))
    row = conn.execute(
        "SELECT data FROM seen_items WHERE source=? AND item_id=?",
        ("x_publish_attempt", draft.content_hash),
    ).fetchone()
    conn.close()

    assert row is not None
    data = json.loads(row[0])
    assert data["status"] == "failed"
    assert data["tweet_ids"] == ["111"]
