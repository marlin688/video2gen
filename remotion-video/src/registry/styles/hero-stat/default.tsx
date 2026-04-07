/**
 * hero-stat.default — 大数字/指标展示
 *
 * 1-3 个超大数字居中，支持 countUp 动画和趋势箭头。
 * 适合 benchmark 对比、效果展示、数据冲击开场。
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
import { ConstellationBg } from "../../components/ConstellationBg";

/* ═══════════════ 颜色系统（从主题读取基础色） ═══════════════ */
function useC() {
  const t = useTheme();
  return {
    bg: t.bg,
    text: t.text,
    label: t.textDim,
    footnote: t.textMuted,
    up: t.success,
    down: t.danger,
    neutral: t.accent,
    arrow: "#ffffff",
    divider: "rgba(148,163,184,0.15)",
    glow: {
      up: `${t.success}26`,   // ~15% opacity
      down: `${t.danger}26`,
      neutral: `${t.accent}26`,
    },
  };
}

/* ═══════════════ 数字动画 ═══════════════ */

function AnimatedValue({ value, oldValue, frame, fps, delay }: {
  value: string;
  oldValue?: string;
  frame: number;
  fps: number;
  delay: number;
}) {
  const C = useC();
  const p = spring({
    frame: Math.max(0, frame - delay),
    fps, config: { damping: 18, stiffness: 80 },
    durationInFrames: 25,
  });

  const numMatch = value.match(/^([<>≈~]?)(\d+\.?\d*)(.*)/);
  if (numMatch) {
    const [, prefix, numStr, suffix] = numMatch;
    const target = parseFloat(numStr);
    const current = target * p;
    const decimals = numStr.includes(".") ? (numStr.split(".")[1]?.length || 1) : 0;
    const display = current.toFixed(decimals);

    if (oldValue) {
      return (
        <div style={{ display: "flex", alignItems: "baseline", gap: 16 }}>
          <span style={{ fontSize: 48, color: C.label, fontWeight: 500, textDecoration: "line-through" }}>
            {oldValue}
          </span>
          <span style={{ fontSize: 36, color: C.label }}>→</span>
          <span>{prefix}{display}{suffix}</span>
        </div>
      );
    }
    return <span>{prefix}{display}{suffix}</span>;
  }

  if (oldValue) {
    return (
      <div style={{ display: "flex", alignItems: "baseline", gap: 16 }}>
        <span style={{ fontSize: 48, color: C.label, fontWeight: 500, textDecoration: "line-through" }}>
          {oldValue}
        </span>
        <span style={{ fontSize: 36, color: C.label }}>→</span>
        <span>{value}</span>
      </div>
    );
  }
  return <span>{value}</span>;
}

/* ═══════════════ 趋势箭头 ═══════════════ */

function TrendArrow({ trend }: { trend: "up" | "down" | "neutral" }) {
  const C = useC();
  const color = trend === "up" ? C.up : trend === "down" ? C.down : C.neutral;
  const arrow = trend === "up" ? "↑" : trend === "down" ? "↓" : "→";
  return (
    <span style={{
      fontSize: 42,
      color,
      fontWeight: 700,
      marginLeft: 12,
    }}>
      {arrow}
    </span>
  );
}

/* ═══════════════ 主组件 ═══════════════ */

