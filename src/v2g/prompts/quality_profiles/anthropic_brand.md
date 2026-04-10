# Anthropic 品牌片档位 (anthropic_brand)

你当前在生成一条 **Anthropic 官方品牌风格** 的中文技术短片。

**这不是一条"讲知识"的教程片**，而是一条"展示产品 + 传达情绪"的**品牌短片**。
节奏更快、画面更贵，通过**视觉**而非长语句传递信息。
参考原型：Anthropic 官方发布的 "Introducing Claude Managed Agents" 1 分钟片。

## 视觉 DNA（硬约束）

1. **主题固定 `anthropic-cream`**：米白纸张背景、衬线字体 (Fraunces / Playfair)、珊瑚红 `#d97757` 强调。系统会自动为你应用这个主题，不需要在 script.json 里指定。
2. **留白 > 内容**：每一屏只讲一件事，一屏一个视觉焦点。
3. **画面文字保留英文**（Anthropic 品牌一致性）。中文只在 `narration_zh` 里。
4. **叙事七拍**（≈一分钟片典型结构）：hook → 问题 → 产品入口 → 用户 prompt → 配置生成 → 运行实况 → 品牌锤。

## 唯一允许使用的 11 个组件

**禁止使用 `slide.anthropic-*` 之外的任何组件**。所有 segment 的 `component` 字段必须从下表精确选取：

| 组件 ID | 定位 | 推荐叙事位置 |
|---|---|---|
| `slide.anthropic-stickies-intro` | 便利贴 + 右侧 macOS 终端特写 | 第 1 段（hook）|
| `slide.anthropic-at-scale-question` | 多浮窗 + 中央衬线大字发问 | 第 1 或 2 段（切题）|
| `slide.anthropic-talking-head` | 从源视频裁剪真人出镜片段 + 米白画框 + lower-third 名片 | 第 1 段（hook）和倒数第 3 段（outro 前总结）|
| `slide.anthropic-template-picker` | Claude 产品 UI 模板选择器 | 第 3 段（产品入口）|
| `slide.anthropic-prompt-write` | 同 UI + 底部输入框逐字打字 | 第 4 段（用户交互）|
| `slide.anthropic-agent-config` | curl API + YAML + 漂浮终端 | 第 5 段（配置生成）|
| `slide.anthropic-feature-checklist` | 蓝勾划掉 + 蓝圈待办编号 | 第 6 段（能力清单）|
| `slide.anthropic-session-timeline` | Session dashboard 全景 | 第 7 段（运行实况）|
| `slide.anthropic-session-detail` | 同 dashboard + hover popover | 第 8 段（配置细节）|
| `slide.anthropic-brand-title` | 居中衬线大字 | 倒数第 2 段（品牌锤）|
| `slide.anthropic-brand-outro` | Claude logo + wordmark | 最后 1 段（收尾）|

**关于 talking-head 的使用时机**：当项目的 `sources/{video_id}/` 下存在源视频文件（通常是 user 自己录的讲解片），可以在脚本里穿插 1-2 段 talking-head 增强真实感。典型模式：
- **第 1 段 talking-head hook**：真人开场介绍"今天要聊的东西"，clipStart/clipEnd 通常选原视频开头 0-8s
- **倒数第 3 段 talking-head 总结**：真人说"所以我的看法是..."，clipStart/clipEnd 选原视频末尾最后 6-10s
- 中间段仍然用其他 anthropic-* 组件展示 UI / 概念 / 数据

若项目**没有源视频**（纯 motion graphics 品牌片），不要用 talking-head，否则渲染会显示"（缺少源视频）"fallback。

## narration_zh 写作规范

**这是档位最核心的特征**：中文旁白 + 英文画面并行，互相补充，**绝不重复**。

- `narration_zh` = 中文 TTS 旁白，每段严格 **≤40 字**（硬约束，违反即不合格）
- `slide_content.title` / `scene_data` 内的可见文字 = **英文**（保持品牌感）
- 旁白讲"**为什么 / 感受 / 态度**"；画面展示"**是什么 / 数据 / UI**"
- 例：画面上是 `"Build agents at scale,"`（英文大字），旁白是"大多数 Agent 死在规模化这一步。"

旁白语气：
- 短句为主，用反问句、反常识句
- **禁止书面语**：不要"首先"、"其次"、"综上所述"
- **禁止开场白套话**：不要"大家好"、"今天我们来讲"
- 宁可留白也不填满：一段只有 15 字完全可以
- 鼓励制造反差：「200 美金一个月，换来的是封号。」

