/**
 * video2gen 主视频组合
 *
 * 通过 registry 动态分发 segment 到注册的 style 组件。
 * 向后兼容：无 component 字段时按 material A/B/C 走默认 style。
 *
 * Phase 1 升级:
 * - TransitionSeries 替换 Series，支持 fade / slide / wipe 多种转场
 * - LightLeak 光晕叠加层
 * - 自动按 segment.type 选择转场类型
 */

import {
  AbsoluteFill, Sequence, staticFile,
  useCurrentFrame, useVideoConfig, interpolate, Easing,
} from "remotion";
import React from "react";
import { Audio } from "@remotion/media";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import type { TransitionPresentation } from "@remotion/transitions";

import type {
  VideoCompositionProps,
  ScriptSegment,
  TransitionType,
  CinematographyTags,
  CameraMoveTag,
  LightingTag,
} from "./types";
import { registry } from "./registry/registry";
import "./registry/init"; // 触发所有 style 自注册
import { ThemeProvider, getTheme } from "./registry/theme";
import { fadeThroughBlack } from "./registry/components/FadeThroughBlack";
import { glitch } from "./registry/components/GlitchTransition";
import { zoomIn } from "./registry/components/ZoomIn";
import { ProgressBar } from "./registry/components/ProgressBar";
import { LightLeak } from "./registry/components/LightLeak";
import { FlashMeme } from "./registry/components/FlashMeme";
import { CameraRig } from "./registry/components/CameraRig";
import { FilmGrain } from "./registry/components/FilmGrain";
import { LightingRig } from "./registry/components/LightingRig";
import { SubtitleOverlay } from "./components/SubtitleOverlay";

import type {
  SlideData, TerminalData, RecordingData, SourceClipData,
  CodeBlockData, SocialCardData, DiagramData, HeroStatData, BrowserData,
  ImageOverlayData, WebVideoData,
  SegmentData, StyleComponentProps,
} from "./registry/types";

/* ═══════════════ 转场常量 ═══════════════ */

const TRANSITION_FRAMES = 12; // 转场持续帧数（0.4s @ 30fps）

type AnyPresentation = TransitionPresentation<Record<string, unknown>>;

const VALID_CAMERA_MOVES: CameraMoveTag[] = [
  "static",
  "push-in",
  "subtle-zoom",
  "drift-left",
  "drift-right",
];

const VALID_LIGHTING_TAGS: LightingTag[] = [
  "neutral",
  "bright",
  "dramatic",
  "cool",
  "warm",
  "accent",
];

const isCameraMove = (v: unknown): v is CameraMoveTag =>
  typeof v === "string" && VALID_CAMERA_MOVES.includes(v as CameraMoveTag);

const isLightingTag = (v: unknown): v is LightingTag =>
  typeof v === "string" && VALID_LIGHTING_TAGS.includes(v as LightingTag);

/**
 * 解析转场类型 → TransitionPresentation
 *
 * 优先级:
 *   1. segment.transition 显式指定
 *   2. 按 segment index 在 4 种入场中严格轮换 (fade / slide-left / zoom-in / glitch)
 *      — 保证相邻段入场动画必不相同
 *   3. 关键叙事节拍用 fadeThroughBlack 作为"喘息"
 */
function resolveTransition(
  explicit?: TransitionType,
  prevType?: "intro" | "body" | "outro",
  nextType?: "intro" | "body" | "outro",
  idx?: number,
): AnyPresentation {
  const t = explicit
    || autoTransition(prevType, nextType, idx);

  switch (t) {
    case "slide":
      return slide({ direction: "from-right" }) as AnyPresentation;
    case "slide-left":
      return slide({ direction: "from-left" }) as AnyPresentation;
    case "zoom-in":
      return zoomIn() as AnyPresentation;
    case "wipe":
      return wipe() as AnyPresentation;
    case "fade":
      return fade() as AnyPresentation;
    case "glitch":
      return glitch({ intensity: 12 }) as unknown as AnyPresentation;
    case "none":
    default:
      return fadeThroughBlack() as AnyPresentation;
  }
}

