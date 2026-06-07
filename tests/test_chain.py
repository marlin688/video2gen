from copy import deepcopy

from v2g.scout.chain import (
    REQUIRED_DISCLAIMER,
    _chain_blockers,
    _enforce_invariants,
    _validate_chain,
)


def _valid_chain_data():
    return {
        "topic": "AI 存储产业链",
        "short_tweet": "AI 这轮不是只看模型，资金正在沿基础设施往下挖。",
        "long_tweet": "AI 这轮不是只看模型，资金正在沿基础设施往下挖。\n\n" + REQUIRED_DISCLAIMER,
        "infographic": {
            "title": "AI 产业链轮动",
            "subtitle": "从模型到基础设施",
            "waves": [
                {
                    "label": "第一波: 基础模型",
                    "tickers": ["$MSFT", "$GOOG", "$META"],
                    "logic": "谁有模型谁先吃估值",
                },
                {
                    "label": "第二波: 算力芯片",
                    "tickers": ["$NVDA", "$AMD", "$AVGO"],
                    "logic": "推理越多算力越贵",
                },
                {
                    "label": "第三波: 存储服务器",
                    "tickers": ["$MU", "$STX", "$WDC"],
                    "logic": "数据吞吐成为瓶颈",
                },
                {
                    "label": "现在: 企业应用",
                    "tickers": ["$CRM", "$NOW", "$ADBE"],
                    "logic": "流程落地开始收钱",
                },
            ],
            "next_candidates": ["Agent Runtime", "推理成本优化", "AI 可观测性"],
            "bottom_line": "模型决定上限，系统决定落地。",
        },
        "comment_starter": "你觉得下一波轮到哪一层？",
        "disclaimer": REQUIRED_DISCLAIMER,
    }


def test_validate_chain_requires_three_to_five_tickers_per_wave():
    data = _valid_chain_data()
    data["infographic"]["waves"][0]["tickers"] = ["$MSFT", "$GOOG"]

    assert _validate_chain(data) is False


def test_chain_blockers_reject_duplicate_tickers_after_normalization():
    data = _valid_chain_data()
    data["infographic"]["waves"][1]["tickers"][0] = "$MSFT"
    fixed = _enforce_invariants(deepcopy(data), data["topic"])

    blockers = _chain_blockers(fixed)

    assert any("$MSFT" in blocker for blocker in blockers)


def test_chain_blockers_reject_unknown_ticker_review_marker():
    data = _valid_chain_data()
    data["infographic"]["waves"][0]["tickers"][0] = "$ZZZZ"
    fixed = _enforce_invariants(deepcopy(data), data["topic"])

    blockers = _chain_blockers(fixed)

    assert any("需要人工复核" in blocker for blocker in blockers)


def test_chain_blockers_reject_investment_advice_language():
    data = _valid_chain_data()
    data["long_tweet"] += "\n\n建议买入。"
    fixed = _enforce_invariants(deepcopy(data), data["topic"])

    blockers = _chain_blockers(fixed)

    assert any("投资建议" in blocker for blocker in blockers)
