# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

video2gen (v2g) is an automated pipeline for creating derivative (二创) video content from YouTube source videos using AI. It combines a Python backend (pipeline orchestration, LLM scripting, TTS) with a TypeScript/React frontend (Remotion video rendering).

## Commands

### Python

```bash
pip install -e .              # Install in dev mode
v2g run <video_id_or_url>     # Full pipeline with human review checkpoints
v2g select --csv trending.csv # Stage 1: interactive video selection
v2g prepare <video_id>        # Stage 2: download + subtitle generation
v2g script <video_id>         # Stage 3: AI script generation
v2g review <video_id>         # Human review checkpoint
v2g tts <video_id>            # Stage 4: text-to-speech
v2g slides <video_id>         # Stage 5a: slide image generation
v2g assemble <video_id>       # Stage 5b: final video composition
v2g multi "url1;url2" --topic "topic"  # Multi-source synthesis
v2g status <video_id>         # Check pipeline progress
```

### Remotion (from `remotion-video/`)

```bash
npm run dev                   # Remotion studio (interactive preview)
npm run build                 # TypeScript type-check
npm run render                # Render video composition
```

## Architecture

### Pipeline Stages (Python — `src/v2g/`)

The pipeline is a linear sequence of stages, each independently runnable via CLI. State is persisted in `output/{video_id}/checkpoint.json` enabling resumption at any point.

```
CLI (cli.py) → Pipeline (pipeline.py)
  Stage 1: Selector   — pick video from trending CSV
  Stage 2: Preparer   — download video + generate subtitles (delegates to lecture2note)
  Stage 3: ScriptWriter — LLM generates script.json with segments
  ── Human Review Checkpoint ──
  Stage 4: TTS        — edge-tts or MiniMax → voiceover.mp3 + timing.json
  Stage 5a: Slides    — Pillow/AI image gen → slide PNGs
  Stage 5b: Editor    — FFmpeg composition or Remotion render → final.mp4
```

### Three Material Types

Each script segment specifies one of three material types:
- **A (PPT slides)** — AI-generated slide images with 6 layout modes (code, compare, metric, grid, steps, standard)
- **B (Screen recording)** — User-provided screen captures following generated instructions
- **C (Source clip)** — Trimmed + speed-adjusted clips from the original YouTube video

Target ratio: A ~40%, B ~40%, C ~20%.

### LLM Router (`llm.py`)

Routes to Claude, GPT, or Gemini based on model name prefix. Supports configurable base URL for proxies.

### Video Rendering (TypeScript — `remotion-video/src/`)

Remotion compositions render the final video declaratively:
- `VideoComposition.tsx` — main container, sequences segments via `<Series>`
- `SlideSegment.tsx` — renders material A with layout detection
- `SourceClipSegment.tsx` — material C with speed-matching to TTS duration
- `RecordingSegment.tsx` — material B video playback
- `SubtitleOverlay.tsx` — frame-synced subtitle display across all segments
- `render.mjs` — Node.js orchestrator that reads script/timing data and invokes Remotion renderer

### Key Data Flow

`script.json` (LLM output) + `voiceover_timing.json` (TTS output) are the two central data files that bridge Python stages to the Remotion renderer. The `ScriptSegment` and `TimingMap` types in `types.ts` define their schemas.

### External Dependencies

- **lecture2note** — sibling project (`../lecture2note/`) used for video download and subtitle generation
- **youtube-trending** — sibling project (`../youtube-trending/`) provides trending video CSV data
- Configuration via `.env` file (see `.env.example`)
