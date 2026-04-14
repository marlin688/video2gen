# video2gen (v2g)

AI 驱动的 YouTube 二创视频自动生成流水线。覆盖从**选题发现 → 脚本生成 → 配音 → 视觉渲染 → 内容分发**的全链路。

## 功能特性

- **智能选片** — 从 YouTube 热榜 CSV 中交互式筛选素材
- **AI 脚本生成** — 支持 Claude / GPT / Gemini / GLM / MiniMax 多模型，自动分配三种素材类型（A-幻灯片 / B-录屏 / C-原片）
- **Agent 智能编排** — 从 markdown、公众号文章、字幕等异构素材自动编排视频脚本（两阶段：大纲→分段脚本，含截断自动恢复）
- **TTS 配音** — VoxCPM（本地高质量）/ edge-tts / MiniMax，按段落生成独立音频 + 可选 mlx-whisper 词级字幕对齐
- **9 种视觉组件** — Schema × Style 两层模型：slide（3 风格）、terminal（2 风格）、code-block、social-card、diagram、hero-stat、browser
- **双渲染后端** — FFmpeg 快速合成 或 Remotion 声明式渲染（带动画组件）
- **多源合成** — 将多个 YouTube 视频融合为一个二创作品
- **断点续传** — checkpoint 机制 + 流水线预检（启动前秒级检测依赖）
- **质量门控** — Pydantic 结构验证 + 规则评估（critical/warning/info 三级），critical 失败自动重试
- **成本追踪** — 全流程 token 用量统计 + 可配置硬性上限（`V2G_MAX_TOKENS`）+ 降级事件记录
- **Scout 自动化** — GitHub 趋势 + Hacker News 热帖 + Twitter + 文章监控，自动发现选题并输出到 Obsidian 知识库
- **内容分发** — 内容瀑布（视频→博客+Twitter+LinkedIn）+ 短视频再利用（30/60/90 秒脚本）

## 快速开始

### 环境要求

- Python >= 3.11
- Node.js >= 18
- yt-dlp（视频/字幕下载）
- FFmpeg（视频合并 + Remotion 渲染，强烈推荐）

### 安装

```bash
# 1. 创建虚拟环境（首次）
python3 -m venv .venv

# 2. 激活虚拟环境
source .venv/bin/activate

# 3. 安装项目 + 依赖
pip install -e .
pip install yt-dlp
# VoxCPM TTS（默认引擎）
pip install -e ".[tts_voxcpm]"

# 4. 安装 Remotion 前端依赖
cd remotion-video && npm install && cd ..

# 5. 安装 FFmpeg（macOS，如未安装）
brew install ffmpeg
```

### 配置

```bash
# 1. 复制环境变量模板
cp .env.example .env

# 2. 编辑 .env，填入 API Key
#    至少需要一个 LLM 的 Key（ANTHROPIC_API_KEY / GPT_API_KEY / ZHIPU_API_KEY）

# 3. 每次使用前，加载环境变量
source .env

# 4. 查看所有配置项及当前值
v2g config
```

> **注意**：每次打开新终端都需要执行 `source .venv/bin/activate && source .env`。可以写个 alias 简化：
> ```bash
> alias v2g-env='source /path/to/video2gen/.venv/bin/activate && source /path/to/video2gen/.env'
> ```

关键配置项（`.env`）：

| 变量 | 说明 | 必需 |
|------|------|------|
| `ANTHROPIC_API_KEY` | Claude API 密钥 | 至少一个 LLM Key |
| `GPT_API_KEY` / `GPT_BASE_URL` | OpenAI 兼容接口 | 可选 |
| `ZHIPU_API_KEY` | 智谱 GLM API | 可选 |
| `TTS_ENGINE` | TTS 引擎 (`voxcpm` / `edge` / `minimax` / `sovits`) | 默认 `voxcpm`（本地高质量） |
| `TTS_VOXCPM_MODEL` | VoxCPM 模型 ID | 默认 `openbmb/VoxCPM2` |
| `TTS_MINMAX_KEY` | MiniMax API 密钥 | `minimax` 引擎时必需 |
| `SCRIPT_MODEL` | 脚本生成模型 | 默认 `claude-sonnet-4-5-20250929` |
| `V2G_THEME` | Remotion 渲染主题 | 默认 `tech-blue` |
| `OBSIDIAN_VAULT_PATH` | Obsidian vault 路径 | 可选，默认 `output/` |
| `YOUTUBE_API_KEY` | YouTube Data API v3 | 可选，ideation 竞品分析用 |
| `TWITTER_API_IO_KEY` | TwitterAPI.io 密钥 | 可选，Twitter 监控用 |

