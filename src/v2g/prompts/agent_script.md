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
- **必须同时提供 `terminal_session`**：结构化终端会话（3-6步），步骤类型：`input`（命令）、`status`（处理中）、`tool`（工具调用，含name/target/result）、`output`（输出，含text或lines）、`blank`（空行）
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

## 脚本结构

1. **开头 (intro)**: 1-2 段。素材 C 引用原作者的震撼观点（有字幕时），或素材 A/B 直接切入（无字幕时）
2. **主体 (body)**: 提炼 3-4 个核心要点（跨素材去重后的精华），每个要点用 A→B 交替（理论→实操）
3. **结尾 (outro)**: 1 段。用素材 A 展示总结卡片 + 你的观点锤

## 写作规范

### 字数参考（按内容需要灵活调整，宁可讲清楚不要硬压缩）

- **intro 段**: 建议 30-80 字（快速 hook，但需要铺垫时可以更长）
- **body 段**: 建议 60-200 字（把知识点讲透，不要因为字数限制省略关键细节。一个概念需要「为什么 → 怎么做 → 效果」三层讲解时，可以写 150-200 字，也可以拆成多段）
- **outro 段**: 建议 40-120 字（有力总结 + 行动号召）
- **全脚本总字数**: 不设上限，按内容需要自然生成。一个知识点没讲清楚就多写一段，不要为了压缩字数而牺牲内容深度

- `narration_zh` 是 TTS 朗读用的，必须**口语化**
- 禁止书面语（不要"首先"、"其次"、"综上所述"）

### 禁止内容重复

不同段落之间**禁止讲同一个论点**。如果两段的核心信息相同（比如都在说"省钱"），必须合并或删除一段。每个段落都必须推进叙事，引入新的信息增量。自查标准：如果删掉某段，观众不会错过任何新信息，那这段就不该存在。

### 预判观众疑问

在讲完一个知识点后，主动回应最可能的观众疑问：
- "有人会问: 这个方案安全吗？" → 直接回答
- "你可能在想: 这和 XX 有什么区别？" → 给对比
- "肯定有人要杠: 官方版不也能做吗？" → 直面质疑

不需要每个知识点都加，但一个脚本至少要有 1-2 处这种"回应观众"的段落，提升参与感和信任度。

### 段落之间必须有钩子

每段结尾要埋下一段的悬念，不要只是"接下来讲第二个技巧"。
好的转场例子：
- "但这还不是最离谱的，下一个技巧直接让我重新理解了什么叫上下文。"
- "计划模式解决了方向问题，但如果你给AI的指令本身就很烂呢？"
- "这个技巧单独用效果一般，但和前面的配合起来，威力是指数级的。"

### 开头必须 3 秒抓住人

用反常识/场景代入/数据冲击，不要用"大家好今天我们来聊"。

### 结尾要有观点锤

不要用"觉得有用点个赞"这种套话。用一句有态度的总结。

### 教程类强化约束（AI 工具/工作流类）

