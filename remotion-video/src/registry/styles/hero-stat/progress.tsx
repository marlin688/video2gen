/**
 * hero-stat.progress — 进度条指标面板
 *
 * 彩色 badge 标签 + 进度条 + 百分比数字。
 * 适合评测结果、模型跑分、代码质量分析展示。
 * 参考：Code AI Labs 视频中 /simplify 的 evaluation metrics 效果。
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

/* ═══════════════ Badge 配色轮换 ═══════════════ */

const BADGE_PALETTE = [
  { bg: "rgba(168,130,255,0.25)", border: "#a882ff", text: "#c4a8ff" }, // 紫
  { bg: "rgba(56,189,248,0.25)",  border: "#38bdf8", text: "#7dd3fc" }, // 青
  { bg: "rgba(52,211,153,0.25)",  border: "#34d399", text: "#6ee7b7" }, // 绿
  { bg: "rgba(251,191,36,0.25)",  border: "#fbbf24", text: "#fde047" }, // 橙
  { bg: "rgba(244,114,182,0.25)", border: "#f472b6", text: "#f9a8d4" }, // 粉
  { bg: "rgba(74,158,255,0.25)",  border: "#4a9eff", text: "#93c5fd" }, // 蓝
];

/* ═══════════════ 进度条颜色 ═══════════════ */

function useBarColors() {
  const t = useTheme();
  return {
    up:      { bar: t.success,  glow: `${t.success}40` },
    down:    { bar: t.danger,   glow: `${t.danger}40` },
    neutral: { bar: t.accent,   glow: `${t.accent}40` },
  };
}

/* ═══════════════ 解析百分比 ═══════════════ */

function parsePercent(value: string): number | null {
  const m = value.match(/(\d+\.?\d*)%?/);
  if (!m) return null;
  return Math.min(parseFloat(m[1]), 100);
}

/* ═══════════════ 主组件 ═══════════════ */

const HeroStatProgress: React.FC<StyleComponentProps<"hero-stat">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();
  const barColors = useBarColors();

  const { stats, footnote } = data;

  // 行高和间距
  const ROW_H = 72;
  const GAP = stats.length <= 3 ? 28 : 18;
  const totalH = stats.length * ROW_H + (stats.length - 1) * GAP;

  return (
    <AbsoluteFill style={{
      background: t.bg,
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      padding: "60px 100px",
      fontFamily: t.bodyFont,
    }}>
      {/* 标题（使用 footnote 字段） */}
      {footnote && (
        <div style={{
          fontSize: 30,
          color: t.textDim,
          fontWeight: 600,
          marginBottom: 48,
          fontFamily: t.titleFont,
          letterSpacing: "0.02em",
          textTransform: "uppercase" as const,
          opacity: interpolate(frame, [0, 12], [0, 1], { extrapolateRight: "clamp", extrapolateLeft: "clamp" }),
        }}>
          {footnote}
        </div>
      )}

      {/* 进度条列表 */}
      <div style={{
        display: "flex",
        flexDirection: "column",
        gap: GAP,
        width: "100%",
        maxWidth: 1400,
      }}>
        {stats.map((stat, i) => {
          const delay = 8 + i * 10;
          const enterP = spring({
            frame: Math.max(0, frame - delay),
            fps,
            config: { damping: 16, stiffness: 100 },
            durationInFrames: 20,
          });
          const fillP = spring({
            frame: Math.max(0, frame - delay - 6),
            fps,
            config: { damping: 22, stiffness: 60 },
            durationInFrames: 35,
          });

          const percent = parsePercent(stat.value);
          const trend = stat.trend || "neutral";
          const colors = barColors[trend];
          const badge = BADGE_PALETTE[i % BADGE_PALETTE.length];

          return (
            <div key={i} style={{
              display: "flex",
              alignItems: "center",
              gap: 24,
              opacity: interpolate(enterP, [0, 1], [0, 1]),
              transform: `translateX(${interpolate(enterP, [0, 1], [-60, 0])}px)`,
            }}>
              {/* Badge 标签 */}
              <div style={{
                flexShrink: 0,
                minWidth: 180,
                padding: "8px 20px",
                borderRadius: 8,
                background: badge.bg,
                border: `1.5px solid ${badge.border}`,
                fontSize: 22,
                fontWeight: 700,
                color: badge.text,
                fontFamily: t.monoFont,
                textAlign: "center" as const,
                whiteSpace: "nowrap" as const,
              }}>
                {stat.label}
              </div>

              {/* 进度条容器 */}
              <div style={{
                flex: 1,
                height: 32,
                borderRadius: 16,
                background: "rgba(255,255,255,0.06)",
                overflow: "hidden",
                position: "relative" as const,
              }}>
                {/* 填充 */}
                <div style={{
                  height: "100%",
                  width: percent !== null ? `${percent * fillP}%` : `${50 * fillP}%`,
                  borderRadius: 16,
                  background: `linear-gradient(90deg, ${colors.bar}88, ${colors.bar})`,
                  boxShadow: `0 0 20px ${colors.glow}`,
                  transition: "none",
                }} />
              </div>

              {/* 数值 */}
              <div style={{
                flexShrink: 0,
                minWidth: 90,
                fontSize: 32,
                fontWeight: 800,
                color: colors.bar,
                fontFamily: t.monoFont,
                textAlign: "right" as const,
              }}>
                {percent !== null
                  ? `${Math.round(percent * fillP)}%`
                  : stat.value
                }
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/* ═══════════════ 注册 ═══════════════ */

registry.register(
  {
    id: "hero-stat.progress",
    schema: "hero-stat",
    name: "进度条指标面板",
    description:
      "彩色 badge 标签 + 水平进度条 + 百分比数字。每行一个指标，" +
      "badge 颜色自动轮换（紫/青/绿/橙），进度条颜色跟随 trend（up=绿/down=红/neutral=蓝）。" +
      "适合展示评测结果、代码质量分、模型跑分对比。value 应为百分比格式如 '92%'。",
    isDefault: false,
    tags: ["数据", "进度", "评测", "质量", "跑分"],
  },
  HeroStatProgress,
);

export { HeroStatProgress };