/**
 * 按段落语义 + index 严格轮换入场动画。
 *
 * 设计原则：
 * - 叙事边界 (intro→body, body→outro) 用专属动画，强化"章节切换"感
 * - intro/body 内部按 idx 严格轮换 4 种：fade / slide-left / zoom-in / glitch
 * - 每 5 段用一次 fadeThroughBlack 作为"视觉喘息"，避免连续动感过载
 * - 相邻段保证使用不同入场（通过 4-周期轮换自然实现）
 */
function autoTransition(
  prevType?: string,
  nextType?: string,
  idx?: number,
): TransitionType | undefined {
  // 叙事章节边界
  if (prevType === "intro" && nextType === "body") return "zoom-in";
  if (prevType === "body" && nextType === "outro") return "wipe";
  if (prevType === "outro" && nextType === "outro") return "fade";

  // 主体段落：idx 严格轮换
  if (idx === undefined) return undefined;

  // 每 5 段插一次 fadeThroughBlack 作为呼吸点
  if (idx > 0 && idx % 5 === 0) return "none";

  // 4 周期轮换，覆盖所有剩余段落
  const rotation: TransitionType[] = ["fade", "slide-left", "zoom-in", "glitch"];
  return rotation[idx % rotation.length];
}

/* ═══════════════ 主组件 ═══════════════ */

