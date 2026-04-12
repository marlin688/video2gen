# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

video2gen (v2g) is an automated pipeline for creating original AI Tech video content. It combines a Python backend (pipeline orchestration, LLM scripting, TTS, asset management) with a TypeScript/React frontend (Remotion video rendering). The pipeline supports topic discovery, script generation, multi-schema visual rendering, and a growing asset library with retention-based feedback loops.

## Directory Structure

```
sources/{video_id}/              ← 输入素材 (下载的视频 + 字幕)
    video.mp4, subtitle_en.srt, subtitle_zh.srt

output/{project_id}/             ← 项目工作目录
    checkpoint.json              ← 流水线状态 (含 cost_summary, bvid, published_at)
    script.json, script.md       ← 脚本 (顶层方便引用)
    script_meta.json             ← 生成元数据 (模型、prompt hash、时间戳)
    recording_guide.md
    preview/seg_*.png            ← 静帧预览 (渲染前确认)
    voiceover/                   ← TTS 配音
        full.mp3                 ← 合并后完整音轨
        timing.json              ← 时间轴
        word_timing.json         ← 词级时间戳 (mlx-whisper, 可选)
        segments/seg_*.mp3       ← 分段音频
    slides/slide_*.png           ← 幻灯片图片
    images/                      ← 图片叠加素材 (image-overlay 组件用)
    web_videos/                  ← 下载的网络视频片段 (web-video 组件用)
    recordings/seg_*.mp4         ← 录屏素材
    asset_clips/seg_*.mp4        ← 素材库切片 (ingest 产物)
    clips/seg_*.mp4              ← FFmpeg 中间产物
    screenshots/                 ← recorder 中间产物
    final/                       ← 最终交付物
        video.mp4                ← 最终视频
        subtitles.srt            ← SRT 字幕

output/assets.db                 ← 素材库 SQLite 数据库
```

## Commands

### Python

```bash
pip install -e .                          # Install in dev mode
v2g run <video_id_or_url>                 # Full single-video pipeline (FFmpeg backend)
v2g run <video_id_or_url> --auto          # Full auto mode: skip review, B-material uses terminal animation
v2g eval <video_id>                       # Rule-based script quality check (Pydantic schema + business rules, no LLM cost)
v2g preview <video_id>                    # Render per-segment keyframe PNGs (10x faster than full render)
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
v2g scout all                         # Run all knowledge sources + daily digest
v2g scout github [--since 7]          # GitHub AI trending repos
v2g scout hn [--hours 24]             # Hacker News AI hot posts
v2g scout article [--urls "url1;url2"]# Article monitor (RSS / manual URL / inbox)
v2g scout ideation "topic"            # Competitive analysis + content ideation (optional YOUTUBE_API_KEY)
v2g scout ideation --from-daily       # Auto-extract topics from daily digest
v2g scout twitter [--temperature 0.5] # Twitter/X monitor (requires TWITTER_API_IO_KEY)
v2g scout plan [-i N]                 # One-click planning: pick topic → NotebookLM(opt) → hook+title+outline
v2g scout plan --skip-notebooklm      # Skip NotebookLM deep analysis
v2g scout produce [-i N] [--model M]  # One-click production: pick video → download → agent → script.json
v2g scout produce --skip-download     # Skip video download (use existing sources/)
v2g scout script "topic" -a "angle"   # Run hook + title + outline in one shot
v2g scout notebooklm "topic" -s URL   # NotebookLM deep analysis (no local token cost)
v2g scout title "topic" --history t.json  # Title generation with historical performance benchmarking
v2g scout waterfall "topic" --video-id ID # Content waterfall: video → blog + Twitter thread + LinkedIn
v2g scout waterfall "topic" --url URL     # Content waterfall from article URL
v2g scout waterfall "topic" --file path   # Content waterfall from local file
v2g scout shorts "topic" --video-id ID    # Short-form repurpose: long → 30/60/90s scripts
v2g assets ingest <project_id>            # Post-render: cut video into clips → auto-tag → SQLite
v2g assets refresh                        # Monthly: mark stale assets (product_ui 3mo, terminal 6mo)
v2g assets stats                          # Asset library statistics + engagement aggregation
v2g assets context [--limit N]            # Output LLM-ready asset list for script generation
v2g assets annotate <project_id> --retention <csv>  # Map B站 retention curve to segment scores
v2g assets fetch <project_id> --bvid BVxxx  # Fetch B站 stats + creator diagnostics → assets.db
v2g assets fetch-all                      # Batch update all linked videos' stats
v2g assets extract <project_id>           # Extract script structural features → assets.db
```

