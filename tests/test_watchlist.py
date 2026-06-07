import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import v2g.scout.watchlist as watchlist


def _valid_glass_candidate(**overrides):
    candidate = {
        "source_account": "@aleabitoreddit",
        "source_url": "https://x.com/aleabitoreddit/status/2063442668844167613",
        "source_type": "person",
        "raw_event": "Serenity 转发 TrendForce 关于 glass substrate 的时间线，提到 SKC Absolics、H2 2026、AMAT、AMD/AWS testing。",
        "one_line_summary": "玻璃基板开始进入 2026 下半年的量产窗口。",
        "why_now": "TrendForce 时间线把 SKC Absolics 的 H2 2026 放量、AMAT 设备和 AMD/AWS testing 放到同一条验证链上。",
        "industry_chain_mapping": "AI 封装链条从 CoWoS / HBM 继续前移到底层基板材料、设备工艺、客户验证和量产爬坡。",
        "related_tickers": {
            "direct": ["SKC", "AMAT"],
            "indirect": ["AMD", "AWS"],
            "sentiment": ["TSMC", "NVDA"],
        },
        "bottleneck_logic": "如果玻璃基板进入量产，瓶颈就不只是 GPU 设计，而是封装能力、基板良率、设备验证和 hyperscaler 客户导入。",
        "market_mispricing_angle": "市场容易把它当成玻璃基板概念，但真正的预期差在谁最早进入 AMD/AWS 验证链并把产能变成订单。",
        "what_to_verify": [
            "SKC Absolics H2 2026 是否按期量产",
            "AMD/AWS testing 是否进入正式客户验证",
            "AMAT 相关设备是否进入订单或产能扩张",
        ],
        "counter_argument": "玻璃基板良率、热膨胀匹配和客户验证周期可能拖慢量产，短期也可能只是实验室叙事。",
        "confidence": "medium",
        "recommended_action": "write",
        "tweet_hooks": [
            "技术切入：AI 封装瓶颈可能继续前移到玻璃基板。",
            "投资切入：这条线不只是 SKC，而是设备、封装和客户验证链。",
            "反直觉切入：GPU 出货不是唯一瓶颈，底层基板可能先卡住扩张。",
        ],
        "draft_short": (
            "很多人看 AI 基建还停留在 GPU 出货量。\n\n"
            "但 Serenity 这条真正值得看的信号是：glass substrate 开始进入 H2 2026 的量产窗口。\n\n"
            "如果 SKC Absolics 真能率先放量，AI 封装的讨论就不只是 CoWoS / HBM，而会继续前移到底层基板材料、AMAT 设备工艺、AMD/AWS 客户验证和量产爬坡。\n\n"
            "这条线的市场预期差不在“玻璃基板概念”，而在谁能把实验室叙事变成产能、订单和 hyperscaler 验证。反方也清楚：良率、热膨胀匹配和客户验证周期任何一个出问题，H2 2026 的窗口都可能后移。"
            "所以后面真正要跟的不是概念热度，而是 SKC 的产能爬坡、AMAT 设备导入、AMD/AWS testing 进展，以及这些节点能否反映到封装成本曲线。"
        ),
        "draft_thread": [
            "很多人看 AI 基建还停留在 GPU 出货量。但 Serenity 这条真正值得看的信号是：glass substrate 开始进入 H2 2026 的量产窗口。",
            "如果 SKC Absolics 真能率先放量，AI 封装的讨论就不只是 CoWoS / HBM，而会继续前移到底层基板材料、AMAT 设备工艺和客户验证。",
            "这条线的关键不是“玻璃基板概念”，而是谁最早量产、谁掌握关键设备和工艺、谁进入 AMD / AWS / hyperscaler 验证链条。",
            "反方风险也很清楚：良率、热膨胀匹配、客户验证周期都可能拖慢量产。后续要看 H2 2026 产能和 AMD/AWS testing 是否变成订单。",
        ],
    }
    candidate.update(overrides)
    return watchlist._normalize_candidate(candidate)


