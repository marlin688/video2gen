# 技术解说片档位 (tech_explainer)

你当前在生成一条 **Anthropic 风格的技术解说片** — 米白纸张 + 衬线字体 + 珊瑚红强调的视觉 DNA，但**叙事结构是技术教程型**，不是 60 秒品牌短片。

## 这个档位和 anthropic_brand 的区别

| 维度 | anthropic_brand (品牌片) | **tech_explainer (你当前档位)** |
|---|---|---|
| 时长 | 45-75s 硬约束 | **无限制，内容驱动** |
| 段数 | 8-12 | **无限制**（5-30 段都可以） |
| 结构 | 固定套路 (hook→发问→产品→...) | **talking-head + screen-clip 交替**，随内容自由 |
| 段间转场 | 轮换 fade/zoom/slide | **硬切 (none)** — 技术解说片干净利落 |
| 画面运镜 | 启用 CameraRig 微推进 | **关闭** — 屏幕录制 + 真人画面不要任何漂移 |
| narration_zh | 每段 ≤40 字 | **每段 ≤80 字**（因 screen-clip 可能 30s+ 长）|

## 视觉 DNA（保留）

1. **主题固定 anthropic-cream**（系统自动应用）
2. **衬线字体**用于所有标题、章节、callout
3. **珊瑚红 #d97757** 作为高亮和强调色
4. **画面文字可以中文**（技术解说片面向中文观众，不强制英文）

## 核心叙事模式

这个档位的典型结构：

```
[1] talking-head intro         ← 作者开场：今天要讲什么 (8-15s)
[2] section-title: Part 1      ← 章节卡 (3s)，可选
[3] screen-clip demo           ← 屏幕演示，任意长度
[4] callout: insight           ← 关键点卡片 (5-6s)，可选
[5] screen-clip demo (续)      ← 继续演示
[6] talking-head transition    ← 作者过场：现在看 Part 2 (8-12s)
[7] section-title: Part 2
[8] screen-clip config
[9] agent-config 或 code展示   ← 展示配置或代码
[10] screen-clip run           ← 运行效果
[11] callout: warning          ← 踩坑警告，可选
[12] screen-clip fix           ← 修复过程
[13] talking-head outro        ← 作者收尾总结 (10-20s)
[14] brand-outro              ← Logo 收尾 (3s)，可选
```

**你不必**严格照抄 —— 内容驱动。有些视频可能只有 6 段 (talk→demo→talk→demo→talk→brand)，有些可能 20+ 段。

## 14 个可用组件

**禁止使用 `slide.anthropic-*` 之外的任何组件**。

### 核心两个（承载大部分内容）

| 组件 ID | 作用 | 何时用 |
|---|---|---|
| `slide.anthropic-talking-head` ⭐ | 真人出镜片段 + lower-third 名片 | 开场 / 过场 / 收尾总结 |
| `slide.anthropic-screen-clip` ⭐ | 屏幕录制片段 + macOS 窗框 + 高亮区 | 所有演示段 |

### 辅助结构（可选）

| 组件 ID | 作用 | 何时用 |
|---|---|---|
| `slide.anthropic-section-title` | 章节分隔卡 (Part 1 / Part 2) | 长视频需要章节感时 |
| `slide.anthropic-callout` | 关键点强调卡 (tip/warning/insight/quote) | 强调关键技巧、踩坑、洞察 |
| `slide.anthropic-brand-title` | 衬线大字 | 观点锤 / 转场金句 |
| `slide.anthropic-brand-outro` | Claude logo 收尾 | 结尾品牌 hook |

### 通用视觉（9 个老组件，按需用）

下面 9 个组件原本是为品牌片做的，但都已参数化，**在技术解说片里可以当"画面多样性调味料"用**：

| 组件 ID | 原定位 | **技术解说片里的通用用法** |
|---|---|---|
| `slide.anthropic-stickies-intro` | 便利贴+终端 | "这是我手上的 todo + 终端在跑任务" 的工作场景开场 |
| `slide.anthropic-at-scale-question` | 大字发问 | 任何**切题段**的"一个大问题" |
| `slide.anthropic-template-picker` | 模板选择器 UI | **"从选项里挑一个"** 的产品/工具展示 (VSCode 插件对比等) |
| `slide.anthropic-prompt-write` | AI 输入框 | **"用户向 AI 输入指令"** 的交互演示 |
| `slide.anthropic-agent-config` | Agent YAML + API | **"配置文件 + 终端测试"** 的组合 (任何 devops 场景) |
| `slide.anthropic-feature-checklist` | 能力清单 | 任何**"进度清单 / 已完成 vs 待办"** |
| `slide.anthropic-session-timeline` | Agent dashboard | 任何 **"日志 / 监控 / 任务追踪"** 可视化 |
| `slide.anthropic-session-detail` | Agent popover | 任何 **"配置项 hover 详情"** |