export const VideoComposition: React.FC<VideoCompositionProps> = (props) => {
  const {
    script,
    timing,
    fps,
    recordingsDir,
    sourceVideoFiles = [],
    sourceChannels = [],
    voiceoverFile,
    availableRecordings = [],
    defaultTransition = "",
    sourceVideoMap = {},
  } = props;
  const segments = script.segments;

  const segmentCinematography = React.useMemo(() => {
    const fromPlan = new Map<number, Partial<CinematographyTags>>();
    const planned = props.renderPlan?.segments || [];
    for (const row of planned) {
      if (typeof row.segment_id === "number" && row.cinematography) {
        fromPlan.set(row.segment_id, row.cinematography as Partial<CinematographyTags>);
      }
    }

    const plans: Record<number, {
      shot_type: string;
      camera_move: CameraMoveTag;
      lighting_tag: LightingTag;
      camera_intensity: number;
    }> = {};

    for (const seg of segments) {
      const rp = fromPlan.get(seg.id) || {};
      const shot_type = (seg.shot_type || rp.shot_type || "medium") as string;
      const rawMove = seg.camera_move || rp.camera_move || "subtle-zoom";
      const camera_move = isCameraMove(rawMove) ? rawMove : "subtle-zoom";
      const rawLight = seg.lighting_tag || rp.lighting_tag || "neutral";
      const lighting_tag = isLightingTag(rawLight) ? rawLight : "neutral";
      const defaultIntensity =
        seg.rhythm === "fast" ? 1.0 : seg.rhythm === "slow" ? 0.55 : 0.75;
      const rawIntensity = Number(seg.camera_intensity ?? rp.camera_intensity ?? defaultIntensity);
      const camera_intensity = Number.isFinite(rawIntensity)
        ? Math.max(0, Math.min(rawIntensity, 1.2))
        : defaultIntensity;

      plans[seg.id] = {
        shot_type,
        camera_move,
        lighting_tag,
        camera_intensity: camera_move === "static" ? 0 : camera_intensity,
      };
    }
    return plans;
  }, [segments, props.renderPlan]);

  // 获取视频主题（通过 props 传入或默认 tech-blue）
  const { theme: themeId } = props;
  const theme = React.useMemo(() => getTheme(themeId), [themeId]);

  const renderSegment = (seg: ScriptSegment) => {
    const hasRecording = availableRecordings.includes(seg.id);
    const entry = registry.resolveForSegment(seg, hasRecording);

    if (!entry) {
      return <AbsoluteFill style={{ backgroundColor: "#000" }} />;
    }

    const webSourceRaw = String(seg.web_video?.source_url || "").trim();
    const normalizedWebSource = webSourceRaw
      ? (webSourceRaw.startsWith("web_videos/") ? webSourceRaw : `web_videos/${webSourceRaw}`)
      : "";
    if (entry.meta.schema === "web-video" && !normalizedWebSource) {
      const fallbackComponent = String(seg.web_video?.fallback_component || "slide.tech-dark").trim();
      if (fallbackComponent && fallbackComponent !== seg.component) {
        return renderSegment({ ...seg, component: fallbackComponent });
      }
    }

    // 根据 schema 构建 data
    const schema = entry.meta.schema;
    const t = timing[String(seg.id)];
    const segFps = fps;

    let data: SegmentData;

    switch (schema) {
      case "slide": {
        // slide 组件可以通过 scene_data.__source 拿到源视频信息
        // (talking-head / screen-clip 场景用)。不扩展 StyleComponentProps
        // 就能让 slide schema 组件访问 sourceVideoFiles + sourceVideoMap。
        const baseSceneData = seg.slide_content?.scene_data || {};
        const sourceIdx = seg.source_video_index ?? 0;
        const mergedSceneData = {
          ...baseSceneData,
          __source: {
            videoFile: sourceVideoFiles[sourceIdx] || "",
            videoFiles: sourceVideoFiles,
            videoFileMap: sourceVideoMap,
            start: seg.source_start,
            end: seg.source_end,
            channel: sourceChannels[sourceIdx] || "",
          },
        };
        data = {
          schema: "slide",
          title: seg.slide_content?.title || "Info",
          bullet_points: seg.slide_content?.bullet_points || [],
          chart_hint: seg.slide_content?.chart_hint,
          scene_data: mergedSceneData,
        } satisfies SlideData;
        break;
      }

      case "terminal":
        data = {
          schema: "terminal",
          instruction: seg.recording_instruction || "需要录屏",
          narrationText: seg.narration_zh,
          session: seg.terminal_session,
        } satisfies TerminalData;
        break;

      case "recording":
        data = {
          schema: "recording",
          recordingFile: `${recordingsDir}/seg_${seg.id}.mp4`,
        } satisfies RecordingData;
        break;

      case "source-clip": {
        const idx = seg.source_video_index ?? 0;
        const videoFile = sourceVideoFiles[idx] || sourceVideoFiles[0] || "";
        const ttsDur = t ? t.duration : 10;
        data = {
          schema: "source-clip",
          sourceVideoFile: videoFile,
          sourceStart: seg.source_start || 0,
          sourceEnd: Math.min(seg.source_end || 8, (seg.source_start || 0) + 10),
          sourceChannel: sourceChannels[idx] || script.source_channel || "",
          ttsDuration: ttsDur,
        } satisfies SourceClipData;
        break;
      }

      case "code-block":
        data = {
          schema: "code-block",
          fileName: seg.code_content?.fileName || "code.ts",
          language: seg.code_content?.language || "typescript",
          code: seg.code_content?.code || [],
          highlightLines: seg.code_content?.highlightLines,
          annotations: seg.code_content?.annotations,
        } satisfies CodeBlockData;
        break;

      case "social-card":
        data = {
          schema: "social-card",
          platform: seg.social_card?.platform || "twitter",
          author: seg.social_card?.author || "",
          avatarColor: seg.social_card?.avatarColor,
          text: seg.social_card?.text || "",
          stats: seg.social_card?.stats,
          subtitle: seg.social_card?.subtitle,
          language: seg.social_card?.language,
        } satisfies SocialCardData;
        break;

      case "diagram":
        data = {
          schema: "diagram",
          title: seg.diagram?.title,
          nodes: (seg.diagram?.nodes || []).map(n => ({
            ...n,
            type: (n.type || "default") as "default" | "primary" | "success" | "warning" | "danger",
          })),
          edges: seg.diagram?.edges || [],
          direction: (seg.diagram?.direction || "LR") as "LR" | "TB",
        } satisfies DiagramData;
        break;

      case "hero-stat": {
        let hsStats = (seg.hero_stat?.stats || []).map(s => ({
          ...s,
          trend: (s.trend || "neutral") as "up" | "down" | "neutral",
        }));

        // hero_stat 缺失时从 slide_content.bullet_points 提取指标
        if (!hsStats.length && seg.slide_content?.bullet_points?.length) {
          hsStats = seg.slide_content.bullet_points.slice(0, 3).map(bp => {
            // 尝试解析 "标签: 值" 或 "标签 → 值" 格式
            const colonMatch = bp.match(/^(.+?)[:：]\s*(.+)$/);
            if (colonMatch) {
              const arrowMatch = colonMatch[2].match(/(.+?)\s*[→>]\s*(.+)/);
              return {
                label: colonMatch[1].trim(),
                value: arrowMatch ? arrowMatch[2].trim() : colonMatch[2].trim(),
                oldValue: arrowMatch ? arrowMatch[1].trim() : undefined,
                trend: (bp.includes("↑") || bp.includes("提升") ? "up"
                  : bp.includes("↓") || bp.includes("降") ? "down" : "neutral") as "up" | "down" | "neutral",
              };
            }
            return { label: bp.slice(0, 20), value: bp.slice(20) || "—", trend: "neutral" as const };
          });
        }

        data = {
          schema: "hero-stat",
          stats: hsStats,
          footnote: seg.hero_stat?.footnote || seg.slide_content?.title,
        } satisfies HeroStatData;
        break;
      }

      case "browser": {
        // browser_content 存在时直接使用；缺失时从 recording_instruction / terminal_session 提取
        const bc = seg.browser_content;
        let bUrl = bc?.url || "";
        let bTab = bc?.tabTitle || "";
        let bTitle = bc?.pageTitle;
        let bLines = bc?.contentLines || [];

        if (!bc) {
          const inst = seg.recording_instruction || "";
          // 从 recording_instruction 提取第一个 URL
          const urlMatch = inst.match(/https?:\/\/[^\s,，。)）\]]+/);
          if (urlMatch) {
            bUrl = urlMatch[0];
            try {
              const u = new URL(bUrl);
              bTab = u.hostname;
              // 从 URL path 生成页面标题
              const pathTitle = decodeURIComponent(u.pathname)
                .replace(/^\/|\/$/g, "").split("/").pop() || "";
              if (pathTitle) bTitle = pathTitle.replace(/[-_]/g, " ");
            } catch { bTab = bUrl.slice(0, 40); }
          }

          // 优先从 terminal_session 提取（结构化输出）
          if (seg.terminal_session?.length) {
            bLines = seg.terminal_session.flatMap(step => {
              if (step.type === "output" && step.lines) return step.lines;
              if (step.type === "status" && step.text) return [step.text];
              if (step.type === "input" && step.text) return [`$ ${step.text}`];
              return [];
            });
          }

          // 无 terminal_session 时，从 recording_instruction 提取操作要点作为页面内容
          if (!bLines.length && inst) {
            // 去掉 URL 部分，按中文标点/逗号/句号/步骤编号拆分
            const stripped = inst.replace(/https?:\/\/[^\s,，。)）\]]+/g, "").trim();
            bLines = stripped
              .split(/[，。；;]\s*|\d+\.\s*/)
              .map(s => s.trim())
              .filter(s => s.length > 2);
          }

          // 兜底：slide_content 的 bullet_points
          if (!bLines.length && seg.slide_content?.bullet_points?.length) {
            bLines = seg.slide_content.bullet_points;
            if (!bTitle && seg.slide_content.title) bTitle = seg.slide_content.title;
          }
        }

        data = {
          schema: "browser",
          url: bUrl,
          tabTitle: bTab,
          pageTitle: bTitle,
          contentLines: bLines,
          theme: (bc?.theme || "dark") as "light" | "dark",
          repoInfo: bc?.repoInfo,
        } satisfies BrowserData;
        break;
      }

      case "image-overlay":
        data = {
          schema: "image-overlay",
          imagePath: seg.image_content?.image_path || "",
          overlayText: seg.image_content?.overlay_text,
          overlayPosition: seg.image_content?.overlay_position,
          kenBurns: seg.image_content?.ken_burns || "zoom-in",
        } satisfies ImageOverlayData;
        break;

      case "web-video": {
        const ttsDur = t ? t.duration : 10;
        data = {
          schema: "web-video",
          videoFile: normalizedWebSource,
          overlayText: seg.web_video?.overlay_text,
          overlayPosition: seg.web_video?.overlay_position,
          filter: (seg.web_video?.filter || "none") as "none" | "desaturate" | "tint",
          ttsDuration: ttsDur,
        } satisfies WebVideoData;
        break;
      }

      default:
        return <AbsoluteFill style={{ backgroundColor: "#000" }} />;
    }

    const Component = entry.component as React.ComponentType<StyleComponentProps>;
    return <Component data={data} segmentId={seg.id} fps={segFps} />;
  };

  // ── 计算每段的帧范围（用于 LightLeak 定位） ──

  const segmentFrameInfo = React.useMemo(() => {
    let accum = 0;
    return segments.map((seg) => {
      const t = timing[String(seg.id)];
      if (!t) return { segmentId: seg.id, start: accum, duration: 0, gap: 0 };
      const dur = Math.round(t.duration * fps);
      const gap = Math.round((t.gap_after || 0) * fps);
      const info = { segmentId: seg.id, start: accum, duration: dur, gap };
      accum += dur + gap;
      return info;
    });
  }, [segments, timing, fps]);

  const beatCinematography = React.useMemo(() => {
    const shots = props.shotPlan?.shots || [];
    if (!shots.length) return [];

    const segMap = new Map<number, ScriptSegment>();
    for (const seg of segments) segMap.set(seg.id, seg);

    return shots
      .map((shot) => {
        if (typeof shot.segment_id !== "number") return null;
        if (typeof shot.start_sec !== "number" || typeof shot.end_sec !== "number") return null;
        if (!(shot.end_sec > shot.start_sec)) return null;

        const seg = segMap.get(shot.segment_id);
        const fallback = segmentCinematography[shot.segment_id];
        const move = isCameraMove(shot.camera_move)
          ? shot.camera_move
          : fallback?.camera_move || "subtle-zoom";
        const lighting = isLightingTag(shot.lighting_tag)
          ? shot.lighting_tag
          : fallback?.lighting_tag || "neutral";
        const defaultIntensity =
          seg?.rhythm === "fast" ? 1.0 : seg?.rhythm === "slow" ? 0.55 : 0.75;
        const rawIntensity = Number(
          shot.camera_intensity ?? fallback?.camera_intensity ?? defaultIntensity,
        );
        const intensity = Number.isFinite(rawIntensity)
          ? Math.max(0, Math.min(rawIntensity, 1.2))
          : defaultIntensity;

        const rawStart = Math.max(0, Math.round(shot.start_sec * fps));
        const rawEnd = Math.max(rawStart + 1, Math.round(shot.end_sec * fps));
        return {
          beatId: shot.beat_id,
          segmentId: shot.segment_id,
          startFrame: rawStart,
          endFrame: rawEnd,
          camera_move: move,
          lighting_tag: lighting,
          camera_intensity: move === "static" ? 0 : intensity,
        };
      })
      .filter((v): v is {
        beatId: number;
        segmentId: number;
        startFrame: number;
        endFrame: number;
        camera_move: CameraMoveTag;
        lighting_tag: LightingTag;
        camera_intensity: number;
      } => Boolean(v))
      .sort((a, b) => a.startFrame - b.startFrame);
  }, [props.shotPlan, segments, segmentCinematography, fps]);

  // ── LightLeak 位置：每 3 个转场边界 ──

  const lightLeakEnabled = props.lightLeaks !== false;

  const lightLeakSequences = React.useMemo(() => {
    if (!lightLeakEnabled) return [];
    const leaks: Array<{ from: number; duration: number; seed: string }> = [];
    for (let i = 1; i < segments.length; i++) {
      if (i % 3 !== 0) continue; // 每 3 个转场
      const info = segmentFrameInfo[i];
      if (!info) continue;
      const leakDuration = TRANSITION_FRAMES + 30;
      leaks.push({
        from: Math.max(0, info.start - 10),
        duration: leakDuration,
        seed: `leak-${i}`,
      });
    }
    return leaks;
  }, [lightLeakEnabled, segments.length, segmentFrameInfo]);

  return (
    <ThemeProvider value={theme}>
      <AbsoluteFill style={{ overflow: "hidden" }}>
        {/* CameraRig 全局运镜（包裹所有可视内容） */}
        <CameraRig
          segmentFrameInfo={segmentFrameInfo}
          segmentCameraPlans={segmentCinematography}
          beatCameraPlans={beatCinematography}
          enabled={props.cameraRig !== false}
        >
          {/* 视频片段序列（TransitionSeries 多种转场） */}
          <TransitionSeries>
            {segments.flatMap((seg, idx) => {
              const t = timing[String(seg.id)];
              if (!t) return [];
              const durationFrames = Math.round(t.duration * fps);
              const gapFrames = Math.round((t.gap_after || 0) * fps);
              const prevSeg = idx > 0 ? segments[idx - 1] : undefined;

              const items: React.ReactNode[] = [];

              // 段间转场：优先级 seg.transition > props.defaultTransition > 自动轮换。
              // "none" = 硬切（直接跳过 TransitionSeries.Transition 节点）。
              const effectiveTransition =
                (seg.transition as TransitionType | undefined) ||
                (defaultTransition as TransitionType | undefined);
              if (idx > 0 && effectiveTransition !== "none") {
                // 转场帧数不能超过前后 segment 中较短者的时长
                const prevT = timing[String(prevSeg?.id)];
                const prevDur = prevT ? Math.round(prevT.duration * fps) : Infinity;
                const transFrames = Math.min(TRANSITION_FRAMES, durationFrames - 1, prevDur - 1);
                if (transFrames > 0) {
                  items.push(
                    <TransitionSeries.Transition
                      key={`t-${seg.id}`}
                      presentation={resolveTransition(
                        effectiveTransition,
                        prevSeg?.type,
                        seg.type,
                        idx,
                      )}
                      timing={linearTiming({
                        durationInFrames: transFrames,
                      })}
                    />,
                  );
                }
              }

              // 段内容
              items.push(
                <TransitionSeries.Sequence
                  key={seg.id}
                  durationInFrames={durationFrames}
                >
                  {renderSegment(seg)}
                </TransitionSeries.Sequence>,
              );

              // 段后静音间隔
              if (gapFrames > 0 && idx < segments.length - 1) {
                items.push(
                  <TransitionSeries.Sequence
                    key={`gap-${seg.id}`}
                    durationInFrames={gapFrames}
                  >
                    <AbsoluteFill style={{ backgroundColor: "#000" }} />
                  </TransitionSeries.Sequence>,
                );
              }

              return items;
            })}
          </TransitionSeries>

          {/* FlashMeme 闪现梗图叠加层 */}
          {segments.map((seg, idx) => {
            if (!seg.flash_meme) return null;
            const info = segmentFrameInfo[idx];
            if (!info || !info.duration) return null;
            const fm = seg.flash_meme;
            const offset = fm.frame_offset ?? 0;
            const dur = fm.duration ?? 15;
            return (
              <Sequence
                key={`flash-${seg.id}`}
                from={info.start + offset}
                durationInFrames={dur}
              >
                <FlashMeme
                  imageFileName={fm.image}
                  displayMode={fm.display_mode}
                  contrast={fm.contrast}
                  brightness={fm.brightness}
                />
              </Sequence>
            );
          })}

          {/* LightLeak 光晕叠加层 */}
          {lightLeakSequences.map((leak) => (
            <Sequence
              key={leak.seed}
              from={leak.from}
              durationInFrames={leak.duration}
            >
              <LightLeak
                seed={leak.seed}
                intensity={0.25}
              />
            </Sequence>
          ))}

          {/* 底部进度条 */}
          {props.progressBar !== false && (
            <ProgressBar
              sectionStartFrames={segmentFrameInfo.map((info) => info.start)}
            />
          )}
        </CameraRig>

        {/* 逐段光线标签叠加层（基于 render_plan / script 标签） */}
        <LightingRig
          segmentFrameInfo={segmentFrameInfo}
          segmentLightingPlans={segmentCinematography}
          beatLightingPlans={beatCinematography}
          enabled={true}
        />

        {/* FilmGrain 后期质感层（固定在屏幕上，不受运镜影响） */}
        <FilmGrain enabled={props.filmGrain !== false} />

        {/* 字幕叠加层（固定在屏幕上，不受运镜影响） */}
        {props.subtitles !== false && (
          <SubtitleOverlay segments={segments} timing={timing} />
        )}

        {/* 配音音轨 */}
        <Sequence from={0}>
          <Audio src={staticFile(voiceoverFile)} />
        </Sequence>

        {/* BGM 音轨（可选） */}
        {props.bgmFile && (
          <Sequence from={0}>
            <Audio src={staticFile(props.bgmFile)} volume={props.bgmVolume ?? 0.15} loop />
          </Sequence>
        )}
      </AbsoluteFill>
    </ThemeProvider>
  );
};