### Remotion (from `remotion-video/`)

```bash
npm run dev                   # Remotion studio (interactive preview)
npm run build                 # TypeScript type-check only (tsc --noEmit)
npm run render                # Dev render with empty props (not production)
node render.mjs <project_id>  # Production render → final/video.mp4 + final/subtitles.srt
node preview.mjs <project_id> # Quick keyframe preview → output/{id}/preview/seg_*.png
```

Production rendering is done via `render.mjs`, not `npm run render`. It auto-cleans `public/` cache after rendering. Use `preview.mjs` before full render to verify visual results (10x faster).

## Architecture

### Dual Rendering Backends

The pipeline has **two independent video rendering paths** that diverge at Stage 5b:

```
Single-video (v2g run):
  prepare → script → [quality gate] → [review] → tts → [word align] → slides → [preview] → assemble (FFmpeg) → final/

Multi-source (v2g multi):
  multi-prepare → multi-script → [quality gate] → [review] → tts → slides → [preview] → Remotion → final/

Agent orchestration (v2g agent):
  fetch/read/search → outline → [confirm] → phased script → [quality gate] → tts → slides → render
```

- **FFmpeg path** (`editor.py`): direct video composition with ASS subtitle burn-in. Output: `output/{video_id}/final/video.mp4`
- **Remotion path** (`render.mjs`): declarative React rendering with animated components. Output: `output/{video_id}/final/video.mp4` + `final/subtitles.srt`

### Python-to-Remotion Bridge

`render.mjs` is the bridge between Python output and Remotion rendering:
1. Reads `script.json` and `voiceover/timing.json` from `output/{video_id}/`
2. Parses `checkpoint.json` to detect single vs multi-source mode
3. Finds source videos in `sources/{video_id}/` (fallback: `output/subtitle/`)
4. Auto-transcodes source videos (AV1/VP9 → H.264) if needed
5. Copies assets into `remotion-video/public/` (auto-cleaned after render): slides/, images/, web_videos/, recordings/, voiceover
6. Generates `final/subtitles.srt` (uses `word_timing.json` for precise alignment when available, falls back to character-proportional splitting) and renders `final/video.mp4`

Composition ID is hardcoded as `V2GVideo` in `Root.tsx`. Resolution is 1920x1080 @ 30fps.

### Component Registry (Schema × Style)

Visual rendering uses a two-layer model separating data contracts (Schema) from visual implementations (Style):

- **Schemas** (stable): `slide`, `terminal`, `recording`, `source-clip`, `code-block`, `social-card`, `diagram`, `hero-stat`, `browser`, `image-overlay`, `web-video` — define data interfaces in `registry/types.ts`
- **Styles** (iterable): visual implementations in `registry/styles/{schema}/{name}.tsx` — self-register via `registry.register()` at import time
- **Registry** (`registry/registry.ts`): `ComponentRegistry` class with `resolve()`, `resolveForSegment()`, `toLLMPromptTable()`
- **Init** (`registry/init.ts`): imports all style files to trigger registration

Style ID format: `"{schema}.{style-name}"`, e.g. `"slide.tech-dark"`.

`VideoComposition.tsx` resolves components via `registry.resolveForSegment(seg, hasRecording)`:
1. If `segment.component` is set → look up that style ID
2. Else fallback by `segment.material`: A→slide default, B→recording/terminal default, C→source-clip default

To add a new visual style: create `registry/styles/{schema}/{name}.tsx` with `registry.register()` call at bottom + add import to `init.ts`.

### Three Material Types (Original Content Semantics)

