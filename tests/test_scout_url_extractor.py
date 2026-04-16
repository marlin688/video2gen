"""url_extractor 关键逻辑测试。"""

from datetime import date
from pathlib import Path

from v2g.scout.url_extractor import _tokenize, find_scout_scripts, match_urls_to_topic


def test_tokenize_mixed_zh_en_keeps_english_terms():
    tokens = _tokenize("Claude Code团队协作最佳实践")
    assert "claude" in tokens
    assert "code" in tokens


def test_match_urls_to_topic_returns_empty_when_no_keyword_match():
    all_urls = [
        {"url": "https://www.youtube.com/watch?v=abc", "title": "Video A", "source_type": "youtube"},
        {"url": "https://github.com/org/repo", "title": "Repo A", "source_type": "github"},
        {"url": "https://example.com/article", "title": "Article A", "source_type": "article"},
    ]
    topic = {"title": "完全不相关的话题", "angle_context": ""}
    matched = match_urls_to_topic(all_urls, topic, max_results=8)
    assert matched == []


def test_match_urls_to_topic_prefers_keyword_hits():
    all_urls = [
        {"url": "https://github.com/org/claude-code-helper", "title": "claude helper", "source_type": "github"},
        {"url": "https://example.com/other", "title": "other", "source_type": "article"},
    ]
    topic = {"title": "Claude Code", "angle_context": ""}
    matched = match_urls_to_topic(all_urls, topic, max_results=3)
    assert matched[0]["url"] == "https://github.com/org/claude-code-helper"
    assert matched[0]["match_score"] > 0


def test_find_scout_scripts_prefers_exact_topic_frontmatter(tmp_path: Path):
    scripts_dir = tmp_path / "scout" / "scripts"
    scripts_dir.mkdir(parents=True)
    today = date(2026, 4, 16)

    exact = scripts_dir / "2026-04-16-hook-吃瓜锐评-万物皆可-ai-盘点魔幻跨界与泡沫危机.md"
    exact.write_text(
        "---\n"
        "date: 2026-04-16\n"
        "type: hook\n"
        "topic: 吃瓜锐评：万物皆可 AI？盘点魔幻跨界与泡沫危机\n"
        "---\n",
        encoding="utf-8",
    )
    similar = scripts_dir / "2026-04-16-hook-吃瓜锐评-万物皆可-ai-另一条相似热点.md"
    similar.write_text(
        "---\n"
        "date: 2026-04-16\n"
        "type: hook\n"
        "topic: 吃瓜锐评：万物皆可 AI？另一条相似热点\n"
        "---\n",
        encoding="utf-8",
    )

    matched = find_scout_scripts(
        tmp_path,
        today,
        "吃瓜锐评：万物皆可 AI？盘点魔幻跨界与泡沫危机",
    )
    assert matched == [exact]
