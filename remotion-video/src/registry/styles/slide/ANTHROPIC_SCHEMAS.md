# Anthropic Brand Styles — `scene_data` Reference

这个文件记录 11 个 `slide.anthropic-*` 组件各自接受的 `scene_data` 结构，
供手写 `script.json` 或通过 agent LLM 生成品牌片时参考。

## 通用约定

所有 `slide.anthropic-*` 组件共享以下数据入口：

- `slide_content.title` — 简单场景（brand-title / brand-outro / question）直接当标题/文案
- `slide_content.bullet_points` — 简单列表场景（feature-checklist / stickies-intro fallback）
- `slide_content.scene_data` — 场景专属结构化数据（复杂场景必须用）

**优先级**：`scene_data` > `bullet_points` / `title` > 组件内置 DEFAULT 示范数据。
完全不填任何数据时，每个场景都会渲染它原来复刻 Anthropic 官方片时用的那份 hardcoded 内容，方便你先预览一次再逐段替换。

**主题**：所有 anthropic-* 组件在 `anthropic-cream` 主题下视觉最一致。在 `checkpoint.json` 里设 `"theme": "anthropic-cream"` 或启动时 `V2G_THEME=anthropic-cream node ...`。

---

## 1. `slide.anthropic-stickies-intro`

开场便利贴 + 右侧 macOS 风格终端。

**数据来源（任一即可）**：

### A) 用 `bullet_points`（最简）
```json
{
  "slide_content": {
    "title": "",
    "bullet_points": [
      "FIX AUTH FLOW by next week",
      "Don't forget\nto eat\ndinner"
    ]
  }
}
```
前 4 条 bullet 渲染为 4 张便利贴（颜色自动循环 yellow/blue/pink/green）。终端用内置 DEFAULT 日志。

### B) 用 `scene_data`（完全自定义）
```json
{
  "slide_content": {
    "title": "",
    "bullet_points": [],
    "scene_data": {
      "stickies": [
        { "color": "yellow", "text": "...", "rotation": -3 },
        { "color": "blue", "text": "...", "rotation": 3 }
      ],
      "terminalTitle": "your-shell — claude — 84×34",
      "terminalLines": [
        { "kind": "tool", "name": "Read", "args": "(file.py)", "result": "done" },
        { "kind": "spacer" },
        { "kind": "tool", "name": "Bash", "args": "(ls -la)", "result": "10 files\ndone" },
        { "kind": "status", "text": "Cogitating (12s · 450 tokens)" }
      ]
    }
  }
}
```

`terminalLines` 元素类型：
- `{ kind: "tool", name, args, result }` — 绿色 ●，name 白粗体，args 灰括号
- `{ kind: "status", text }` — 状态提示，"Cogitating" 前缀自动上色珊瑚红
- `{ kind: "spacer" }` — 空行间距

---

## 2. `slide.anthropic-at-scale-question`

镜头拉开 + 中央衬线大字发问 + 周围浮动的代码/告警/浏览器/终端窗口（窗口内容内置，不可改）。

```json
{
  "slide_content": {
    "title": "How can you build and deploy\nagents at scale…",
    "bullet_points": [],
    "scene_data": {
      "question": "可选，覆盖 title。\n支持 \\n 换行"
    }
  }
}
```

**注**：周围的 4-5 个浮动 UI 窗口目前是 hardcoded 的（属于"视觉复杂度展示"而非内容），若要改需要直接编辑 `anthropic-at-scale-question.tsx`。

---

## 3. `slide.anthropic-template-picker`

Claude 产品 UI 风格的模板选择器：左问题 + 右模板网格。

```json
{
  "slide_content": {
    "title": "What do you\nwant to build?",
    "bullet_points": [],
    "scene_data": {
      "appName": "New agent",
      "question": "可选，覆盖 title",
      "tags": [
        { "label": "All", "active": true },
        { "label": "Research & retrieval" },
        { "label": "Evaluate & judge" }
      ],
      "templates": [
        { "title": "Deep research", "desc": "Multi-step web research…" },
        { "title": "RAG retrieval", "desc": "…" }
      ]
    }
  }
}
```

`templates` 最多显示 8 个，超出会溢出窗口。

---

## 4. `slide.anthropic-prompt-write`

延续 template-picker 布局，展示用户正在打字的 prompt + 左侧快捷选项。

