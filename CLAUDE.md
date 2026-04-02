# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

video2gen (v2g) is an automated pipeline for creating derivative (二创) video content from YouTube source videos using AI. It combines a Python backend (pipeline orchestration, LLM scripting, TTS) with a TypeScript/React frontend (Remotion video rendering).

## Directory Structure

```
sources/{video_id}/              ← 输入素材 (下载的视频 + 字幕)
    video.mp4, subtitle_en.srt, subtitle_zh.srt

output/{project_id}/             ← 项目工作目录
    checkpoint.json              ← 流水线状态
    script.json, script.md       ← 脚本 (顶层方便引用)
    recording_guide.md
    voiceover/                   ← TTS 配音
        full.mp3                 ← 合并后完整音轨
        timing.json              ← 时间轴
        segments/seg_*.mp3       ← 分段音频
    slides/slide_*.png           ← 幻灯片图片
    recordings/seg_*.mp4         ← 录屏素材
    clips/seg_*.mp4              ← FFmpeg 中间产物
    screenshots/                 ← recorder 中间产物
    final/                       ← 最终交付物
        video.mp4                ← 最终视频
        subtitles.srt            ← SRT 字幕
```

## Commands

### Python

```bash
pip install -e .                          # Install in dev mode
v2g run <video_id_or_url>                 # Full single-video pipeline (FFmpeg backend)
v2g select --csv trending.csv             # Stage 1: interactive video selection
v2g prepare <video_id_or_url>             # Stage 2: download → sources/{video_id}/
v2g script <video_id>                     # Stage 3: AI script generation
v2g review <video_id>                     # Human review checkpoint
v2g tts <video_id> [--voice] [--rate]     # Stage 4: TTS → voiceover/
v2g slides <video_id> [--model]           # Stage 5a: slide image generation
v2g record <video_id>                     # Screenshots → video (material B fallback)
v2g assemble <video_id>                   # Stage 5b: FFmpeg → final/video.mp4
v2g multi "url1;url2" --topic "topic" [--project-id]  # Multi-source pipeline (Remotion backend)
v2g agent <project_id> -s <source> -t <topic> [--model] [--duration]  # Agent multi-source script orchestration
v2g status <video_id>                     # Check pipeline progress
v2g knowledge all                         # Run all knowledge sources + daily digest
v2g knowledge github [--since 7]          # GitHub AI trending repos
v2g knowledge hn [--hours 24]             # Hacker News AI hot posts
v2g knowledge article [--urls "url1;url2"]# Article monitor (RSS / manual URL / inbox)
v2g knowledge ideation "topic"            # Competitive analysis + content ideation (optional YOUTUBE_API_KEY)
v2g knowledge ideation --from-daily       # Auto-extract topics from daily digest
v2g knowledge twitter [--temperature 0.5] # Twitter/X monitor (requires APIFY_TOKEN)
v2g knowledge title "topic" --history t.json  # Title generation with historical performance benchmarking
v2g knowledge waterfall "topic" --video-id ID # Content waterfall: video → blog + Twitter thread + LinkedIn
v2g knowledge waterfall "topic" --url URL     # Content waterfall from article URL
v2g knowledge waterfall "topic" --file path   # Content waterfall from local file
v2g knowledge shorts "topic" --video-id ID    # Short-form repurpose: long → 30/60/90s scripts
```

### Remotion (from `remotion-video/`)

```bash
npm run dev                   # Remotion studio (interactive preview)
npm run build                 # TypeScript type-check only (tsc --noEmit)
npm run render                # Dev render with empty props (not production)
node render.mjs <project_id>  # Production render → final/video.mp4 + final/subtitles.srt
```

Production rendering is done via `render.mjs`, not `npm run render`. It auto-cleans `public/` cache after rendering.

## Architecture

### Dual Rendering Backends

The pipeline has **two independent video rendering paths** that diverge at Stage 5b:

```
Single-video (v2g run):
  prepare → script → [review] → tts → slides → record → assemble (FFmpeg) → final/video.mp4

Multi-source (v2g multi):
  multi-prepare → multi-script → [review] → tts → slides → Remotion (render.mjs) → final/video.mp4

Agent orchestration (v2g agent):
  fetch/read sources → outline → [human confirm] → script.json → tts → slides → render
```

- **FFmpeg path** (`editor.py`): direct video composition with ASS subtitle burn-in. Output: `output/{video_id}/final/video.mp4`
- **Remotion path** (`render.mjs`): declarative React rendering with animated components. Output: `output/{video_id}/final/video.mp4` + `final/subtitles.srt`

### Python-to-Remotion Bridge

