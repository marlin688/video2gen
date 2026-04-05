/**
 * slide.result-showcase — 成果展示
 *
 * 蓝色/成就风格，带大数字 + 成就徽章感。
 * title = 成果标题，bullet_points = 成果数据（数字+描述格式）。
 * 叙事三段式的最后一环：problem → solution → result。
 */

import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import React from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";

const RESULT_COLORS = ["#4a9eff", "#a882ff", "#22c55e", "#38bdf8", "#f472b6"];

const SlideResultShowcase: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  const titleP = spring({ frame: Math.max(0, frame - 3), fps, config: { damping: 12, stiffness: 100 }, durationInFrames: 18 });

  return (
    <AbsoluteFill style={{ background: t.bg, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "60px 100px" }}>
      {/* 蓝色光晕 */}
      <div style={{
        position: "absolute", width: 800, height: 800, borderRadius: "50%",
        background: `radial-gradient(circle, ${t.accent}15, transparent 70%)`,
        filter: "blur(80px)", opacity: 0.8,
      }} />

      {/* 标题 */}
      <div style={{
        position: "relative", zIndex: 1,
        fontSize: 40, fontWeight: 800, color: t.text, fontFamily: t.titleFont,
        textAlign: "center" as const, lineHeight: 1.3, marginBottom: 50,
        opacity: interpolate(titleP, [0, 1], [0, 1]),
        transform: `translateY(${interpolate(titleP, [0, 1], [-20, 0])}px)`,
      }}>
        {data.title}
      </div>

      {/* 成果卡片行 */}
      <div style={{
        position: "relative", zIndex: 1,
        display: "flex", gap: 28, justifyContent: "center", flexWrap: "wrap" as const,
        maxWidth: 1400,
      }}>
        {data.bullet_points.map((item, i) => {
          const delay = 12 + i * 10;
          const p = spring({ frame: Math.max(0, frame - delay), fps, config: { damping: 12, stiffness: 80 }, durationInFrames: 20 });
          const color = RESULT_COLORS[i % RESULT_COLORS.length];

          // 解析 "95% 任务成功率" 或 "减少 80% 手动操作"
          const numMatch = item.match(/([\d.]+\s*[%倍xKkM+]*)/);
          const num = numMatch ? numMatch[1] : "";
          const label = item.replace(num, "").trim();

          return (
            <div key={i} style={{
              display: "flex", flexDirection: "column", alignItems: "center",
              gap: 12, padding: "32px 36px", borderRadius: 20,
              background: t.surface, border: `1px solid ${t.surfaceBorder}`,
              borderTop: `3px solid ${color}`,
              minWidth: 200,
              opacity: interpolate(p, [0, 1], [0, 1]),
              transform: `scale(${interpolate(p, [0, 1], [0.85, 1])}) translateY(${interpolate(p, [0, 1], [30, 0])}px)`,
            }}>
              {num && (
                <div style={{
                  fontSize: 52, fontWeight: 900, color,
                  fontFamily: t.titleFont, lineHeight: 1, letterSpacing: "-0.02em",
                }}>
                  {num}
                </div>
              )}
              <div style={{
                fontSize: 18, color: t.textDim, fontFamily: t.bodyFont,
                textAlign: "center" as const, maxWidth: 200,
              }}>
                {label}
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

registry.register({ id: "slide.result-showcase", schema: "slide", name: "成果展示", description: "蓝色成就风格成果展示：大数字 + 描述卡片 + 彩色顶线。bullet_points 含数字时自动提取为大字。叙事三段式终章：problem→solution→result。", isDefault: false, tags: ["成果", "成就", "结果", "数据"] }, SlideResultShowcase);
export { SlideResultShowcase };
