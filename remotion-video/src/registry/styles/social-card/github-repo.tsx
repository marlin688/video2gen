/**
 * social-card.github-repo — GitHub 仓库卡片
 *
 * GitHub 风格的仓库展示卡片：仓库名、描述、星标数、语言标签。
 * 适合展示开源项目、推荐仓库。
 *
 * 数据映射：author = "owner/repo", text = 描述, subtitle = topic tags,
 * stats = { stars, forks, issues }, language = 编程语言。
 */

import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import React from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";

const LANG_COLORS: Record<string, string> = {
  TypeScript: "#3178c6", JavaScript: "#f1e05a", Python: "#3572A5",
  Rust: "#dea584", Go: "#00ADD8", Java: "#b07219", Ruby: "#701516",
  "C++": "#f34b7d", C: "#555555", Swift: "#F05138", Kotlin: "#A97BFF",
};

const SocialCardGithubRepo: React.FC<StyleComponentProps<"social-card">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  const cardP = spring({ frame: Math.max(0, frame - 5), fps, config: { damping: 14, stiffness: 80 }, durationInFrames: 20 });
  const statsP = spring({ frame: Math.max(0, frame - 18), fps, config: { damping: 16, stiffness: 100 }, durationInFrames: 15 });

  const [owner, repo] = data.author.includes("/") ? data.author.split("/") : ["", data.author];
  const langColor = LANG_COLORS[data.language || ""] || "#8b949e";
  const stars = data.stats?.stars || 0;
  const forks = data.stats?.forks || 0;
  const topics = data.subtitle ? data.subtitle.split(",").map(s => s.trim()) : [];

  return (
    <AbsoluteFill style={{ background: "#0d1117", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "-apple-system, sans-serif" }}>
      <div style={{
        width: 900, padding: "40px 48px", borderRadius: 16,
        background: "#161b22", border: "1px solid #30363d",
        opacity: interpolate(cardP, [0, 1], [0, 1]),
        transform: `scale(${interpolate(cardP, [0, 1], [0.95, 1])})`,
      }}>
        {/* 仓库名 */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          <svg width="20" height="20" viewBox="0 0 16 16" fill="#8b949e"><path d="M2 2.5A2.5 2.5 0 014.5 0h8.75a.75.75 0 01.75.75v12.5a.75.75 0 01-.75.75h-2.5a.75.75 0 010-1.5h1.75v-2h-8a1 1 0 00-.714 1.7.75.75 0 01-1.072 1.05A2.495 2.495 0 012 11.5zm10.5-1h-8a1 1 0 00-1 1v6.708A2.486 2.486 0 014.5 9h8z" /></svg>
          {owner && <><span style={{ fontSize: 22, color: "#58a6ff" }}>{owner}</span><span style={{ color: "#8b949e", fontSize: 22 }}>/</span></>}
          <span style={{ fontSize: 22, color: "#58a6ff", fontWeight: 700 }}>{repo}</span>
        </div>

        {/* 描述 */}
        <div style={{ fontSize: 20, color: "#e6edf3", lineHeight: 1.5, marginBottom: 20 }}>
          {data.text}
        </div>

        {/* Topics */}
        {topics.length > 0 && (
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" as const, marginBottom: 20 }}>
            {topics.map((topic, i) => (
              <span key={i} style={{
                padding: "4px 12px", borderRadius: 20, fontSize: 14,
                background: "rgba(56,139,253,0.15)", color: "#58a6ff", fontWeight: 600,
              }}>
                {topic}
              </span>
            ))}
          </div>
        )}

        {/* 底部统计 */}
        <div style={{
          display: "flex", gap: 24, opacity: interpolate(statsP, [0, 1], [0, 1]),
          borderTop: "1px solid #21262d", paddingTop: 16,
        }}>
          {data.language && (
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{ width: 14, height: 14, borderRadius: "50%", background: langColor }} />
              <span style={{ fontSize: 15, color: "#e6edf3" }}>{data.language}</span>
            </div>
          )}
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ color: "#8b949e", fontSize: 16 }}>⭐</span>
            <span style={{ fontSize: 15, color: "#e6edf3" }}>{stars.toLocaleString()}</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ color: "#8b949e", fontSize: 16 }}>🔀</span>
            <span style={{ fontSize: 15, color: "#e6edf3" }}>{forks.toLocaleString()}</span>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

registry.register({ id: "social-card.github-repo", schema: "social-card", name: "GitHub 仓库卡片", description: "GitHub 风格仓库展示卡片。author='owner/repo', text=描述, language=编程语言, stats={stars,forks}, subtitle='topic1,topic2'。适合展示开源项目。", isDefault: false, tags: ["GitHub", "仓库", "开源", "项目"] }, SocialCardGithubRepo);
export { SocialCardGithubRepo };
