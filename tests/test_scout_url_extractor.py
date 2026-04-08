"""url_extractor 关键逻辑测试。"""

from v2g.scout.url_extractor import _tokenize, match_urls_to_topic


def test_tokenize_mixed_zh_en_keeps_english_terms():
    tokens = _tokenize("Claude Code团队协作最佳实践")
    assert "claude" in tokens
    assert "code" in tokens


def test_match_urls_to_topic_fallback_when_no_keyword_match():
    all_urls = [
        {"url": "https://www.youtube.com/watch?v=abc", "title": "Video A", "source_type": "youtube"},
        {"url": "https://github.com/org/repo", "title": "Repo A", "source_type": "github"},
        {"url": "https://example.com/article", "title": "Article A", "source_type": "article"},
    ]
    topic = {"title": "完全不相关的话题", "angle_context": ""}
    matched = match_urls_to_topic(all_urls, topic, max_results=8)
    assert len(matched) > 0
    assert all("url" in m for m in matched)


def test_match_urls_to_topic_prefers_keyword_hits():
    all_urls = [
        {"url": "https://github.com/org/claude-code-helper", "title": "claude helper", "source_type": "github"},
        {"url": "https://example.com/other", "title": "other", "source_type": "article"},
    ]
    topic = {"title": "Claude Code", "angle_context": ""}
    matched = match_urls_to_topic(all_urls, topic, max_results=3)
    assert matched[0]["url"] == "https://github.com/org/claude-code-helper"
    assert matched[0]["match_score"] > 0