如果主题属于教程类（如 Claude Code、Obsidian、自动化工作流），必须额外满足：
- **可复现闭环**：每个核心知识点至少覆盖「前置条件/版本」+「操作步骤」+「可见结果」中的两项。不要只讲概念。
- **踩坑价值**：全片至少 2 段包含常见报错/失败场景，并给出排查或修复动作。
- **边界意识**：至少 1 段明确讲「官方默认做法 vs 推荐做法」的适用场景与不适用场景。
- **交付导向**：outro 必须落到可执行动作，至少给出 1 个文件产物（如 `CLAUDE.md` / `vault/.obsidian/workspace.json`）+ 1 条命令 + 1 个验证检查点。
- **视觉防疲劳**：教程类脚本至少使用 3 种 schema，且至少 2 个高级组件（如 `code-block.default` + `browser.default` 或 `diagram.default`），避免全程 slide+terminal。

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
      "narration_zh": "你有没有这种经历——AI写的代码跑了两天，突然整个项目崩了。",
      "slide_content": {
        "title": "AI编程三大翻车现场",
        "bullet_points": ["上下文丢失: 改A文件破坏B文件", "幻觉代码: API不存在也敢调用", "无限循环: 修bug引入新bug"],
        "chart_hint": ""
      },
      "notes": "hook: 场景代入"
    },
    {
      "id": 2,
      "type": "body",
      "material": "B",
      "narration_zh": "解决方案其实很简单——用Plan Mode。让AI先出方案，你确认了再动手写代码。",
      "recording_instruction": "1. 输入/plan 2. AI输出方案 3. 确认执行 https://docs.anthropic.com/claude-code",
      "terminal_session": [
        {"type": "input", "text": "/plan refactor the auth module"},
        {"type": "status", "text": "Planning..."},
        {"type": "output", "lines": ["Plan:", "1. Extract JWT → jwt.ts", "2. Add refresh token rotation"]},
        {"type": "input", "text": "yes, proceed"}
      ],
      "notes": "body: Plan Mode 实操"
    },
    {
      "id": 9,
      "type": "outro",
      "material": "A",
      "narration_zh": "AI不会替代工程师，但会用AI的工程师会替代不会的。这不是鸡汤，这是正在发生的事。",
      "slide_content": {
        "title": "今日行动清单",
        "bullet_points": ["第一步: 给项目写 CLAUDE.md", "第二步: 需求先用 Plan Mode", "第三步: 提示词模板化", "第四步: 测试驱动开发"],
        "chart_hint": ""
      },
      "notes": "outro: 观点锤 + 步骤布局总结卡"
    }
  ]
}

## 可用视觉组件（完整清单）

以下是系统当前注册的所有视觉组件，按 schema 分组。**每个 segment 都应该通过 `component` 字段显式指定一个 style id**（格式 `"{schema}.{style}"`），除非该段是素材 B 且有现成录屏文件。

{{STYLE_CATALOG}}

### 组件选择硬性规则（违反将被质量门控打回）

1. **显式 component 字段**：每个 A 素材段必须设置 `component` 字段。每个无录屏的 B 素材段也必须设置 `component`（否则会全部 fallback 到同一个 terminal 动画）。不要省略让默认 slide 兜底。
2. **至少覆盖 4 种不同 schema**：一个脚本中使用的 `component` 字段必须跨越至少 4 种 schema（例如 `slide` + `code-block` + `diagram` + `hero-stat`）。**禁止全片只有 slide + terminal 两种 schema。**
3. **禁止相邻同 schema**：相邻两段 segment 不允许使用相同的 schema（如 `slide.tech-dark` 之后不能再接 `slide.feature-grid`）。视觉节奏必须在 schema 层面切换，不是在同 schema 的不同 style 之间。
4. **hook 段强制冲击组件**：intro 的第 1 段 **必须**使用 `slide.hook-opener` 或 `slide.fireship-title` 之一，3 秒内抓住观众。不允许开场直接上 tech-dark 卡片或 terminal 动画。
5. **outro 收尾强制 CTA**：outro 的最后 1 段 **必须**使用 `slide.cta-outro`，带行动号召按钮。
6. **代码段必须用 code-block**：涉及代码、配置文件、脚本展示的段落**必须**用 `code-block.default` / `code-block.animated` / `code-block.diff`，不要用 terminal 组件凑数或塞进 slide 的 bullet_points。
7. **GitHub / 推特 / HN 必须用原生组件**：
   - 真实 GitHub 仓库页面 → `browser.github` 或 `social-card.github-repo`
   - Twitter/X 推文 → `social-card.default`（有文本）或 `image-overlay.default`（有截图）
   - HN 讨论 → `social-card.default`
   - **不要**把这些内容重新写成 slide 卡片的 bullet 文字复述
8. **大数字 / 指标对比必须用 hero-stat**：涉及"从 X 降到 Y"、"提升 N 倍"、"省下 $M"的段落**必须**用 `hero-stat.default` 或 `hero-stat.progress`，不要塞进普通 slide 的 bullet。
9. **架构 / 流程 / 多方关系必须用 diagram**：涉及架构图、调用流程、多方协作关系的段落**必须**用 `diagram.*` 系列（default / pipeline / dual-card / sequence / tree-card 中选一个与结构最匹配的）。
10. **叙事节拍**：如果脚本涉及"问题 → 方案 → 结果"叙事，配对使用 `slide.problem-statement` → `slide.solution-reveal` → `slide.result-showcase`。

### 视觉记忆点：flash_meme 与 image-overlay