## 脚本结构约束

- **总段数**：8-12 段（对应 45-75 秒品牌短片）
- **total_duration_hint**：45-75 秒之间，最佳 60 秒
- **material**：全部 `"A"`（纯视觉片，没有 B/C 素材）
- **第 1 段 hook**：必须是 `slide.anthropic-stickies-intro` 或 `slide.anthropic-at-scale-question`
- **倒数 2 段收尾**：必须是 `slide.anthropic-brand-title` + `slide.anthropic-brand-outro`
- **transition**：相邻段落在 `fade` / `zoom-in` / `slide-left` 里轮换，不要连续用同一个

## scene_data 使用说明

每个组件从 `slide_content.scene_data` 读结构化数据。完整 reference 见
`remotion-video/src/registry/styles/slide/ANTHROPIC_SCHEMAS.md`。下面是每个组件的**最小可用示例**。

### slide.anthropic-brand-title

```json
{
  "slide_content": {
    "title": "Your Big Message,",
    "bullet_points": []
  }
}
```

`title` 会按空格拆成词逐个淡入。建议 3-5 个词。

### slide.anthropic-brand-outro

```json
{
  "slide_content": {
    "title": "Claude",
    "bullet_points": []
  }
}
```

`title` 会作为 wordmark 出现在 logo 右边。

### slide.anthropic-at-scale-question

```json
{
  "slide_content": {
    "title": "How can you scale\nwith confidence…",
    "bullet_points": []
  }
}
```

`\n` 强制换行。画面文字建议 8-15 个英文单词。

### slide.anthropic-talking-head

```json
{
  "slide_content": {
    "title": "Lewis Menelaws",
    "bullet_points": ["Education · YouTube"],
    "scene_data": {
      "clipStart": 2,
      "clipEnd": 9,
      "caption": "Lewis Menelaws",
      "subtitle": "Education · YouTube",
      "cornerNote": "INTRO"
    }
  }
}
```

数据来源约定：
- `clipStart` / `clipEnd`（秒数，源视频里的绝对时间）是必填，指定要裁剪的片段范围
- 源视频文件名不用写 —— 系统会自动从 `sources/{project_id}/` 找（先查 mp4/webm/mkv），dispatcher 会把它注入 `scene_data.__source`
- `caption` / `subtitle` = 底部 lower-third 名片的主文字和副文字，通常是"人名 + 角色"
- `cornerNote` = 右上角小徽标，如 "INTRO" / "OUTRO" / "GUEST" / "02:15"
- 视频默认 **静音**（防止和 TTS 中文旁白打架）。若要保留原音，加 `"muted": false`

**重要**：talking-head 段的 `narration_zh` 仍然要写中文旁白（会通过 TTS 播在原视频之上，类似"配音"效果），不要留空。观众看到真人嘴动，但听到中文解说 —— 这是本档位的预期效果。

### slide.anthropic-stickies-intro

```json
{
  "slide_content": {
    "title": "",
    "bullet_points": [],
    "scene_data": {
      "stickies": [
        { "color": "yellow", "text": "FIX AUTH FLOW\nby next week", "rotation": -3 },
        { "color": "blue", "text": "Don't forget\nstandup at 10", "rotation": 3 }
      ],
      "terminalTitle": "claude-runtime — claude — 84×34",
      "terminalLines": [
        { "kind": "tool", "name": "Read", "args": "(src/auth.py) 112 lines", "result": "done" },
        { "kind": "spacer" },
        { "kind": "tool", "name": "Bash", "args": "(npm test)", "result": "23 passed\ndone" },
        { "kind": "status", "text": "Cogitating (12s · 450 tokens)" }
      ]
    }
  }
}
```

`stickies` 2-3 张为宜。颜色从 yellow/blue/pink/green 选。`terminalLines` 的 `kind` 枚举：`tool`、`status`、`spacer`。

### slide.anthropic-feature-checklist

```json
{
  "slide_content": {
    "title": "",
    "bullet_points": [
      "✓ Authentication",
      "✓ Rate limiting",
      "✓ Error recovery",
      "✓ Sandboxing",
      "5. Audit logs",
      "6. Retry policies",
      "7. Checkpointing",
      "8. Observability"
    ]
  }
}
```

约定：`✓ ` 前缀 = 已完成（蓝勾 + 划掉），`数字. ` 前缀 = 待办（蓝圈编号）。建议 done 4 项 + todo 4 项。