## 使用方式

### 从零到成品视频（推荐流程）

三条命令完成选题到脚本，再三条命令生成视频：

```bash
# 激活环境
source .venv/bin/activate && source .env

# ---- 阶段 1: 选题 ----
v2g scout all                    # 跑 GitHub+HN+Twitter+文章+日报+创意构思

# ---- 阶段 2: 规划 ----
v2g scout plan -i 1              # 选第 1 个话题 → 钩子 + 标题 + 大纲

# ---- 阶段 3: 生产 ----
v2g scout produce -i 1           # 下载竞品视频 + agent 生成 script.json
#    → 自动执行 TTS + slides + 质量门控

# ---- 阶段 4: 渲染 ----
v2g tts <project_id>             # TTS 配音（如果 produce 没自动完成）
v2g slides <project_id>          # 生成幻灯片
v2g preview <project_id>         # 静帧预览（快速检查视觉效果）
# 在 remotion-video/ 目录下渲染最终视频：
cd remotion-video
node render.mjs <project_id> --output-dir ../output
```

最终产出在 `output/<project_id>/final/`：
- `video.mp4` — 成品视频
- `subtitles.srt` — SRT 字幕

### 单视频流水线

针对单个 YouTube 视频的全流程：

```bash
v2g run <video_id_or_url>            # 全自动（含人工审核环节）
v2g run <video_id_or_url> --auto     # 全自动跳过审核
```

分步执行：

```bash
v2g prepare <video_id>            # 1. 下载视频 + 英文字幕（yt-dlp）
v2g script <video_id>             # 2. AI 生成脚本
v2g review <video_id>             # 3. 人工审核脚本
v2g tts <video_id>                # 4. 文本转语音
v2g slides <video_id>             # 5. 生成幻灯片
v2g preview <video_id>            # 6. 静帧预览（可选，推荐）
v2g assemble <video_id>           # 7. FFmpeg 合成 → final/video.mp4
```

### Agent 智能编排

从 markdown、公众号文章 URL、视频字幕等多种素材自动编排脚本：

```bash
v2g agent my-video \
  -s article.md \
  -s "https://mp.weixin.qq.com/s/xxx" \
  -s sources/VIDEO_ID/subtitle_en.srt \
  -t "AI编程工具横评" \
  --duration 300

# 支持指定模型 (默认 Claude，可选 glm-5 / minimax-m2.7 等)
v2g agent my-video -s notes.md -t "主题" --model glm-5
```

### 多源合成

将多个视频融合为一个作品：

```bash
v2g multi "url1;url2;url3" --topic "主题" --project-id my-project
```

### Scout 内容自动化

```bash
# ---- 检索（发现话题）----
v2g scout all                        # 一键运行全部：GitHub+HN+Twitter+digest+ideation
v2g scout github [--since 7]         # GitHub AI 趋势 (免费)
v2g scout hn [--hours 24]            # Hacker News AI 热帖 (免费)
v2g scout twitter [--temperature 0.5]# Twitter/X 监控 (需要 TWITTER_API_IO_KEY)
v2g scout article --urls "url1;url2" # 文章/公众号抓取 + LLM 摘要
v2g scout ideation "话题"            # 竞品分析 + 5-9 个内容创意
v2g scout ideation --from-daily      # 从每日汇总自动提取话题

# ---- 规划（选题+脚本规划）----
v2g scout plan [-i N]                # 一键规划：选话题 → NotebookLM(可选) → hook+title+outline
v2g scout plan --skip-notebooklm     # 跳过 NotebookLM
v2g scout script "话题" -a "角度"    # 一键三连：钩子 + 标题 + 大纲

# ---- 生产（自动生成 script.json）----
v2g scout produce [-i N] [--model M] # 一键生产：选视频→下载→agent→script.json
v2g scout produce --skip-download    # 跳过视频下载

# ---- 内容分发（一鱼多吃）----
v2g scout waterfall "话题" -v VIDEO_ID   # 内容瀑布: → 博客 + Twitter 帖串 + LinkedIn
v2g scout shorts "话题" -v VIDEO_ID      # 短视频再利用: → 30/60/90 秒脚本
```

配合 cron 实现全自动：

```cron
0 8 * * * cd /path/to/video2gen && source .venv/bin/activate && source .env && v2g scout all --quiet >> logs/scout.log 2>&1
```

