/**
 * WavyPaperBg — 米白纸张 + 手绘水平波纹背景
 *
 * Anthropic 品牌片的标志性背景：淡米白 + 从上到下均布的手绘波纹。
 * 纯 SVG 实现，零依赖，任意组件可直接 <WavyPaperBg /> 包一层。
 */

import React, { useMemo } from "react";
import { AbsoluteFill } from "remotion";

interface WavyPaperBgProps {
  /** 纸张底色，默认米白 */
  bgColor?: string;
  /** 波纹线条色，支持 rgba */
  lineColor?: string;
  /** 波纹根数 */
  lineCount?: number;
  /** 波幅 */
  amplitude?: number;
  /** 线条粗细 */
  strokeWidth?: number;
}

export const WavyPaperBg: React.FC<WavyPaperBgProps> = ({
  bgColor = "#f3f0e6",
  lineColor = "rgba(80, 70, 50, 0.07)",
  lineCount = 16,
  amplitude = 14,
  strokeWidth = 1.4,
}) => {
  const paths = useMemo(() => {
    const out: React.ReactNode[] = [];
    const step = 1080 / (lineCount + 1);
    for (let i = 0; i < lineCount; i++) {
      const baseY = step * (i + 1);
      // 每条线用 6 段 quadratic bezier 组合出"手绘波浪"感；相位按 i 偏移。
      const phase = i * 0.8;
      const segments = 6;
      const segW = 1920 / segments;
      let d = `M 0 ${baseY}`;
      for (let k = 0; k < segments; k++) {
        const cx = segW * (k + 0.5);
        const cy = baseY + Math.sin(phase + k * 1.3) * amplitude;
        const ex = segW * (k + 1);
        const ey = baseY + Math.sin(phase + (k + 1) * 1.1) * (amplitude * 0.6);
        d += ` Q ${cx} ${cy}, ${ex} ${ey}`;
      }
      out.push(
        <path
          key={i}
          d={d}
          fill="none"
          stroke={lineColor}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />,
      );
    }
    return out;
  }, [lineCount, amplitude, strokeWidth, lineColor]);

  return (
    <AbsoluteFill style={{ backgroundColor: bgColor }}>
      <svg
        width="100%"
        height="100%"
        viewBox="0 0 1920 1080"
        preserveAspectRatio="none"
        style={{ position: "absolute", inset: 0 }}
      >
        {paths}
      </svg>
    </AbsoluteFill>
  );
};
