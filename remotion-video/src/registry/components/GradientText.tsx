/**
 * GradientText -- CSS 渐变文字
 *
 * 用法:
 *   <GradientText colors={["#FF6B00", "#00d4ff"]}>Title</GradientText>
 *   <GradientText useAccent>Title</GradientText>   // 自动从 theme 取色
 */

import type { CSSProperties } from "react";
import { useTheme } from "../theme";

interface GradientTextProps {
  /** 显式指定渐变色（至少 2 个） */
  colors?: string[];
  /** 为 true 时自动从当前 theme 取 accent 色系 */
  useAccent?: boolean;
  children: React.ReactNode;
  fontSize?: number;
  fontWeight?: number | string;
  style?: CSSProperties;
}

export const GradientText: React.FC<GradientTextProps> = ({
  colors,
  useAccent,
  children,
  fontSize,
  fontWeight,
  style,
}) => {
  const theme = useTheme();

  const resolvedColors =
    colors && colors.length >= 2
      ? colors
      : useAccent
        ? [theme.accent, theme.accentDim || theme.accent]
        : undefined;

  // 没有可用渐变色时退化为普通文字
  if (!resolvedColors || resolvedColors.length < 2) {
    return (
      <span style={{ fontSize, fontWeight, ...style }}>{children}</span>
    );
  }

  const gradient = `linear-gradient(135deg, ${resolvedColors.join(", ")})`;

  return (
    <span
      style={{
        background: gradient,
        WebkitBackgroundClip: "text",
        WebkitTextFillColor: "transparent",
        fontSize,
        fontWeight,
        display: "inline-block",
        ...style,
      }}
    >
      {children}
    </span>
  );
};