Each script segment specifies one of three material types, and optionally a `component` field (style ID like `"slide.tech-dark"`) for explicit visual component selection:
- **A (Generated visuals)** — AI-generated content: slide cards (6 auto-detected layouts), diagrams, code blocks, social cards, hero stats, browser mocks, **image overlays** (real screenshots/photos with Ken Burns effect + text overlay). The `component` field selects the visual schema.
- **B (Recordings/demos)** — User-provided screen captures, or screenshots auto-converted via `v2g record`. Missing recordings fall back to `terminal.aurora` style (animated Claude Code TUI simulation) in Remotion, or a placeholder card in FFmpeg.
- **C (Referenced materials)** — External content: **web video clips** (product demos, conference talks, downloaded via yt-dlp with overlay text + filter), or trimmed source clips. Web-video segments include a `fallback_component` for graceful degradation when download fails.

Target ratio: A 40-60%, B ≥20%, C optional (original content may not need external references).

### Pipeline State

State persists in `output/{video_id}/checkpoint.json` (`PipelineState` dataclass in `checkpoint.py`). Stage flags (`selected`, `downloaded`, `scripted`, `tts_done`, `slides_done`, `assembled`, etc.) enable resuming at any stage. Multi-source mode adds `project_id`, `topic`, and `sources[]` (list of `SourceVideo` with per-source paths and `prepared` flag).

### Input/Output Separation

- **Input materials** (`sources/`): Downloaded source videos and subtitles, organized by video ID
- **Working files** (`output/{project}/`): Script, voiceover, slides, recordings — grouped by type
- **Final deliverables** (`output/{project}/final/`): Only `video.mp4` and `subtitles.srt`
- **Remotion staging** (`remotion-video/public/`): Temporary asset cache, auto-cleaned after render

### Key Data Files

- `script.json` — LLM-generated script with segments (id, type, material, component?, narration_zh, slide_content/recording_instruction/terminal_session/source timing/image_content/web_video/flash_meme). The optional `component` field specifies a style ID (e.g. `"slide.tech-dark"`, `"image-overlay.default"`, `"web-video.default"`); when absent, defaults by material type. B-material segments include `terminal_session` (structured terminal steps: input/output/status/tool/blank) for driving terminal animation when no recording exists. A-material segments may use `image_content` (image_path, overlay_text, ken_burns) for image overlay. C-material segments may use `web_video` (search_query, source_url, fallback_component) for external video. Any segment may include `flash_meme` (image, frame_offset?, duration?, contrast?, brightness?) to flash a meme image overlay at a specific frame within the segment. Multi-source mode adds `sources_used`, `total_duration_hint`.
- `script_meta.json` — Generation metadata: model name, prompt hash, timestamp, input/output char counts. Used for prompt version tracking.
- `voiceover/timing.json` — `{segment_id: {file, duration, text_length}}` mapping from TTS output.
- `voiceover/word_timing.json` — (optional) `{segment_id: [{word, start, end}, ...]}` word-level timestamps from mlx-whisper alignment.
- `recording_guide.md` — Extracted material B instructions for the user.
- `preview/seg_*.png` — Per-segment keyframe previews (rendered at frame 60, ~2s).
- `final/subtitles.srt` — SRT subtitles (Remotion backend) or `final/subtitles.ass` (FFmpeg backend).

### Agent Orchestration (`agent.py`)

`v2g agent` implements a two-phase LLM-driven script generation pipeline:

1. **Phase 1 — Outline**: Agent loop with tool use (fetch URLs, read files, search GitHub/HN, save outline). Supports both Anthropic and OpenAI-compatible backends.
2. **Human review**: User confirms/edits `outline.json`
3. **Phase 2 — Phased Script**: Two-step generation (skeleton → batch fill, 3 segments per batch) to avoid proxy truncation. Falls back to single-shot with truncation recovery.

Agent tools: `fetch_url` (web article extraction), `read_source_file` (local files), `search_github` (GitHub REST API), `search_hn` (HN Algolia API), `save_outline`, `save_script`.

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

**Proxy handling** (`_make_http_client()` in `llm.py`): Per-request httpx.Client with `trust_env=False`, never modifies global `os.environ`. Domestic APIs (智谱/MiniMax/Gemini) use `proxy=None`; custom gateway URLs skip system proxy; official API URLs read system proxy (read-only).

**Cost tracking** (`cost.py`): Module-level `CostTracker` singleton records token usage from every LLM call (extracted from API responses) and TTS character consumption. Summary saved to `checkpoint.json` `cost_summary` field and printed at pipeline end.