`render.mjs` is the bridge between Python output and Remotion rendering:
1. Reads `script.json` and `voiceover/timing.json` from `output/{video_id}/`
2. Parses `checkpoint.json` to detect single vs multi-source mode
3. Finds source videos in `sources/{video_id}/` (fallback: `output/subtitle/`)
4. Auto-transcodes source videos (AV1/VP9 → H.264) if needed
5. Copies assets into `remotion-video/public/` (auto-cleaned after render)
6. Generates `final/subtitles.srt` and renders `final/video.mp4`

Composition ID is hardcoded as `V2GVideo` in `Root.tsx`. Resolution is 1920x1080 @ 30fps.

### Component Registry (Schema × Style)

Visual rendering uses a two-layer model separating data contracts (Schema) from visual implementations (Style):

- **Schemas** (stable): `slide`, `terminal`, `recording`, `source-clip` — define data interfaces in `registry/types.ts`
- **Styles** (iterable): visual implementations in `registry/styles/{schema}/{name}.tsx` — self-register via `registry.register()` at import time
- **Registry** (`registry/registry.ts`): `ComponentRegistry` class with `resolve()`, `resolveForSegment()`, `toLLMPromptTable()`
- **Init** (`registry/init.ts`): imports all style files to trigger registration

Style ID format: `"{schema}.{style-name}"`, e.g. `"slide.tech-dark"`.

`VideoComposition.tsx` resolves components via `registry.resolveForSegment(seg, hasRecording)`:
1. If `segment.component` is set → look up that style ID
2. Else fallback by `segment.material`: A→slide default, B→recording/terminal default, C→source-clip default

To add a new visual style: create `registry/styles/{schema}/{name}.tsx` with `registry.register()` call at bottom + add import to `init.ts`.

### Three Material Types

Each script segment specifies one of three material types, and optionally a `component` field (style ID like `"slide.tech-dark"`) for explicit visual component selection:
- **A (PPT slides)** — AI-generated slide images. Layout detection happens in TypeScript (`registry/styles/slide/tech-dark.tsx` `detectLayout()`), not Python. 6 layout modes: code, compare, metric, grid, steps, standard.
- **B (Screen recording)** — User-provided screen captures, or screenshots auto-converted via `v2g record`. Missing recordings fall back to `terminal.aurora` style (animated Claude Code TUI simulation) in Remotion, or a placeholder card in FFmpeg.
- **C (Source clip)** — Trimmed + speed-adjusted clips from original video. Capped at 10 seconds, bottom 15% cropped to remove hardcoded subtitles.

Target ratio: A ≤30%, B ≥50%, C ~20%.

### Pipeline State

State persists in `output/{video_id}/checkpoint.json` (`PipelineState` dataclass in `checkpoint.py`). Stage flags (`selected`, `downloaded`, `scripted`, `tts_done`, `slides_done`, `assembled`, etc.) enable resuming at any stage. Multi-source mode adds `project_id`, `topic`, and `sources[]` (list of `SourceVideo` with per-source paths and `prepared` flag).

### Input/Output Separation

- **Input materials** (`sources/`): Downloaded source videos and subtitles, organized by video ID
- **Working files** (`output/{project}/`): Script, voiceover, slides, recordings — grouped by type
- **Final deliverables** (`output/{project}/final/`): Only `video.mp4` and `subtitles.srt`
- **Remotion staging** (`remotion-video/public/`): Temporary asset cache, auto-cleaned after render

### Key Data Files

- `script.json` — LLM-generated script with segments (id, type, material, component?, narration_zh, slide_content/recording_instruction/source timing). The optional `component` field specifies a style ID (e.g. `"slide.tech-dark"`); when absent, defaults by material type. Multi-source mode adds `sources_used`, `total_duration_hint`.
- `voiceover/timing.json` — `{segment_id: {file, duration, text_length}}` mapping from TTS output.
- `recording_guide.md` — Extracted material B instructions for the user.
- `final/subtitles.srt` — SRT subtitles (Remotion backend) or `final/subtitles.ass` (FFmpeg backend).

### Agent Orchestration (`agent.py`)

`v2g agent` implements a two-phase LLM-driven script generation pipeline:

1. **Phase 1 — Outline**: Agent loop with tool use (fetch URLs, read files, save outline). Supports both Anthropic and OpenAI-compatible backends.
2. **Human review**: User confirms/edits `outline.json`
3. **Phase 2 — Script**: Direct LLM call expands outline into `script.json` (uses `call_llm`, not agent loop, for stability with long outputs)

Agent tools: `fetch_url` (web article extraction via trafilatura), `read_source_file` (local .md/.srt/.txt), `save_outline`, `save_script`.

Article fetching (`fetcher.py`): Uses trafilatura with browser UA headers. WeChat articles require direct HTTP download (trafilatura's default downloader fails on WeChat's environment verification).

