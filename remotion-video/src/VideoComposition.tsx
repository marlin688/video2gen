/**
 * video2gen 主视频组合
 *
 * 通过 registry 动态分发 segment 到注册的 style 组件。
 * 向后兼容：无 component 字段时按 material A/B/C 走默认 style。
 */

import {
  AbsoluteFill, Sequence, Series, staticFile,
  useCurrentFrame, useVideoConfig, interpolate, Easing,
} from "remotion";
import React from "react";
import { Audio } from "@remotion/media";

import type { VideoCompositionProps, ScriptSegment } from "./types";
import { registry } from "./registry/registry";
import "./registry/init"; // 触发所有 style 自注册
import { ThemeProvider, getTheme } from "./registry/theme";

import type {
  SlideData, TerminalData, RecordingData, SourceClipData,
  CodeBlockData, SocialCardData, DiagramData, HeroStatData, BrowserData,
  ImageOverlayData, WebVideoData,
  SegmentData, StyleComponentProps,
} from "./registry/types";

/**
 * 段间转场：每个 segment 首尾 fade through black
 * - 淡入：前 8 帧 (0.27s) 从黑色渐显
 * - 淡出：后 8 帧 (0.27s) 渐隐到黑色
 * - 第一段只淡入不淡出，最后一段只淡出不淡入（避免开头/结尾突兀）
 */
const FADE_FRAMES = 8;

const SCALE_FRAMES = 12; // 入场微缩放持续帧数 (0.4s @30fps)

const SegmentTransition: React.FC<{
  isFirst: boolean;
  isLast: boolean;
  children: React.ReactNode;
}> = ({ isFirst, isLast, children }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // 淡入：第一段从黑到亮；中间段从黑到亮
  const fadeIn = isFirst
    ? interpolate(frame, [0, FADE_FRAMES], [0, 1], { extrapolateRight: "clamp" })
    : interpolate(frame, [0, FADE_FRAMES], [0, 1], { extrapolateRight: "clamp" });

  // 淡出：最后一段从亮到黑；中间段从亮到黑
  const fadeOut = isLast
    ? interpolate(frame, [durationInFrames - FADE_FRAMES, durationInFrames], [1, 0], { extrapolateLeft: "clamp" })
    : interpolate(frame, [durationInFrames - FADE_FRAMES, durationInFrames], [1, 0], { extrapolateLeft: "clamp" });

  const opacity = Math.min(fadeIn, fadeOut);

  // 入场微缩放：从 0.97 → 1.0，配合 fade 形成"推入"感
  const scale = interpolate(
    frame, [0, SCALE_FRAMES], [0.97, 1],
    { extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) },
  );

  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ transform: `scale(${scale})` }}>
        {children}
      </AbsoluteFill>
      {/* 黑色遮罩层实现 fade through black */}
      <AbsoluteFill
        style={{
          backgroundColor: "#000",
          opacity: 1 - opacity,
          pointerEvents: "none",
        }}
      />
    </AbsoluteFill>
  );
};

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
  } = props;
  const segments = script.segments;

  // 获取视频主题（通过 props 传入或默认 tech-blue）
  const { theme: themeId } = props;
  const theme = React.useMemo(() => getTheme(themeId), [themeId]);

  const renderSegment = (seg: ScriptSegment) => {
    const hasRecording = availableRecordings.includes(seg.id);
    const entry = registry.resolveForSegment(seg, hasRecording);

    if (!entry) {
      return <AbsoluteFill style={{ backgroundColor: "#000" }} />;
    }

    // 根据 schema 构建 data
    const schema = entry.meta.schema;
    const t = timing[String(seg.id)];
    const segFps = fps;

    let data: SegmentData;

    switch (schema) {
      case "slide":
        data = {
          schema: "slide",
          title: seg.slide_content?.title || "Info",
          bullet_points: seg.slide_content?.bullet_points || [],
          chart_hint: seg.slide_content?.chart_hint,
        } satisfies SlideData;
        break;

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
          videoFile: seg.web_video?.source_url
            ? `web_videos/${seg.web_video.source_url}`
            : "",
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

  return (
    <ThemeProvider value={theme}>
      <AbsoluteFill>
        {/* 视频片段序列（带段间淡入淡出转场） */}
        <Series>
          {segments.flatMap((seg, idx) => {
            const t = timing[String(seg.id)];
            if (!t) return [];
            const durationFrames = Math.round(t.duration * fps);
            const gapFrames = Math.round((t.gap_after || 0) * fps);
            const isFirst = idx === 0;
            const isLast = idx === segments.length - 1;

            const items: React.ReactNode[] = [
              <Series.Sequence key={seg.id} durationInFrames={durationFrames}>
                <SegmentTransition
                  isFirst={isFirst}
                  isLast={isLast}
                >
                  {renderSegment(seg)}
                </SegmentTransition>
              </Series.Sequence>,
            ];

            if (gapFrames > 0 && !isLast) {
              items.push(
                <Series.Sequence key={`gap-${seg.id}`} durationInFrames={gapFrames}>
                  <AbsoluteFill style={{ backgroundColor: "#000" }} />
                </Series.Sequence>,
              );
            }

            return items;
          })}
        </Series>

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