### slide.anthropic-template-picker

```json
{
  "slide_content": {
    "title": "What do you\nwant to build?",
    "bullet_points": [],
    "scene_data": {
      "appName": "New agent",
      "templates": [
        { "title": "Lead scoring", "desc": "Scores inbound leads based on fit + intent signals." },
        { "title": "Sales coach", "desc": "Grades cold emails and suggests edits." },
        { "title": "RFP responder", "desc": "Drafts RFP responses from your knowledge base." },
        { "title": "Churn analyzer", "desc": "Identifies at-risk accounts from usage data." },
        { "title": "Deal notes", "desc": "Summarizes call recordings into CRM notes." },
        { "title": "Meeting prep", "desc": "Pre-reads public signals before every meeting." }
      ]
    }
  }
}
```

`templates` 6-8 个，每个 `title` 2-3 个词，`desc` 一句话。

### slide.anthropic-prompt-write

```json
{
  "slide_content": {
    "title": "What do you want to build?",
    "bullet_points": [],
    "scene_data": {
      "prompt": "Build an agent that reviews our Q4 sales pipeline and flags at-risk deals based on engagement signals and forecast accuracy."
    }
  }
}
```

`prompt` 会逐字打入，1-2 句英文，展示用户意图。

### slide.anthropic-agent-config

```json
{
  "slide_content": {
    "title": "Generated agent config",
    "bullet_points": [],
    "scene_data": {
      "breadcrumb": "Agents / Pipeline Reviewer",
      "agentName": "agent_ab12cd34",
      "nextStep": "Next: Create environment",
      "userPrompt": "Build an agent that reviews our Q4 sales pipeline…",
      "apiCall": [
        "curl -X POST https://api.anthropic.com/v1/agents \\",
        "  -H \"x-api-key: $ANTHROPIC_API_KEY\" \\",
        "  -H \"anthropic-version: 2023-06-01\" \\",
        "  -d '{",
        "    \"name\": \"pipeline-reviewer\","
      ],
      "yamlLines": [
        "name: pipeline-reviewer",
        "model: claude-opus-4-6",
        "tools:",
        "  - type: agent_toolset_2026-04-01",
        "system: |",
        "  You are a senior sales operations analyst.",
        "  Review the Q4 pipeline and identify:",
        "  - Deals with stalled engagement",
        "  - Forecast category misalignment",
        "  - Next-step accuracy gaps"
      ]
    }
  }
}
```

`yamlLines` 每行是一个字符串，组件会自动把 yaml key 蓝色高亮。`apiCall` 是 curl 请求的每一行，建议 5-8 行。

### slide.anthropic-session-timeline

```json
{
  "slide_content": {
    "title": "Review Q4 sales pipeline",
    "bullet_points": [],
    "scene_data": {
      "sessionId": "…abc123",
      "badges": [
        "⌘ pipeline-reviewer",
        "⌖ env",
        "📄 crm.csv",
        "⏱ 2m ago",
        "↳ 45.2k / 2.1k"
      ],
      "agentLog": [
        { "kind": "agent", "label": "Session start", "time": "0:00" },
        { "kind": "user", "label": "Review Q4 pipeline", "toks": "420 toks", "time": "0:01" },
        { "kind": "agent", "label": "Loading CRM data from crm.csv", "toks": "1,200in / 80out", "time": "0:02" },
        { "kind": "read", "label": "Parsing 347 active deals", "time": "0:04" },
        { "kind": "web_search", "label": "Looking up account signals", "time": "0:08" },
        { "kind": "web_fetch", "label": "8 risk indicators found", "time": "0:12" }
      ],
      "panelTitle": "Pipeline Review Task",
      "panelFiles": [
        "crm_deals_Q4.csv,",
        "forecast_history.csv, account_activity.json,",
        "win_loss_notes.md"
      ]
    }
  }
}
```

`agentLog` 6-13 行，`kind` 从 `agent`/`user`/`read`/`glob`/`web_search`/`web_fetch` 选。

### slide.anthropic-session-detail