**Schema validation** (`schema.py`): Pydantic v2 models mirror `remotion-video/src/types.ts`. `validate_script()` runs before `eval_script()` business rules, catching structural errors (wrong types, missing fields, invalid component IDs) before they reach the rendering layer. Validates `image_content` for `image-overlay` components and `web_video` for `web-video` components.

### TTS Dual Engine (`tts.py`) + Word Alignment (`subtitle.py`)

- **edge-tts** (default, free): Microsoft Edge TTS
- **MiniMax Speech** (paid, high quality): requires `TTS_MINMAX_KEY`
- Switch via `TTS_ENGINE` env var. Each segment rendered separately to `voiceover/segments/seg_{id}.mp3`.
- **Word-level alignment** (optional): After TTS, `mlx-whisper` (Apple Silicon GPU) extracts word-level timestamps → `voiceover/word_timing.json`. Used by `render.mjs` for precise SRT subtitle timing. Install: `pip install -e ".[subtitle]"`. Graceful fallback when unavailable.

### Scout Automation (`scout/`)

`v2g scout` implements automated topic discovery for AI Tech content creators. Three knowledge sources feed into an Obsidian vault:

1. **GitHub Trending** (`github_trending.py`): Uses GitHub REST API `/search/repositories` (no token needed, 60 req/hour). Per-topic queries merged and deduped. LLM analyzes repos for content creation opportunities.
2. **Hacker News** (`hn_monitor.py`): Uses HN Algolia API (free, no rate limit). Per-keyword queries merged and deduped. LLM identifies hot topics and discussion-worthy posts.
3. **Article Monitor** (`article_monitor.py`): Three input modes — RSS feeds (via feedparser), manual URLs (`--urls`), and Obsidian inbox (`{vault}/inbox/articles.md`). Reuses `fetcher.fetch_article()` for content extraction. LLM generates TL;DR + key points.
4. **Twitter/X** (`twitter_monitor.py`): Uses Apify `apidojo~tweet-scraper` Actor (async polling model). Rule-based pre-filter → LLM scoring (virality/authority/timeliness/opportunity) → softmax probabilistic selection. Currently limited by X's anti-scraping measures.

Shared infrastructure:
- **`store.py`**: Generic SQLite dedup store shared by all sources. Table `seen_items(source, item_id, data, fetched_at)`.
- **`obsidian.py`**: `ObsidianWriter` class writes YAML-frontmatter Markdown to `{vault}/scout/{source}/` dirs. Falls back to `output/scout/` when `OBSIDIAN_VAULT_PATH` is unset.
- **`telegram.py`**: Telegram Bot notifications via httpx POST (HTML parse_mode). Best-effort, failures logged but not raised.

`v2g scout all` runs GitHub + HN + articles sequentially, generates a daily digest, then auto-runs ideation on topics extracted from the digest.

5. **Ideation** (`ideation.py`): Takes a topic (user-specified or auto-extracted from daily digest), searches YouTube via Data API v3 for competitive landscape, then LLM generates 5-9 content ideas with Tier 1/Tier 2 ranking. Degrades gracefully without `YOUTUBE_API_KEY` (LLM-only ideation).

Each source is idempotent per date (overwrites same-date files). SQLite dedup ensures no repeated processing across runs. Designed for cron scheduling: `0 8 * * * v2g scout all --quiet`.

### Content Distribution (`scout/`)

Post-production distribution layer for repurposing finished content across platforms:

6. **Content Waterfall** (`waterfall.py`): Takes video subtitles/scripts/articles and generates three formats: SEO blog post (800-1200 words), Twitter thread (7 tweets), and LinkedIn posts (2 versions). Input sources: `--video-id` (reads from sources/ or output/), `--url` (fetches article), `--file` (local file). Output: `scout/distribution/{date}-waterfall-{slug}.md`.

7. **Short-form Repurpose** (`shorts.py`): Converts long-form content into three independent short video scripts (30s/60s/90s). Each version includes hook (oral + text overlay), core content points, and CTA. Not simple trimming — each version is re-conceived for its time constraint. Output: `scout/distribution/{date}-shorts-{slug}.md`.

Shared content loading (`_load_video_content()` in `__init__.py`): Resolves video content from multiple paths — `output/{id}/script.md` > `sources/{id}/subtitle_zh.srt` > `subtitle_en.srt`, or fetches from URL, or reads local file. Truncates to 8000 chars.