def _valid_grep_candidate(**overrides):
    candidate = {
        "source_account": "@karpathy",
        "source_url": "https://x.com/karpathy/status/agent-runtime",
        "source_type": "person",
        "raw_event": "某开源 AI 项目在 2026-06-07 修复 grep timeout，涉及 agent 工具调用、代码库搜索和运行时稳定性。",
        "one_line_summary": "grep timeout 暴露 agent runtime 从 demo 进入生产系统的问题。",
        "why_now": "本周修复进入主分支，说明 agent 开始频繁调用工具、读代码库、跑命令，运行时可靠性变成实际瓶颈。",
        "industry_chain_mapping": "映射到 AI agent runtime、代码搜索、工具调用、长任务控制、权限、上下文管理和可观测性层。",
        "related_tickers": {
            "direct": ["GitHub", "Cursor"],
            "indirect": ["MSFT", "OpenAI"],
            "sentiment": ["AI agent tooling"],
        },
        "bottleneck_logic": "模型会回答只是上限，grep timeout、重试、权限和失败恢复决定 agent 能不能完成真实代码任务。",
        "market_mispricing_angle": "市场容易追模型分数，但可能低估 runtime、工具编排和工程可靠性成为产品体验护城河。",
        "what_to_verify": [
            "grep timeout 修复是否减少长代码库任务失败率",
            "工具调用是否有超时、重试和状态恢复机制",
            "真实项目中的任务完成率是否提升",
        ],
        "counter_argument": "单个 timeout 修复可能只是普通 bug，不一定代表平台级护城河，需要看持续任务完成率和用户留存。",
        "confidence": "medium",
        "recommended_action": "write",
        "tweet_hooks": [
            "技术切入：grep timeout 比模型分数更能说明 agent runtime 问题。",
            "投资切入：AI 工具的护城河可能从模型切到 runtime 可靠性。",
            "反直觉切入：低级 bug 反而是 agent 进入生产的信号。",
        ],
        "draft_short": (
            "这周开源 AI 里，我觉得最值得看的不是某个模型又刷了多少分。\n\n"
            "而是一个很小的工程细节：grep timeout。\n\n"
            "一旦 agent 真正开始调用工具、读代码库、跑命令、改文件，模型能力只是一部分。真正决定体验的是超时、重试、权限、上下文管理和失败恢复。\n\n"
            "市场容易继续追模型分数，但产品层的预期差可能在 runtime：谁能把低级工程问题系统性解决，谁才更接近可每天使用的 AI coding agent。反方风险是这可能只是普通 bug，所以要继续看真实任务完成率、长代码库稳定性和用户留存。"
            "如果这些指标持续改善，agent tooling 的价值就不只是“接了一个更强模型”，而是把工程可靠性本身做成产品壁垒。"
        ),
        "draft_thread": [
            "这周开源 AI 里，我觉得最值得看的不是某个模型又刷了多少分，而是一个很小的工程细节：grep timeout。",
            "这类问题看起来很低级，但它说明 AI agent 正在从 demo 走向生产系统。只要开始读代码库、跑命令、改文件，工具调用稳定性就会变成真实瓶颈。",
            "模型能力只是一部分。真正决定体验的是：长任务是否可控，超时和重试是否可靠，权限和上下文管理是否清楚，失败后能不能恢复现场。",
            "模型负责聪明，runtime 负责靠谱。而生产环境里，靠谱往往比聪明更稀缺。",
        ],
    }
    candidate.update(overrides)
    return watchlist._normalize_candidate(candidate)


def test_load_watchlist_config_and_normalize_author_groups(tmp_path: Path):
    cfg_path = tmp_path / "watchlist.toml"
    cfg_path.write_text(
        """
since_hours = 2
min_likes = 5
max_tweets = 50
drafts_per_run = 2
publish_count = 1
keywords = ["agent", "inference"]
editorial_principle = "选题 + 催化剂 + 验证"

[[few_shots]]
name = "agent-runtime"
signal = "Karpathy 讨论 Agent runtime"
bad = "Agent runtime 很重要。"
good = "模型决定上限，runtime 决定它能不能从 demo 变成每天跑的系统。"

[groups]
daily = ["@karpathy", "https://x.com/SemiAnalysis_", "karpathy"]
trigger = ["x.com/sama/status/123", "elonmusk"]
""",
        encoding="utf-8",
    )
    cfg = SimpleNamespace(watchlist_config_path=cfg_path)

    loaded = watchlist.load_watchlist_config(cfg_path)
    groups = watchlist.build_author_groups(cfg, watchlist_config=loaded)

    assert loaded["since_hours"] == 2
    assert loaded["keywords"] == ["agent", "inference"]
    assert loaded["few_shots"][0]["name"] == "agent-runtime"
    assert groups["daily"] == ["karpathy", "SemiAnalysis_"]
    assert groups["trigger"] == ["sama", "elonmusk"]