```json
{
  "slide_content": {
    "title": "Review Q4 sales pipeline",
    "bullet_points": [],
    "scene_data": {
      "sessionId": "…abc123",
      "badges": ["⌘ pipeline-reviewer", "⌖ env", "📄 crm.csv", "⏱ 2m ago"],
      "popover": {
        "name": "pipeline-reviewer",
        "model": "claude-opus-4-6",
        "version": "v1.2.0",
        "updated": "2 mins ago",
        "agentId": "agent_ab12cd34"
      },
      "agentName": "pipeline-reviewer",
      "systemPrompt": [
        "You are a senior sales operations analyst.",
        " ",
        "## Framework",
        " ",
        "### 1. Stalled deal detection",
        "- No activity in last 14 days",
        "- Missing next-step field",
        " ",
        "### 2. Forecast alignment",
        "- Category mismatch with close date"
      ],
      "mcpTools": [
        { "name": "crm_toolset", "desc": "Read and write", "count": 7 }
      ]
    }
  }
}
```

`systemPrompt` 是 YAML `system:` 字段的每一行，空行用 `" "`（单空格）。

## 完整骨架参考

下面给出**两个骨架**：A 是纯 motion graphics 无真人，B 是混合真人出镜（需要项目有源视频）。
照抄其中一个，**只改 narration_zh + scene_data 里的英文文案**，保持 component / transition / 段数不变。

### 骨架 A — 纯 motion graphics（无源视频项目使用）

```json
{
  "title": "...",
  "description": "...",
  "tags": ["..."],
  "source_channel": "",
  "total_duration_hint": 60,
  "segments": [
    { "id": 1, "type": "intro", "material": "A", "component": "slide.anthropic-stickies-intro", "transition": "fade",      "narration_zh": "<中文 hook ≤40字>",       "slide_content": { "title": "", "bullet_points": [], "scene_data": { /* stickies + terminal */ } } },
    { "id": 2, "type": "intro", "material": "A", "component": "slide.anthropic-at-scale-question", "transition": "zoom-in", "narration_zh": "<中文 ≤40字>",            "slide_content": { "title": "<英文大字发问>", "bullet_points": [] } },
    { "id": 3, "type": "body",  "material": "A", "component": "slide.anthropic-template-picker", "transition": "fade",      "narration_zh": "<中文 ≤40字>",            "slide_content": { "title": "What do you\nwant to build?", "bullet_points": [], "scene_data": { /* templates */ } } },
    { "id": 4, "type": "body",  "material": "A", "component": "slide.anthropic-prompt-write", "transition": "slide-left",   "narration_zh": "<中文 ≤40字>",            "slide_content": { "title": "", "bullet_points": [], "scene_data": { "prompt": "<英文 prompt 1-2 句>" } } },
    { "id": 5, "type": "body",  "material": "A", "component": "slide.anthropic-agent-config", "transition": "zoom-in",      "narration_zh": "<中文 ≤40字>",            "slide_content": { "title": "", "bullet_points": [], "scene_data": { /* yaml + api */ } } },
    { "id": 6, "type": "body",  "material": "A", "component": "slide.anthropic-feature-checklist", "transition": "fade",   "narration_zh": "<中文 ≤40字>",            "slide_content": { "title": "", "bullet_points": ["✓ Feature A", "✓ Feature B", "3. Feature C", "4. Feature D"] } },
    { "id": 7, "type": "body",  "material": "A", "component": "slide.anthropic-session-timeline", "transition": "slide-left", "narration_zh": "<中文 ≤40字>",         "slide_content": { "title": "<session title>", "bullet_points": [], "scene_data": { /* dashboard */ } } },
    { "id": 8, "type": "outro", "material": "A", "component": "slide.anthropic-brand-title", "transition": "fade",          "narration_zh": "<观点锤 ≤40字>",          "slide_content": { "title": "<英文观点锤>", "bullet_points": [] } },
    { "id": 9, "type": "outro", "material": "A", "component": "slide.anthropic-brand-outro", "transition": "fade",          "narration_zh": "",                         "slide_content": { "title": "Claude", "bullet_points": [] } }
  ]
}
```

### 骨架 B — 混合真人出镜（项目有源视频时使用）

用这个骨架的前提：`sources/{project_id}/` 下已经放了源视频文件（mp4/webm/mkv）。
dispatcher 会自动把文件信息注入 `scene_data.__source`，talking-head 组件读取后播放。

