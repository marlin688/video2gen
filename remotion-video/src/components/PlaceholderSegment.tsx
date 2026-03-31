/**
 * 素材 B 占位: 录屏缺失时显示简要操作提示
 */

import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";

interface PlaceholderSegmentProps {
  instruction: string;
}

export const PlaceholderSegment: React.FC<PlaceholderSegmentProps> = ({ instruction }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: "clamp" });
  const shortText = "待录屏: " + instruction.slice(0, 30);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#1a1a2e",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "'PingFang SC', sans-serif",
        opacity,
      }}
    >
      <div
        style={{
          fontSize: 42,
          color: "#aaaaaa",
          textAlign: "center",
          padding: "0 100px",
        }}
      >
        {shortText}
      </div>
    </AbsoluteFill>
  );
};
