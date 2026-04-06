# v2g 操作手册

从零到成品视频的完整操作流程。

## 一、环境准备

### 1. 系统依赖

```bash
brew install ffmpeg yt-dlp    # macOS
node --version                # 需要 >= 18
```

### 2. Python 环境

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
pip install -e ".[scout]"          # RSS 监控（feedparser）
pip install -e ".[subtitle]"       # 词级字幕对齐（mlx-whisper，Apple Silicon）
```

### 3. Remotion 前端

```bash
cd remotion-video && npm install && cd ..
```

### 4. 配置 .env

```bash
cp .env.example .env
```

必填（至少一个 LLM Key）：

| 变量 | 说明 | 获取 |
|------|------|------|
| `ANTHROPIC_API_KEY` | Claude API（主力模型） | https://console.anthropic.com |
| `GPT_API_KEY` + `GPT_BASE_URL` | OpenAI 兼容接口（GPT/DeepSeek/Qwen） | 可选替代 |
| `ZHIPU_API_KEY` | 智谱 GLM | 可选替代 |

按需填：

| 变量 | 说明 |
|------|------|
| `TTS_ENGINE` | `edge`（免费，默认）或 `minimax`（高质量） |
| `TTS_MINMAX_KEY` | MiniMax TTS 密钥（minimax 引擎时必填） |
| `OBSIDIAN_VAULT_PATH` | Obsidian vault 路径（scout 输出位置，默认 `output/`） |
| `TWITTER_API_IO_KEY` | Twitter 监控 |
| `YOUTUBE_API_KEY` | YouTube Data API v3（ideation 竞品分析） |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | Telegram 推送 |
| `GEMINI_API_KEY` | Google Gemini |
| `SCRIPT_MODEL` | 脚本生成模型（默认 `claude-sonnet-4-5-20250929`） |
| `V2G_MAX_TOKENS` | token 硬性上限（默认无限制） |

### 5. 验证

```bash
source .venv/bin/activate && source .env
v2g config    # 无报错即可
```

> 建议加 alias：`alias v2g-env='source /path/to/.venv/bin/activate && source /path/to/.env'`

---

## 二、工作流 A：Scout 自动化（原创内容，推荐）

完整链路：**发现选题 → 规划 → 生产 → 渲染 → 入库**

### Step 1: 发现选题

```bash
v2g scout all
```

一键运行：GitHub 趋势 + HN 热帖 + Twitter 精选 + 文章监控 → 每日摘要 → 自动 ideation。

产出位置：`{vault}/scout/{github,hn,twitter,articles,daily,ideation}/`

也可单独运行：

```bash
v2g scout github [--since 7]          # GitHub AI 趋势（免费，无需 Key）
v2g scout hn [--hours 24]             # HN 热帖（免费）
v2g scout twitter [--temperature 0.5] # Twitter 精选（需 TWITTER_API_IO_KEY）
v2g scout article --urls "url1;url2"  # 文章抓取 + LLM 摘要
v2g scout ideation "话题"             # 竞品分析 + 内容创意
v2g scout ideation --from-daily       # 从每日摘要自动提取话题
```

### Step 2: 规划

```bash
v2g scout plan [-i N]
```

选话题 → 可选 NotebookLM 深度分析 → 生成 hook（5 种开头）+ title（分层标题）+ outline（大纲）。

跳过 NotebookLM：`v2g scout plan --skip-notebooklm`

也可单独运行：

```bash
v2g scout script "话题" -a "角度"     # 一键三连：hook + title + outline
v2g scout hook "话题"                 # 只生成 5 种 hook
v2g scout title "话题" [--history t.json]  # 标题生成（支持历史基准）
v2g scout outline "话题" [-d 600]     # 只生成大纲
```

### Step 3: 生产

```bash
v2g scout produce [-i N] [--model M]
```

自动：选竞品视频下载 → 截图 Twitter 推文 → 组装素材 → agent 生成 script.json。

- `--skip-download` 跳过视频下载（用已有 sources/）
- 推文截图自动注入 agent（需当天有 `scout twitter` 数据）
- agent 自动确认大纲（质量 >= 85 分）

### Step 4: TTS + 幻灯片

如果 produce 没自动完成（或需要重跑）：

```bash
v2g tts {project_id} [--voice zh-CN-YunxiNeural] [--rate "+5%"]
v2g slides {project_id} [--model M]
```

### Step 5: 预览（推荐）

```bash
v2g preview {project_id}
```

渲染每段关键帧到 `output/{project_id}/preview/seg_*.png`，比完整渲染快 10x+。确认视觉效果无误再全量渲染。

### Step 6: 渲染

```bash
cd remotion-video
node render.mjs {project_id}
```

产出：`output/{project_id}/final/video.mp4` + `subtitles.srt`

### Step 7: 素材入库（渲染后）

```bash
v2g assets ingest {project_id}
```

自动切片 + 打标签（visual_type, product, mood, freshness）→ 写入 `output/assets.db`。

### Step 8: 留存反馈（发布后，B站数据回来时）

```bash
v2g assets annotate {project_id} --retention retention.csv
```

映射 B站留存曲线到每个段落，更新 engagement_score（-1/0/+1）。

---

## 三、工作流 B：单视频二创（快速）

### 全自动

```bash
v2g run "https://youtube.com/watch?v=xxx" --auto
```

### 分步执行

```bash
v2g prepare {video_id}        # 1. 下载视频 + 英文字幕
v2g script {video_id}         # 2. AI 生成脚本 → script.json
v2g eval {video_id}           # 3. 质量检查（规则化，无 LLM 成本）
v2g review {video_id}         # 4. 人工审核（编辑 script.json）
v2g tts {video_id}            # 5. 配音
v2g slides {video_id}         # 6. 幻灯片
v2g preview {video_id}        # 7. 预览关键帧
v2g assemble {video_id}       # 8. FFmpeg 合成 → final/video.mp4
```

---

## 四、工作流 C：Agent 多源编排

从 markdown、文章 URL、字幕等混合素材生成视频：

```bash
v2g agent my-video \
  -s article.md \
  -s "https://mp.weixin.qq.com/s/xxx" \
  -s sources/VIDEO_ID/subtitle_en.srt \
  -t "AI编程工具横评" \
  --duration 300 \
  --model claude-sonnet-4-5-20250929
