/**
 * slide.anthropic-callout — Anthropic 风格关键点强调卡
 *
 * 4 种 kind：
 *   - tip       💡 蓝色     — 实用技巧 / 建议
 *   - warning   ⚠  橙色     — 踩坑警告 / 注意事项
 *   - insight   ✻  珊瑚红   — 深度洞察 / 关键点 (默认)
 *   - quote     ❝  紫灰色   — 引用 / 观点
 *
 * scene_data shape:
 * {
 *   kind?: "tip" | "warning" | "insight" | "quote";  // 默认 "insight"
 *   title?: string;  // 小标题 (加粗)
 *   body: string;    // 主文案 (可 \n 换行)
 * }
 */

import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";
import { WavyPaperBg } from "../../components/WavyPaperBg";

type CalloutKind = "tip" | "warning" | "insight" | "quote";

interface CalloutSceneData {
  kind?: CalloutKind;
  title?: string;
  body?: string;
}

const KIND_STYLES: Record<
  CalloutKind,
  { icon: string; lineColor: string; iconBg: string; iconColor: string; kindLabel: string }
> = {
  tip: {
    icon: "💡",
    lineColor: "#3b82f6",
    iconBg: "rgba(59, 130, 246, 0.12)",
    iconColor: "#3b82f6",
    kindLabel: "TIP",
  },
  warning: {
    icon: "⚠",
    lineColor: "#f59e0b",
    iconBg: "rgba(245, 158, 11, 0.12)",
    iconColor: "#f59e0b",
    kindLabel: "WARNING",
  },
  insight: {
    icon: "✻",
    lineColor: "#d97757",
    iconBg: "rgba(217, 119, 87, 0.12)",
    iconColor: "#d97757",
    kindLabel: "INSIGHT",
  },
  quote: {
    icon: "\u201C",
    lineColor: "#8a7fa8",
    iconBg: "rgba(138, 127, 168, 0.12)",
    iconColor: "#8a7fa8",
    kindLabel: "QUOTE",
  },
};

const AnthropicCallout: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  const sd = (data.scene_data || {}) as CalloutSceneData;
  const kind = (sd.kind || "insight") as CalloutKind;
  const title = sd.title || data.title || "";
  const body =
    sd.body ||
    (data.bullet_points && data.bullet_points.join("\n")) ||
    "";

  const style = KIND_STYLES[kind];

  // 卡片弹入
  const cardIn = spring({
    frame,
    fps,
    config: { damping: 18, stiffness: 100 },
    durationInFrames: 20,
  });
  // body 晚 8 帧淡入
  const bodyIn = spring({
    frame: Math.max(0, frame - 8),
    fps,
    config: { damping: 22, stiffness: 85 },
    durationInFrames: 18,
  });

  return (
    <AbsoluteFill>
      <WavyPaperBg />

      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "0 180px",
        }}
      >
        <div
          style={{
            maxWidth: 1280,
            width: "100%",
            backgroundColor: "#ffffff",
            borderRadius: 14,
            padding: "56px 64px 56px 88px",
            boxShadow:
              "0 30px 70px rgba(30,24,18,0.18), 0 10px 22px rgba(30,24,18,0.08), 0 0 0 1px rgba(0,0,0,0.05)",
            position: "relative",
            opacity: interpolate(cardIn, [0, 1], [0, 1]),
            transform: `translateY(${interpolate(cardIn, [0, 1], [24, 0])}px)`,
          }}
        >
          {/* 左侧竖线 */}
          <div
            style={{
              position: "absolute",
              left: 0,
              top: 0,
              bottom: 0,
              width: 6,
              backgroundColor: style.lineColor,
              borderTopLeftRadius: 14,
              borderBottomLeftRadius: 14,
            }}
          />

          {/* kind 小徽标 + icon */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 14,
              marginBottom: title ? 20 : 28,
            }}
          >
            <div
              style={{
                width: 52,
                height: 52,
                borderRadius: "50%",
                backgroundColor: style.iconBg,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 30,
                color: style.iconColor,
                fontFamily:
                  "'Fraunces', 'Playfair Display', Georgia, serif",
                fontWeight: 700,
              }}
            >
              {style.icon}
            </div>
            <div
              style={{
                fontFamily: "'SF Pro Text', -apple-system, sans-serif",
                fontSize: 13,
                fontWeight: 700,
                letterSpacing: "0.18em",
                color: style.iconColor,
              }}
            >
              {style.kindLabel}
            </div>
          </div>

          {title && (
            <div
              style={{
                fontFamily: t.titleFont,
                fontSize: 44,
                fontWeight: 600,
                color: t.text,
                lineHeight: 1.18,
                letterSpacing: "-0.015em",
                marginBottom: 18,
              }}
            >
              {title}
            </div>
          )}

          <div
            style={{
              fontFamily: t.bodyFont,
              fontSize: 28,
              color: "#333333",
              lineHeight: 1.55,
              whiteSpace: "pre-line",
              opacity: interpolate(bodyIn, [0, 1], [0, 1]),
              transform: `translateY(${interpolate(bodyIn, [0, 1], [8, 0])}px)`,
            }}
          >
            {body}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

registry.register(
  {
    id: "slide.anthropic-callout",
    schema: "slide",
    name: "Anthropic 关键点卡片",
    description:
      "4 种 kind 的关键点强调卡 (tip/warning/insight/quote)，每种对应不同左侧竖线色 + icon。用于技术解说片里强调关键技巧、踩坑警告、深度洞察或引用。",
    isDefault: false,
    tags: ["anthropic", "callout", "强调", "tip", "warning", "insight"],
  },
  AnthropicCallout,
);
export { AnthropicCallout };
