/**
 * slide.hook-opener — 开场冲击
 *
 * 3-5 秒抓住注意力：大字问题/痛点 + 闪烁/缩放动画。
 * title = 冲击文案，bullet_points[0] = 小字补充（可选）。
 * 如"你还在手写代码？"、"这个工具，让 95% 的人用错了"
 */

import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import React from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";
import { GlowOrb } from "../../components/GlowOrb";
import { WordReveal } from "../../components/WordReveal";

const SlideHookOpener: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = useTheme();

  // 大字弹入
  const titleP = spring({ frame: Math.max(0, frame - 3), fps, config: { damping: 10, stiffness: 120 }, durationInFrames: 18 });
  // 闪烁脉冲
  const pulse = 1 + Math.sin(frame * 0.12) * 0.03;
  // 背景闪光
  const flash = frame < 8 ? interpolate(frame, [0, 4, 8], [0, 0.3, 0]) : 0;
  // 副标题
  const subP = spring({ frame: Math.max(0, frame - 20), fps, config: { damping: 16, stiffness: 100 }, durationInFrames: 15 });

  const sub = data.bullet_points[0] || "";

  return (
    <AbsoluteFill style={{ background: t.bg, display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden" }}>
      <GlowOrb intensity={0.2} seed="hook-orb" count={4} />
      {/* 中心光晕 */}
      <div style={{
        position: "absolute", width: 800, height: 800, borderRadius: "50%",
        background: `radial-gradient(circle, ${t.accentGlow}, transparent 70%)`,
        filter: "blur(80px)", opacity: 0.6 * titleP,
      }} />

      {/* 背景闪光 */}
      <div style={{
        position: "absolute", inset: 0,
        background: t.accent, opacity: flash,
      }} />

      {/* 大字标题 */}
      <div style={{
        position: "relative", zIndex: 1, textAlign: "center" as const, padding: "0 120px",
        opacity: interpolate(titleP, [0, 1], [0, 1]),
        transform: `scale(${interpolate(titleP, [0, 1], [1.3, 1]) * pulse})`,
      }}>
        <div style={{
          fontSize: 72, fontWeight: 900, color: t.text,
          fontFamily: t.titleFont, lineHeight: 1.2, letterSpacing: "-0.02em",
          textShadow: `0 0 60px ${t.accentGlow}`,
        }}>
          <WordReveal text={data.title} startFrame={3} staggerFrames={2} />
        </div>

        {sub && (
          <div style={{
            marginTop: 28, fontSize: 28, color: t.textDim, fontWeight: 500,
            fontFamily: t.bodyFont,
            opacity: interpolate(subP, [0, 1], [0, 1]),
            transform: `translateY(${interpolate(subP, [0, 1], [20, 0])}px)`,
          }}>
            {sub}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};

registry.register({ id: "slide.hook-opener", schema: "slide", name: "开场冲击", description: "3-5秒开场冲击：超大加粗文字 + 闪光弹入 + 脉冲呼吸动画。title = 冲击文案，bullet_points[0] = 小字补充。适合开头抓注意力。", isDefault: false, tags: ["开场", "hook", "冲击", "注意力"] }, SlideHookOpener);
export { SlideHookOpener };