const HeroStatDefault: React.FC<StyleComponentProps<"hero-stat">> = ({ data, segmentId }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const C = useC();

  const { stats, footnote } = data;
  const count = stats.length;

  // 布局: 1个=全屏居中，2个=左右分栏，3个=三列
  const isMulti = count > 1;

  return (
    <AbsoluteFill style={{
      background: C.bg,
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      padding: "40px 80px",
      overflow: "hidden",
    }}>
      <ConstellationBg nodeCount={25} opacity={0.2} seed={`hero-stat-${count}`} connectionDistance={220} />
      {/* 背景光晕（缓慢呼吸 + 漂移动画） */}
      {stats.map((stat, i) => {
        const trend = stat.trend || "neutral";
        const glowColor = C.glow[trend];
        const baseX = count === 1 ? 50 : count === 2 ? 25 + i * 50 : 20 + i * 30;
        const t = frame / Math.max(durationInFrames, 1);
        const driftX = Math.sin(t * Math.PI * 2 + i * 1.5) * 5;
        const driftY = Math.cos(t * Math.PI * 2 * 0.7 + i * 2) * 4;
        const breathe = 1 + Math.sin(t * Math.PI * 2 * 0.5 + i) * 0.08;
        return (
          <div key={i} style={{
            position: "absolute",
            left: `${baseX + driftX}%`,
            top: `${40 + driftY}%`,
            width: 500 * breathe,
            height: 500 * breathe,
            borderRadius: "50%",
            background: glowColor,
            filter: "blur(100px)",
            transform: "translate(-50%, -50%)",
            zIndex: 0,
          }} />
        );
      })}

      {/* 指标容器 */}
      <div style={{
        position: "relative",
        zIndex: 1,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: isMulti ? 60 : 0,
        width: "100%",
      }}>
        {stats.map((stat, i) => {
          const delay = 5 + i * 12;
          const p = spring({
            frame: Math.max(0, frame - delay),
            fps, config: { damping: 14, stiffness: 100 },
            durationInFrames: 20,
          });

          const trendColor = stat.trend === "up" ? C.up : stat.trend === "down" ? C.down : C.neutral;
          const valueSize = count === 1 ? 120 : count === 2 ? 96 : 80;
          const labelSize = count === 1 ? 32 : 26;

          return (
            <React.Fragment key={i}>
              {i > 0 && (
                <div style={{
                  width: 1,
                  height: 160,
                  background: C.divider,
                  alignSelf: "center",
                  opacity: interpolate(p, [0, 1], [0, 1]),
                }} />
              )}
              <div style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 16,
                flex: isMulti ? 1 : undefined,
                opacity: interpolate(p, [0, 1], [0, 1]),
                transform: `translateY(${interpolate(p, [0, 1], [40, 0])}px)`,
              }}>
                {/* 数值 */}
                <div style={{
                  fontSize: valueSize,
                  fontWeight: 800,
                  color: trendColor,
                  fontFamily: "'Inter', 'SF Pro Display', -apple-system, sans-serif",
                  letterSpacing: "-0.02em",
                  display: "flex",
                  alignItems: "baseline",
                  justifyContent: "center",
                  lineHeight: 1.1,
                }}>
                  <AnimatedValue
                    value={stat.value}
                    oldValue={stat.oldValue}
                    frame={frame}
                    fps={fps}
                    delay={delay}
                  />
                  {stat.trend && <TrendArrow trend={stat.trend} />}
                </div>

                {/* 标签 */}
                <div style={{
                  fontSize: labelSize,
                  color: C.label,
                  fontWeight: 500,
                  textAlign: "center",
                  fontFamily: "'Inter', sans-serif",
                }}>
                  {stat.label}
                </div>
              </div>
            </React.Fragment>
          );
        })}
      </div>

      {/* 脚注 */}
      {footnote && (
        <div style={{
          position: "relative",
          zIndex: 1,
          marginTop: 50,
          fontSize: 22,
          color: C.footnote,
          fontFamily: "'Inter', sans-serif",
          opacity: interpolate(
            frame, [30, 40], [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
          ),
        }}>
          {footnote}
        </div>
      )}
    </AbsoluteFill>
  );
};

/* ═══════════════ 注册 ═══════════════ */

registry.register(
  {
    id: "hero-stat.default",
    schema: "hero-stat",
    name: "大数字指标展示",
    description:
      "1-3 个超大数字居中展示，支持 countUp 跳动动画、趋势箭头（up/down/neutral）、" +
      "前后对比（oldValue → value）。适合 benchmark、效果展示、数据冲击。",
    isDefault: true,
    tags: ["数据", "指标", "benchmark", "统计", "对比"],
  },
  HeroStatDefault,
);

export { HeroStatDefault };
