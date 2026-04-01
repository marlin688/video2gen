# video2gen (v2g)

AI 驱动的 YouTube 二创视频自动生成流水线。从选片、下载翻译、AI 脚本编写、TTS 配音到视频合成，全流程自动化。

## 功能特性

- **智能选片** — 从 YouTube 热榜 CSV 中交互式筛选素材
- **AI 脚本生成** — 支持 Claude / GPT / Gemini / GLM / MiniMax 多模型，自动分配三种素材类型
- **Agent 智能编排** — 从 markdown、公众号文章、字幕等异构素材自动编排视频脚本（两阶段：大纲→脚本）
- **TTS 配音** — edge-tts（免费）或 MiniMax（高质量），按段落生成独立音频
- **幻灯片生成** — 6 种布局模式（代码、对比、指标、网格、步骤、标准）
- **双渲染后端** — FFmpeg 快速合成 或 Remotion 声明式渲染（带动画）
- **多源合成** — 将多个 YouTube 视频融合为一个二创作品
- **断点续传** — 每阶段独立可执行，checkpoint 机制支持任意阶段恢复

## 快速开始

### 环境要求

- Python >= 3.11
- Node.js >= 18
- FFmpeg
- [lecture2note](../lecture2note/) 和 [youtube-trending](../youtube-trending/) 兄弟项目

### 安装

```bash
# Python 后端
pip install -e .

# Remotion 前端
cd remotion-video
npm install
```

### 配置

复制 `.env.example` 为 `.env` 并填写必要的 API Key：

```bash
cp .env.example .env
```

关键配置项：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ANTHROPIC_API_KEY` | Claude API 密钥 | — |
| `SCRIPT_MODEL` | 脚本生成模型 | `claude-sonnet-4-5-20250929` |
| `ZHIPU_API_KEY` | 智谱 GLM API 密钥 | — |
| `GPT_API_KEY` | OpenAI 兼容接口密钥 | — |
| `GPT_BASE_URL` | OpenAI 兼容接口地址 | — |
| `TTS_MINMAX_KEY` | MiniMax API 密钥（TTS + 文本模型共用） | — |
| `TTS_VOICE` | TTS 语音 | `zh-CN-YunxiNeural` |
| `TTS_ENGINE` | TTS 引擎 (`edge` / `minimax`) | `edge` |
| `VIDEO_RESOLUTION` | 输出分辨率 | `1920x1080` |

## 使用方式

### 单视频流水线

全自动执行，含人工审核环节：

```bash
v2g run <video_id_or_url>
```

分步执行：

```bash
v2g select --csv trending.csv     # 1. 从热榜选择视频
v2g prepare <video_id>            # 2. 下载 + 生成字幕
v2g script <video_id>             # 3. AI 生成脚本
v2g review <video_id>             # 4. 人工审核脚本
v2g tts <video_id>                # 5. 文本转语音
v2g slides <video_id>             # 6. 生成幻灯片
v2g record <video_id>             # 7. 截图转视频（可选）
v2g assemble <video_id>           # 8. FFmpeg 合成 → final.mp4
```

### Agent 智能编排（推荐）

从 markdown、公众号文章 URL、视频字幕等多种素材自动编排脚本：

```bash
v2g agent my-video \
  -s article.md \
  -s "https://mp.weixin.qq.com/s/xxx" \
  -s sources/VIDEO_ID/subtitle_zh.srt \
  -t "AI编程工具横评" \
  --duration 300

