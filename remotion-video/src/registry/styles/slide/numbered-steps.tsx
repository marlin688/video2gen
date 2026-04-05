/**
 * slide.numbered-steps — 编号步骤卡片
 *
 * 大号序号 (01, 02, 03...) + 步骤描述，水平或垂直排列。
 * 适合教程步骤、安装指南、操作流程。
 */

import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import React from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";

const STEP_ACCENTS = ["#4a9eff", "#a882ff", "#22c55e", "#eab308", "#f472b6", "#38bdf8"];

const SlideNumberedSteps: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();
  const items = data.bullet_points;
  const isHorizontal = items.length <= 4;

  return (
    <AbsoluteFill style={{ background: t.bg, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "50px 100px", fontFamily: t.bodyFont }}>
      <div style={{
        fontSize: 32, fontWeight: 700, color: t.text, marginBottom: 50, fontFamily: t.titleFont,
        opacity: interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp", extrapolateLeft: "clamp" }),
      }}>
        {data.title}
      </div>

      <div style={{
        display: "flex", flexDirection: isHorizontal ? "row" : "column",
        gap: isHorizontal ? 32 : 24, alignItems: isHorizontal ? "flex-start" : "stretch",
        maxWidth: 1400, width: "100%",
      }}>
        {items.map((item, i) => {
          const delay = 10 + i * 10;
          const p = spring({ frame: Math.max(0, frame - delay), fps, config: { damping: 14, stiffness: 100 }, durationInFrames: 18 });
          const accent = STEP_ACCENTS[i % STEP_ACCENTS.length];
          const num = String(i + 1).padStart(2, "0");

          return (
            <div key={i} style={{
              flex: isHorizontal ? 1 : undefined,
              display: "flex", flexDirection: isHorizontal ? "column" : "row",
              alignItems: isHorizontal ? "center" : "center",
              gap: isHorizontal ? 16 : 24,
              padding: isHorizontal ? "28px 20px" : "20px 28px",
              borderRadius: 16, background: t.surface, border: `1px solid ${t.surfaceBorder}`,
              opacity: interpolate(p, [0, 1], [0, 1]),
              transform: isHorizontal
                ? `translateY(${interpolate(p, [0, 1], [30, 0])}px)`
                : `translateX(${interpolate(p, [0, 1], [-30, 0])}px)`,
            }}>
              <span style={{
                fontSize: isHorizontal ? 48 : 40, fontWeight: 800, color: accent,
                fontFamily: t.titleFont, lineHeight: 1, opacity: 0.9,
              }}>
                {num}
              </span>
              <span style={{
                fontSize: isHorizontal ? 19 : 22, color: t.text, fontWeight: 500,
                textAlign: isHorizontal ? "center" as const : "left" as const,
                lineHeight: 1.4,
              }}>
                {item}
              </span>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

registry.register({ id: "slide.numbered-steps", schema: "slide", name: "编号步骤", description: "大号序号 (01, 02, 03) + 步骤描述卡片。≤4 项水平排列，>4 项垂直列表。适合教程步骤、安装指南。", isDefault: false, tags: ["步骤", "教程", "指南", "编号"] }, SlideNumberedSteps);
export { SlideNumberedSteps };