### Title Historical Benchmarking (`scout/title.py`)

The title generation skill supports historical performance data for data-driven title optimization:
- `--history titles.json`: Load explicit performance data (`[{title, views, likes}]`), LLM references patterns from high-performing titles
- Auto-scan: Without `--history`, automatically scans `scout/scripts/*-title-*.md` in the Obsidian vault for past generated titles as reference
- Prompt instructs LLM to identify successful patterns and explicitly cite which historical title inspired each suggestion

### Prompt Engineering

`src/v2g/prompts/` contains LLM prompt templates:
- `script_system.md` — single-source script generation rules
- `script_multi_system.md` — multi-source synthesis rules
- `slide_system.md` — slide content and layout generation
- `agent_system.md` — Agent role and orchestration principles
- `agent_outline.md` — outline generation requirements and JSON format
- `agent_script.md` — script expansion rules (reuses material type system from script_system.md)
- `scout_github.md` — GitHub repo analysis (trending, top 3, emerging directions)
- `scout_hn.md` — HN post analysis (trends, top 3, controversy detection)
- `scout_article.md` — article summarization (TL;DR, key points, content angle)
- `scout_daily.md` — daily digest generation (highlights, content suggestions, trends)
- `scout_ideation.md` — competitive analysis + content ideation (landscape, 5-9 ideas with tiers)
- `scout_hook.md` — 5-variant opening hook generation (oral/visual/text overlay)
- `scout_title.md` — tiered title generation with historical benchmarking support
- `scout_outline.md` — video outline (chapters, visual aids, references)
- `scout_waterfall.md` — content waterfall distribution (blog + Twitter thread + LinkedIn)
- `scout_shorts.md` — short-form repurpose (30/60/90s independent scripts)
- `asset_tag.md` — LLM multimodal tagging for external video assets (constrained enum output)

### Remotion Components (`remotion-video/src/`)

- `VideoComposition.tsx` — main container, sequences segments via `<Series>`, dispatches to registered styles via `registry.resolveForSegment()`
- `registry/` — Schema × Style component library system:
  - `types.ts` — `SlideData`, `TerminalData`, `RecordingData`, `SourceClipData`, `ImageOverlayData`, `WebVideoData` + 7 more schema interfaces + `StyleMeta`, `StyleComponentProps<S>` generics
  - `registry.ts` — `ComponentRegistry` class (register, resolve, resolveForSegment, toLLMPromptTable)
  - `init.ts` — import-triggers all style self-registration
  - `styles/slide/tech-dark.tsx` — PPT cards with 6 auto-detected layouts (default for material A)
  - `styles/slide/glass-morphism.tsx` — Glass morphism gradient style PPT cards
  - `styles/slide/chalk-board.tsx` — Blackboard hand-drawn style with semantic colors
  - `styles/terminal/aurora.tsx` — Claude Code TUI simulation with aurora background (default for material B fallback)
  - `styles/terminal/vscode.tsx` — VS Code editor simulation with file tree and terminal panel
  - `styles/recording/default.tsx` — video playback (default for material B with recording file)
  - `styles/source-clip/default.tsx` — trimmed source clip with bottom mask (default for material C)
  - `styles/code-block/default.tsx` — syntax-highlighted code display with line numbers, highlight lines, annotations
  - `styles/social-card/default.tsx` — Twitter/GitHub/HN card rendering (data-driven, no screenshots)
  - `styles/diagram/default.tsx` — flow/architecture diagrams with nodes + edges, LR/TB layout
  - `styles/hero-stat/default.tsx` — big number display with countUp animation and trend arrows
  - `styles/browser/default.tsx` — Chrome browser frame simulation with address bar and content area
  - `styles/image-overlay/default.tsx` — full-screen image with Ken Burns effect (zoom-in/out/pan) + gradient overlay + text (default for image-overlay schema)
  - `styles/web-video/default.tsx` — external video playback with optional filter (desaturate/tint) + text overlay (default for web-video schema)