# 支持指定模型 (默认 Claude，可选 glm-5 / minimax-m2.7 等)
v2g agent my-video -s notes.md -t "主题" --model glm-5
```

工作流：素材抓取/读取 → 交叉分析 → 大纲生成 → 人工确认 → 展开 script.json → 衔接 TTS/slides/render。

### 多源合成

将多个视频融合为一个作品：

```bash
v2g multi "url1;url2;url3" --topic "主题" --project-id my-project
```

多源模式使用 Remotion 渲染，输出 `final_remotion.mp4`。

### Remotion 预览

```bash
cd remotion-video
npm run dev      # 启动 Remotion Studio 交互式预览
npm run build    # TypeScript 类型检查
```

### 查看进度

```bash
v2g status <video_id>
```

## 项目结构

```
video2gen/
├── src/v2g/                    # Python 后端
│   ├── cli.py                  # CLI 入口，所有子命令定义
│   ├── agent.py                # Agent 多源编排（Anthropic + OpenAI 双 loop）
│   ├── fetcher.py              # 网页/公众号文章抓取（trafilatura）
│   ├── pipeline.py             # 流水线编排（单视频 + 多源）
│   ├── scriptwriter.py         # LLM 脚本生成 + JSON 修复
│   ├── tts.py                  # 双引擎 TTS（edge-tts / MiniMax）
│   ├── slides.py               # 幻灯片生成（Playwright / Pillow）
│   ├── editor.py               # FFmpeg 视频合成
│   ├── recorder.py             # 截图转录屏视频
│   ├── llm.py                  # 多模型路由（Claude / GPT / Gemini / GLM / MiniMax）
│   ├── config.py               # 配置加载 + 平台代理
│   ├── checkpoint.py           # 断点续传状态管理
│   ├── selector.py             # 热榜视频选择
│   ├── preparer.py             # 视频下载 + 字幕生成
│   └── prompts/                # LLM 提示词模板
│       ├── script_system.md
│       ├── script_multi_system.md
│       ├── slide_system.md
│       ├── agent_system.md     # Agent 角色和编排原则
│       ├── agent_outline.md    # 大纲生成要求
│       └── agent_script.md     # 脚本展开规则
├── remotion-video/             # TypeScript 前端
│   ├── src/
│   │   ├── VideoComposition.tsx # 主合成容器（通过 registry 动态分发）
│   │   ├── registry/           # 组件库（Schema × Style 两层模型）
│   │   │   ├── types.ts        # Schema 数据接口 + Style 元信息
│   │   │   ├── registry.ts     # 组件注册表
│   │   │   ├── init.ts         # 自注册入口
│   │   │   └── styles/         # 视觉组件实现
│   │   │       ├── slide/      # PPT 卡片风格
│   │   │       ├── terminal/   # 终端模拟风格
│   │   │       ├── recording/  # 录屏播放风格
│   │   │       └── source-clip/# 原视频片段风格
│   │   ├── components/         # 旧组件（保留兼容）
│   │   └── types.ts            # 类型定义
│   └── render.mjs              # Python→Remotion 渲染桥接
├── output/                     # 运行产出（gitignore）
├── pyproject.toml
└── .env.example
```

## 组件库系统

视频渲染采用 **Schema × Style 两层模型**，将数据契约（稳定）与视觉实现（频繁迭代）解耦：

- **Schema** — 定义数据结构：slide（PPT）、terminal（终端）、recording（录屏）、source-clip（原片）
- **Style** — 实现视觉效果：每个 schema 可以有多种风格，通过 `component` 字段在 script.json 中指定

当前可用组件：

| 组件 ID | 说明 | Schema |
|---------|------|--------|
| `slide.tech-dark` | 深色 PPT 卡片，6 种自动布局 | slide |
| `terminal.aurora` | Claude Code TUI 模拟，极光背景 | terminal |
| `recording.default` | 录屏视频播放 | recording |
| `source-clip.default` | 原视频片段裁剪 | source-clip |

新增组件只需：写一个 style 文件 + `init.ts` 加一行 import，框架代码无需改动。

## 三种素材类型

脚本中每个段落指定一种素材类型（向后兼容），也可通过 `component` 字段直接指定视觉组件：

| 类型 | 说明 | 默认组件 | 占比 |
|------|------|---------|------|
| **A (PPT 幻灯片)** | AI 生成的图文幻灯片，支持 6 种布局 | `slide.tech-dark` | ~30% |
| **B (录屏)** | 用户提供的屏幕录制，缺失时自动降级为动画模拟 | `recording.default` / `terminal.aurora` | ~50% |
| **C (原片剪辑)** | 原视频片段，限 10 秒内，自动调速匹配配音时长 | `source-clip.default` | ~20% |

## 渲染后端对比

| 特性 | FFmpeg (`v2g assemble`) | Remotion (`v2g multi`) |
|------|------------------------|----------------------|
| 输出文件 | `final.mp4` | `final_remotion.mp4` |
| 速度 | 快 | 较慢 |
| 动画效果 | 基础 | 丰富（React 组件） |
| 字幕烧录 | ASS 格式 | 组件级渲染 |
| 适用场景 | 单视频快速合成 | 多源精品合成 |

## 许可证

MIT