```json
{
  "slide_content": {
    "title": "What do you want to build?",
    "bullet_points": [],
    "scene_data": {
      "prompt": "Build an agent that evaluates acquisition targets…",
      "question": "可选",
      "quickActions": [
        { "icon": "⤒", "text": "Upload existing spec as context" },
        { "icon": "◐", "text": "/ to add skills or sub agents" },
        { "icon": "|||", "text": "Let Claude interview you" }
      ],
      "templates": ["Deep research", "RAG retrieval", "..."]
    }
  }
}
```

**关键细节**：`prompt` 字段会逐字打字动画（每 1.2 帧一字符）。确保紧跟 scene 3 使用，且 scene 3 里的 `templates` 列表要和这里一致，否则 fade 交叉溶解会产生抖动。

---

## 5. `slide.anthropic-agent-config`

左面板展示生成的 agent 配置（用户 prompt + curl API 调用 + agent_id），右面板 YAML 源码，右上角漂浮 terminal。

```json
{
  "slide_content": {
    "title": "Generated agent config",
    "bullet_points": [],
    "scene_data": {
      "breadcrumb": "Agents  /  Merges & Acks",
      "agentName": "agent_01JR4kW9",
      "nextStep": "Next: Create environment",
      "userPrompt": "Build an agent that evaluates acquisition targets…",
      "apiCall": [
        "curl -X POST https://api.anthropic.com/v1/agents \\",
        "  -H \"x-api-key: $ANTHROPIC_API_KEY\" \\",
        "  ..."
      ],
      "yamlLines": [
        "name: my-agent",
        "model: claude-opus-4-6",
        "system: |",
        "  You are an expert in ...",
        "  ## Framework"
      ],
      "terminalTitle": "proposal-system — claude — 80×34",
      "terminalLines": [
        { "kind": "code", "text": "import" },
        { "kind": "code", "text": "client" },
        { "kind": "blank", "text": "" },
        { "kind": "comment", "text": "// explanation" },
        { "kind": "status", "text": "✻ Cogitating (26s · ↑ 570 tokens)" }
      ]
    }
  }
}
```

**YAML 高亮规则**：每一行若匹配 `^(\s*)([A-Za-z_][A-Za-z0-9_-]*)(\s*:)(.*)$`，开头的 key 会自动着色为蓝色 `#0550ae`。其余按原文渲染。

**terminalLines 的 kind**：`code` (亮色), `comment` (灰 `//`), `status` (珊瑚红/紫), `blank` (空行)。

---

## 6. `slide.anthropic-feature-checklist`

白色圆角卡：上半是蓝色实心勾+划掉的已完成项，下半是蓝色描边编号+待办项。

### A) 用 `bullet_points` 约定（推荐）

```json
{
  "slide_content": {
    "title": "",
    "bullet_points": [
      "✓ Sandboxing",
      "✓ Error recovery",
      "✓ Auth",
      "✓ Memory",
      "5. Event state mgmt",
      "6. File persistence",
      "7. Checkpointing",
      "8. Retry policies"
    ]
  }
}
```

- 以 `✓ ` 开头 → 已完成（划掉 + 蓝勾）
- 以 `数字. ` 或 `- ` 开头 → 待办（蓝圈编号）

### B) 用 `scene_data` 显式指定

```json
{
  "slide_content": {
    "scene_data": {
      "done": ["Sandboxing", "Error recovery", "Auth", "Memory"],
      "todo": ["Event state mgmt", "File persistence", "Checkpointing", "Retry policies"],
      "todoStartIndex": 5
    }
  }
}
```

`todoStartIndex` 是待办项的起始编号（默认 = done.length + 1）。

---

## 7. `slide.anthropic-session-timeline`

Claude Agents session dashboard 全景：顶部 session 名 + Active 徽标 + 元信息标签 + 顶部彩色时间线 + 左栏 agent 日志 + 右栏数据分析面板。

