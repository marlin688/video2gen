/**
 * ConstellationBg -- 星座网络背景
 *
 * 随机分布的圆点 + 距离内连线，整体缓慢漂移。
 * alea 确定性随机，SVG 渲染。
 */

import React, { useMemo } from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import alea from "alea";
import { useTheme } from "../theme";

interface ConstellationBgProps {
  nodeCount?: number;
  color?: string;
  seed?: string;
  connectionDistance?: number;
  opacity?: number;
}

interface Node {
  baseX: number;
  baseY: number;
  driftSpeedX: number;
  driftSpeedY: number;
  phase: number;
}

export const ConstellationBg: React.FC<ConstellationBgProps> = ({
  nodeCount = 30,
  color,
  seed = "constellation",
  connectionDistance = 200,
  opacity = 0.12,
}) => {
  const frame = useCurrentFrame();
  const theme = useTheme();
  const resolvedColor = color || theme.accent;

  const nodes = useMemo(() => {
    const rng = alea(seed);
    return Array.from({ length: nodeCount }).map((): Node => ({
      baseX: rng() * 1920,
      baseY: rng() * 1080,
      driftSpeedX: (rng() - 0.5) * 0.4,
      driftSpeedY: (rng() - 0.5) * 0.3,
      phase: rng() * Math.PI * 2,
    }));
  }, [nodeCount, seed]);

  const positions = nodes.map((n) => ({
    x: n.baseX + Math.sin(frame * 0.01 + n.phase) * 30 + frame * n.driftSpeedX,
    y: n.baseY + Math.cos(frame * 0.008 + n.phase) * 25 + frame * n.driftSpeedY,
  }));

  const lines: { x1: number; y1: number; x2: number; y2: number; dist: number }[] = [];
  for (let i = 0; i < positions.length; i++) {
    for (let j = i + 1; j < positions.length; j++) {
      const dx = positions[i].x - positions[j].x;
      const dy = positions[i].y - positions[j].y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < connectionDistance) {
        lines.push({
          x1: positions[i].x,
          y1: positions[i].y,
          x2: positions[j].x,
          y2: positions[j].y,
          dist,
        });
      }
    }
  }

  return (
    <AbsoluteFill style={{ opacity, pointerEvents: "none" }}>
      <svg width="1920" height="1080">
        {lines.map((line, i) => {
          const lineOpacity = interpolate(
            line.dist,
            [0, connectionDistance],
            [0.6, 0],
            { extrapolateRight: "clamp" },
          );
          return (
            <line
              key={`l${i}`}
              x1={line.x1}
              y1={line.y1}
              x2={line.x2}
              y2={line.y2}
              stroke={resolvedColor}
              strokeWidth={1}
              opacity={lineOpacity}
            />
          );
        })}
        {positions.map((pos, i) => (
          <circle
            key={`n${i}`}
            cx={pos.x}
            cy={pos.y}
            r={2}
            fill={resolvedColor}
            opacity={0.8}
          />
        ))}
      </svg>
    </AbsoluteFill>
  );
};