- `components/` — reusable effect components and legacy wrappers:
  - `FlashMeme.tsx` — flash meme overlay (instant appear/disappear, high contrast + scanlines + random rotation, zIndex 9999)
  - `HumanTyping.tsx` — code/text typing display with human-like rhythm (uses `useHumanTypist` hook)
  - `WordReveal.tsx`, `SectionTitle.tsx`, `GlitchTransition.tsx`, `LightLeak.tsx`, `ParticleBackground.tsx`, `FloatingCode.tsx`, `GlowOrb.tsx`, `GridBackground.tsx`, `ConstellationBg.tsx`, `ProgressBar.tsx`, `GradientText.tsx`, `TechIcons.tsx`, `TechLogo.tsx`
- `hooks/`:
  - `useHumanTypist.ts` — deterministic human typing simulation hook (alea PRNG, variable speed, punctuation pauses, typo→backspace→retype). Pre-computes frame schedule in `useMemo`, O(1) binary search per frame.
  - `useAnimatedText.ts` — simple linear character reveal hook
- `types.ts` — `ScriptSegment` (includes optional `component?: string`, `image_content?`, `web_video?`, `flash_meme?` fields), `TimingMap`, `VideoCompositionProps` type definitions

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
- `OBSIDIAN_VAULT_PATH` — Obsidian vault directory (fallback: `output/scout/`)
- `GITHUB_TOPICS` — comma-separated topics for GitHub trending (default: `ai,ml,llm,agent,rag`)
- `APIFY_TOKEN` — Apify API token (for Twitter monitoring)
- `TWITTER_KEYWORDS`, `TWITTER_AUTHORS` — Twitter monitoring targets
- `ARTICLE_RSS_URLS` — comma-separated RSS feed URLs
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — Telegram push notifications
- `YOUTUBE_API_KEY` — YouTube Data API v3 (optional, for ideation competitive analysis)
- `BILIBILI_SESSDATA` — B站 SESSDATA cookie (for creator dashboard diagnostics)
- `BILIBILI_BILI_JCT` — B站 bili_jct cookie (csrf token, paired with SESSDATA)
- `BILIBILI_RETENTION_API` — custom retention API endpoint (override if default path changes)

### Global Segment Animation

`VideoComposition.tsx`'s `SegmentTransition` wrapper applies two effects to every segment:
1. **Fade through black**: 8-frame (0.27s) fade in/out at segment boundaries
2. **Entrance scale**: 12-frame (0.4s) subtle zoom from 0.97→1.0 with `Easing.out(cubic)`, creating a "push-in" feel

Both effects apply globally — no per-component changes needed. All 30+ registered styles automatically get the animation.

### Asset Library (`asset_store.py`)

SQLite-based reusable asset library at `output/assets.db`. Follows `scout/store.py` patterns.

**Three tables**:
- `assets` — segment-level clips with visual_type/mood/product tags + engagement_score
- `video_stats` — video-level B站 metrics (views, likes, coins, interact_rate, crash_rate, viewer_tags)
- `video_features` — script structural features (segment_count, material ratios, schema_diversity, narration stats)

**Enum tag system** (hardcoded, no free-form values):
- `visual_type`: screen_recording, product_ui, terminal, browser, code_editor, diagram, chart, text_slide, person, screenshot, image_overlay, web_video
- `product`: claude, claude-code, cursor, github, vscode, chatgpt, openai, anthropic, google, deepseek, gemini, other
- `mood`: hook, problem, explain, demo, reveal, compare, celebrate, warning, summary, cta
- `freshness`: current, possibly_outdated, evergreen

**Lifecycle**:
1. **Ingest** (`asset_ingest.py`): After render, `v2g assets ingest` reads script.json + timing.json → ffmpeg cuts video by segment → auto-tags from script metadata → SQLite insert
2. **Search** (`AssetStore.search()`): Tag-based hard filter, ordered by `captured_date` DESC (newer assets first)
3. **Context injection** (`asset_context.py`): `build_asset_context()` generates LLM-ready text listing available assets + engagement stats + high-performing patterns, for injection into script generation prompts (`scriptwriter.py` and `agent.py`)
4. **Freshness** (`AssetStore.mark_stale()`): product_ui/screenshot expire at 3 months, terminal/browser at 6 months, diagram/chart/text_slide are evergreen
5. **Retention feedback** (`retention.py`): Maps B站 retention CSV to segment engagement scores (-1/0/1), stored per-asset for data-driven optimization
6. **B站 data fetch** (`bilibili.py`): Public API (views/likes/coins) + creator dashboard diagnostics (interact_rate/crash_rate/viewer_tags). Requires `BILIBILI_SESSDATA` + `BILIBILI_BILI_JCT` for diagnostics.
7. **Feature extraction** (`feature_extractor.py`): Extracts 17 structural features from script.json (material ratios, schema diversity, narration density, component usage). `get_high_performing_patterns()` correlates features with video_stats to identify winning structures.

