/**
 * video2gen 主视频组合
 *
 * 根据 script.json 的 segments 顺序，用 Series 依次渲染三类素材，
 * 叠加 SubtitleOverlay 和 Audio。
 */

import { AbsoluteFill, Sequence, Series, staticFile } from "remotion";
import React, { useMemo } from "react";
import { Audio } from "@remotion/media";

import type { VideoCompositionProps, ScriptSegment } from "./types";
import { SlideSegment } from "./components/SlideSegment";
import { SourceClipSegment } from "./components/SourceClipSegment";
import { PlaceholderSegment } from "./components/PlaceholderSegment";
import { RecordingSegment } from "./components/RecordingSegment";
import { TerminalDemoSegment } from "./components/TerminalDemoSegment";

export const VideoComposition: React.FC<VideoCompositionProps> = (props) => {
  const {
    script,
    timing,
    fps,
    slidesDir,
    recordingsDir,
    sourceVideoFiles = [],
    sourceChannels = [],
    voiceoverFile,
    availableRecordings = [],
  } = props;
  const segments = script.segments;

  // 预计算素材 A 段总数及每个 segment 的 slide 序号
  const totalSlides = useMemo(
    () => segments.filter((s) => s.material === "A").length,
    [segments]
  );
  const slideIndexMap = useMemo(() => {
    const map = new Map<number, number>();
    let idx = 0;
    for (const seg of segments) {
      if (seg.material === "A") {
        idx++;
        map.set(seg.id, idx);
      }
    }
    return map;
  }, [segments]);

  const renderSegment = (seg: ScriptSegment) => {
    switch (seg.material) {
      case "A": {
        return (
          <SlideSegment
            slideContent={
              seg.slide_content || {
                title: "Info",
                bullet_points: [],
              }
            }
            segmentId={slideIndexMap.get(seg.id) || 1}
            totalSlides={totalSlides}
          />
        );
      }
      case "B": {
        const recFile = `${recordingsDir}/seg_${seg.id}.mp4`;
        const hasRecording = availableRecordings.includes(seg.id);
        if (hasRecording) {
          return <RecordingSegment recordingFile={recFile} />;
        }
        // 无录屏时降级为终端模拟演示
        const instruction = seg.recording_instruction || "需要录屏";
        return <TerminalDemoSegment instruction={instruction} />;
      }
      case "C": {
        const t = timing[String(seg.id)];
        const ttsDur = t ? t.duration : 10;
        // 多源: 按 source_video_index 选择视频; 单源: 用第一个
        const idx = seg.source_video_index ?? 0;
        const videoFile = sourceVideoFiles[idx] || sourceVideoFiles[0] || "";
        const channel = sourceChannels[idx] || script.source_channel || "";
        return (
          <SourceClipSegment
            sourceVideoFile={videoFile}
            sourceStart={seg.source_start || 0}
            sourceEnd={Math.min(seg.source_end || 8, (seg.source_start || 0) + 10)}
            sourceChannel={channel}
            ttsDuration={ttsDur}
          />
        );
      }
      default:
        return (
          <AbsoluteFill style={{ backgroundColor: "#000" }} />
        );
    }
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
