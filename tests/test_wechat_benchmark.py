from pathlib import Path

from v2g.wechat_benchmark import (
    BenchmarkArticle,
    html_to_markdownish,
    render_benchmark_markdown,
    score_benchmark_article,
    wordpress_items_to_articles,
)


def test_wordpress_items_to_articles_extracts_content():
    items = [
        {
            "date": "2026-04-20T10:00:00",
            "link": "https://example.com/a",
            "title": {"rendered": "测试标题"},
            "content": {"rendered": "<h2>小标题</h2><p>正文</p><img src=\"https://img/a.png\" />"},
        }
    ]

    articles = wordpress_items_to_articles("qbitai", "量子位", items, per_source=2)

    assert len(articles) == 1
    assert articles[0].title == "测试标题"
    assert "![图](https://img/a.png)" in articles[0].markdown


def test_score_benchmark_article_rewards_media_signals():
    html = """
    <h2>事件</h2><p>2026年4月20日，公司宣布新模型，参数达到14B。</p>
    <figure><img src="https://img/a.png"><figcaption>图：产品截图</figcaption></figure>
    <figure><img src="https://img/b.png"><figcaption>图：架构图</figcaption></figure>
    <figure><img src="https://img/c.png"><figcaption>图：对比图</figcaption></figure>
    <p>CEO表示，团队已经在5个基准测试拿到第一。</p>
    <p>更多见 <a href="https://source.example/a">来源</a> 和 <a href="https://other.example/b">资料</a>。</p>
    <h2>影响</h2><p>这意味着行业进入新阶段。</p>
    """
    article = BenchmarkArticle(
        source_key="demo",
        source_name="样本",
        title="新模型首次发布！14B参数刷新5项纪录",
        url="https://example.com/a",
        published_at="2026-04-20T10:00:00",
        markdown=html_to_markdownish(html) + "\n" + ("公司、团队、用户、案例、未来。 " * 120),
        html=html,
    )

    report = score_benchmark_article(article)

    assert report["score_pct"] >= 70
    assert report["metrics"]["images"] == 3
    assert report["metrics"]["unique_source_domains"] == 2


def test_render_benchmark_markdown_contains_delta(tmp_path: Path):
    report = {
        "target_date": "2026-04-20",
        "media_average": 82.5,
        "media_average_all": 80.0,
        "media_effective_sample_count": 2,
        "media_total_sample_count": 3,
        "missing_effective_sources": [],
        "missing_sample_sources": [],
        "media_top_score": 86.0,
        "media_top_title": "媒体样本",
        "media_top_source": "量子位",
        "own_score": 88.0,
        "own_delta_vs_media_avg": 5.5,
        "own_delta_vs_media_top": 2.0,
        "own_beats_media_top": True,
        "notes": [],
        "articles": [
            {
                "source": "AGI通识",
                "title": "测试",
                "url": str(tmp_path / "article.md"),
                "score_pct": 88.0,
                "eligible_for_average": True,
                "checks": [],
                "metrics": {"chars": 3000, "images": 5, "number_facts": 8},
            }
        ],
    }

    markdown = render_benchmark_markdown(report)

    assert "相对媒体均值：+5.5" in markdown
    assert "相对媒体最高分：+2.0" in markdown
    assert "是否高于媒体最高分：是" in markdown
    assert "| 1 | AGI通识 | 88.0 | 是 |" in markdown