### 工具命令

```bash
v2g status <video_id>           # 查看流水线进度
v2g eval <video_id>             # 脚本质量评估（规则化，不消耗 LLM）
v2g preview <video_id>          # 渲染各段关键帧预览（比完整渲染快 10x+）
v2g intake "<source>"           # 统一入口识别（A/B/C/D/E）并生成 intake.json
v2g config                      # 列出所有配置项及当前值
```

每个项目目录会自动维护三个 workflow 契约文件：
- `workflow.md`：输入/输出约定与阶段说明
- `artifacts_manifest.json`：产物索引与存在性
- `run_log.jsonl`：阶段执行日志（append-only）

## 项目结构

```
video2gen/
├── .env.example                # 环境变量模板
├── .venv/                      # Python 虚拟环境
├── src/v2g/                    # Python 后端
│   ├── cli.py                  # CLI 入口 (20+ 子命令)
│   ├── pipeline.py             # 流水线编排 + 预检 + 质量门控
│   ├── agent.py                # Agent 多源编排（大纲→分段脚本）
│   ├── preparer.py             # yt-dlp 视频下载 + 字幕下载
│   ├── llm.py                  # 多模型路由（Claude/GPT/Gemini/GLM/MiniMax）
│   ├── tts.py                  # 多引擎 TTS（VoxCPM / edge-tts / MiniMax / GPT-SoVITS）
│   ├── schema.py               # Pydantic v2 结构验证（镜像 types.ts）
│   ├── eval.py                 # 规则化质量评估
│   ├── scout/                  # Scout 自动化 (14 模块)
│   └── prompts/                # LLM 提示词模板 (17 个 .md)
├── remotion-video/             # TypeScript 前端 (Remotion 4.x + React 19)
│   ├── src/registry/           # 组件库（12 个视觉组件）
│   ├── render.mjs              # 最终视频渲染
│   └── preview.mjs             # 静帧预览
├── sources/                    # 下载的视频 + 字幕
├── output/                     # 项目工作目录 + 最终产出
└── tests/                      # 测试 (eval + schema)
```

## 组件库系统

视频渲染采用 **Schema × Style 两层模型**，将数据契约（稳定）与视觉实现（频繁迭代）解耦：

| 组件 ID | 说明 | Schema |
|---------|------|--------|
| `slide.tech-dark` | 深色 PPT 卡片，6 种自动布局（默认） | slide |
| `slide.glass-morphism` | 毛玻璃渐变风格 | slide |
| `slide.chalk-board` | 黑板手绘风格 | slide |
| `terminal.aurora` | Claude Code TUI 模拟，极光背景（默认） | terminal |
| `terminal.vscode` | VS Code 编辑器模拟 | terminal |
| `code-block.default` | 语法高亮 + 行号 + 注解 | code-block |
| `social-card.default` | Twitter/GitHub/HN 卡片 | social-card |
| `diagram.default` | 流程/架构图（节点+边） | diagram |
| `hero-stat.default` | 大数字 + countUp 动画 | hero-stat |
| `browser.default` | Chrome 浏览器框模拟 | browser |
| `recording.default` | 录屏视频播放 | recording |
| `source-clip.default` | 原视频片段裁剪 | source-clip |

新增组件只需：写一个 style 文件 + `init.ts` 加一行 import。

## 容错与降级

| 环节 | 正常路径 | 降级路径 |
|------|----------|----------|
| 视频下载 | yt-dlp + FFmpeg 合并最佳画质 | 无 FFmpeg → 下载已合并单流（画质较低） |
| 词级对齐 | mlx-whisper → `word_timing.json` | 不可用时按字符数均分时长 |
| B 素材渲染 | 检测到录屏 → `recording.default` | 无录屏 → `terminal.aurora` 动画 |
| Agent 脚本 | 骨架 + 3 段批量填充 | 失败 → 单次生成 + 截断自动续写 |
| 组件解析 | `segment.component` 显式指定 | 未指定 → 按 material 走默认映射 |

## 已知限制

- **仅支持中文旁白**：`narration_zh` 是唯一旁白字段，TTS 语音和 prompt 模板均针对中文
- **Remotion 许可**：Remotion 框架个人/小团队免费，SaaS 需付费许可（[详情](https://remotion.dev/license)）
- **质量评估盲区**：`eval.py` 只检查结构规则（段数/字数/素材比例），不评估叙事质量
- **跨语言契约**：`schema.py`（Python）和 `types.ts`（TypeScript）手动同步

## 许可证

MIT
