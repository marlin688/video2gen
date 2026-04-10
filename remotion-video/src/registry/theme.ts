/**
 * 全局视频主题系统
 *
 * 所有视觉组件共享同一套色彩 token，确保单个视频内风格一致。
 * 不同视频可选不同 preset，在频道层面保持新鲜感。
 *
 * 使用方式：
 *   const theme = useTheme();          // 在组件内获取当前主题
 *   <ThemeProvider value={themes['tech-blue']}> // 在顶层设置
 */

import React, { createContext, useContext } from "react";

// ---------------------------------------------------------------------------
// Token 定义
// ---------------------------------------------------------------------------

export interface VideoTheme {
  /** 主题 ID */
  id: string;

  // ── 背景层 ──
  /** 最底层背景 */
  bg: string;
  /** 卡片/面板背景 */
  surface: string;
  /** 卡片边框 */
  surfaceBorder: string;
  /** 背景网格线 */
  gridLine: string;

  // ── 文字层 ──
  /** 主标题、关键文字 */
  text: string;
  /** 二级说明文字 */
  textDim: string;
  /** 最弱文字（行号、脚注） */
  textMuted: string;

  // ── 强调色 ──
  /** 主强调色（高亮、链接、关键数据） */
  accent: string;
  /** 弱化强调 */
  accentDim: string;
  /** 强调色 glow（用于背景光斑，需要 rgba） */
  accentGlow: string;

  // ── 语义色 ──
  success: string;
  warning: string;
  danger: string;

  // ── 背景装饰 ──
  /** 浮动光斑色 1 (rgba) */
  orbColor1: string;
  /** 浮动光斑色 2 (rgba) */
  orbColor2: string;

  // ── 字体 ──
  titleFont: string;
  bodyFont: string;
  monoFont: string;
}

// ---------------------------------------------------------------------------
// 预设主题
// ---------------------------------------------------------------------------

const FONTS = {
  title: "'Inter', 'SF Pro Display', -apple-system, sans-serif",
  body: "'Inter', 'SF Pro Text', -apple-system, sans-serif",
  mono: "'SF Mono', 'Fira Code', 'JetBrains Mono', 'Cascadia Code', monospace",
};

// Anthropic 品牌字体栈：衬线（Fraunces / Playfair Display / EB Garamond / Georgia）
const ANTHROPIC_SERIF =
  "'Fraunces', 'Playfair Display', 'EB Garamond', 'Tiempos Text', Georgia, serif";

/** 科技蓝 — 冷色极简，适合编程/AI/技术类内容（默认） */
export const techBlue: VideoTheme = {
  id: "tech-blue",
  bg: "#0a0e1a",
  surface: "rgba(20, 35, 65, 0.7)",
  surfaceBorder: "rgba(74, 158, 255, 0.15)",
  gridLine: "rgba(74, 158, 255, 0.06)",
  text: "#e8edf5",
  textDim: "#8899aa",
  textMuted: "#4a5568",
  accent: "#4a9eff",
  accentDim: "#2a5a9e",
  accentGlow: "rgba(74, 158, 255, 0.12)",
  success: "#22c55e",
  warning: "#eab308",
  danger: "#ef4444",
  orbColor1: "rgba(74, 158, 255, 0.06)",
  orbColor2: "rgba(108, 92, 231, 0.05)",
  titleFont: FONTS.title,
  bodyFont: FONTS.body,
  monoFont: FONTS.mono,
};

/** 暖紫 — 深沉优雅，适合产品/设计/趋势类内容 */
export const warmPurple: VideoTheme = {
  id: "warm-purple",
  bg: "#0e0a1a",
  surface: "rgba(40, 20, 65, 0.65)",
  surfaceBorder: "rgba(168, 130, 255, 0.18)",
  gridLine: "rgba(168, 130, 255, 0.05)",
  text: "#ede8f5",
  textDim: "#9a8aaa",
  textMuted: "#564a68",
  accent: "#a882ff",
  accentDim: "#6e4ab0",
  accentGlow: "rgba(168, 130, 255, 0.12)",
  success: "#34d399",
  warning: "#fbbf24",
  danger: "#f87171",
  orbColor1: "rgba(168, 130, 255, 0.07)",
  orbColor2: "rgba(224, 85, 142, 0.05)",
  titleFont: FONTS.title,
  bodyFont: FONTS.body,
  monoFont: FONTS.mono,
};

/** 翠绿 — 清新科技，适合开源/开发者工具/环保类内容 */
export const emeraldDark: VideoTheme = {
  id: "emerald-dark",
  bg: "#0a1210",
  surface: "rgba(16, 45, 35, 0.7)",
  surfaceBorder: "rgba(52, 211, 153, 0.15)",
  gridLine: "rgba(52, 211, 153, 0.05)",
  text: "#e8f5ef",
  textDim: "#88aa99",
  textMuted: "#4a6858",
  accent: "#34d399",
  accentDim: "#1a8a62",
  accentGlow: "rgba(52, 211, 153, 0.10)",
  success: "#4ade80",
  warning: "#fbbf24",
  danger: "#f87171",
  orbColor1: "rgba(52, 211, 153, 0.06)",
  orbColor2: "rgba(56, 189, 248, 0.04)",
  titleFont: FONTS.title,
  bodyFont: FONTS.body,
  monoFont: FONTS.mono,
};

/** Anthropic 奶油米白 — 衬线 + 珊瑚红 + 手绘波纹。官方品牌片风格（Claude Managed Agents 发布片同款）。 */
export const anthropicCream: VideoTheme = {
  id: "anthropic-cream",
  bg: "#f3f0e6",                              // 米白纸张色
  surface: "rgba(255, 255, 255, 0.96)",       // 浮窗用的纯白
  surfaceBorder: "rgba(0, 0, 0, 0.08)",
  gridLine: "rgba(80, 70, 50, 0.05)",         // 波纹色
  text: "#1a1a1a",
  textDim: "#555555",
  textMuted: "#9a958d",
  accent: "#d97757",                          // Claude 珊瑚红
  accentDim: "#b85e3f",
  accentGlow: "rgba(217, 119, 87, 0.12)",
  success: "#3b82f6",                         // 蓝色勾（checklist 用）
  warning: "#f59e0b",
  danger: "#ef4444",
  orbColor1: "rgba(217, 119, 87, 0.04)",
  orbColor2: "rgba(80, 70, 50, 0.03)",
  titleFont: ANTHROPIC_SERIF,
  bodyFont: ANTHROPIC_SERIF,
  monoFont: "'JetBrains Mono', 'SF Mono', 'Fira Code', monospace",
};

// ---------------------------------------------------------------------------
// 主题注册表
// ---------------------------------------------------------------------------

export const themes: Record<string, VideoTheme> = {
  "tech-blue": techBlue,
  "warm-purple": warmPurple,
  "emerald-dark": emeraldDark,
  "anthropic-cream": anthropicCream,
};

export const DEFAULT_THEME_ID = "tech-blue";

export function getTheme(id?: string): VideoTheme {
  if (id && themes[id]) return themes[id];
  return themes[DEFAULT_THEME_ID];
}

// ---------------------------------------------------------------------------
// React Context
// ---------------------------------------------------------------------------

const ThemeContext = createContext<VideoTheme>(techBlue);

export const ThemeProvider = ThemeContext.Provider;

/** 在任意 style 组件内获取当前视频主题 */
export function useTheme(): VideoTheme {
  return useContext(ThemeContext);
}
