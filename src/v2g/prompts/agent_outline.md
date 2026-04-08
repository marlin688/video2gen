你已经阅读了所有素材。现在请生成视频大纲。

## 大纲要求

### 结构
- **开头 (intro)**: 1-2 段，Hook 抓住观众
- **主体 (body)**: 3-5 个核心知识点（不是素材的逐条复述，而是跨素材提炼）
- **结尾 (outro)**: 1 段，观点锤总结

### 每个段落需标注
- **section**: intro / body / outro
- **theme**: 这一段讲什么（一句话概括）
- **key_points**: 要覆盖的关键点
- **source_refs**: 引用了哪些素材（编号列表）
- **suggested_materials**: 建议的素材类型 (A=图文卡片, B=操作演示, C=原始片段)
- **est_duration**: 预估时长（秒）

### 素材类型分配原则
- **A (PPT 图文, ≤30%)**: **仅用于**数据密集型内容（多组数据对比、架构总览、总结清单）。如果一个知识点可以通过展示网页/代码仓库/文档来呈现，优先用 B 而不是 A。
- **B (网页/操作演示, ≥50%)**: 展示真实的网页、代码仓库、文档页面、工具界面。**关键：recording_instruction 中必须尽可能包含具体 URL**（GitHub 仓库、npm 包页面、官方文档、在线工具等），便于自动截图生成素材。没有 URL 的纯终端操作也可以，但优先考虑有 URL 的场景。
- **C (原始片段, ~20%)**: 引用原文/原视频的精华（仅当输入包含字幕时）

注意：如果输入素材中没有视频字幕（即全部是文章/笔记），则不需要分配素材 C，将比例调整为 A ≤30%, B ≥70%。

**视觉多样性原则**: 避免连续出现两个相同类型的段落。理想节奏是 A→B→B→A→B→B→A 这样交替，让观众不会产生"又是 PPT"的疲劳感。

### 时长控制
- 总时长应接近目标时长
- 每段 15-90 秒，复杂知识点的讲解段可以更长，开头和结尾可以短一些

## 输出格式

调用 `save_outline` 工具，传入以下 JSON 字符串：

{
  "title": "视频标题（15字以内，有冲击力）",
  "theme": "一句话概括视频主线",
  "target_duration": <目标时长秒数>,
  "source_summary": [
    {
      "id": 0,
      "type": "article|srt|markdown",
      "title": "素材标题",
      "key_points": ["核心观点1", "核心观点2"]
    }
  ],
  "outline": [
    {
      "section": "intro",
      "theme": "Hook: ...",
      "key_points": ["..."],
      "source_refs": [0, 1],
      "suggested_materials": ["C"],
      "est_duration": 20
    },
    {
      "section": "body",
      "theme": "...",
      "key_points": ["...", "..."],
      "source_refs": [0],
      "suggested_materials": ["A", "B"],
      "est_duration": 50
    }
  ]
}