```json
{
  "slide_content": {
    "title": "Build investment thesis for BuyCo",
    "bullet_points": [],
    "scene_data": {
      "sessionId": "…heC6T3Y",
      "badges": [
        "⌘ my-agent",
        "⌖ env",
        "📄 1 file",
        "⏱ 22 hours ago",
        "⏱ 5m 34s"
      ],
      "agentLog": [
        { "kind": "agent", "label": "Session start", "time": "0:00" },
        { "kind": "user", "label": "Your request here", "toks": "780 toks", "time": "0:01" },
        { "kind": "agent", "label": "Starting analysis", "toks": "1,878in / 100out", "time": "0:02" },
        { "kind": "glob", "label": "Scanning files", "time": "0:05" },
        { "kind": "read", "label": "Opening file X", "time": "0:09" },
        { "kind": "web_search", "label": "Search query", "time": "0:12" },
        { "kind": "web_fetch", "label": "Fetch URL", "time": "0:18" }
      ],
      "panelTitle": "Data Analysis Task",
      "panelFiles": [
        "file1.csv,",
        "file2.csv, file3.csv,"
      ],
      "panelFooter": [
        "Scanned /workspace/… done (142ms)",
        "Matched 8 of 11 entries"
      ]
    }
  }
}
```

`agentLog` 的 `kind` 决定行前徽章的颜色和标签：
- `agent` — 黑底白字 "Agent"
- `user` — 红底白字 "User"
- `read` / `glob` / `web_search` / `web_fetch` — 灰底灰字

顶部的彩色时间线色条目前是 hardcoded 的（18 格粉/蓝/灰）。

---

## 8. `slide.anthropic-session-detail`

延续 session-timeline，不做入场动画（避免和前一幕产生文字 shimmer）。左栏保持 agent 日志，右栏换成 agent 详情面板，左上角浮出 hover popover。

```json
{
  "slide_content": {
    "title": "Build investment thesis for BuyCo",
    "bullet_points": [],
    "scene_data": {
      "sessionId": "…heC6T3Y",
      "badges": ["..."],
      "badgeHighlightIndex": 0,
      "agentLog": [
        { "k": "Agent", "bg": "#1a1a1a", "c": "#fff", "label": "...", "meta": "1,878in / 100out · 3s · 0:02" },
        { "k": "Glob", "bg": "#f0efea", "c": "#555", "label": "...", "meta": "4s · 0:05", "active": true },
        { "k": "Read", "bg": "#f0efea", "c": "#555", "label": "...", "meta": "3s · 0:09" }
      ],
      "popover": {
        "name": "my-agent",
        "model": "claude-opus-4-6",
        "version": "17748465448...",
        "updated": "22 hours ago",
        "agentId": "agent_011CZ…"
      },
      "agentName": "my-agent",
      "systemPrompt": [
        "You are a senior analyst specializing in retail",
        "sector transactions...",
        " ",
        "## Framework"
      ],
      "mcpTools": [
        { "name": "agent_toolset", "desc": "Read and write", "count": 9 }
      ]
    }
  }
}
```

**注意**：这里的 `agentLog` 结构和 scene 7 略有不同（直接用 `{k, bg, c, label, meta, active?}` 原生样式，而不是 `kind` 自动映射）。这是历史遗留，两个场景可能会在后续统一。

`badgeHighlightIndex` 决定哪个 badge 有珊瑚红外框（表示鼠标正悬停）。默认 0 即第一个。

---

## 9. `slide.anthropic-brand-title`

米白背景 + 居中衬线大字，按词逐个淡入。

```json
{
  "slide_content": {
    "title": "Your Big Brand Message,",
    "bullet_points": [],
    "scene_data": {
      "words": ["Your", "Big", "Message,"]
    }
  }
}
```

- 只填 `title`，会按空格拆成词依次淡入（推荐）
- 或显式用 `scene_data.words` 手动控制拆分

---

## 10. `slide.anthropic-brand-outro`

米白背景 + Claude 星芒 logo + 衬线 wordmark 文字。

```json
{
  "slide_content": {
    "title": "YourBrand",
    "bullet_points": [],
    "scene_data": {
      "wordmark": "YourBrand",
      "showLogo": true
    }
  }
}
```

- `wordmark` 覆盖 title 作为主文字
- `showLogo = false` 会去掉 Claude 星芒 logo，只保留衬线文字（适合做 "Powered by X" 类品牌收尾）

Logo 目前是 Claude 的珊瑚红星芒（SVG 硬编码在 `ClaudeLogo.tsx`），不支持运行时换 logo。要做其他品牌的 outro，直接 fork 一个 `your-brand-outro.tsx` 并换 SVG。

---

## 11. `slide.anthropic-talking-head`