**Self-evolution feedback loop**:
```
v2g assets fetch <project> --bvid BVxxx   → pull B站 stats + diagnostics
v2g assets extract <project>               → extract script structural features
                                            → data accumulates in assets.db
                                            → eval.py auto-compares against historical patterns (≥3 videos)
                                            → build_asset_context() injects high-performing patterns into LLM
                                            → next script generation biases toward winning structures
```

**Asset preprocessing** (`asset_normalize.py`): Normalizes external assets to 1920x1080 H.264 — supports center-crop or Gaussian blur background fill for mismatched aspect ratios.

### Fallback & Degradation Strategy

| Stage | Normal Path | Fallback | Trigger |
|-------|-------------|----------|---------|
| Word alignment | mlx-whisper → `word_timing.json` | Character-proportional duration split | mlx-whisper not installed |
| B-material render | `seg_*.mp4` detected → `recording.default` | `terminal.aurora` animated TUI | No recording file for segment |
| Agent script gen | Skeleton + 3-segment batch fill | Single-shot + auto-detect truncation + continuation prompt | Phased generation throws exception |
| Component resolve | `segment.component` explicit style ID | Material type → schema default (A→slide, B→terminal, C→source-clip) | component field absent or unresolved |
| Web-video render | `web_video.source_url` set → `web-video.default` | `fallback_component` field → specified component (e.g. `slide.tech-dark`) | source_url not set (download not confirmed) |
| TTS engine | `TTS_ENGINE` env var selects edge-tts or MiniMax | **No auto-fallback** — pipeline fails if chosen engine is unavailable | N/A |

### Known Limitations

- **Chinese-only narration**: `narration_zh` is the only narration field. TTS voices (`zh-CN-YunxiNeural`, MiniMax Chinese voices), prompts, and eval rules all assume Chinese. Multi-language support requires schema changes.
- **Remotion license**: Remotion framework uses a [commercial license](https://remotion.dev/license). Free for personal use and companies with <3 employees. SaaS/larger teams require a paid license.
- **Eval blind spots**: `eval.py` checks structural rules + historical pattern comparison (when ≥3 videos have stats+features). No semantic quality assessment (narrative coherence, hook effectiveness, terminology consistency).
- **Render performance**: No benchmarks recorded. `preview.mjs` claims "10x+ faster than full render" but no timing data. Full Remotion render for 5-8 min video is significantly slower than FFmpeg path.
- **No test coverage for LLM/TTS/pipeline**: Only `eval.py` and `schema.py` have unit tests. Core modules (`llm.py`, `agent.py`, `tts.py`) require real API keys and are not easily testable without mocks.

## Agent Operating Rules

Rules for Claude Code when executing v2g pipeline stages:

### Source of Truth

- **`script.json` is the source of truth** for all downstream stages (TTS, slides, render). `script.md` is a read-only Markdown export for human review. Edits to `script.md` are silently ignored.
- When modifying script content, always edit `script.json` directly.

### Cross-Language Contract

- **`schema.py` and `types.ts` must stay in sync.** When adding/removing/changing fields in either file, update the other immediately. The Pydantic model (`schema.py`) and TypeScript interface (`types.ts`) define the same `ScriptSegment` / `ScriptData` contract.
- Run `pytest tests/test_schema.py` after schema changes to verify.

### Quality Gate

- Eval uses three severity levels: **critical** (weight≥3, must retry), **warning** (weight=2, log and continue), **info** (weight≤1, record only).
- Only critical failures trigger automatic script regeneration. Don't retry on warnings alone.

### Pipeline Execution

- Always run `preflight_check()` before starting any pipeline mode (single/multi/agent). It detects missing dependencies in seconds.
- After TTS, optionally run word-level alignment (`mlx-whisper`). It's a graceful degradation — absence doesn't break the pipeline.
- Before full Remotion render, run `preview.mjs` to generate per-segment keyframe PNGs (10x faster).