```

Agent 工具：`fetch_url`（文章抓取）、`read_source_file`（本地文件）、`search_github`、`search_hn`、`save_outline`、`save_script`。

两阶段生成：大纲 → 分段脚本（3 段/批，含截断自动恢复）。

渲染：

```bash
cd remotion-video && node render.mjs my-video
```

---

## 五、工作流 D：多源合成

将多个 YouTube 视频融合：

```bash
v2g multi "url1;url2;url3" --topic "主题" [--project-id my-project]
```

---

## 六、内容分发（一鱼多吃）

```bash
# 内容瀑布：视频 → 博客 + Twitter 帖串 + LinkedIn
v2g scout waterfall "话题" --video-id {id}
v2g scout waterfall "话题" --url {article_url}
v2g scout waterfall "话题" --file {path}

# 短视频再利用：长视频 → 30/60/90 秒独立脚本
v2g scout shorts "话题" --video-id {id}
```

---

## 七、素材库管理

### 生命周期

```
渲染完成 → v2g assets ingest    → SQLite 入库（自动打标签）
B站数据 → v2g assets annotate   → 留存评分 engagement_score
定期    → v2g assets refresh    → 标记过期素材（product_ui 3月, terminal 6月）
```

### 命令

```bash
v2g assets ingest {project_id}                     # 入库
v2g assets annotate {project_id} --retention r.csv  # 留存反馈
v2g assets refresh                                  # 过期扫描（月度）
v2g assets stats                                    # 库存统计
v2g assets context [--limit 30]                     # 输出 LLM-ready 素材列表
```

### 标签体系

| 维度 | 可选值 |
|------|--------|
| `visual_type` | screen_recording, product_ui, terminal, browser, code_editor, diagram, chart, text_slide, person, screenshot, image_overlay, web_video |
| `product` | claude, claude-code, cursor, github, vscode, chatgpt, openai, anthropic, google, deepseek, gemini, other |
| `mood` | hook, problem, explain, demo, reveal, compare, celebrate, warning, summary, cta |
| `freshness` | current, possibly_outdated, evergreen |

### 当前状态

素材库目前是**只写不读**——`build_asset_context()` 已实现但未接入脚本生成。等积累几十条素材后再接入 agent prompt。

---

## 八、日常自动化

### Cron 配置

```cron
# 每天早 8 点跑 scout 全量
0 8 * * * cd /path/to/video2gen && source .venv/bin/activate && source .env && v2g scout all --quiet >> logs/scout.log 2>&1
```

### 推荐日常节奏

| 时间 | 操作 | 命令 |
|------|------|------|
| 早上 | 发现选题 | `v2g scout all`（可 cron） |
| 上午 | 选题规划 | `v2g scout plan -i N` |
| 下午 | 生产脚本 | `v2g scout produce -i N` |
| 傍晚 | 预览 + 渲染 | `v2g preview` → `node render.mjs` |
| 发布后 | 入库 + 反馈 | `v2g assets ingest` → `v2g assets annotate` |

---

## 九、关键文件位置

| 产出 | 路径 |
|------|------|
| 下载的视频/字幕 | `sources/{video_id}/` |
| 脚本（源真相） | `output/{project}/script.json` |
| 脚本（可读版） | `output/{project}/script.md` |
| 录屏指南 | `output/{project}/recording_guide.md` |
| 配音 | `output/{project}/voiceover/` |
| 幻灯片 | `output/{project}/slides/` |
| 推文截图 | `output/{project}/images/tweet_*.png` |
| 预览帧 | `output/{project}/preview/seg_*.png` |
| 最终视频 | `output/{project}/final/video.mp4` |
| 字幕 | `output/{project}/final/subtitles.srt` |
| 素材库 | `output/assets.db` |
| Scout 报告 | `{vault}/scout/{source}/{date}-*.md` |
| Twitter JSON | `{vault}/scout/twitter/{date}-curated.json` |
| 流水线状态 | `output/{project}/checkpoint.json` |

---

## 十、常见问题

### ffmpeg/yt-dlp 未找到

```bash
brew install ffmpeg yt-dlp    # macOS
# 或
pip install yt-dlp            # Python 包
```

### Remotion node_modules 缺失

```bash
cd remotion-video && npm install
```

### 脚本质量门控不通过

```bash
v2g eval {video_id}                    # 查看具体问题
nano output/{video_id}/script.json     # 手动修复 critical 问题
```

### Playwright 未安装（推文截图跳过）

```bash
pip install playwright
playwright install chromium
```

不安装也不影响管线——推文截图会跳过，agent 改用 social-card 组件渲染。

### Token 超限

```bash
# .env 中调大限制
V2G_MAX_TOKENS=1000000
```

### 每次开终端都要 source

```bash
# 加到 ~/.zshrc
alias v2g-env='source /path/to/video2gen/.venv/bin/activate && source /path/to/video2gen/.env'
```
