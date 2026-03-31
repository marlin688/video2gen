/**
 * 素材 B: 操作录屏（有录屏文件时使用）
 */

import { AbsoluteFill } from "remotion";
import { Video } from "@remotion/media";
import { staticFile } from "remotion";

interface RecordingSegmentProps {
  recordingFile: string; // public/ 下的录屏文件名
}

export const RecordingSegment: React.FC<RecordingSegmentProps> = ({ recordingFile }) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <Video
        src={staticFile(recordingFile)}
        muted
        style={{
          width: "100%",
          height: "100%",
          objectFit: "contain",
        }}
      />
    </AbsoluteFill>
  );
};
