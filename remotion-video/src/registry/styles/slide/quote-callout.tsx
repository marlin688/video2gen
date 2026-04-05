/**
 * slide.quote-callout — 大号引用卡片
 *
 * title = 引用内容，bullet_points[0] = 作者，bullet_points[1] = 来源/职位。
 * 适合引用大佬观点、官方声明、推文。
 */

import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import React from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";

const SlideQuoteCallout: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();
  const author = data.bullet_points[0] || "";
  const source = data.bullet_points[1] || "";

  const quoteP = spring({ frame: Math.max(0, frame - 5), fps, config: { damping: 16, stiffness: 80 }, durationInFrames: 20 });
  const authorP = spring({ frame: Math.max(0, frame - 20), fps, config: { damping: 16, stiffness: 100 }, durationInFrames: 15 });

  const initial = author.replace(/^@/, "").charAt(0).toUpperCase() || "?";
  const avatarHue = Array.from(author).reduce((a, c) => a + c.charCodeAt(0), 0) * 37 % 360;

  return (
    <AbsoluteFill style={{ background: t.bg, display: "flex", alignItems: "center", justifyContent: "center", padding: "80px 140px", fontFamily: t.bodyFont }}>
      {/* 背景光斑 */}
      <div style={{ position: "absolute", left: "20%", top: "30%", width: 500, height: 500, borderRadius: "50%", background: t.accentGlow, filter: "blur(120px)" }} />

      <div style={{ position: "relative", zIndex: 1, maxWidth: 1200 }}>
        {/* 引号 */}
        <div style={{
          fontSize: 160, color: t.accent, opacity: 0.2, fontFamily: "Georgia, serif",
          position: "absolute", top: -80, left: -40, lineHeight: 1,
          transform: `scale(${interpolate(quoteP, [0, 1], [0.5, 1])})`,
        }}>
          &ldquo;
        </div>

        {/* 引用内容 */}
        <div style={{
          fontSize: 36, color: t.text, fontWeight: 500, lineHeight: 1.6,
          fontStyle: "italic" as const, fontFamily: "Georgia, 'Noto Serif SC', serif",
          opacity: interpolate(quoteP, [0, 1], [0, 1]),
          transform: `translateY(${interpolate(quoteP, [0, 1], [30, 0])}px)`,
        }}>
          {data.title}
        </div>

        {/* 作者信息 */}
        <div style={{
          display: "flex", alignItems: "center", gap: 16, marginTop: 40,
          opacity: interpolate(authorP, [0, 1], [0, 1]),
        }}>
          {/* 头像 */}
          <div style={{
            width: 52, height: 52, borderRadius: "50%",
            background: `hsl(${avatarHue}, 55%, 45%)`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 22, color: "#fff", fontWeight: 700,
          }}>
            {initial}
          </div>
          <div>
            <div style={{ fontSize: 22, color: t.text, fontWeight: 700 }}>{author}</div>
            {source && <div style={{ fontSize: 17, color: t.textDim }}>{source}</div>}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

registry.register({ id: "slide.quote-callout", schema: "slide", name: "引用卡片", description: "大号引用卡片，title = 引用内容，bullet_points[0] = 作者名，bullet_points[1] = 来源/职位。带左侧大引号装饰和作者头像。适合引用大佬观点、官方声明。", isDefault: false, tags: ["引用", "名言", "观点", "声明"] }, SlideQuoteCallout);
export { SlideQuoteCallout };
