/**
 * ProgressBar -- 底部视频进度条
 *
 * 4px 进度条 + 段落标记点。
 */

import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { useTheme } from "../theme";

interface ProgressBarProps {
  color?: string;
  sectionStartFrames: number[];
  dotColor?: string;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  color,
  sectionStartFrames,
  dotColor,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const theme = useTheme();
  const resolvedColor = color || theme.accent;

  const progress = interpolate(frame, [0, durationInFrames], [0, 100], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {/* Track */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          width: "100%",
          height: 4,
          backgroundColor: `${resolvedColor}22`,
        }}
      >
        {/* Fill */}
        <div
          style={{
            width: `${progress}%`,
            height: "100%",
            backgroundColor: resolvedColor,
          }}
        />
      </div>

      {/* Section marker dots */}
      {sectionStartFrames.map((startFrame, i) => {
        const dotX = (startFrame / durationInFrames) * 100;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              bottom: 0,
              left: `${dotX}%`,
              width: 6,
              height: 6,
              borderRadius: 3,
              backgroundColor: dotColor ?? resolvedColor,
              transform: "translate(-50%, 1px)",
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};