从项目的源视频里裁剪一段真人出镜片段，嵌进米白圆角白框 + 珊瑚红竖线 lower-third 名片。专门用于品牌短片里穿插"作者本人讲解"片段，保留真实感。

**前提**：项目目录 `sources/{project_id}/` 下必须已经放了源视频文件（`.mp4` / `.webm` / `.mkv`）。`render.mjs` 会自动找到并转码（AV1/VP9 → H.264），dispatcher 会把文件信息注入 `scene_data.__source`，组件读取后播放。

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
      "cornerNote": "INTRO",
      "muted": true,
      "framePadding": 120
    }
  }
}
```

### scene_data 字段

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `clipStart` | number | 0 | 源视频里的起始秒数 |
| `clipEnd` | number | clipStart + 8 | 源视频里的结束秒数 |
| `muted` | boolean | `true` | **默认静音**以避免和 TTS 中文旁白打架。要保留原音设 `false` |
| `caption` | string | `data.title` | lower-third 主文字（人名） |
| `subtitle` | string | `bullet_points[0]` | lower-third 副文字（角色/标签） |
| `cornerNote` | string | `""` | 右上角小徽标，如 `"INTRO"` / `"OUTRO"` / `"02:15"` |
| `framePadding` | number | 120 | 视频窗口距画面边缘的内边距（px） |
| `accent` | string | `theme.accent` | lower-third 左侧竖线色，默认珊瑚红 |
| `videoFile` | string | 自动 | 通常不用填，dispatcher 会从 `sources/{id}/` 自动注入 |

### 典型用法

**intro 真人 hook**（段 1）：
```json
{
  "id": 1, "type": "intro", "material": "A",
  "component": "slide.anthropic-talking-head",
  "narration_zh": "Anthropic 刚发布了 Managed Agents。",
  "slide_content": {
    "title": "Lewis Menelaws",
    "bullet_points": ["Education"],
    "scene_data": { "clipStart": 2, "clipEnd": 9, "cornerNote": "INTRO" }
  }
}
```

**outro 真人总结**（倒数第 3 段）：
```json
{
  "id": 7, "type": "body", "material": "A",
  "component": "slide.anthropic-talking-head",
  "narration_zh": "作者的总结是这样的。",
  "slide_content": {
    "title": "Lewis Menelaws",
    "bullet_points": ["Closing thoughts"],
    "scene_data": { "clipStart": 217, "clipEnd": 225, "cornerNote": "OUTRO" }
  }
}
```

### 注意事项

- **必须有源视频**：若 `sources/{project_id}/` 下没有视频文件，组件会显示"（缺少源视频）"占位，不报错但画面会空。
- **默认静音 + 中文 TTS**：默认会静掉原视频的音频，把 `narration_zh` 的中文 TTS 叠在上面。观众看到真人嘴动，听到中文配音 —— 这是品牌片的标准做法。如果要保留英文原音，加 `"muted": false`，但这样就不能同时有 TTS 旁白。
- **每段 ≤10 秒**：长了观众会走神。品牌片节奏里 talking-head 只是"锚点"不是"主菜"。
- **一条片最多 2 段**：更多会让品牌片感变弱，变成"普通解说片"。

### 项目结构示例

```
output/my-brand-video/
├── checkpoint.json           # theme: "anthropic-cream"
├── script.json               # 含 slide.anthropic-talking-head 段
├── voiceover/
│   ├── full.mp3
│   └── segments/seg_*.mp3
└── ...

sources/my-brand-video/
└── video.mp4                 # 你的讲解片源视频（自动被 render.mjs 找到）
```

或 symlink：
```bash
ln -s "/path/to/your/lecture.mp4" sources/my-brand-video/video.mp4
```

---

## 快速上手

1. 复制 `output/claude-managed-agents-clone/` 作为模板
2. 编辑 `script.json` 的 10 段 segments，逐段填你自己的 scene_data
3. 重新生成 `voiceover/timing.json` + 对应时长的静音 mp3（参考现有文件）
4. 如果段数或时长变了，同步更新 `timing.json` 和 `voiceover/full.mp3`
5. `node remotion-video/render.mjs your-project-id` 出片

完整示例见 `output/claude-managed-agents-clone/script.json` — 这个 clone 项目本身就是"所有 10 个 scene_data 的规范用法"的参考实现。