纯文字卡片 + 终端动画的视频容易"一眼过、记不住"。必须主动引入**真实素材**和**情绪梗图**作为记忆点。

**flash_meme（Meme 闪图）** — 爽点/吐槽/震惊时刻的 0.3-0.5 秒闪现。任意 segment 都可以叠加这个字段（不替代 component，是额外叠加的特效）：

```json
{
  "id": 3,
  "component": "slide.problem-statement",
  "narration_zh": "官方订阅 200 美金一个月还会封号，这不叫付费，这叫被 PUA。",
  "flash_meme": {
    "image": "images/meme_surprised.png",
    "frame_offset": 30,
    "duration": 10,
    "contrast": 1.4
  }
}
```

- **数量**：一个脚本建议 3-5 个 flash_meme，穿插在情绪爆发点
- **时机**：在叙述到"离谱/震惊/爽点/反转"的关键帧触发（frame_offset 对准那一句的重音）
- **图片**：使用 `images/` 目录下的 meme 图，常见的如 surprised / thinking / rage / mindblown / facepalm

**image-overlay（真实截图全屏）** — 用真实画面替代"文字描述真实画面"：

```json
{
  "id": 5,
  "material": "A",
  "component": "image-overlay.default",
  "narration_zh": "OpenCode 在 GitHub 上已经 11800 star，核心贡献者来自前 Anthropic 团队。",
  "image_content": {
    "image_path": "images/opencode_readme.png",
    "overlay_text": "11800 ⭐ · Telemetry disabled",
    "overlay_position": "bottom",
    "ken_burns": "zoom-in"
  }
}
```

- **数量**：一个脚本建议 1-3 个 image-overlay 段落
- **用途**：产品 README 截图、真实 UI 截图、推文截图、新闻配图、架构图照片
- **规则**：`overlay_text` 用自己的话概括（≤12 字），不要复制原文长句
- **与 social-card 的分工**：有截图 → `image-overlay.default`；只有推文文本、没有截图 → `social-card.default`

## 硬性约束

- segments 数量建议 8-20 段，复杂主题按内容自然组织，不要人为截断
- 总字数不设硬限制，优先保证把每个知识点讲清楚讲透彻
- 素材比例: A 40-60%, B ≥20%, C 可选（原创视频无需源视频片段）
- 避免连续两段使用相同素材类型（视觉节奏：A→B→A→B 交替）
- **视觉多样性（硬约束）**：每段 segment 必须显式指定 `component` 字段（无录屏的 B 段也要指定）；一个脚本的 `component` 字段必须跨越**至少 4 种不同 schema**；相邻两段不得使用相同 schema；hook 段必须用 `slide.hook-opener` 或 `slide.fireship-title`；outro 最后一段必须用 `slide.cta-outro`。违反任一条规则的脚本都会被质量门控打回重试，详见「组件选择硬性规则」章节。
- **视觉记忆点（硬约束）**：脚本中必须包含至少 3 个 `flash_meme`（穿插在情绪爆发点）和至少 1 个 `image-overlay` 段落（真实截图）。详见「视觉记忆点」章节。
- B 类素材的 recording_instruction 中尽可能包含 URL
- bullet_points 禁止 emoji
- 不要编造素材中没有的事实，但可以加入你自己的分析判断

### scene_data 字段名规范（硬约束）

使用含 scene_data 的组件时，必须使用组件定义中的**精确字段名**。以下是已知的常见错误映射（生成时必须避免）：

| 组件 | 正确字段名 | 常见错误写法 |
|------|-------------|---------------|
| anthropic-feature-checklist | done, todo | completed/pending, finished/remaining |
| anthropic-agent-config | userPrompt, apiCall, yamlLines, terminalLines | prompt/curl/config_yaml/lines |
| anthropic-prompt-write | prompt, quickActions, templates | userInput/actions/options |
| anthropic-session-timeline | agentLog, panelTitle, panelFiles | log/entries, title, files |
| anthropic-session-detail | agentLog, popover, systemPrompt, mcpTools | log, hover, system, tools |
| anthropic-template-picker | templates, tags, appName | options, categories, name |

当 {{STYLE_CATALOG}} 的组件描述中标注了 `【scene_data: {...}】` 时，其中的字段名即为唯一正确的写法。