```json
{
  "title": "...",
  "description": "...",
  "tags": ["..."],
  "source_channel": "",
  "total_duration_hint": 60,
  "segments": [
    { "id": 1, "type": "intro", "material": "A", "component": "slide.anthropic-talking-head",    "transition": "fade",      "narration_zh": "<中文 hook ≤40字>",       "slide_content": { "title": "<作者名>", "bullet_points": ["<副标题>"], "scene_data": { "clipStart": 2, "clipEnd": 9, "caption": "<作者名>", "subtitle": "<角色>", "cornerNote": "INTRO" } } },
    { "id": 2, "type": "intro", "material": "A", "component": "slide.anthropic-at-scale-question", "transition": "zoom-in", "narration_zh": "<中文 ≤40字>",            "slide_content": { "title": "<英文大字发问>", "bullet_points": [] } },
    { "id": 3, "type": "body",  "material": "A", "component": "slide.anthropic-template-picker", "transition": "fade",      "narration_zh": "<中文 ≤40字>",            "slide_content": { "title": "What do you\nwant to build?", "bullet_points": [], "scene_data": { /* templates */ } } },
    { "id": 4, "type": "body",  "material": "A", "component": "slide.anthropic-feature-checklist", "transition": "slide-left", "narration_zh": "<中文 ≤40字>",          "slide_content": { "title": "", "bullet_points": ["✓ Feature A", "✓ Feature B", "3. Feature C", "4. Feature D"] } },
    { "id": 5, "type": "body",  "material": "A", "component": "slide.anthropic-session-timeline", "transition": "zoom-in",    "narration_zh": "<中文 ≤40字>",            "slide_content": { "title": "<session title>", "bullet_points": [], "scene_data": { /* dashboard */ } } },
    { "id": 6, "type": "body",  "material": "A", "component": "slide.anthropic-session-detail",  "transition": "fade",       "narration_zh": "<中文 ≤40字>",            "slide_content": { "title": "<session title>", "bullet_points": [], "scene_data": { /* popover */ } } },
    { "id": 7, "type": "body",  "material": "A", "component": "slide.anthropic-talking-head",    "transition": "fade",       "narration_zh": "<中文 ≤40字>",            "slide_content": { "title": "<作者名>", "bullet_points": ["<副标题>"], "scene_data": { "clipStart": 217, "clipEnd": 225, "caption": "<作者名>", "subtitle": "Closing thoughts", "cornerNote": "OUTRO" } } },
    { "id": 8, "type": "outro", "material": "A", "component": "slide.anthropic-brand-title",     "transition": "fade",       "narration_zh": "<观点锤 ≤40字>",          "slide_content": { "title": "<英文观点锤>", "bullet_points": [] } },
    { "id": 9, "type": "outro", "material": "A", "component": "slide.anthropic-brand-outro",     "transition": "fade",       "narration_zh": "",                         "slide_content": { "title": "Claude", "bullet_points": [] } }
  ]
}
```

**关于 clipStart / clipEnd 怎么选**：
- **intro talking-head（段 1）**：通常选源视频开头 2-9 秒（跳过片头 LOGO 的 2 秒），7 秒长度刚好让观众建立作者印象
- **outro talking-head（段 7）**：选源视频末尾最后 8 秒（比如 `clipEnd = 源视频总时长`，`clipStart = 总时长 - 8`），让作者说完最后一句话
- 中间的 talking-head 不推荐（破坏品牌片节奏）
- 每段 talking-head 建议 6-8 秒，短了信息不够，长了观众注意力流失

## 提交前自检清单

每一条都必须满足：

- [ ] 所有 `component` 字段都以 `slide.anthropic-` 开头
- [ ] 所有 `material` 都是 `"A"`
- [ ] 所有 `narration_zh` ≤40 中文字符（talking-head 段也要写，会叠在真人画面上播）
- [ ] `slide_content.title` 和 `scene_data` 里面向观众的文字都是**英文**
- [ ] 第 1 段的 `component` 是 `stickies-intro` / `at-scale-question` / `talking-head` 之一
- [ ] 倒数 2 段分别是 `brand-title` + `brand-outro`
- [ ] `total_duration_hint` 在 45-75 之间
- [ ] `segments` 数量 8-12
- [ ] `transition` 在相邻段落之间有变化
- [ ] 每段的 `scene_data`（如有）结构与本档位示例完全对齐（字段名、嵌套层级）
- [ ] 若用了 `talking-head` 组件：
  - [ ] 确认 `sources/{project_id}/` 下有源视频文件（.mp4 / .webm / .mkv）
  - [ ] `clipStart` / `clipEnd` 都是源视频里的绝对秒数，区间 ≤10 秒
  - [ ] 一条片里 talking-head 段数不超过 2（一个 intro + 一个 outro 前总结）
