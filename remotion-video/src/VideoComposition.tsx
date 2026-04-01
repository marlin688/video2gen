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

import type { SlideData, TerminalData, RecordingData, SourceClipData, StyleComponentProps } from "./registry/types";

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

    let data: SlideData | TerminalData | RecordingData | SourceClipData;

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
