/**
 * slide.hero-text — 大标题强调卡片
 *
 * 居中纯文字冲击：小字副标题 + 超大加粗主标题 + 关键词彩色高亮。
 * bullet_points 用于：[0]=副标题（小字），[1..]=补充说明行（可选）。
 * title 中用 <hl>关键词</hl> 标记需要高亮的文字。
 *
 * 适合概念引入、观点强调、转场、金句展示。
 * 参考：code秘密花园 Harness Engineering 视频（占画面 38%+）。
 */

import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import React, { useMemo } from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";
import { GlowOrb } from "../../components/GlowOrb";

/* ═══════════════ 解析高亮标记 ═══════════════ */

interface TextPart {
  text: string;
  highlight: boolean;
}

function parseHighlight(raw: string): TextPart[] {
  const parts: TextPart[] = [];
  const regex = /<hl>(.*?)<\/hl>/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(raw)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ text: raw.slice(lastIndex, match.index), highlight: false });
    }
    parts.push({ text: match[1], highlight: true });
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < raw.length) {
    parts.push({ text: raw.slice(lastIndex), highlight: false });
  }
  // 如果没有 <hl> 标记，尝试自动检测引号、加粗等
  if (parts.length === 1 && !parts[0].highlight) {
    return [{ text: raw, highlight: false }];
  }
  return parts;
}

/* ═══════════════ 主组件 ═══════════════ */

const SlideHeroText: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  const titleParts = useMemo(() => parseHighlight(data.title), [data.title]);
  const subtitle = data.bullet_points[0] || "";
  const extraLines = data.bullet_points.slice(1);

  const titleP = spring({
    frame: Math.max(0, frame - 5),
    fps,
    config: { damping: 14, stiffness: 80 },
    durationInFrames: 22,
  });
  const subP = spring({
    frame: Math.max(0, frame - 0),
    fps,
    config: { damping: 16, stiffness: 100 },
    durationInFrames: 15,
  });
  const extraP = spring({
    frame: Math.max(0, frame - 18),
    fps,
    config: { damping: 16, stiffness: 100 },
    durationInFrames: 15,
  });

  return (
    <AbsoluteFill style={{
      background: t.bg,
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      padding: "80px 160px",
      fontFamily: t.titleFont,
    }}>
      {/* 背景光斑 */}
      <div style={{
        position: "absolute",
        left: "50%", top: "45%",
        width: 600, height: 600,
        borderRadius: "50%",
        background: t.accentGlow,
        filter: "blur(120px)",
        transform: "translate(-50%, -50%)",
      }} />
      <GlowOrb intensity={0.2} seed="hero-text-orb" count={4} />

      {/* 副标题（小字） */}
      {subtitle && (
        <div style={{
          position: "relative", zIndex: 1,
          fontSize: 22,
          color: t.textDim,
          fontWeight: 500,
          marginBottom: 20,
          letterSpacing: "0.03em",
          opacity: interpolate(subP, [0, 1], [0, 1]),
          transform: `translateY(${interpolate(subP, [0, 1], [-15, 0])}px)`,
        }}>
          {subtitle}
        </div>
      )}

      {/* 主标题（超大字） */}
      <div style={{
        position: "relative", zIndex: 1,
        fontSize: 64,
        fontWeight: 800,
        lineHeight: 1.3,
        textAlign: "center" as const,
        maxWidth: 1400,
        opacity: interpolate(titleP, [0, 1], [0, 1]),
        transform: `translateY(${interpolate(titleP, [0, 1], [30, 0])}px)`,
      }}>
        {titleParts.map((part, i) => (
          <span key={i} style={{
            color: part.highlight ? t.accent : t.text,
            textDecoration: part.highlight ? "underline" : "none",
            textDecorationColor: part.highlight ? `${t.accent}40` : "transparent",
            textUnderlineOffset: "8px",
            textDecorationThickness: "3px",
          }}>
            {part.text}
          </span>
        ))}
      </div>

      {/* 补充说明行 */}
      {extraLines.length > 0 && (
        <div style={{
          position: "relative", zIndex: 1,
          marginTop: 32,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 12,
          opacity: interpolate(extraP, [0, 1], [0, 1]),
        }}>
          {extraLines.map((line, i) => (
            <div key={i} style={{
              fontSize: 24,
              color: t.textDim,
              fontWeight: 400,
              fontFamily: t.bodyFont,
              textAlign: "center" as const,
            }}>
              {line}
            </div>
          ))}
        </div>
      )}
    </AbsoluteFill>
  );
};

/* ═══════════════ 注册 ═══════════════ */

registry.register(
  {
    id: "slide.hero-text",
    schema: "slide",
    name: "大标题强调",
    description:
      "居中纯文字冲击卡片。title 为主标题（用 <hl>关键词</hl> 标记高亮），" +
      "bullet_points[0] 为副标题（小字），bullet_points[1..] 为补充说明。" +
      "适合概念引入、观点强调、转场、金句。不需要 bullet list 时优先使用此组件。",
    isDefault: false,
    tags: ["标题", "强调", "概念", "金句", "转场"],
  },
  SlideHeroText,
);

export { SlideHeroText };
