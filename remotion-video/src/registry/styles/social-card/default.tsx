/**
 * social-card.default — 社交媒体卡片
 *
 * 支持三种平台: Twitter/X, GitHub, Hacker News
 * 数据驱动渲染，不依赖截图。
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

/* ═══════════════ 平台配色 ═══════════════ */
const THEMES = {
  twitter: {
    bg: "#15202b",
    cardBg: "#1c2938",
    border: "#38444d",
    accent: "#1d9bf0",
    text: "#e7e9ea",
    textDim: "#8899a6",
    icon: "𝕏",
    iconBg: "#000000",
  },
  github: {
    bg: "#0d1117",
    cardBg: "#161b22",
    border: "#30363d",
    accent: "#58a6ff",
    text: "#e6edf3",
    textDim: "#8b949e",
    icon: "⬡",
    iconBg: "#238636",
  },
  hackernews: {
    bg: "#1a1a2e",
    cardBg: "#16213e",
    border: "#2a3a5c",
    accent: "#ff6600",
    text: "#e0e0e0",
    textDim: "#999999",
    icon: "Y",
    iconBg: "#ff6600",
  },
};

/* ═══════════════ 头像生成 ═══════════════ */

function Avatar({ name, color, size = 64 }: { name: string; color?: string; size?: number }) {
  const initial = name.replace(/^@/, "").charAt(0).toUpperCase();
  const bg = color || `hsl(${name.length * 37 % 360}, 60%, 45%)`;
  return (
    <div style={{
      width: size,
      height: size,
      borderRadius: "50%",
      background: bg,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontSize: size * 0.45,
      fontWeight: 700,
      color: "#fff",
      flexShrink: 0,
    }}>
      {initial}
    </div>
  );
}

/* ═══════════════ 统计数字格式化 ═══════════════ */

