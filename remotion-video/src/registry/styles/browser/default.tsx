/**
 * browser.default — 浏览器窗口模拟
 *
 * Chrome 风格浏览器框架，地址栏 + 标签页 + 内容区。
 * 替代不稳定的 Playwright 截图方案。
 */

import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import React from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";

/* ═══════════════ 颜色系统 ═══════════════ */
const DARK = {
  bg: "#0a0a1a",
  chrome: "#202124",
  chromeBorder: "#3c4043",
  tab: "#292a2d",
  tabActive: "#35363a",
  tabText: "#9aa0a6",
  tabTextActive: "#e8eaed",
  addressBar: "#303134",
  addressText: "#9aa0a6",
  addressDomain: "#bdc1c6",
  page: "#1a1a2e",
  pageTitle: "#e8eaed",
  pageText: "#bdc1c6",
  pageBorder: "#2a2d3a",
  accent: "#8ab4f8",
  green: "#81c995",
};

const LIGHT = {
  bg: "#e8eaed",
  chrome: "#dee1e6",
  chromeBorder: "#dadce0",
  tab: "#e8eaed",
  tabActive: "#ffffff",
  tabText: "#5f6368",
  tabTextActive: "#202124",
  addressBar: "#f1f3f4",
  addressText: "#5f6368",
  addressDomain: "#202124",
  page: "#ffffff",
  pageTitle: "#202124",
  pageText: "#5f6368",
  pageBorder: "#e8eaed",
  accent: "#1a73e8",
  green: "#188038",
};

/* ═══════════════ URL 解析 ═══════════════ */

function parseUrl(url: string): { protocol: string; domain: string; path: string } {
  const m = url.match(/^(https?:\/\/)?([^/]+)(\/.*)?$/);
  return {
    protocol: m?.[1] || "https://",
    domain: m?.[2] || url,
    path: m?.[3] || "",
  };
}

/* ═══════════════ Favicon 生成 ═══════════════ */

function Favicon({ domain }: { domain: string }) {
  const colors: Record<string, string> = {
    "github.com": "#24292f",
    "twitter.com": "#1d9bf0",
    "x.com": "#000000",
    "npmjs.com": "#cb3837",
    "youtube.com": "#ff0000",
    "docs.anthropic.com": "#d97757",
    "arxiv.org": "#b31b1b",
  };
  const bg = colors[domain] || `hsl(${domain.length * 37 % 360}, 50%, 50%)`;
  const initial = domain.replace(/^www\./, "").charAt(0).toUpperCase();

  return (
    <div style={{
      width: 18,
      height: 18,
      borderRadius: 4,
      background: bg,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontSize: 11,
      fontWeight: 700,
      color: "#fff",
      flexShrink: 0,
    }}>
      {initial}
    </div>
  );
}

/* ═══════════════ 主组件 ═══════════════ */

