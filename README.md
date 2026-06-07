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
- **Watchlist 发推 Agent** — 定期监控重点 X 账号，按主题聚类生成中文草稿，默认 dry-run，支持去重和安全发布门禁
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
#    至少需要一套可用 LLM 凭证（如 ANTHROPIC_API_KEY / GPT_API_KEY / ZHIPU_API_KEY / OPENAI_AUTH_FILE）

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
| `OPENAI_AUTH_FILE` | OpenAI OAuth 凭证文件（`auth.json`）；当 token 无 `api.*` scope 时自动走 ChatGPT Codex 路由 | 可选 |
| `OPENAI_CODEX_BASE_URL` | ChatGPT Codex 兼容网关地址（默认 `https://chatgpt.com/backend-api/codex`） | 可选 |
| `ZHIPU_API_KEY` | 智谱 GLM API | 可选 |
| `TTS_ENGINE` | TTS 引擎 (`voxcpm` / `edge` / `minimax` / `sovits`) | 默认 `voxcpm`（本地高质量） |
| `TTS_VOXCPM_MODEL` | VoxCPM 模型 ID | 默认 `openbmb/VoxCPM2` |
| `TTS_MINMAX_KEY` | MiniMax API 密钥 | `minimax` 引擎时必需 |
| `SCRIPT_MODEL` | 脚本生成模型 | 默认 `gpt-5.4` |
| `V2G_THEME` | Remotion 渲染主题 | 默认 `tech-blue` |
| `OBSIDIAN_VAULT_PATH` | Obsidian vault 路径 | 可选，默认 `output/` |
| `YOUTUBE_API_KEY` | YouTube Data API v3 | 可选，ideation 竞品分析用 |
| `TWITTER_API_IO_KEY` | TwitterAPI.io 密钥 | 可选，Twitter 监控用 |
| `WATCHLIST_CONFIG` | Watchlist 账号/策略配置文件路径 | 可选，默认 `config/watchlist.toml` |
| `X_CONSUMER_KEY` / `X_CONSUMER_SECRET` | X OAuth 1.0a App 凭证 | 真实发推时必需 |
| `X_ACCESS_TOKEN` / `X_ACCESS_TOKEN_SECRET` | X OAuth 1.0a 用户访问令牌 | 真实发推时必需 |

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
v2g scout watchlist                  # 重点账号监控 + 中文发推草稿 (默认 dry-run)
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
v2g scout chain "话题"                   # 产业链轮动型 X 推文草稿
v2g scout publish --dry-run              # 预览最新 waterfall 推文，不真实发布
v2g scout publish-chain --dry-run        # 预览最新产业链推文，不真实发布
```

#### Watchlist Monitor + Draft Agent

Watchlist 适合高频监控重点账号，生成“可发但先不发”的中文观点草稿。账号名单和内容策略维护在独立配置文件：

```text
config/watchlist.toml
```

运行依赖 `TWITTER_API_IO_KEY` 和可用的 `SCOUT_MODEL`。真实发推还需要 X OAuth 1.0a 的四个发布凭证。

默认已按三组账号组织：

- `daily`：每天必看，负责选题信号
- `trigger`：事件触发，负责催化剂
- `context`：叙事补充，负责长期框架

`config/watchlist.toml` 还包含 `[[few_shots]]` 风格样例。草稿太像摘要、太短或判断不够时，优先改这里的 bad/good examples，让模型模仿“信号 → 判断 → 影响/下一步”的写法。

常用命令：

```bash
# 默认 dry-run：抓取、去重、生成报告和草稿，不真实发推
v2g scout watchlist

# 调试时不写入去重记录，方便反复看同一批输入
v2g scout watchlist --no-mark-seen --max-tweets 30 --max-drafts 2

# 临时覆盖账号列表，不改配置文件
v2g scout watchlist --authors "sama,karpathy,SemiAnalysis_" --since-hours 1

# 真实发布需要显式 --publish；建议先长期 dry-run 调风格
v2g scout watchlist --publish --publish-count 1 --yes
```

输出文件：

```text
{OBSIDIAN_VAULT_PATH}/scout/watchlist/YYYY-MM-DD-HHMM-watchlist.md
{OBSIDIAN_VAULT_PATH}/scout/watchlist/YYYY-MM-DD-HHMM-watchlist.json
```

去重分三层：

- `watchlist_tweet`：同一条源推文只处理一次
- `watchlist_topic`：同一主题/观点短期内不重复生成
- `x_publish` / `x_publish_attempt`：真实发推前后记录内容 hash，防止重复发布或部分失败后重发首推

自动监控（macOS launchd）：

```bash
# 每小时生成 dry-run 草稿，不真实发布
v2g scout watchlist-cron-setup -i 1

# 每小时最多自动发布 1 条，通过发布门禁后才发
v2g scout watchlist-cron-setup -i 1 --publish --publish-count 1

# 卸载 watchlist 定时任务
v2g scout watchlist-cron-setup --uninstall
```

真实发推还需要 `.env` 中配置 X OAuth 1.0a 的四个值，并确保 App 权限是 Read and Write。

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

### 素材审核台（Web）

```bash
# 启动素材审核台（默认 http://127.0.0.1:8877）
v2g assets review-ui --open-browser
```

支持能力：
- 素材筛选：关键词 / `visual_type` / `rights_status` / 项目 / 时间区间 / 审核队列
- 批量操作：`approve` / `block` / `set tags` / `remove`
- 预览：图片 / 视频片段在线预览
- 结果回写：所有操作直接写入 `output/assets.db`

每个项目目录会自动维护三个 workflow 契约文件：
- `workflow.md`：输入/输出约定与阶段说明
- `artifacts_manifest.json`：产物索引与存在性
- `run_log.jsonl`：阶段执行日志（append-only）

### 公众号素材批量入库

```bash
# 从微信公众号文章 URL 批量抓图入库（默认目标 100 条）
v2g assets seed-wechat \
  --urls "https://mp.weixin.qq.com/s/xxx;https://mp.weixin.qq.com/s/yyy" \
  --seed-id seed-wechat-2026-04-14 \
  --allow-account 智东西 --allow-account 36氪 --allow-account 新智元 \
  --allow-account 机器之心 --allow-account 量子位

# 或者从文本文件读取 URL（每行一条）
v2g assets seed-wechat --urls-file wechat_urls.txt --limit 120 --per-article 10
```

说明：
- 自动做质量过滤（最小尺寸/文件大小）和去重（按图片 hash）。
- 入库后会生成清单：`output/asset_library/seeds/<seed_id>.json`。
- 默认版权状态为 `unknown`，建议在审核台批量 `approve/block/set tags` 后再进入商用渲染。

## 项目结构

```
video2gen/
├── .env.example                # 环境变量模板
├── config/watchlist.toml       # Watchlist 账号分组与内容策略
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
│   ├── scout/                  # Scout 自动化、Watchlist、内容分发与发布
│   └── prompts/                # LLM 提示词模板
├── remotion-video/             # TypeScript 前端 (Remotion 4.x + React 19)
│   ├── src/registry/           # 组件库（12 个视觉组件）
│   ├── render.mjs              # 最终视频渲染
│   └── preview.mjs             # 静帧预览
├── sources/                    # 下载的视频 + 字幕
├── output/                     # 项目工作目录 + 最终产出
└── tests/                      # 单元测试与 workflow 回归
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
