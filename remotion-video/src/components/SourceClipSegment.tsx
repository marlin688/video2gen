/**
 * 素材 C: 原视频片段
 * 原速播放 + 播完定格最后一帧 + 底部遮挡 + Source 水印
 */

import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { Video } from "@remotion/media";
import { staticFile } from "remotion";

interface SourceClipSegmentProps {
  sourceVideoFile: string;
  sourceStart: number;  // 秒
  sourceEnd: number;    // 秒
  sourceChannel: string;
  ttsDuration: number;  // TTS 配音时长（秒）
}

export const SourceClipSegment: React.FC<SourceClipSegmentProps> = ({
  sourceVideoFile,
  sourceStart,
  sourceEnd,
  sourceChannel,
  ttsDuration,
}) => {
  const { fps } = useVideoConfig();
  const frame = useCurrentFrame();

  // 直接从 sourceStart 取 ttsDuration 长度的片段，原速播放
  const adjustedEnd = sourceStart + ttsDuration;

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <Video
        src={staticFile(sourceVideoFile)}
        trimBefore={Math.round(sourceStart * fps)}
        trimAfter={Math.round(adjustedEnd * fps)}
        playbackRate={1}
        muted
        style={{
          width: "100%",
          height: "100%",
          objectFit: "contain",
        }}
      />

      {/* 底部遮罩: 遮挡原视频英文硬字幕 */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: "15%",
          background: "linear-gradient(transparent, rgba(0,0,0,0.95) 40%)",
        }}
      />

    </AbsoluteFill>
  );
};