def test_build_user_message_includes_few_shot_examples():
    message = watchlist._build_user_message(
        tweets=[
            {
                "tweet_id": "t1",
                "watch_group": "daily",
                "author": "karpathy",
                "created_at": "2026-06-07T08:00:00Z",
                "likes": 10,
                "retweets": 1,
                "replies": 1,
                "url": "https://x.com/karpathy/status/t1",
                "text": "Agent runtime is the next bottleneck.",
            }
        ],
        max_drafts=2,
        principle="选题 + 催化剂 + 验证",
        keywords=["agent"],
        few_shots=[
            {
                "name": "agent-runtime",
                "signal": "Karpathy 讨论 Agent runtime",
                "bad": "Agent runtime 很重要。",
                "good": "模型决定上限，runtime 决定它能不能从 demo 变成每天跑的系统。",
            }
        ],
    )

    assert "## Few-shot 风格样例" in message
    assert "不要这样: Agent runtime 很重要。" in message
    assert "模型决定上限" in message
    assert "## Watchlist 推文" in message


def test_glass_substrate_generic_draft_fails_quality_gate():
    generic = _valid_glass_candidate(
        draft_short=(
            "很多人看 AI 基建只盯着 GPU 出货，但真正决定下一轮扩张速度的瓶颈可能已经前移到封装、玻璃基板和材料体系。"
            "AI 基建是一张供应链网络。"
        )
    )

    issues = watchlist.quality_check_candidate(generic)

    assert "generic_or_banned_draft_expression" in issues


def test_glass_substrate_specific_candidate_passes_quality_gate():
    candidate = _valid_glass_candidate()

    assert watchlist._validate_plan({"candidates": [candidate]})
    assert watchlist.quality_check_candidate(candidate) == []
    assert "SKC Absolics" in candidate["raw_event"]
    assert "H2 2026" in candidate["why_now"]
    assert "AMD" in candidate["related_tickers"]["indirect"]


def test_grep_timeout_candidate_maps_to_agent_runtime_not_generic_open_source_ai():
    candidate = _valid_grep_candidate()

    assert watchlist.quality_check_candidate(candidate) == []
    assert "grep timeout" in candidate["raw_event"]
    assert "runtime" in candidate["industry_chain_mapping"].lower()
    assert "模型竞争转向工程化" not in candidate["draft_short"]


def test_insufficient_signal_candidate_is_skip_and_not_publishable():
    candidate = watchlist._normalize_candidate({
        "source_account": "@someone",
        "source_url": "https://x.com/someone/status/1",
        "source_type": "person",
        "raw_event": "某账号说 AI 基建未来很重要，没有公司、时间线、数据、订单、客户验证或产业链细节。",
        "one_line_summary": "信息过于泛化，不适合生成推文。",
        "why_now": "",
        "industry_chain_mapping": "",
        "related_tickers": {"direct": [], "indirect": [], "sentiment": []},
        "bottleneck_logic": "",
        "market_mispricing_angle": "",
        "what_to_verify": ["等待具体公司、订单、产能、客户验证或时间线"],
        "counter_argument": "没有可验证细节，容易变成空泛行业评论。",
        "confidence": "low",
        "recommended_action": "skip",
        "tweet_hooks": [],
        "draft_short": "",
        "draft_thread": [],
    })

    assert watchlist._validate_plan({"candidates": [candidate]})
    assert watchlist.quality_check_candidate(candidate) == []
    assert watchlist.build_watchlist_drafts([candidate], "watchlist.json", max_drafts=1) == []


def test_watchlist_candidate_schema_fields_are_complete_after_normalization():
    candidate = watchlist._normalize_candidate({"raw_event": "only raw event"})

    assert set(watchlist.WATCHLIST_CANDIDATE_FIELDS).issubset(candidate.keys())
    assert set(candidate["related_tickers"].keys()) == {"direct", "indirect", "sentiment"}
    assert isinstance(candidate["what_to_verify"], list)
    assert isinstance(candidate["tweet_hooks"], list)
    assert isinstance(candidate["draft_thread"], list)


