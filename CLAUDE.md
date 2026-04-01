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

### Prompt Engineering

`src/v2g/prompts/` contains LLM prompt templates:
- `script_system.md` — single-source script generation rules
- `script_multi_system.md` — multi-source synthesis rules
- `slide_system.md` — slide content and layout generation
- `agent_system.md` — Agent role and orchestration principles
- `agent_outline.md` — outline generation requirements and JSON format
- `agent_script.md` — script expansion rules (reuses material type system from script_system.md)

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
