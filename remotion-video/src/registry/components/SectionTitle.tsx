/**
 * SectionTitle -- 带 accent bar 的段落标题
 *
 * accent bar 宽度弹入 + 标题 translateX 滑入 + 副标题淡入。
 */

import React from "react";
import type { CSSProperties } from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { useTheme } from "../theme";

interface SectionTitleProps {
  title: string;
  subtitle?: string;
  accentColor?: string;
  textColor?: string;
  fontStyle?: CSSProperties;
  monoStyle?: CSSProperties;
  align?: "left" | "center";
}

export const SectionTitle: React.FC<SectionTitleProps> = ({
  title,
  subtitle,
  accentColor,
  textColor,
  fontStyle,
  monoStyle,
  align = "left",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const theme = useTheme();

  const resolvedAccent = accentColor || theme.accent;
  const resolvedText = textColor || theme.text;
  const resolvedFont = fontStyle || { fontFamily: theme.titleFont, fontWeight: 800 };

  const titleSpring = spring({ fps, frame, config: { damping: 200 } });
  const barSpring = spring({ fps, frame: frame - 3, config: { damping: 200 } });
  const subtitleSpring = spring({ fps, frame: frame - 10, config: { damping: 200 } });

  const titleX = interpolate(titleSpring, [0, 1], [40, 0]);
  const barWidth = interpolate(barSpring, [0, 1], [0, 4]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "row",
        alignItems: "flex-start",
        gap: 16,
        textAlign: align,
      }}
    >
      {align === "left" && (
        <div
          style={{
            width: barWidth,
            height: 60,
            backgroundColor: resolvedAccent,
            borderRadius: 2,
            marginTop: 6,
            flexShrink: 0,
          }}
        />
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <div
          style={{
            ...resolvedFont,
            fontSize: 56,
            color: resolvedText,
            opacity: titleSpring,
            transform: `translateX(${titleX}px)`,
            lineHeight: 1.2,
          }}
        >
          {title}
        </div>
        {subtitle && (
          <div
            style={{
              ...(monoStyle ?? { fontFamily: theme.monoFont }),
              fontSize: 28,
              color: resolvedAccent,
              opacity: subtitleSpring,
              letterSpacing: 2,
            }}
          >
            {subtitle}
          </div>
        )}
      </div>
    </div>
  );
};
