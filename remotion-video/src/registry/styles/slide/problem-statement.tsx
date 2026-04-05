/**
 * slide.problem-statement — 痛点展示
 *
 * 红色/警告风格，情绪是"焦虑"。
 * title = 痛点标题，bullet_points = 具体问题列表。
 * 配合 solution-reveal 组件形成情绪对比。
 */

import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import React from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";

const SlideProblemStatement: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  const titleP = spring({ frame: Math.max(0, frame - 3), fps, config: { damping: 12, stiffness: 100 }, durationInFrames: 18 });
  // 背景脉冲（焦虑感）
  const pulse = Math.sin(frame * 0.06) * 0.02;

  return (
    <AbsoluteFill style={{ background: t.bg, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "60px 120px" }}>
      {/* 红色光晕 */}
      <div style={{
        position: "absolute", width: 700, height: 700, borderRadius: "50%",
        background: `radial-gradient(circle, ${t.danger}20, transparent 70%)`,
        filter: "blur(80px)", opacity: 0.7 + pulse,
      }} />

      {/* 警告图标 */}
      <div style={{
        position: "relative", zIndex: 1,
        width: 64, height: 64, borderRadius: "50%",
        background: `${t.danger}20`, border: `2px solid ${t.danger}50`,
        display: "flex", alignItems: "center", justifyContent: "center",
        marginBottom: 28,
        opacity: interpolate(titleP, [0, 1], [0, 1]),
        transform: `scale(${interpolate(titleP, [0, 1], [0.5, 1])})`,
      }}>
        <span style={{ fontSize: 32, color: t.danger }}>⚠</span>
      </div>

      {/* 标题 */}
      <div style={{
        position: "relative", zIndex: 1,
        fontSize: 48, fontWeight: 800, color: t.danger, fontFamily: t.titleFont,
        textAlign: "center" as const, lineHeight: 1.3, marginBottom: 40,
        opacity: interpolate(titleP, [0, 1], [0, 1]),
        transform: `scale(${interpolate(titleP, [0, 1], [1.1, 1])})`,
      }}>
        {data.title}
      </div>

      {/* 问题列表 */}
      <div style={{
        position: "relative", zIndex: 1,
        display: "flex", flexDirection: "column", gap: 16,
        maxWidth: 1000, width: "100%",
      }}>
        {data.bullet_points.map((item, i) => {
          const delay = 12 + i * 8;
          const p = spring({ frame: Math.max(0, frame - delay), fps, config: { damping: 16, stiffness: 100 }, durationInFrames: 15 });
          return (
            <div key={i} style={{
              display: "flex", alignItems: "center", gap: 16,
              padding: "16px 24px", borderRadius: 12,
              background: `${t.danger}08`, borderLeft: `3px solid ${t.danger}60`,
              opacity: interpolate(p, [0, 1], [0, 1]),
              transform: `translateX(${interpolate(p, [0, 1], [-30, 0])}px)`,
            }}>
              <span style={{ fontSize: 20, color: t.danger }}>✗</span>
              <span style={{ fontSize: 22, color: t.textDim, fontFamily: t.bodyFont }}>{item}</span>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

registry.register({ id: "slide.problem-statement", schema: "slide", name: "痛点展示", description: "红色警告风格痛点展示：⚠ 图标 + 红色标题 + 红边框问题列表。情绪是焦虑/紧迫。配合 solution-reveal 形成叙事对比。", isDefault: false, tags: ["痛点", "问题", "焦虑", "警告"] }, SlideProblemStatement);
export { SlideProblemStatement };
