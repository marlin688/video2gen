/**
 * StickyNote — 手写风格便利贴
 *
 * 用在 Anthropic 品牌片开场："FIX AUTH FLOW by next week" / "Don't forget to eat dinner" 等。
 * 4 色可选 (黄/蓝/粉/绿)，支持轻微旋转和阴影。
 */

import React from "react";

export type StickyColor = "yellow" | "blue" | "pink" | "green";

const COLORS: Record<StickyColor, { bg: string; shadow: string }> = {
  yellow: { bg: "#fff5a0", shadow: "rgba(200, 180, 20, 0.25)" },
  blue: { bg: "#c8e4fd", shadow: "rgba(60, 130, 220, 0.22)" },
  pink: { bg: "#ffccdf", shadow: "rgba(230, 110, 150, 0.25)" },
  green: { bg: "#d0f5b8", shadow: "rgba(90, 170, 60, 0.22)" },
};

interface StickyNoteProps {
  color?: StickyColor;
  text: string;
  width?: number;
  height?: number;
  rotation?: number;
  fontSize?: number;
  style?: React.CSSProperties;
}

export const StickyNote: React.FC<StickyNoteProps> = ({
  color = "yellow",
  text,
  width = 170,
  height = 170,
  rotation = 0,
  fontSize = 19,
  style,
}) => {
  const c = COLORS[color];
  return (
    <div
      style={{
        width,
        height,
        backgroundColor: c.bg,
        padding: "18px 20px",
        fontSize,
        lineHeight: 1.32,
        color: "#2a2a2a",
        fontFamily:
          "'Patrick Hand', 'Kalam', 'Comic Sans MS', 'Fraunces', Georgia, serif",
        fontWeight: 500,
        transform: `rotate(${rotation}deg)`,
        boxShadow: `0 14px 32px ${c.shadow}, 0 6px 12px rgba(0,0,0,0.08)`,
        borderRadius: 2,
        display: "flex",
        alignItems: "flex-start",
        whiteSpace: "pre-wrap",
        ...style,
      }}
    >
      {text}
    </div>
  );
};
