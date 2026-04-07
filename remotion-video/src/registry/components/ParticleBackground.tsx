/**
 * ParticleBackground -- 上升粒子背景
 *
 * 粒子从底部缓慢上升，顶底渐隐。
 * alea 确定性随机，SVG 渲染。
 */

import React, { useMemo } from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import alea from "alea";
import { useTheme } from "../theme";

interface ParticleBackgroundProps {
  count?: number;
  colors?: [string, string];
  opacity?: number;
  seed?: string;
}

interface Particle {
  x: number;
  y: number;
  size: number;
  speed: number;
  colorIndex: number;
}

export const ParticleBackground: React.FC<ParticleBackgroundProps> = ({
  count = 16,
  colors,
  opacity = 0.4,
  seed = "particles",
}) => {
  const frame = useCurrentFrame();
  const theme = useTheme();
  const resolvedColors = colors || [theme.accent, theme.accentDim];

  const particles = useMemo(() => {
    const rng = alea(seed);
    return Array.from({ length: count }).map((): Particle => ({
      x: rng() * 1920,
      y: rng() * 1080,
      size: 2 + rng() * 4,
      speed: 0.5 + rng() * 1.0,
      colorIndex: rng() > 0.5 ? 1 : 0,
    }));
  }, [count, seed]);

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <svg width="1920" height="1080">
        {particles.map((p, i) => {
          const y = 1080 - ((frame * p.speed + p.y) % 1200);
          const x = p.x + Math.sin(frame * 0.02 + i) * 30;
          const particleOpacity = interpolate(
            y,
            [0, 150, 900, 1080],
            [0, opacity, opacity, 0],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
          );

          return (
            <circle
              key={i}
              cx={x}
              cy={y}
              r={p.size}
              fill={resolvedColors[p.colorIndex] ?? resolvedColors[0]}
              opacity={particleOpacity}
            />
          );
        })}
      </svg>
    </AbsoluteFill>
  );
};