### LLM Router (`llm.py`)

Routes by model name prefix:
- `glm*` → 智谱官方 API (`ZHIPU_API_KEY`, base: `open.bigmodel.cn`)
- `minimax*` → MiniMax 官方 API (`TTS_MINMAX_KEY`, base: `api.minimax.chat`), fallback to GPT proxy on overload
- `gemini*` → Google Generative AI SDK
- `gpt*`, `o1*`, `o3*`, `o4*` → OpenAI SDK (optional Anthropic proxy fallback)
- `deepseek*`, `qwen*`, `abab*` → OpenAI-compatible via GPT proxy
- All others → Anthropic Claude SDK (streaming via httpx)

Platform proxy system (`config.py` `_apply_platform()`) maps platform-specific env vars (e.g. `ITSSX_API_KEY`) to standard `ANTHROPIC_*` variables.

**Proxy handling**: When `ANTHROPIC_BASE_URL` is a third-party gateway, local system proxy is skipped. 智谱/MiniMax API calls temporarily clear all proxy env vars.

### TTS Dual Engine (`tts.py`)

- **edge-tts** (default, free): Microsoft Edge TTS
- **MiniMax Speech** (paid, high quality): requires `TTS_MINMAX_KEY`
- Switch via `TTS_ENGINE` env var. Each segment rendered separately to `voiceover_segments/seg_{id}.mp3`.

### Knowledge Source Automation (`knowledge/`)

`v2g knowledge` implements automated topic discovery for AI Tech content creators. Three knowledge sources feed into an Obsidian vault:

1. **GitHub Trending** (`github_trending.py`): Uses GitHub REST API `/search/repositories` (no token needed, 60 req/hour). Per-topic queries merged and deduped. LLM analyzes repos for content creation opportunities.
2. **Hacker News** (`hn_monitor.py`): Uses HN Algolia API (free, no rate limit). Per-keyword queries merged and deduped. LLM identifies hot topics and discussion-worthy posts.
3. **Article Monitor** (`article_monitor.py`): Three input modes — RSS feeds (via feedparser), manual URLs (`--urls`), and Obsidian inbox (`{vault}/inbox/articles.md`). Reuses `fetcher.fetch_article()` for content extraction. LLM generates TL;DR + key points.
4. **Twitter/X** (`twitter_monitor.py`): Uses Apify `apidojo~tweet-scraper` Actor (async polling model). Rule-based pre-filter → LLM scoring (virality/authority/timeliness/opportunity) → softmax probabilistic selection. Currently limited by X's anti-scraping measures.

Shared infrastructure:
- **`store.py`**: Generic SQLite dedup store shared by all sources. Table `seen_items(source, item_id, data, fetched_at)`.
- **`obsidian.py`**: `ObsidianWriter` class writes YAML-frontmatter Markdown to `{vault}/knowledge/{source}/` dirs. Falls back to `output/knowledge/` when `OBSIDIAN_VAULT_PATH` is unset.
- **`telegram.py`**: Telegram Bot notifications via httpx POST (HTML parse_mode). Best-effort, failures logged but not raised.

`v2g knowledge all` runs GitHub + HN + articles sequentially, generates a daily digest, then auto-runs ideation on topics extracted from the digest.

5. **Ideation** (`ideation.py`): Takes a topic (user-specified or auto-extracted from daily digest), searches YouTube via Data API v3 for competitive landscape, then LLM generates 5-9 content ideas with Tier 1/Tier 2 ranking. Degrades gracefully without `YOUTUBE_API_KEY` (LLM-only ideation).

Each source is idempotent per date (overwrites same-date files). SQLite dedup ensures no repeated processing across runs. Designed for cron scheduling: `0 8 * * * v2g knowledge all --quiet`.

### Content Distribution (`knowledge/`)

Post-production distribution layer for repurposing finished content across platforms:

6. **Content Waterfall** (`waterfall.py`): Takes video subtitles/scripts/articles and generates three formats: SEO blog post (800-1200 words), Twitter thread (7 tweets), and LinkedIn posts (2 versions). Input sources: `--video-id` (reads from sources/ or output/), `--url` (fetches article), `--file` (local file). Output: `knowledge/distribution/{date}-waterfall-{slug}.md`.

7. **Short-form Repurpose** (`shorts.py`): Converts long-form content into three independent short video scripts (30s/60s/90s). Each version includes hook (oral + text overlay), core content points, and CTA. Not simple trimming — each version is re-conceived for its time constraint. Output: `knowledge/distribution/{date}-shorts-{slug}.md`.

Shared content loading (`_load_video_content()` in `__init__.py`): Resolves video content from multiple paths — `output/{id}/script.md` > `sources/{id}/subtitle_zh.srt` > `subtitle_en.srt`, or fetches from URL, or reads local file. Truncates to 8000 chars.

