/**
 * slide.cta-outro — 结尾行动号召
 *
 * 关注/点赞/链接 + 品牌元素。
 * title = CTA 主文案，bullet_points = 各个行动项（如"关注频道"、"GitHub链接在简介"）。
 */

import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import React from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";
import { ParticleBackground } from "../../components/ParticleBackground";
import { GlowOrb } from "../../components/GlowOrb";

const CTA_ICONS: Record<string, string> = {
  "关注": "🔔", "订阅": "🔔", "follow": "🔔", "subscribe": "🔔",
  "点赞": "👍", "like": "👍", "三连": "👍",
  "收藏": "⭐", "star": "⭐", "bookmark": "⭐",
  "评论": "💬", "comment": "💬", "留言": "💬",
  "github": "📦", "链接": "🔗", "link": "🔗", "简介": "🔗",
  "分享": "📤", "share": "📤", "转发": "📤",
};

function getIcon(text: string): string {
  const lower = text.toLowerCase();
  for (const [key, icon] of Object.entries(CTA_ICONS)) {
    if (lower.includes(key)) return icon;
  }
  return "→";
}

const SlideCtaOutro: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  const titleP = spring({ frame: Math.max(0, frame - 3), fps, config: { damping: 12, stiffness: 100 }, durationInFrames: 20 });

  return (
    <AbsoluteFill style={{ background: t.bg, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 40, padding: "60px 120px" }}>
      {/* 背景效果 */}
      <ParticleBackground count={16} opacity={0.25} seed="cta-particles" />
      <GlowOrb intensity={0.15} seed="cta-glow" count={4} />
      <div style={{ position: "absolute", width: 600, height: 600, borderRadius: "50%", background: t.accentGlow, filter: "blur(100px)", opacity: 0.5 }} />

      {/* 主文案 */}
      <div style={{
        position: "relative", zIndex: 1,
        fontSize: 52, fontWeight: 800, color: t.text, fontFamily: t.titleFont,
        textAlign: "center" as const, lineHeight: 1.3,
        opacity: interpolate(titleP, [0, 1], [0, 1]),
        transform: `scale(${interpolate(titleP, [0, 1], [0.9, 1])})`,
      }}>
        {data.title}
      </div>

      {/* CTA 按钮行 */}
      <div style={{
        position: "relative", zIndex: 1,
        display: "flex", gap: 20, flexWrap: "wrap" as const, justifyContent: "center",
      }}>
        {data.bullet_points.map((item, i) => {
          const delay = 15 + i * 8;
          const p = spring({ frame: Math.max(0, frame - delay), fps, config: { damping: 14, stiffness: 100 }, durationInFrames: 15 });
          const icon = getIcon(item);

          return (
            <div key={i} style={{
              display: "flex", alignItems: "center", gap: 12,
              padding: "16px 32px", borderRadius: 14,
              background: i === 0 ? t.accent : t.surface,
              border: `1px solid ${i === 0 ? t.accent : t.surfaceBorder}`,
              color: i === 0 ? "#000" : t.text,
              fontSize: 22, fontWeight: 700, fontFamily: t.bodyFont,
              opacity: interpolate(p, [0, 1], [0, 1]),
              transform: `translateY(${interpolate(p, [0, 1], [30, 0])}px)`,
            }}>
              <span style={{ fontSize: 26 }}>{icon}</span>
              {item}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

registry.register({ id: "slide.cta-outro", schema: "slide", name: "结尾号召", description: "结尾 CTA：大字主文案 + 行动按钮行（自动匹配图标：关注🔔/点赞👍/GitHub📦等）。第一个按钮高亮为主色。", isDefault: false, tags: ["CTA", "结尾", "号召", "关注"] }, SlideCtaOutro);
export { SlideCtaOutro };
