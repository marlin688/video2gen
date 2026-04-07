/**
 * LightLeak -- 程序化光晕叠加层
 *
 * 使用 simplex-noise + alea 实现确定性有机运动（Remotion 帧确定性要求）。
 * 两个径向渐变光斑 + 一个水平变形光条，mixBlendMode: "screen"。
 */

import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { createNoise2D } from "simplex-noise";
import alea from "alea";
import { useTheme } from "../theme";

interface LightLeakProps {
  color1?: string;
  color2?: string;
  seed?: string;
  intensity?: number;
}

export const LightLeak: React.FC<LightLeakProps> = ({
  color1,
  color2,
  seed = "light-leak",
  intensity = 0.3,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const theme = useTheme();

  const c1 = color1 || theme.accent;
  const c2 = color2 || theme.orbColor2 || theme.accentDim || theme.accent;

  const rng = alea(seed);
  const noise = createNoise2D(rng);

  // 渐入渐出包络
  const fadeIn = spring({ fps, frame, config: { damping: 200 } });
  const fadeOut = interpolate(
    frame,
    [durationInFrames - 15, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const envelope = fadeIn * fadeOut;

  // 噪声驱动的有机运动
  const t = frame * 0.02;
  const x1 = interpolate(noise(t, 0), [-1, 1], [10, 70]);
  const y1 = interpolate(noise(t, 100), [-1, 1], [10, 60]);
  const x2 = interpolate(noise(t + 50, 200), [-1, 1], [30, 90]);
  const y2 = interpolate(noise(t + 50, 300), [-1, 1], [20, 80]);
  const scale1 = interpolate(noise(t, 400), [-1, 1], [0.8, 1.4]);
  const scale2 = interpolate(noise(t + 30, 500), [-1, 1], [0.6, 1.2]);

  return (
    <AbsoluteFill
      style={{
        opacity: envelope * intensity,
        mixBlendMode: "screen",
        pointerEvents: "none",
      }}
    >
      {/* 暖色主光斑 */}
      <div
        style={{
          position: "absolute",
          left: `${x1}%`,
          top: `${y1}%`,
          width: 600 * scale1,
          height: 400 * scale1,
          borderRadius: "50%",
          background: `radial-gradient(ellipse at center, ${c1}90 0%, ${c1}30 40%, transparent 70%)`,
          filter: "blur(80px)",
          transform: `translate(-50%, -50%) rotate(${frame * 0.5}deg)`,
        }}
      />
      {/* 冷色副光斑 */}
      <div
        style={{
          position: "absolute",
          left: `${x2}%`,
          top: `${y2}%`,
          width: 500 * scale2,
          height: 350 * scale2,
          borderRadius: "50%",
          background: `radial-gradient(ellipse at center, ${c2}70 0%, ${c2}20 40%, transparent 70%)`,
          filter: "blur(100px)",
          transform: `translate(-50%, -50%) rotate(${-frame * 0.3}deg)`,
        }}
      />
      {/* 变形光条 */}
      <div
        style={{
          position: "absolute",
          left: `${(x1 + x2) / 2}%`,
          top: "50%",
          width: 1200,
          height: 40,
          background: `linear-gradient(90deg, transparent, ${c1}40, ${c2}30, transparent)`,
          filter: "blur(20px)",
          transform: `translate(-50%, -50%) scaleX(${scale1})`,
          opacity: interpolate(noise(t, 600), [-1, 1], [0.3, 0.8]),
        }}
      />
    </AbsoluteFill>
  );
};
