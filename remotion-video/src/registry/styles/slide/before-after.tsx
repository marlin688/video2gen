/**
 * slide.before-after — 前后对比分屏
 *
 * 左侧 Before（红/暗）→ 右侧 After（绿/亮），中间分隔线。
 * title = 标题，bullet_points 前半 = Before 内容，后半 = After 内容。
 * 用 "---" 分隔前后，或自动对半分。
 */

import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import React from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";

function splitBeforeAfter(bullets: string[]): [string[], string[]] {
  const divider = bullets.indexOf("---");
  if (divider >= 0) return [bullets.slice(0, divider), bullets.slice(divider + 1)];
  const mid = Math.ceil(bullets.length / 2);
  return [bullets.slice(0, mid), bullets.slice(mid)];
}

const SlideBeforeAfter: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  const [before, after] = splitBeforeAfter(data.bullet_points);

  const leftP = spring({ frame: Math.max(0, frame - 5), fps, config: { damping: 14, stiffness: 80 }, durationInFrames: 20 });
  const dividerP = spring({ frame: Math.max(0, frame - 18), fps, config: { damping: 20, stiffness: 100 }, durationInFrames: 15 });
  const rightP = spring({ frame: Math.max(0, frame - 25), fps, config: { damping: 14, stiffness: 80 }, durationInFrames: 20 });

  return (
    <AbsoluteFill style={{ background: t.bg, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "50px 80px" }}>
      {/* 标题 */}
      <div style={{
        fontSize: 34, fontWeight: 700, color: t.text, fontFamily: t.titleFont,
        marginBottom: 40, textAlign: "center" as const,
        opacity: interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp", extrapolateLeft: "clamp" }),
      }}>
        {data.title}
      </div>

      <div style={{ display: "flex", width: "100%", maxWidth: 1400, gap: 0, alignItems: "stretch" }}>
        {/* Before 区 */}
        <div style={{
          flex: 1, padding: "32px 40px", borderRadius: "16px 0 0 16px",
          background: `${t.danger}10`, border: `1px solid ${t.danger}30`,
          opacity: interpolate(leftP, [0, 1], [0, 1]),
          transform: `translateX(${interpolate(leftP, [0, 1], [-40, 0])}px)`,
        }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: t.danger, fontFamily: t.monoFont, marginBottom: 20, textTransform: "uppercase" as const, letterSpacing: "0.1em" }}>
            ✗ Before
          </div>
          {before.map((item, i) => (
            <div key={i} style={{
              fontSize: 22, color: t.textDim, lineHeight: 1.7, fontFamily: t.bodyFont,
              padding: "8px 0", borderBottom: i < before.length - 1 ? `1px solid ${t.danger}15` : "none",
              textDecoration: "line-through" as const, textDecorationColor: `${t.danger}40`,
            }}>
              {item}
            </div>
          ))}
        </div>

        {/* 分隔线 + VS */}
        <div style={{
          width: 60, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
          opacity: interpolate(dividerP, [0, 1], [0, 1]),
        }}>
          <div style={{ flex: 1, width: 2, background: `linear-gradient(180deg, transparent, ${t.textMuted}, transparent)` }} />
          <div style={{
            width: 44, height: 44, borderRadius: "50%",
            background: t.surface, border: `2px solid ${t.surfaceBorder}`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 16, fontWeight: 800, color: t.textDim, fontFamily: t.monoFont,
          }}>
            VS
          </div>
          <div style={{ flex: 1, width: 2, background: `linear-gradient(180deg, transparent, ${t.textMuted}, transparent)` }} />
        </div>

        {/* After 区 */}
        <div style={{
          flex: 1, padding: "32px 40px", borderRadius: "0 16px 16px 0",
          background: `${t.success}10`, border: `1px solid ${t.success}30`,
          opacity: interpolate(rightP, [0, 1], [0, 1]),
          transform: `translateX(${interpolate(rightP, [0, 1], [40, 0])}px)`,
        }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: t.success, fontFamily: t.monoFont, marginBottom: 20, textTransform: "uppercase" as const, letterSpacing: "0.1em" }}>
            ✓ After
          </div>
          {after.map((item, i) => (
            <div key={i} style={{
              fontSize: 22, color: t.text, lineHeight: 1.7, fontFamily: t.bodyFont, fontWeight: 600,
              padding: "8px 0", borderBottom: i < after.length - 1 ? `1px solid ${t.success}15` : "none",
            }}>
              {item}
            </div>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};

registry.register({ id: "slide.before-after", schema: "slide", name: "前后对比", description: "左 Before(红/删除线) → 右 After(绿/加粗) 分屏对比。用 '---' 分隔前后内容，或自动对半分。适合效果对比、优化前后。", isDefault: false, tags: ["对比", "before", "after", "优化"] }, SlideBeforeAfter);
export { SlideBeforeAfter };
