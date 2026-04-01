/**
 * source-clip.default — 原视频片段裁剪播放
 */

import { AbsoluteFill, useVideoConfig, staticFile } from "remotion";
import { Video } from "@remotion/media";
import React from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";

const SourceClipDefault: React.FC<StyleComponentProps<"source-clip">> = ({ data, fps: _fps }) => {
  const { fps } = useVideoConfig();
  const adjustedEnd = data.sourceStart + data.ttsDuration;

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <Video
        src={staticFile(data.sourceVideoFile)}
        trimBefore={Math.round(data.sourceStart * fps)}
        trimAfter={Math.round(adjustedEnd * fps)}
        playbackRate={1}
        muted
        style={{ width: "100%", height: "100%", objectFit: "contain" }}
      />

      {/* 底部遮罩: 遮挡原视频英文硬字幕 */}
      <div style={{
        position: "absolute", bottom: 0, left: 0, right: 0,
        height: "15%",
        background: "linear-gradient(transparent, rgba(0,0,0,0.95) 40%)",
      }} />
    </AbsoluteFill>
  );
};

registry.register(
  {
    id: "source-clip.default",
    schema: "source-clip",
    name: "原视频片段",
    description: "裁剪并播放原视频的指定时间段，底部遮罩隐藏硬字幕。用于引用原视频精华片段（C 类素材）。",
    isDefault: true,
    tags: ["原视频", "片段裁剪"],
  },
  SourceClipDefault,
);

export { SourceClipDefault };
