/**
 * ClaudeLogo — Anthropic 官方 Claude 星芒 logo 的 SVG 近似
 *
 * 8-瓣不对称的放射星花造型，珊瑚红 (#d97757) 填充。
 * 可选搭配黑色 "Claude" 衬线文字（brand outro 用）。
 */

import React from "react";

interface ClaudeLogoProps {
  size?: number;
  color?: string;
  style?: React.CSSProperties;
}

/**
 * 生成一个 8-瓣"炸裂"星芒：每瓣是细长的椭圆 / 花瓣，围绕中心旋转放射。
 * 用 SVG path + rotate 实现，不依赖外部图片。
 */
export const ClaudeLogo: React.FC<ClaudeLogoProps> = ({
  size = 96,
  color = "#d97757",
  style,
}) => {
  const petalCount = 12;
  // 每个 petal 是一条两端收尖的瘦椭圆（菱形圆角化）
  const petalPath =
    "M0,0 Q 6,-42 0,-96 Q -6,-42 0,0 Z"; // 朝上的一瓣

  return (
    <svg
      width={size}
      height={size}
      viewBox="-100 -100 200 200"
      style={{ display: "block", ...style }}
    >
      {Array.from({ length: petalCount }).map((_, i) => {
        const angle = (360 / petalCount) * i;
        // 轻微长度变化，让星花显得手绘（非严格对称）
        const len = 0.85 + (i % 3) * 0.05;
        return (
          <g key={i} transform={`rotate(${angle}) scale(${len})`}>
            <path d={petalPath} fill={color} />
          </g>
        );
      })}
      {/* 中心小圆压住交界 */}
      <circle cx={0} cy={0} r={6} fill={color} />
    </svg>
  );
};

interface ClaudeWordmarkProps {
  text?: string;
  size?: number;
  color?: string;
  style?: React.CSSProperties;
}

/** 衬线字样 wordmark，用于 brand outro 的 logo+文字组合 */
export const ClaudeWordmark: React.FC<ClaudeWordmarkProps> = ({
  text = "Claude",
  size = 96,
  color = "#1a1a1a",
  style,
}) => {
  return (
    <div
      style={{
        fontSize: size,
        fontFamily:
          "'Fraunces', 'Playfair Display', 'EB Garamond', Georgia, serif",
        fontWeight: 500,
        color,
        letterSpacing: "-0.01em",
        lineHeight: 1,
        ...style,
      }}
    >
      {text}
    </div>
  );
};
