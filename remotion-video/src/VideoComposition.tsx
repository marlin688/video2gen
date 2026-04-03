/**
 * video2gen 主视频组合
 *
 * 通过 registry 动态分发 segment 到注册的 style 组件。
 * 向后兼容：无 component 字段时按 material A/B/C 走默认 style。
 */

import { AbsoluteFill, Sequence, Series, staticFile } from "remotion";
import React from "react";
import { Audio } from "@remotion/media";

import type { VideoCompositionProps, ScriptSegment } from "./types";
import { registry } from "./registry/registry";
import "./registry/init"; // 触发所有 style 自注册

import type {
  SlideData, TerminalData, RecordingData, SourceClipData,
  CodeBlockData, SocialCardData, DiagramData, HeroStatData, BrowserData,
  SegmentData, StyleComponentProps,
} from "./registry/types";

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

      case "hero-stat":
        data = {
          schema: "hero-stat",
          stats: (seg.hero_stat?.stats || []).map(s => ({
            ...s,
            trend: (s.trend || "neutral") as "up" | "down" | "neutral",
          })),
          footnote: seg.hero_stat?.footnote,
        } satisfies HeroStatData;
        break;

      case "browser":
        data = {
          schema: "browser",
          url: seg.browser_content?.url || "",
          tabTitle: seg.browser_content?.tabTitle || "",
          pageTitle: seg.browser_content?.pageTitle,
          contentLines: seg.browser_content?.contentLines || [],
          theme: (seg.browser_content?.theme || "dark") as "light" | "dark",
        } satisfies BrowserData;
        break;

      default:
        return <AbsoluteFill style={{ backgroundColor: "#000" }} />;
    }

    const Component = entry.component as React.ComponentType<StyleComponentProps>;
    return <Component data={data} segmentId={seg.id} fps={segFps} />;
  };

  return (
    <AbsoluteFill>
      {/* 视频片段序列 */}
      <Series>
        {segments.map((seg) => {
          const t = timing[String(seg.id)];
          if (!t) return null;
          const durationFrames = Math.round(t.duration * fps);
          return (
            <Series.Sequence key={seg.id} durationInFrames={durationFrames}>
              {renderSegment(seg)}
            </Series.Sequence>
          );
        })}
      </Series>

      {/* 配音音轨 */}
      <Sequence from={0}>
        <Audio src={staticFile(voiceoverFile)} />
      </Sequence>
    </AbsoluteFill>
  );
};
