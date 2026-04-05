/**
 * slide.solution-reveal — 方案展示
 *
 * 绿色/成功风格，情绪是"释然"。
 * title = 方案标题，bullet_points = 具体解决方案。
 * 配合 problem-statement 组件形成情绪对比。
 */

import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import React from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";

const SlideSolutionReveal: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  const titleP = spring({ frame: Math.max(0, frame - 3), fps, config: { damping: 12, stiffness: 100 }, durationInFrames: 18 });

  return (
    <AbsoluteFill style={{ background: t.bg, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "60px 120px" }}>
      {/* 绿色光晕 */}
      <div style={{
        position: "absolute", width: 700, height: 700, borderRadius: "50%",
        background: `radial-gradient(circle, ${t.success}18, transparent 70%)`,
        filter: "blur(80px)", opacity: 0.7,
      }} />

      {/* 成功图标 */}
      <div style={{
        position: "relative", zIndex: 1,
        width: 64, height: 64, borderRadius: "50%",
        background: `${t.success}20`, border: `2px solid ${t.success}50`,
        display: "flex", alignItems: "center", justifyContent: "center",
        marginBottom: 28,
        opacity: interpolate(titleP, [0, 1], [0, 1]),
        transform: `scale(${interpolate(titleP, [0, 1], [0.5, 1])})`,
      }}>
        <span style={{ fontSize: 32, color: t.success }}>✓</span>
      </div>

      {/* 标题 */}
      <div style={{
        position: "relative", zIndex: 1,
        fontSize: 48, fontWeight: 800, color: t.success, fontFamily: t.titleFont,
        textAlign: "center" as const, lineHeight: 1.3, marginBottom: 40,
        opacity: interpolate(titleP, [0, 1], [0, 1]),
        transform: `translateY(${interpolate(titleP, [0, 1], [20, 0])}px)`,
      }}>
        {data.title}
      </div>

      {/* 方案列表 */}
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
              background: `${t.success}08`, borderLeft: `3px solid ${t.success}60`,
              opacity: interpolate(p, [0, 1], [0, 1]),
              transform: `translateX(${interpolate(p, [0, 1], [30, 0])}px)`,
            }}>
              <span style={{ fontSize: 20, color: t.success }}>✓</span>
              <span style={{ fontSize: 22, color: t.text, fontWeight: 600, fontFamily: t.bodyFont }}>{item}</span>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

registry.register({ id: "slide.solution-reveal", schema: "slide", name: "方案展示", description: "绿色成功风格方案展示：✓ 图标 + 绿色标题 + 绿边框方案列表。情绪是释然/解决。配合 problem-statement 形成叙事对比。", isDefault: false, tags: ["方案", "解决", "成功", "释然"] }, SlideSolutionReveal);
export { SlideSolutionReveal };