这些组件不是必须用，但当你需要**中间某段"演示没法用屏幕录制"**（比如你在讲一个理论概念或架构图）时，可以用这些组件 mock 出画面。

## 关键组件的 scene_data 最小示例

### slide.anthropic-talking-head（真人出镜）

```json
{
  "component": "slide.anthropic-talking-head",
  "narration_zh": "今天聊一个刚发现的东西。",
  "slide_content": {
    "title": "<作者名>",
    "bullet_points": ["<角色/频道>"],
    "scene_data": {
      "videoFile": "talking/lecture.mp4",
      "clipStart": 5,
      "clipEnd": 15,
      "caption": "<作者名>",
      "subtitle": "<角色/频道>",
      "cornerNote": "INTRO"
    }
  }
}
```

- `videoFile` 写相对 `sources/{project_id}/` 的路径，render.mjs 会自动找并转码
- `clipStart` / `clipEnd` 是源视频里的**绝对秒数**
- 默认静音，中文 TTS 旁白叠在上面播
- **每段 talking-head 建议 6-15 秒**

### slide.anthropic-screen-clip（屏幕录制）⭐ 最重要

```json
{
  "component": "slide.anthropic-screen-clip",
  "narration_zh": "第一步是跑 lighthouse audit，看当前分数。",
  "slide_content": {
    "title": "Lighthouse audit",
    "bullet_points": [],
    "scene_data": {
      "videoFile": "recordings/demo-1-audit.mov",
      "clipStart": 0,
      "clipEnd": 28,
      "label": "Lighthouse 初始分 = 62",
      "cornerNote": "Part 1 · Step 1",
      "highlights": [
        {
          "x": 0.45, "y": 0.60, "w": 0.12, "h": 0.08,
          "start": 60, "end": 180,
          "kind": "rect",
          "label": "Performance 分数"
        },
        {
          "x": 0.30, "y": 0.40, "w": 0.08, "h": 0.12,
          "start": 200, "end": 320,
          "kind": "circle"
        }
      ]
    }
  }
}
```

- **`highlights` 坐标是归一化 0-1**（相对视频 16:9 显示区域），和源视频分辨率无关
- `start` / `end` 是**相对 clip 起始的帧数**（非源视频绝对时间）
- `kind: "rect"` 画矩形框，`kind: "circle"` 画圆圈
- `label` 可选，框下方跟一个说明卡片
- `clipEnd - clipStart` **可以任意长度**（30 秒以上也 OK，不要拆）
- screen-clip 段的 `narration_zh` 很可能比 clip 短，剩余时间是静音看画面 —— 这是预期效果

### slide.anthropic-section-title（章节卡）

```json
{
  "component": "slide.anthropic-section-title",
  "narration_zh": "接下来看第二部分。",
  "slide_content": {
    "title": "",
    "bullet_points": [],
    "scene_data": {
      "chapter": "Part 2",
      "title": "把它接进 CI",
      "subtitle": "GitHub Actions + 自动触发"
    }
  }
}
```

长度建议 **2-4 秒**。

### slide.anthropic-callout（关键点卡）

```json
{
  "component": "slide.anthropic-callout",
  "narration_zh": "这里最容易踩的坑在下面这点。",
  "slide_content": {
    "title": "",
    "bullet_points": [],
    "scene_data": {
      "kind": "warning",
      "title": "容易踩的坑",
      "body": "rate limit 是按 request 数算的，不是 token。你的并发设计要从这一层反推。"
    }
  }
}
```

`kind` 四选一：
- `"tip"` 💡 蓝色 — 实用技巧
- `"warning"` ⚠ 橙色 — 踩坑警告
- `"insight"` ✻ 珊瑚红 — 深度洞察（默认）
- `"quote"` ❝ 紫灰 — 引用

长度建议 **4-6 秒**。

## narration_zh 写作规范

- **每段 ≤80 字**（长 screen-clip 也只给 80 字以内的旁白）
- 口语化，禁止"首先/其次/综上所述"类书面语
- **screen-clip 段的 narration 是"画外音解说"**，要和屏幕上发生的事对齐
  - 好例：画面在跑 audit，旁白说"第一次跑出来是 62 分，主要问题是图片没压缩"
  - 坏例：画面在跑 audit，旁白说"我们的产品很强大，已经被 1000 家公司采用"
- **talking-head 段的 narration 是"真人讲解的中文翻译"**，观众看到真人嘴动但听中文

## 项目目录约定

```
sources/{project_id}/
├── talking/
│   └── lecture.mp4              # 主讲视频（可以是一个长视频，用时间戳裁多段）
├── recordings/
│   ├── demo-1-install.mov       # 屏幕录制 1
│   ├── demo-2-config.mov
│   └── demo-3-run.mov
└── (可选) assets/
    └── screenshot.png
```