def test_filter_since_keeps_recent_and_unknown_times():
    tweets = [
        {"tweet_id": "recent", "created_at": "2026-06-07T08:30:00Z"},
        {"tweet_id": "old", "created_at": "2026-06-07T06:00:00Z"},
        {"tweet_id": "unknown", "created_at": ""},
    ]
    now = datetime(2026, 6, 7, 9, 0, tzinfo=timezone.utc)

    kept = watchlist.filter_since(tweets, since_hours=1, now=now)

    assert [t["tweet_id"] for t in kept] == ["recent", "unknown"]


def test_run_watchlist_dry_run_writes_report_and_marks_seen(monkeypatch, tmp_path: Path):
    cfg_path = tmp_path / "watchlist.toml"
    cfg_path.write_text(
        """
since_hours = 24
min_likes = 0
max_tweets = 10
drafts_per_run = 1
publish_count = 1
keywords = ["agent"]
editorial_principle = "选题 + 催化剂 + 验证"

[groups]
daily = ["karpathy"]
""",
        encoding="utf-8",
    )
    cfg = SimpleNamespace(
        obsidian_vault_path=tmp_path,
        scout_db_path=tmp_path / "scout.db",
        scout_model="fake-model",
        watchlist_config_path=cfg_path,
    )

    tweet = {
        "tweet_id": "t1",
        "author": "karpathy",
        "watch_author": "karpathy",
        "watch_group": "daily",
        "text": "Agent 的问题不只是模型能力，而是运行时、工具、状态管理和可观测性一起决定上限。",
        "created_at": "2026-06-07T08:00:00Z",
        "likes": 10,
        "retweets": 2,
        "replies": 1,
        "url": "https://x.com/karpathy/status/t1",
    }
    calls = {"publish": 0, "generate": 0}

    monkeypatch.setattr(watchlist, "fetch_watchlist_tweets", lambda *args, **kwargs: [tweet])

    def fake_generate(cfg, tweets, max_drafts, principle, keywords, few_shots):
        calls["generate"] += 1
        assert few_shots == []
        return {
            "candidates": [_valid_grep_candidate(
                source_url="https://x.com/karpathy/status/t1",
                source_account="@karpathy",
            )]
        }

    def fake_publish(cfg, draft, dry_run, force, yes=False):
        calls["publish"] += 1
        assert dry_run is True
        assert draft.source_type == "watchlist"
        assert draft.version == "thread"
        assert "grep timeout" in draft.metadata["candidate"]["raw_event"]
        return True

    monkeypatch.setattr(watchlist, "generate_watchlist_plan", fake_generate)
    monkeypatch.setattr(watchlist, "run_draft_publish", fake_publish)

    path = watchlist.run_watchlist(cfg, dry_run=True)

    assert path is not None
    assert path.exists()
    data = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    assert data["candidates"][0]["recommended_action"] == "write"
    assert data["candidates"][0]["quality_passed"] is True
    assert data["drafts"][0]["publishable"] is True
    assert data["source_tweets"][0]["tweet_id"] == "t1"
    assert calls == {"publish": 1, "generate": 1}

    second = watchlist.run_watchlist(cfg, dry_run=True)

    assert second is None
    assert calls == {"publish": 1, "generate": 1}


def test_build_watchlist_plist_includes_env_config_and_publish_args(tmp_path: Path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".env").write_text("TWITTER_API_IO_KEY=x\n", encoding="utf-8")
    config_path = project_dir / "config" / "watchlist.toml"

    plist = watchlist._build_watchlist_plist(
        "/usr/local/bin/v2g",
        str(project_dir),
        [0, 1],
        config_path=str(config_path),
        publish=True,
        publish_count=2,
    )

    assert "<string>--env</string>" in plist
    assert f"<string>{project_dir / '.env'}</string>" in plist
    assert "<string>watchlist</string>" in plist
    assert "<string>--config</string>" in plist
    assert f"<string>{config_path}</string>" in plist
    assert "<string>--publish</string>" in plist
    assert "<string>--yes</string>" in plist
    assert "<string>--publish-count</string>" in plist
    assert "<string>2</string>" in plist
