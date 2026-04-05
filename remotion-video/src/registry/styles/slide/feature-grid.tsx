/**
 * slide.feature-grid — 特性网格
 *
 * 2x2 或 2x3 特性卡片网格，每个 bullet_point 格式 "emoji 标题: 描述" 或 "标题: 描述"。
 * 适合产品功能、技术特性、框架对比。
 */

import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import React from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";

const CARD_ACCENTS = ["#4a9eff", "#a882ff", "#22c55e", "#eab308", "#f472b6", "#38bdf8"];

function parseFeature(line: string): { icon: string; title: string; desc: string } {
  // "🚀 标题: 描述" or "标题: 描述"
  const emojiMatch = line.match(/^(\p{Emoji_Presentation}|\p{Emoji}\uFE0F?)\s*(.+?)[:：]\s*(.+)$/u);
  if (emojiMatch) return { icon: emojiMatch[1], title: emojiMatch[2].trim(), desc: emojiMatch[3].trim() };
  const colonMatch = line.match(/^(.+?)[:：]\s*(.+)$/);
  if (colonMatch) return { icon: "", title: colonMatch[1].trim(), desc: colonMatch[2].trim() };
  return { icon: "", title: line, desc: "" };
}

const SlideFeatureGrid: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();
  const features = data.bullet_points.map(parseFeature);
  const cols = features.length <= 4 ? 2 : 3;

  return (
    <AbsoluteFill style={{ background: t.bg, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "50px 100px", fontFamily: t.bodyFont }}>
      <div style={{
        fontSize: 32, fontWeight: 700, color: t.text, marginBottom: 48, fontFamily: t.titleFont,
        opacity: interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp", extrapolateLeft: "clamp" }),
      }}>
        {data.title}
      </div>

      <div style={{
        display: "grid",
        gridTemplateColumns: `repeat(${cols}, 1fr)`,
        gap: 24, maxWidth: 1400, width: "100%",
      }}>
        {features.map((feat, i) => {
          const delay = 8 + i * 8;
          const p = spring({ frame: Math.max(0, frame - delay), fps, config: { damping: 14, stiffness: 100 }, durationInFrames: 18 });
          const accent = CARD_ACCENTS[i % CARD_ACCENTS.length];

          return (
            <div key={i} style={{
              padding: "28px 24px", borderRadius: 16,
              background: t.surface, border: `1px solid ${t.surfaceBorder}`,
              borderTop: `3px solid ${accent}`,
              opacity: interpolate(p, [0, 1], [0, 1]),
              transform: `scale(${interpolate(p, [0, 1], [0.9, 1])})`,
            }}>
              {feat.icon && <div style={{ fontSize: 36, marginBottom: 12 }}>{feat.icon}</div>}
              <div style={{ fontSize: 22, fontWeight: 700, color: t.text, marginBottom: 8 }}>{feat.title}</div>
              {feat.desc && <div style={{ fontSize: 17, color: t.textDim, lineHeight: 1.5 }}>{feat.desc}</div>}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

registry.register({ id: "slide.feature-grid", schema: "slide", name: "特性网格", description: "2x2 或 2x3 特性卡片网格，每个 bullet_point 格式 '🚀 标题: 描述'。顶部有彩色强调线。适合产品功能、技术特性概览。", isDefault: false, tags: ["特性", "功能", "网格", "产品"] }, SlideFeatureGrid);
export { SlideFeatureGrid };
