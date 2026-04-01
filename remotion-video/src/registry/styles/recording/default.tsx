/**
 * recording.default — 录屏播放
 */

import { AbsoluteFill, staticFile } from "remotion";
import { Video } from "@remotion/media";
import React from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";

const RecordingDefault: React.FC<StyleComponentProps<"recording">> = ({ data }) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <Video
        src={staticFile(data.recordingFile)}
        muted
        style={{ width: "100%", height: "100%", objectFit: "contain" }}
      />
    </AbsoluteFill>
  );
};

registry.register(
  {
    id: "recording.default",
    schema: "recording",
    name: "录屏播放",
    description: "直接播放录屏视频文件，全屏 contain 适配。用于有现成录屏素材的 B 类段落。",
    isDefault: true,
    tags: ["录屏", "视频播放"],
  },
  RecordingDefault,
);

export { RecordingDefault };