function formatNum(n: number | string): string {
  if (typeof n === "string") return n;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

/* ═══════════════ Twitter 卡片 ═══════════════ */

function TwitterCard({ data, frame, fps }: {
  data: StyleComponentProps<"social-card">["data"];
  frame: number;
  fps: number;
}) {
  const t = THEMES.twitter;
  const stats = data.stats || {};

  return (
    <div style={{
      width: "100%",
      maxWidth: 900,
      background: t.cardBg,
      border: `1px solid ${t.border}`,
      borderRadius: 20,
      padding: "40px 44px",
      display: "flex",
      flexDirection: "column",
      gap: 20,
    }}>
      {/* 头部: 头像 + 名字 */}
      <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
        <Avatar name={data.author} color={data.avatarColor} />
        <div style={{ display: "flex", flexDirection: "column" }}>
          <span style={{ fontSize: 26, fontWeight: 700, color: t.text }}>
            {data.author.replace(/^@/, "")}
          </span>
          <span style={{ fontSize: 20, color: t.textDim }}>
            {data.author.startsWith("@") ? data.author : `@${data.author}`}
          </span>
        </div>
        <div style={{ marginLeft: "auto" }}>
          <div style={{
            width: 40, height: 40, borderRadius: 8,
            background: t.iconBg,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 22, fontWeight: 900, color: "#fff",
          }}>
            {t.icon}
          </div>
        </div>
      </div>

      {/* 正文 */}
      <div style={{
        fontSize: 30,
        lineHeight: 1.5,
        color: t.text,
        whiteSpace: "pre-wrap",
      }}>
        {data.text}
      </div>

      {/* 统计 */}
      {Object.keys(stats).length > 0 && (
        <div style={{
          display: "flex",
          gap: 36,
          paddingTop: 16,
          borderTop: `1px solid ${t.border}`,
        }}>
          {Object.entries(stats).map(([key, val]) => (
            <div key={key} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 22, fontWeight: 700, color: t.text }}>
                {formatNum(val)}
              </span>
              <span style={{ fontSize: 20, color: t.textDim }}>{key}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ═══════════════ GitHub 卡片 ═══════════════ */

function GitHubCard({ data, frame, fps }: {
  data: StyleComponentProps<"social-card">["data"];
  frame: number;
  fps: number;
}) {
  const t = THEMES.github;
  const stats = data.stats || {};

  // 语言色点
  const langColors: Record<string, string> = {
    typescript: "#3178c6", javascript: "#f1e05a", python: "#3572a5",
    rust: "#dea584", go: "#00add8", java: "#b07219", ruby: "#701516",
    c: "#555555", "c++": "#f34b7d", swift: "#f05138",
  };
  const langColor = langColors[(data.language || "").toLowerCase()] || "#8b949e";

  return (
    <div style={{
      width: "100%",
      maxWidth: 900,
      background: t.cardBg,
      border: `1px solid ${t.border}`,
      borderRadius: 12,
      padding: "36px 40px",
      display: "flex",
      flexDirection: "column",
      gap: 18,
    }}>
      {/* 仓库名 */}
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 8,
          background: t.iconBg,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 20, color: "#fff", fontWeight: 700,
        }}>
          {t.icon}
        </div>
        <span style={{ fontSize: 30, fontWeight: 600, color: t.accent }}>
          {data.author}
        </span>
      </div>

      {/* 描述 */}
      <div style={{ fontSize: 26, lineHeight: 1.5, color: t.text }}>
        {data.text}
      </div>

      {/* 标签行: 语言 + stats */}
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: 28,
        paddingTop: 14,
        borderTop: `1px solid ${t.border}`,
        flexWrap: "wrap",
      }}>
        {data.language && (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{
              width: 14, height: 14, borderRadius: "50%",
              background: langColor,
            }} />
            <span style={{ fontSize: 20, color: t.textDim }}>{data.language}</span>
          </div>
        )}
        {Object.entries(stats).map(([key, val]) => (
          <div key={key} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontSize: 20, color: t.textDim }}>
              {key === "stars" ? "★" : key === "forks" ? "⑂" : ""}
            </span>
            <span style={{ fontSize: 20, fontWeight: 600, color: t.text }}>
              {formatNum(val)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ═══════════════ HN 卡片 ═══════════════ */

function HNCard({ data, frame, fps }: {
  data: StyleComponentProps<"social-card">["data"];
  frame: number;
  fps: number;
}) {
  const t = THEMES.hackernews;
  const stats = data.stats || {};

  return (
    <div style={{
      width: "100%",
      maxWidth: 900,
      background: t.cardBg,
      border: `1px solid ${t.border}`,
      borderRadius: 12,
      padding: "36px 40px",
      display: "flex",
      flexDirection: "column",
      gap: 16,
    }}>
      {/* HN 标识 */}
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 4,
          background: t.accent,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 22, fontWeight: 900, color: "#fff",
        }}>
          {t.icon}
        </div>
        <span style={{ fontSize: 20, color: t.textDim }}>Hacker News</span>
        <span style={{ fontSize: 20, color: t.textDim, marginLeft: "auto" }}>
          by {data.author}
        </span>
      </div>

      {/* 标题 */}
      <div style={{ fontSize: 32, fontWeight: 600, lineHeight: 1.4, color: t.text }}>
        {data.text}
      </div>

      {/* subtitle */}
      {data.subtitle && (
        <div style={{ fontSize: 22, color: t.textDim, lineHeight: 1.4 }}>
          {data.subtitle}
        </div>
      )}

      {/* 统计 */}
      {Object.keys(stats).length > 0 && (
        <div style={{
          display: "flex", gap: 28, paddingTop: 14,
          borderTop: `1px solid ${t.border}`,
        }}>
          {Object.entries(stats).map(([key, val]) => (
            <div key={key} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ fontSize: 22, fontWeight: 700, color: t.accent }}>
                {formatNum(val)}
              </span>
              <span style={{ fontSize: 20, color: t.textDim }}>{key}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ═══════════════ 主组件 ═══════════════ */

const SocialCardDefault: React.FC<StyleComponentProps<"social-card">> = ({ data, segmentId }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const t = THEMES[data.platform] || THEMES.twitter;

  const cardP = spring({ frame, fps, config: { damping: 16, stiffness: 110 }, durationInFrames: 18 });

  return (
    <AbsoluteFill style={{
      background: t.bg,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: "40px 120px",
    }}>
      <div style={{
        width: "100%",
        display: "flex",
        justifyContent: "center",
        opacity: interpolate(cardP, [0, 1], [0, 1]),
        transform: `translateY(${interpolate(cardP, [0, 1], [40, 0])}px) scale(${interpolate(cardP, [0, 1], [0.96, 1])})`,
      }}>
        {data.platform === "twitter" && <TwitterCard data={data} frame={frame} fps={fps} />}
        {data.platform === "github" && <GitHubCard data={data} frame={frame} fps={fps} />}
        {data.platform === "hackernews" && <HNCard data={data} frame={frame} fps={fps} />}
      </div>
    </AbsoluteFill>
  );
};

/* ═══════════════ 注册 ═══════════════ */

registry.register(
  {
    id: "social-card.default",
    schema: "social-card",
    name: "社交媒体卡片",
    description:
      "支持 Twitter/X 推文、GitHub 仓库、Hacker News 帖子三种卡片。" +
      "数据驱动渲染，无需截图。适合引用社交媒体内容、展示开源项目。",
    isDefault: true,
    tags: ["社交", "twitter", "github", "hackernews", "引用"],
  },
  SocialCardDefault,
);

export { SocialCardDefault };
