/**
 * slide.checklist — 动画清单
 *
 * 每个 bullet_point 逐个出现并打勾。适合步骤总结、功能列表、要点回顾。
 */

import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import React from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";

const SlideChecklist: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  return (
    <AbsoluteFill style={{ background: t.bg, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "60px 160px", fontFamily: t.bodyFont }}>
      {/* 标题 */}
      <div style={{
        fontSize: 36, fontWeight: 700, color: t.text, marginBottom: 48, fontFamily: t.titleFont,
        opacity: interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp", extrapolateLeft: "clamp" }),
      }}>
        {data.title}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 24, width: "100%", maxWidth: 1100 }}>
        {data.bullet_points.map((item, i) => {
          const delay = 12 + i * 14;
          const slideP = spring({ frame: Math.max(0, frame - delay), fps, config: { damping: 16, stiffness: 100 }, durationInFrames: 15 });
          const checkP = spring({ frame: Math.max(0, frame - delay - 8), fps, config: { damping: 12, stiffness: 120 }, durationInFrames: 12 });

          return (
            <div key={i} style={{
              display: "flex", alignItems: "center", gap: 20,
              opacity: interpolate(slideP, [0, 1], [0, 1]),
              transform: `translateX(${interpolate(slideP, [0, 1], [-40, 0])}px)`,
            }}>
              {/* Checkbox */}
              <div style={{
                width: 36, height: 36, borderRadius: 10, flexShrink: 0,
                border: `2px solid ${interpolate(checkP, [0, 1], [0, 1]) > 0.5 ? t.success : t.surfaceBorder}`,
                background: interpolate(checkP, [0, 1], [0, 1]) > 0.5 ? `${t.success}20` : "transparent",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <span style={{
                  fontSize: 22, color: t.success, fontWeight: 700,
                  opacity: interpolate(checkP, [0, 1], [0, 1]),
                  transform: `scale(${interpolate(checkP, [0, 1], [0, 1.2])})`,
                }}>
                  ✓
                </span>
              </div>
              {/* 文字 */}
              <span style={{ fontSize: 24, color: t.text, fontWeight: 500 }}>{item}</span>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

registry.register({ id: "slide.checklist", schema: "slide", name: "动画清单", description: "逐项出现并打勾的清单。每个 bullet_point 是一个清单项，带绿色打勾动画。适合步骤总结、功能列表、要点回顾。", isDefault: false, tags: ["清单", "步骤", "总结", "checklist"] }, SlideChecklist);
export { SlideChecklist };
