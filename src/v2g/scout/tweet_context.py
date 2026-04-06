"""推文上下文生成：为 agent 生成可读的推文素材文件。"""

from pathlib import Path


def generate_tweet_context(
    tweets: list[dict],
    screenshot_map: dict[str, Path],
    output_path: Path,
) -> Path:
    """生成 tweet_context.md，供 agent 在脚本中引用推文截图。

    Args:
        tweets: 精选推文列表（含 author/text/likes/url 等）。
        screenshot_map: {tweet_url: png_path} 截图映射。
        output_path: 输出文件路径。

    Returns:
        写入的文件路径。
    """
    lines = [
        "# 可用推文截图素材",
        "",
        "以下推文已截图，可作为视频段落素材。",
        "",
        "## 使用方式",
        "",
        "有截图的推文：`component: \"image-overlay.default\"`，在 `image_content` 中指定截图路径。",
        "无截图的推文：`component: \"social-card.default\"`，在 `slide_content` 中填入推文数据。",
        "",
        "---",
        "",
    ]

    for i, t in enumerate(tweets, 1):
        author = t.get("author", "unknown")
        text = t.get("text", "")[:400]
        likes = t.get("likes", 0)
        retweets = t.get("retweets", 0)
        replies = t.get("replies", 0)
        score = t.get("total_score", 0)
        url = t.get("url", "")

        # 查找截图路径
        png_path = screenshot_map.get(url)
        if png_path:
            rel_path = f"images/{png_path.name}"
            screenshot_info = f"截图路径: `{rel_path}`"
        else:
            rel_path = None
            screenshot_info = "无截图（建议使用 social-card.default）"

        lines.append(f"### 推文 {i}: @{author}")
        lines.append(f"Score: {score:.2f} | ❤️ {likes} | 🔄 {retweets} | 💬 {replies}")
        lines.append(f"> {text}")
        lines.append(f"- {screenshot_info}")
        if url:
            lines.append(f"- 原文: {url}")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
