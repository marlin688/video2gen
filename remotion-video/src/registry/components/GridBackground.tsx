/**
 * GridBackground -- 动画网格背景
 *
 * SVG 网格线覆盖层，可选动画滚动。
 */

import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { useTheme } from "../theme";

interface GridBackgroundProps {
  color?: string;
  spacing?: number;
  opacity?: number;
  animated?: boolean;
}

export const GridBackground: React.FC<GridBackgroundProps> = ({
  color,
  spacing = 48,
  opacity = 0.08,
  animated = false,
}) => {
  const frame = useCurrentFrame();
  const theme = useTheme();
  const resolvedColor = color || theme.gridLine;
  const offset = animated ? (frame * 0.3) % spacing : 0;

  const cols = Math.ceil(1920 / spacing) + 1;
  const rows = Math.ceil(1080 / spacing) + 1;

  return (
    <AbsoluteFill style={{ opacity, pointerEvents: "none" }}>
      <svg width="1920" height="1080">
        {Array.from({ length: cols }).map((_, i) => (
          <line
            key={`v${i}`}
            x1={i * spacing + offset}
            y1={0}
            x2={i * spacing + offset}
            y2={1080}
            stroke={resolvedColor}
            strokeWidth={1}
          />
        ))}
        {Array.from({ length: rows }).map((_, i) => (
          <line
            key={`h${i}`}
            x1={0}
            y1={i * spacing + offset}
            x2={1920}
            y2={i * spacing + offset}
            stroke={resolvedColor}
            strokeWidth={1}
          />
        ))}
      </svg>
    </AbsoluteFill>
  );
};
