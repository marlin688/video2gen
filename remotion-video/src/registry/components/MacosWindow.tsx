/**
 * MacosWindow — 可复用的 macOS 风格窗口框架
 *
 * 圆角 + 柔和阴影 + traffic lights + 可选标题栏 + 可插入任意内容。
 * Anthropic 品牌片里几乎所有 UI（terminal/editor/browser/app）都用这一套外观。
 */

import React from "react";

export type MacosWindowVariant = "light" | "dark";

interface MacosWindowProps {
  width: number;
  height: number;
  /** 标题栏中央显示的文本 */
  title?: string;
  variant?: MacosWindowVariant;
  /** 窗口根节点样式覆盖（定位、transform、opacity 等） */
  style?: React.CSSProperties;
  /** body 区样式（背景、padding 等） */
  bodyStyle?: React.CSSProperties;
  children?: React.ReactNode;
  /** 是否显示标题栏；false 时只有一个圆角的 body */
  showHeader?: boolean;
  /** 圆角 */
  radius?: number;
}

export const MacosWindow: React.FC<MacosWindowProps> = ({
  width,
  height,
  title,
  variant = "light",
  style,
  bodyStyle,
  children,
  showHeader = true,
  radius = 12,
}) => {
  const isDark = variant === "dark";
  const bodyBg = isDark ? "#1c1c1e" : "#ffffff";
  const headerBg = isDark ? "#262628" : "#f5f3ef";
  const titleColor = isDark ? "#c9c9cc" : "#666666";
  const borderColor = isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.07)";

  return (
    <div
      style={{
        width,
        height,
        borderRadius: radius,
        overflow: "hidden",
        backgroundColor: bodyBg,
        boxShadow:
          "0 28px 60px rgba(30, 24, 18, 0.18), 0 10px 22px rgba(30, 24, 18, 0.08), 0 0 0 1px rgba(0, 0, 0, 0.05)",
        display: "flex",
        flexDirection: "column",
        position: "relative",
        ...style,
      }}
    >
      {showHeader && (
        <div
          style={{
            height: 32,
            backgroundColor: headerBg,
            display: "flex",
            alignItems: "center",
            padding: "0 14px",
            position: "relative",
            flexShrink: 0,
            borderBottom: `1px solid ${borderColor}`,
          }}
        >
          <div style={{ display: "flex", gap: 7, zIndex: 1 }}>
            <div
              style={{
                width: 12,
                height: 12,
                borderRadius: "50%",
                backgroundColor: "#ff5f57",
              }}
            />
            <div
              style={{
                width: 12,
                height: 12,
                borderRadius: "50%",
                backgroundColor: "#febc2e",
              }}
            />
            <div
              style={{
                width: 12,
                height: 12,
                borderRadius: "50%",
                backgroundColor: "#28c840",
              }}
            />
          </div>
          {title && (
            <div
              style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 13,
                fontFamily: "'SF Pro Text', -apple-system, sans-serif",
                color: titleColor,
                pointerEvents: "none",
              }}
            >
              {title}
            </div>
          )}
        </div>
      )}
      <div
        style={{
          flex: 1,
          overflow: "hidden",
          position: "relative",
          ...bodyStyle,
        }}
      >
        {children}
      </div>
    </div>
  );
};
