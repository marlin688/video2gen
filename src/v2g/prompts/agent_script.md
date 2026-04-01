你正在将已确认的视频大纲展开为完整的脚本。请严格按照大纲的结构和素材分配生成 script.json。

## 三类素材的具体要求

### 素材 A: PPT 图文
- 必须提供 `slide_content` 字段
- slide_content 的 bullet_points 必须用纯文本，禁止 emoji
- bullet_points 至少 3 条，追求信息密度
- 标题 4-12 字，有信息量（如"Plan Mode 三步操作"而非"Plan Mode"）
- **卡片内容和解说词必须互补**：解说词讲故事/感受/为什么，卡片放证据/数据/代码

**卡片 6 种视觉布局（前端自动检测 bullet_points 格式）：**

1. **代码布局** — bullet 中包含反引号 `` ` `` 或命令时触发终端风格
2. **数据指标布局** — bullet 含数字+单位（`60%`、`3.5x`）或箭头（`60% → 10%`）时触发大数字卡片
3. **步骤流程布局** — bullet 以"第X步"或序号开头时触发时间线
4. **对比布局** — chart_hint 含 "vs" 或 "对比" 时触发左右分栏
5. **网格布局** — 4+ 条 bullet 且每条含冒号分隔（`标签: 描述`）时触发 2x2 卡片
6. **标准布局** — 默认编号列表

一个脚本中应包含 2-3 种不同的卡片布局。

### 素材 B: 网页/操作演示（主力素材，占比最高）
- 必须提供 `recording_instruction` 字段
- **关键规则：尽可能在 instruction 中包含具体的 URL**，系统会自动打开网页截图生成素材
- URL 来源示例：
  - GitHub 仓库/文件页面（如 `https://github.com/anthropics/claude-code/blob/main/src/query.ts`）——**指定到具体文件路径**
  - npm/PyPI 包页面
  - 官方文档页面
  - **推特/X 帖子**（如 `https://x.com/user/status/123456`）——系统会自动截取推文卡片
- 如果素材文章中引用了某条推特/社交媒体帖子，**优先使用该推文 URL 作为 B 素材**，比放一张 slide 更有说服力
- 如果知识点涉及某个开源项目、工具、API，**必须**附上其官方页面 URL
- GitHub URL 要**尽可能精确到文件路径**（如 `blob/main/src/analytics/datadog.ts`），不要只放仓库首页
- 没有对应 URL 的终端/IDE 操作也可以，系统会用动画模拟
- 控制在 120 字以内（URL 不计入字数限制）

### 素材 C: 原始片段（仅当输入包含字幕时）
- 必须提供 `source_start` 和 `source_end`（秒数）
- 每段严格 ≤10 秒
- 时间戳必须基于提供的字幕时间线
- 分散引用，不要集中使用

## 写作规范

- `narration_zh` 是 TTS 朗读用的，必须**口语化**
- 禁止书面语（不要"首先"、"其次"、"综上所述"）
- 每段 narration_zh 控制在 40-100 字
- 段落之间必须有转场钩子
- 开头用反常识/场景代入/数据冲击
- 结尾用一句有态度的观点锤

## 输出格式

调用 `save_script` 工具，传入以下格式的 JSON 字符串：

{
  "title": "B站视频标题（15字以内）",
  "description": "B站视频简介（2-3句话）",
  "tags": ["标签1", "标签2", "标签3", "标签4", "标签5"],
  "source_channel": "素材来源",
  "total_duration_hint": 300,
  "segments": [
    {
      "id": 1,
      "type": "intro",
      "material": "A",
      "narration_zh": "解说词（40-100字，口语化）",
      "slide_content": {
        "title": "卡片标题（4-12字）",
        "bullet_points": ["要点1", "要点2", "要点3"],
        "chart_hint": "可选"
      },
      "notes": "段落意图"
    },
    {
      "id": 2,
      "type": "body",
      "material": "B",
      "narration_zh": "解说词...",
      "recording_instruction": "操作步骤说明（≤80字）",
      "notes": "段落意图"
    }
  ]
}

## 硬性约束

- segments 数量: 8-10 段（不要超过 10 段）
- 总字数: 500-800 字（3-4 分钟 TTS）
- 素材比例: 有字幕时 A ≤30% B ≥50% C ~20%；无字幕时 A ≤30% B ≥70%
- 避免连续两段使用相同素材类型（视觉节奏：A→B→B→A→B→B→A）
- B 类素材的 recording_instruction 中尽可能包含 URL
- bullet_points 禁止 emoji
- 不要编造素材中没有的事实，但可以加入你自己的分析判断
