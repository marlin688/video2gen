from v2g.page_quality import assess_page_snapshot, is_auth_risk_host


def test_assess_page_snapshot_rejects_auth_wall():
    ok, reason = assess_page_snapshot(
        {
            "url": "https://x.com/AnthropicAI",
            "title": "登录 X / X",
            "text": "正在发生 现在就加入 发现更多 已有账号？登录 Continue with Google Grok",
            "text_length": 48,
            "heading_count": 1,
            "paragraph_count": 1,
            "link_count": 3,
            "button_count": 2,
            "input_count": 1,
            "code_count": 0,
            "image_count": 0,
            "article_count": 0,
        },
        url="https://x.com/AnthropicAI",
    )
    assert ok is False
    assert reason == "auth_wall"


def test_assess_page_snapshot_rejects_low_density():
    ok, reason = assess_page_snapshot(
        {
            "url": "https://example.com",
            "title": "Brand Hero",
            "text": "Build with AI today.",
            "text_length": 20,
            "heading_count": 1,
            "paragraph_count": 1,
            "link_count": 3,
            "button_count": 1,
            "input_count": 0,
            "code_count": 0,
            "image_count": 1,
            "article_count": 0,
        }
    )
    assert ok is False
    assert reason == "low_density"


def test_assess_page_snapshot_accepts_dense_doc_page():
    ok, reason = assess_page_snapshot(
        {
            "url": "https://docs.example.com/guide",
            "title": "Guardrails Best Practices",
            "text": (
                "Guardrails best practices Data classification Human review Rollback path "
                "Checklist Example policy Allowed public docs Blocked secrets Review required strategy docs"
            ),
            "text_length": 168,
            "heading_count": 3,
            "paragraph_count": 6,
            "link_count": 12,
            "button_count": 0,
            "input_count": 0,
            "code_count": 1,
            "image_count": 0,
            "article_count": 1,
        }
    )
    assert ok is True
    assert reason == "ok"


def test_is_auth_risk_host():
    assert is_auth_risk_host("https://x.com/openai") is True
    assert is_auth_risk_host("https://docs.anthropic.com/en/docs/test-and-evaluate") is False
