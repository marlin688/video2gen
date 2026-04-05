/**
 * slide.transition-bridge — 段落过渡
 *
 * "但是…"、"接下来"、"然而"等转折句，带方向性动画。
 * title = 过渡文案，bullet_points[0] = 可选下一段预告。
 */

import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import React from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";

const SlideTransitionBridge: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  const slideP = spring({ frame: Math.max(0, frame - 2), fps, config: { damping: 14, stiffness: 80 }, durationInFrames: 22 });
  const lineP = spring({ frame: Math.max(0, frame - 8), fps, config: { damping: 20, stiffness: 60 }, durationInFrames: 30 });
  const previewP = spring({ frame: Math.max(0, frame - 25), fps, config: { damping: 16, stiffness: 100 }, durationInFrames: 15 });

  const preview = data.bullet_points[0] || "";

  return (
    <AbsoluteFill style={{ background: t.bg, display: "flex", alignItems: "center", justifyContent: "center" }}>
      {/* 水平线动画 */}
      <div style={{
        position: "absolute", left: "10%", right: "10%", top: "50%",
        height: 2, background: t.surfaceBorder,
        transform: `scaleX(${interpolate(lineP, [0, 1], [0, 1])})`,
        transformOrigin: "left center",
      }} />

      <div style={{
        position: "relative", zIndex: 1, textAlign: "center" as const, padding: "0 100px",
      }}>
        {/* 主文案 */}
        <div style={{
          fontSize: 56, fontWeight: 800, color: t.accent,
          fontFamily: t.titleFont, letterSpacing: "-0.01em",
          opacity: interpolate(slideP, [0, 1], [0, 1]),
          transform: `translateX(${interpolate(slideP, [0, 1], [-80, 0])}px)`,
        }}>
          {data.title}
        </div>

        {/* 预告 */}
        {preview && (
          <div style={{
            marginTop: 24, fontSize: 24, color: t.textDim, fontWeight: 500,
            fontFamily: t.bodyFont,
            opacity: interpolate(previewP, [0, 1], [0, 1]),
            transform: `translateX(${interpolate(previewP, [0, 1], [40, 0])}px)`,
          }}>
            {preview}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};

registry.register({ id: "slide.transition-bridge", schema: "slide", name: "段落过渡", description: "转折/过渡文案，带水平线展开和滑入动画。title = '但是…' / '接下来' 等过渡句，bullet_points[0] = 下一段预告。", isDefault: false, tags: ["过渡", "转折", "bridge", "transition"] }, SlideTransitionBridge);
export { SlideTransitionBridge };