### Title Historical Benchmarking (`knowledge/title.py`)

The title generation skill supports historical performance data for data-driven title optimization:
- `--history titles.json`: Load explicit performance data (`[{title, views, likes}]`), LLM references patterns from high-performing titles
- Auto-scan: Without `--history`, automatically scans `knowledge/scripts/*-title-*.md` in the Obsidian vault for past generated titles as reference
- Prompt instructs LLM to identify successful patterns and explicitly cite which historical title inspired each suggestion

### Prompt Engineering

`src/v2g/prompts/` contains LLM prompt templates:
- `script_system.md` — single-source script generation rules
- `script_multi_system.md` — multi-source synthesis rules
- `slide_system.md` — slide content and layout generation
- `agent_system.md` — Agent role and orchestration principles
- `agent_outline.md` — outline generation requirements and JSON format
- `agent_script.md` — script expansion rules (reuses material type system from script_system.md)
- `knowledge_github.md` — GitHub repo analysis (trending, top 3, emerging directions)
- `knowledge_hn.md` — HN post analysis (trends, top 3, controversy detection)
- `knowledge_article.md` — article summarization (TL;DR, key points, content angle)
- `knowledge_daily.md` — daily digest generation (highlights, content suggestions, trends)
- `knowledge_ideation.md` — competitive analysis + content ideation (landscape, 5-9 ideas with tiers)
- `knowledge_hook.md` — 5-variant opening hook generation (oral/visual/text overlay)
- `knowledge_title.md` — tiered title generation with historical benchmarking support
- `knowledge_outline.md` — video outline (chapters, visual aids, references)
- `knowledge_waterfall.md` — content waterfall distribution (blog + Twitter thread + LinkedIn)
- `knowledge_shorts.md` — short-form repurpose (30/60/90s independent scripts)

### Remotion Components (`remotion-video/src/`)

- `VideoComposition.tsx` — main container, sequences segments via `<Series>`, dispatches to registered styles via `registry.resolveForSegment()`
- `registry/` — Schema × Style component library system:
  - `types.ts` — `SlideData`, `TerminalData`, `RecordingData`, `SourceClipData` schema interfaces + `StyleMeta`, `StyleComponentProps<S>` generics
  - `registry.ts` — `ComponentRegistry` class (register, resolve, resolveForSegment, toLLMPromptTable)
  - `init.ts` — import-triggers all style self-registration
  - `styles/slide/tech-dark.tsx` — PPT cards with 6 auto-detected layouts (default for material A)
  - `styles/terminal/aurora.tsx` — Claude Code TUI simulation with aurora background (default for material B fallback)
  - `styles/recording/default.tsx` — video playback (default for material B with recording file)
  - `styles/source-clip/default.tsx` — trimmed source clip with bottom mask (default for material C)
- `components/` — legacy components (SlideSegment.tsx etc. still present for reference, but rendering goes through registry styles)
- `types.ts` — `ScriptSegment` (includes optional `component?: string` field), `TimingMap`, `VideoCompositionProps` type definitions

### External Dependencies

- **lecture2note** — sibling project (`../lecture2note/`) for video download and subtitle generation
- **youtube-trending** — sibling project (`../youtube-trending/`) provides trending video CSV data

### Key Environment Variables

See `.env.example` for the full list. Notable variables:
- `ANTHROPIC_API_KEY` / `ANTHROPIC_BASE_URL` — Claude API (supports third-party gateways)
- `ZHIPU_API_KEY` — 智谱 GLM API (glm-5, glm-4.7 etc.)
- `TTS_MINMAX_KEY` — MiniMax API (shared by TTS and text models like minimax-m2.7)
- `GPT_API_KEY`, `GPT_BASE_URL` — OpenAI-compatible proxy (for GPT/DeepSeek/Qwen etc.)
- `GEMINI_API_KEY` — Google Gemini
- `TTS_ENGINE` — `edge` (default) or `minimax`
- `REMOTION_CHROME_EXECUTABLE` — override Chrome path for Remotion rendering
- `OBSIDIAN_VAULT_PATH` — Obsidian vault directory (fallback: `output/knowledge/`)
- `GITHUB_TOPICS` — comma-separated topics for GitHub trending (default: `ai,ml,llm,agent,rag`)
- `APIFY_TOKEN` — Apify API token (for Twitter monitoring)
- `TWITTER_KEYWORDS`, `TWITTER_AUTHORS` — Twitter monitoring targets
- `ARTICLE_RSS_URLS` — comma-separated RSS feed URLs
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — Telegram push notifications
- `YOUTUBE_API_KEY` — YouTube Data API v3 (optional, for ideation competitive analysis)
