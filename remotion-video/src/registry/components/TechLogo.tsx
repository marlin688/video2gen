/**
 * TechLogo -- 弹入 + 浮动 + 光晕 Logo
 *
 * spring 弹入缩放 + sin Y 轴浮动 + sin 光晕脉冲。
 */

import React from "react";
import { Img, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { useTheme } from "../theme";

interface TechLogoProps {
  src: string;
  size?: number;
  brandColor?: string;
}

export const TechLogo: React.FC<TechLogoProps> = ({
  src,
  size = 120,
  brandColor,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const theme = useTheme();
  const resolvedColor = brandColor || theme.accent;

  const scaleSpring = spring({
    fps,
    frame,
    config: { mass: 0.5, damping: 12 },
  });

  const floatY = Math.sin(frame * 0.05) * 3;
  const glowPulse = Math.sin(frame * 0.1) * 0.3 + 0.7;

  const resolvedSrc = src.startsWith("http") ? src : staticFile(src);

  return (
    <div
      style={{
        width: size,
        height: size,
        transform: `scale(${scaleSpring}) translateY(${floatY}px)`,
        borderRadius: size * 0.2,
        boxShadow: `0 0 ${glowPulse * 30}px ${resolvedColor}60`,
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        overflow: "hidden",
      }}
    >
      <Img
        src={resolvedSrc}
        style={{ width: size, height: size, objectFit: "contain" }}
      />
    </div>
  );
};