const BrowserDefault: React.FC<StyleComponentProps<"browser">> = ({ data, segmentId }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const globalTheme = useTheme();

  const { url, tabTitle, pageTitle, contentLines, theme = "dark" } = data;
  const t = theme === "light" ? LIGHT : DARK;
  const parsed = parseUrl(url);

  const winP = spring({ frame, fps, config: { damping: 18, stiffness: 120 }, durationInFrames: 15 });

  // 内容逐行出现
  const maxLines = Math.min(contentLines.length, Math.floor(interpolate(
    frame, [12, 12 + contentLines.length * 3], [0, contentLines.length],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  )));

  return (
    <AbsoluteFill style={{
      background: theme === "light" ? t.bg : globalTheme.bg,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: "30px 60px",
    }}>
      {/* 浏览器窗口 */}
      <div style={{
        width: "100%",
        maxWidth: 1600,
        height: "90%",
        borderRadius: 14,
        overflow: "hidden",
        border: `1px solid ${t.chromeBorder}`,
        boxShadow: "0 20px 60px rgba(0,0,0,0.5)",
        display: "flex",
        flexDirection: "column",
        opacity: interpolate(winP, [0, 1], [0, 1]),
        transform: `scale(${interpolate(winP, [0, 1], [0.95, 1])})`,
      }}>
        {/* 标题栏 + 标签 */}
        <div style={{
          display: "flex",
          alignItems: "center",
          padding: "10px 16px 0",
          background: t.chrome,
        }}>
          {/* macOS 按钮 */}
          <div style={{ display: "flex", gap: 8, marginRight: 16, paddingBottom: 10 }}>
            {["#ff5f57", "#febc2e", "#28c840"].map((c, i) => (
              <div key={i} style={{ width: 12, height: 12, borderRadius: "50%", background: c }} />
            ))}
          </div>

          {/* 标签页 */}
          <div style={{
            display: "flex",
            alignItems: "flex-end",
            gap: 1,
            flex: 1,
          }}>
            <div style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 20px",
              background: t.tabActive,
              borderRadius: "10px 10px 0 0",
              maxWidth: 300,
            }}>
              <Favicon domain={parsed.domain} />
              <span style={{
                fontSize: 13,
                color: t.tabTextActive,
                fontFamily: "'Segoe UI', -apple-system, sans-serif",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}>
                {tabTitle}
              </span>
              <span style={{ fontSize: 12, color: t.tabText, marginLeft: 8 }}>×</span>
            </div>
            {/* 空标签占位 */}
            <div style={{
              width: 28,
              height: 28,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 16,
              color: t.tabText,
              marginBottom: 4,
            }}>
              +
            </div>
          </div>
        </div>

        {/* 地址栏 */}
        <div style={{
          display: "flex",
          alignItems: "center",
          padding: "8px 16px",
          background: t.chrome,
          borderBottom: `1px solid ${t.chromeBorder}`,
          gap: 12,
        }}>
          {/* 导航按钮 */}
          <div style={{ display: "flex", gap: 10 }}>
            {["←", "→", "↻"].map((icon, i) => (
              <span key={i} style={{
                fontSize: 16,
                color: t.tabText,
                opacity: i < 2 ? 0.4 : 1,
              }}>
                {icon}
              </span>
            ))}
          </div>

          {/* URL 栏 */}
          <div style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 16px",
            background: t.addressBar,
            borderRadius: 24,
          }}>
            <span style={{ fontSize: 15, color: t.green }}>🔒</span>
            <span style={{
              fontSize: 15,
              fontFamily: "'Roboto', 'Segoe UI', sans-serif",
            }}>
              <span style={{ color: t.addressText }}>{parsed.protocol}</span>
              <span style={{ color: t.addressDomain, fontWeight: 500 }}>{parsed.domain}</span>
              <span style={{ color: t.addressText }}>{parsed.path}</span>
            </span>
          </div>
        </div>

        {/* 页面内容区 */}
        <div style={{
          flex: 1,
          background: t.page,
          padding: "40px 60px",
          overflow: "hidden",
          fontFamily: "'Inter', 'Segoe UI', -apple-system, sans-serif",
        }}>
          {/* 页面标题 */}
          {pageTitle && (
            <div style={{
              fontSize: 36,
              fontWeight: 700,
              color: t.pageTitle,
              marginBottom: 28,
              lineHeight: 1.3,
              opacity: interpolate(
                frame, [8, 14], [0, 1],
                { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
              ),
            }}>
              {pageTitle}
            </div>
          )}

          {/* 内容行 */}
          {contentLines.slice(0, maxLines).map((line, i) => {
            const isHeading = line.startsWith("## ") || line.startsWith("### ");
            const isList = line.startsWith("- ") || line.startsWith("• ");
            const isDivider = line === "---";
            const lineOpacity = interpolate(
              frame, [12 + i * 3, 15 + i * 3], [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            );

            if (isDivider) {
              return (
                <div key={i} style={{
                  height: 1,
                  background: t.pageBorder,
                  margin: "20px 0",
                  opacity: lineOpacity,
                }} />
              );
            }

            return (
              <div key={i} style={{
                fontSize: isHeading ? 28 : 24,
                fontWeight: isHeading ? 700 : 400,
                color: isHeading ? t.pageTitle : t.pageText,
                lineHeight: 1.7,
                paddingLeft: isList ? 24 : 0,
                marginBottom: isHeading ? 12 : 4,
                opacity: lineOpacity,
              }}>
                {isList ? `• ${line.slice(2)}` : isHeading ? line.replace(/^#+\s*/, "") : line}
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ═══════════════ 注册 ═══════════════ */

registry.register(
  {
    id: "browser.default",
    schema: "browser",
    name: "浏览器窗口模拟",
    description:
      "Chrome 风格浏览器框架，含标签页、地址栏、内容区。支持 light/dark 主题。" +
      "替代 Playwright 截图方案，数据驱动渲染。适合展示网页、文档、GitHub 页面。",
    isDefault: true,
    tags: ["浏览器", "browser", "chrome", "网页", "web"],
  },
  BrowserDefault,
);

export { BrowserDefault };