在 `script.json` 里**直接用相对路径引用**：

```json
{ "videoFile": "talking/lecture.mp4" }
{ "videoFile": "recordings/demo-1-install.mov" }
```

`render.mjs` 会递归扫描 `sources/{project_id}/`，转码成 H.264 保持目录结构拷到 `public/`。

## 硬性约束

- `component` 必须以 `slide.anthropic-` 开头（14 选一）
- `material` 固定 `"A"`
- `narration_zh` 每段 ≤80 字
- talking-head 段必须有 `videoFile` 或依赖 `__source` 兜底
- screen-clip 段必须有 `videoFile` + `clipStart` + `clipEnd`
- highlight 的坐标必须 0-1 归一化
- 最后一段建议 talking-head outro 或 brand-outro（让结尾有 closure）

## 完整骨架参考

### 短版 (≈90 秒, 8 段) — 单一主题快速解说

```json
{
  "title": "...",
  "description": "...",
  "total_duration_hint": 90,
  "segments": [
    { "id": 1, "type": "intro", "material": "A", "component": "slide.anthropic-talking-head", "transition": "none", "narration_zh": "<开场 8-15s>", "slide_content": { "scene_data": { "videoFile": "talking/lecture.mp4", "clipStart": 2, "clipEnd": 12, "caption": "<作者>", "cornerNote": "INTRO" } } },
    { "id": 2, "type": "body",  "material": "A", "component": "slide.anthropic-screen-clip",  "transition": "none", "narration_zh": "<讲第一个演示>", "slide_content": { "scene_data": { "videoFile": "recordings/demo-1.mov", "clipStart": 0, "clipEnd": 25, "label": "<演示说明>", "highlights": [/* 可选 */] } } },
    { "id": 3, "type": "body",  "material": "A", "component": "slide.anthropic-callout",       "transition": "none", "narration_zh": "<关键点>", "slide_content": { "scene_data": { "kind": "insight", "title": "<小标题>", "body": "<1-2 句>" } } },
    { "id": 4, "type": "body",  "material": "A", "component": "slide.anthropic-screen-clip",  "transition": "none", "narration_zh": "<第二个演示>", "slide_content": { "scene_data": { "videoFile": "recordings/demo-2.mov", "clipStart": 0, "clipEnd": 20, "label": "<演示说明>" } } },
    { "id": 5, "type": "body",  "material": "A", "component": "slide.anthropic-talking-head", "transition": "none", "narration_zh": "<过场>", "slide_content": { "scene_data": { "videoFile": "talking/lecture.mp4", "clipStart": 60, "clipEnd": 68 } } },
    { "id": 6, "type": "body",  "material": "A", "component": "slide.anthropic-screen-clip",  "transition": "none", "narration_zh": "<第三个演示>", "slide_content": { "scene_data": { "videoFile": "recordings/demo-3.mov", "clipStart": 0, "clipEnd": 15 } } },
    { "id": 7, "type": "outro", "material": "A", "component": "slide.anthropic-talking-head", "transition": "none", "narration_zh": "<收尾总结>", "slide_content": { "scene_data": { "videoFile": "talking/lecture.mp4", "clipStart": 180, "clipEnd": 195, "cornerNote": "OUTRO" } } },
    { "id": 8, "type": "outro", "material": "A", "component": "slide.anthropic-brand-outro",  "transition": "none", "narration_zh": "", "slide_content": { "title": "<频道名>" } }
  ]
}
```

### 长版 (≈4-6 分钟, 12-16 段) — 多章节深度解说

结构：

```
intro talk → section-title Part 1 → screen 1 → screen 2 → callout → talk transition
          → section-title Part 2 → screen 3 → agent-config → screen 4 → callout warning
          → screen 5 → outro talk → brand-outro
```

## 提交前自检清单

- [ ] 所有 `component` 以 `slide.anthropic-` 开头
- [ ] 所有 `material` = `"A"`
- [ ] 所有 `narration_zh` ≤80 字
- [ ] 每段 `transition` 都是 `"none"` 或缺省（档位默认硬切）
- [ ] 所有 `talking-head` / `screen-clip` 段有 `videoFile` + `clipStart` + `clipEnd`
- [ ] `videoFile` 是相对 `sources/{project_id}/` 的路径（例如 `"recordings/demo-1.mov"`）
- [ ] `highlights` 的 x/y/w/h 都在 0-1 范围内
- [ ] 第一段是 `talking-head`（推荐）或 `stickies-intro`
- [ ] 最后 1-2 段是 `talking-head` outro 或 `brand-outro`
- [ ] screen-clip 段的 `narration_zh` 内容和画面对齐（不要讲无关的话）
