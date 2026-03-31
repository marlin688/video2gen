/**
 * 素材 A: PPT 图文卡片 — B站知识区顶级视觉风格
 *
 * 特性:
 *   - 动态渐变背景 + 浮动粒子 + 网格纹理
 *   - 毛玻璃卡片 + 渐变描边，内容撑满全屏
 *   - 逐字入场标题 + 发光装饰
 *   - 6种自适应布局，各有专属动画编排
 */

import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import React, { useMemo } from "react";
import type { SlideContent } from "../types";

/* ════════════════════════════════════════════════
   设计系统
   ════════════════════════════════════════════════ */

const THEME = {
  bg: "#06080f",
  primary: ["#6366f1", "#8b5cf6", "#a855f7"],
  cyan: "#00d4ff",
  teal: "#22d3ee",
  emerald: "#10b981",
  amber: "#f59e0b",
  rose: "#f43f5e",
  red: "#ef4444",
  palette: ["#6366f1", "#22d3ee", "#10b981", "#f59e0b", "#f43f5e", "#a855f7"],
  textPrimary: "#f0f0f0",
  textSecondary: "#a0a0b0",
  textMuted: "#6b7080",
};

const colorAt = (i: number) => THEME.palette[i % THEME.palette.length];

const SPRING_SMOOTH = { damping: 18, stiffness: 120 };
const SPRING_SNAPPY = { damping: 14, stiffness: 160 };
const SPRING_BOUNCY = { damping: 12, stiffness: 100 };

const EASE_OUT_EXPO = Easing.bezier(0.16, 1, 0.3, 1);

interface SlideSegmentProps {
  slideContent: SlideContent;
}

type LayoutType = "compare" | "grid" | "code" | "steps" | "metric" | "standard";

/* ─── 判断布局类型 ─── */
function detectLayout(sc: SlideContent): LayoutType {
  const hint = (sc.chart_hint || "").toLowerCase();
  const bullets = sc.bullet_points;

  if (hint.includes("vs") || hint.includes("对比")) return "compare";

  const codePatterns =
    /`[^`]+`|[a-zA-Z_]+\.[a-zA-Z]{2,3}\b|\/[a-z_]+|--[a-z]|[A-Z][a-z]+[A-Z]|=>|import |export |function |const |\.\/|src\/|npm |git |claude |pip /;
  const codeCount = bullets.filter((bp) => codePatterns.test(bp)).length;
  if (codeCount >= Math.ceil(bullets.length * 0.6)) return "code";

  const stepPattern =
    /^(第[一二三四五六七八九十\d]+步|Step\s*\d|[\d①②③④⑤⑥⑦⑧⑨⑩]\s*[.、)）:])/i;
  const stepCount = bullets.filter((bp) => stepPattern.test(bp.trim())).length;
  if (stepCount >= Math.ceil(bullets.length * 0.6)) return "steps";

  const metricPattern =
    /\d+(\.\d+)?\s*(%|倍|x|×|秒|ms|MB|GB|K|k|次|个|项)|[<>≤≥]\s*\d|→|↑|↓|\d+\s*→\s*\d+/;
  const metricCount = bullets.filter((bp) => metricPattern.test(bp)).length;
  if (metricCount >= Math.ceil(bullets.length * 0.5)) return "metric";

  if (
    bullets.length >= 4 &&
    bullets.every((bp) => bp.includes("：") || bp.includes(":"))
  )
    return "grid";

  return "standard";
}

/* ─── 确定性粒子 ─── */
function makeParticles(seed: number, count: number) {
  const pts: { x: number; y: number; size: number; speed: number; delay: number }[] = [];
  for (let i = 0; i < count; i++) {
    const h = ((seed + i) * 137.508) % 1;
    const v = ((seed + i * 3 + 7) * 97.31) % 1;
    pts.push({
      x: h * 1920,
      y: v * 1080,
      size: 2 + (((seed + i) * 43) % 4),
      speed: 0.15 + (((seed + i * 7) * 23) % 100) / 400,
      delay: (i * 4) % 30,
    });
  }
  return pts;
}

/* ════════════════════════════════════════════════
   装饰组件
   ════════════════════════════════════════════════ */

const AnimatedBackground: React.FC<{ accentColor?: string }> = ({ accentColor }) => {
  const frame = useCurrentFrame();
  const accent = accentColor || THEME.primary[0];
  const particles = useMemo(() => makeParticles(42, 10), []);

  const bgReveal = interpolate(frame, [0, 15], [0, 1], {
    extrapolateRight: "clamp",
    easing: EASE_OUT_EXPO,
  });

  return (
    <AbsoluteFill style={{ opacity: bgReveal }}>
      {/* 渐变雾气 */}
      <div
        style={{
          position: "absolute",
          top: -200 + Math.sin(frame * 0.008) * 30,
          left: -150 + Math.cos(frame * 0.006) * 20,
          width: 700,
          height: 700,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${accent}18 0%, transparent 70%)`,
          filter: "blur(80px)",
          transform: `scale(${1 + 0.04 * Math.sin(frame * 0.02)})`,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: -180 + Math.sin(frame * 0.01) * 25,
          right: -120 + Math.cos(frame * 0.007) * 15,
          width: 600,
          height: 600,
          borderRadius: "50%",
          background: `radial-gradient(circle, #a855f718 0%, transparent 70%)`,
          filter: "blur(80px)",
          transform: `scale(${1 + 0.03 * Math.sin(frame * 0.025 + 1)})`,
        }}
      />
      <div
        style={{
          position: "absolute",
          top: "40%",
          right: "15%",
          width: 400,
          height: 400,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${THEME.amber}0a 0%, transparent 70%)`,
          filter: "blur(60px)",
        }}
      />
      {/* 点阵 */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage:
            "radial-gradient(circle, rgba(255,255,255,0.025) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          opacity: interpolate(frame, [5, 20], [0, 0.6], { extrapolateRight: "clamp" }),
        }}
      />
      {/* 扫描线 */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          height: 2,
          top: interpolate(frame, [0, 120], [-10, 1090], { extrapolateRight: "clamp" }),
          background: `linear-gradient(90deg, transparent 5%, ${accent}15 30%, ${accent}22 50%, ${accent}15 70%, transparent 95%)`,
          filter: "blur(1px)",
        }}
      />
      {/* 粒子 */}
      {particles.map((p, i) => {
        const pFrame = Math.max(0, frame - p.delay);
        const y = p.y - pFrame * p.speed;
        const opacity = interpolate(
          frame,
          [p.delay, p.delay + 10, 200, 250],
          [0, 0.12, 0.12, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        );
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: p.x,
              top: ((y % 1080) + 1080) % 1080,
              width: p.size,
              height: p.size,
              borderRadius: i % 3 === 2 ? 2 : "50%",
              transform: i % 3 === 2 ? "rotate(45deg)" : undefined,
              background: "#fff",
              opacity,
            }}
          />
        );
      })}
      {/* 角落线 */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: interpolate(frame, [0, 20], [0, 300], {
            extrapolateRight: "clamp",
            easing: EASE_OUT_EXPO,
          }),
          height: 1,
          background: `linear-gradient(90deg, ${accent}55, transparent)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: 1,
          height: interpolate(frame, [0, 20], [0, 200], {
            extrapolateRight: "clamp",
            easing: EASE_OUT_EXPO,
          }),
          background: `linear-gradient(180deg, ${accent}55, transparent)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: 0,
          right: 0,
          width: interpolate(frame, [3, 25], [0, 250], {
            extrapolateRight: "clamp",
            easing: EASE_OUT_EXPO,
          }),
          height: 1,
          background: `linear-gradient(270deg, #a855f755, transparent)`,
        }}
      />
    </AbsoluteFill>
  );
};

/* ─── 逐字入场标题 ─── */
const AnimatedTitle: React.FC<{ text: string; accentColor?: string }> = ({
  text,
  accentColor,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const accent = accentColor || THEME.primary[0];
  const chars = useMemo(() => Array.from(text), [text]);

  const barScale = spring({
    frame: Math.max(0, frame - 2),
    fps,
    config: SPRING_SMOOTH,
    durationInFrames: 18,
  });

  const lineWidth = interpolate(frame, [8, 22], [0, 100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE_OUT_EXPO,
  });

  const glowOpacity = interpolate(frame, [10, 20], [0, 0.4], {
    extrapolateRight: "clamp",
  });

  return (
    <div style={{ position: "relative", paddingLeft: 32, marginBottom: 48, flexShrink: 0 }}>
      {/* 竖条 */}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 4,
          bottom: 4,
          width: 5,
          borderRadius: 3,
          background: `linear-gradient(180deg, ${accent}, #a855f7)`,
          boxShadow: `0 0 20px ${accent}66, 0 0 40px ${accent}33`,
          transformOrigin: "top",
          transform: `scaleY(${barScale})`,
        }}
      />
      {/* 逐字 */}
      <div style={{ display: "flex", flexWrap: "wrap" }}>
        {chars.map((ch, i) => {
          const charDelay = 3 + i * 0.6;
          const charSpring = spring({
            frame: Math.max(0, frame - charDelay),
            fps,
            config: SPRING_SNAPPY,
            durationInFrames: 15,
          });
          const charOpacity = interpolate(
            frame,
            [charDelay, charDelay + 5],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );
          return (
            <span
              key={i}
              style={{
                fontSize: 68,
                fontWeight: 900,
                color: "#fff",
                letterSpacing: 4,
                lineHeight: 1.2,
                display: "inline-block",
                opacity: charOpacity,
                transform: `translateY(${interpolate(charSpring, [0, 1], [18, 0])}px)`,
                textShadow: `0 0 40px ${accent}${Math.round(glowOpacity * 255)
                  .toString(16)
                  .padStart(2, "0")}`,
              }}
            >
              {ch}
            </span>
          );
        })}
      </div>
      {/* 下划线 */}
      <div
        style={{
          marginTop: 14,
          height: 2,
          width: `${lineWidth}%`,
          background: `linear-gradient(90deg, ${accent}88, #a855f744, transparent)`,
          borderRadius: 1,
        }}
      />
    </div>
  );
};

/* ─── 毛玻璃卡片 ─── */
const GlassCard: React.FC<{
  children: React.ReactNode;
  accentColor?: string;
  style?: React.CSSProperties;
  glowOnEnter?: boolean;
  enterProgress?: number;
}> = ({ children, accentColor, style, glowOnEnter, enterProgress = 1 }) => {
  const glow =
    glowOnEnter && enterProgress < 1
      ? interpolate(enterProgress, [0.6, 0.9, 1], [0, 0.4, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        })
      : 0;

  return (
    <div
      style={{
        position: "relative",
        background:
          "linear-gradient(135deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02))",
        backdropFilter: "blur(12px)",
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: 18,
        overflow: "hidden",
        boxShadow:
          accentColor && glow > 0
            ? `0 0 ${30 * glow}px ${accentColor}44, inset 0 1px 0 rgba(255,255,255,0.06)`
            : "inset 0 1px 0 rgba(255,255,255,0.06), 0 8px 32px rgba(0,0,0,0.2)",
        ...style,
      }}
    >
      {enterProgress < 1 && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background:
              "linear-gradient(105deg, transparent 40%, rgba(255,255,255,0.04) 45%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 55%, transparent 60%)",
            transform: `translateX(${interpolate(enterProgress, [0.3, 1], [-120, 120], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            })}%)`,
            pointerEvents: "none",
          }}
        />
      )}
      {children}
    </div>
  );
};

/* ════════════════════════════════════════════════
   布局组件 — 所有布局用 flex:1 撑满剩余空间
   ════════════════════════════════════════════════ */

/* ─── 标准布局 ─── */
const StandardLayout: React.FC<{ bullets: string[]; chartHint?: string }> = ({
  bullets,
  chartHint,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        justifyContent: bullets.length <= 3 ? "center" : "flex-start",
        gap: bullets.length <= 3 ? 28 : 18,
        height: "100%",
      }}
    >
      {bullets.map((bp, i) => {
        const delay = 12 + i * 7;
        const prog = spring({
          frame: Math.max(0, frame - delay),
          fps,
          config: SPRING_SMOOTH,
          durationInFrames: 22,
        });
        const opacity = interpolate(frame, [delay, delay + 8], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        const color = colorAt(i);
        // 少量 bullet 时卡片更大
        const bigMode = bullets.length <= 3;

        return (
          <GlassCard
            key={i}
            accentColor={color}
            glowOnEnter
            enterProgress={prog}
            style={{
              padding: bigMode ? "36px 40px" : "24px 30px",
              opacity,
              transform: `translateY(${interpolate(prog, [0, 1], [28, 0])}px)`,
              borderLeft: `4px solid ${color}`,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
              <div
                style={{
                  flexShrink: 0,
                  width: bigMode ? 56 : 48,
                  height: bigMode ? 56 : 48,
                  borderRadius: "50%",
                  background: `linear-gradient(135deg, ${color}, ${color}99)`,
                  color: "#fff",
                  fontSize: bigMode ? 22 : 20,
                  fontWeight: 800,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  boxShadow: `0 0 0 3px ${color}33, 0 4px 16px ${color}44`,
                  transform: `scale(${interpolate(prog, [0, 1], [0.5, 1])})`,
                }}
              >
                {String(i + 1).padStart(2, "0")}
              </div>
              <span
                style={{
                  fontSize: bigMode ? 38 : 33,
                  lineHeight: 1.5,
                  color: THEME.textPrimary,
                }}
              >
                {bp}
              </span>
            </div>
          </GlassCard>
        );
      })}
      {chartHint && (
        <div
          style={{
            marginTop: 16,
            fontSize: 22,
            color: THEME.textMuted,
            fontStyle: "italic",
            paddingLeft: 32,
          }}
        >
          {chartHint}
        </div>
      )}
    </div>
  );
};

/* ─── 对比布局: 大卡片、撑满屏幕 ─── */
const CompareLayout: React.FC<{ bullets: string[]; chartHint?: string }> = ({
  bullets,
  chartHint,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const vsMatch = (chartHint || "").match(/(.+?)(?:vs|VS|→)(.+)/);
  const leftLabel = vsMatch ? vsMatch[1].trim().slice(0, 20) : "Before";
  const rightLabel = vsMatch ? vsMatch[2].trim().slice(0, 20) : "After";

  const mid = Math.ceil(bullets.length / 2);
  const leftItems = bullets.slice(0, mid);
  const rightItems = bullets.slice(mid);

  const leftProg = spring({
    frame: Math.max(0, frame - 8),
    fps,
    config: SPRING_SMOOTH,
    durationInFrames: 24,
  });
  const rightProg = spring({
    frame: Math.max(0, frame - 13),
    fps,
    config: SPRING_SMOOTH,
    durationInFrames: 24,
  });
  const vsPulse = 1 + 0.06 * Math.sin(frame * 0.12);
  const vsLineProg = spring({
    frame: Math.max(0, frame - 10),
    fps,
    config: { damping: 25, stiffness: 80 },
    durationInFrames: 30,
  });

  const renderColumn = (
    items: string[],
    color: string,
    gradientEnd: string,
    fromX: number,
    baseDelay: number
  ) => (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 16,
        flex: 1,
      }}
    >
      {items.map((bp, i) => {
        const itemDelay = baseDelay + i * 6;
        const itemProg = spring({
          frame: Math.max(0, frame - itemDelay),
          fps,
          config: SPRING_SNAPPY,
          durationInFrames: 18,
        });
        return (
          <GlassCard
            key={i}
            accentColor={color}
            glowOnEnter
            enterProgress={itemProg}
            style={{
              padding: "32px 32px",
              flex: 1,
              display: "flex",
              alignItems: "center",
              borderLeft: `4px solid ${color}`,
              opacity: interpolate(frame, [itemDelay, itemDelay + 6], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }),
              transform: `translateX(${interpolate(itemProg, [0, 1], [fromX, 0])}px)`,
            }}
          >
            {/* 序号圆 */}
            <div
              style={{
                flexShrink: 0,
                width: 44,
                height: 44,
                borderRadius: "50%",
                background: `${color}22`,
                border: `2px solid ${color}66`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                marginRight: 20,
                fontSize: 18,
                fontWeight: 800,
                color,
              }}
            >
              {i + 1}
            </div>
            <span style={{ fontSize: 34, color: THEME.textPrimary, lineHeight: 1.6 }}>
              {bp}
            </span>
          </GlassCard>
        );
      })}
    </div>
  );

  return (
    <div style={{ display: "flex", gap: 32, height: "100%", alignItems: "stretch" }}>
      {/* 左列 */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          opacity: interpolate(leftProg, [0, 1], [0, 1]),
          transform: `translateX(${interpolate(leftProg, [0, 1], [-50, 0])}px)`,
        }}
      >
        {/* 列头 */}
        <div
          style={{
            textAlign: "center",
            fontSize: 34,
            fontWeight: 800,
            background: `linear-gradient(135deg, ${THEME.red}, #f97316)`,
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            marginBottom: 24,
            paddingBottom: 14,
            borderBottom: `2px solid ${THEME.red}33`,
            flexShrink: 0,
          }}
        >
          {leftLabel}
        </div>
        {renderColumn(leftItems, THEME.red, "#f97316", -40, 14)}
      </div>

      {/* VS 分隔 */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          width: 80,
          flexShrink: 0,
        }}
      >
        <div
          style={{
            width: 2,
            flex: 1,
            background: `linear-gradient(180deg, transparent, rgba(255,255,255,0.12), transparent)`,
            transformOrigin: "center",
            transform: `scaleY(${vsLineProg})`,
          }}
        />
        <div
          style={{
            width: 64,
            height: 64,
            borderRadius: "50%",
            background:
              "linear-gradient(135deg, rgba(99,102,241,0.15), rgba(168,85,247,0.1))",
            border: "2px solid rgba(255,255,255,0.15)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 22,
            fontWeight: 900,
            color: "#ccc",
            margin: "20px 0",
            transform: `scale(${vsPulse})`,
            boxShadow: "0 0 30px rgba(99,102,241,0.2)",
          }}
        >
          VS
        </div>
        <div
          style={{
            width: 2,
            flex: 1,
            background: `linear-gradient(180deg, transparent, rgba(255,255,255,0.12), transparent)`,
            transformOrigin: "center",
            transform: `scaleY(${vsLineProg})`,
          }}
        />
      </div>

      {/* 右列 */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          opacity: interpolate(rightProg, [0, 1], [0, 1]),
          transform: `translateX(${interpolate(rightProg, [0, 1], [50, 0])}px)`,
        }}
      >
        <div
          style={{
            textAlign: "center",
            fontSize: 34,
            fontWeight: 800,
            background: `linear-gradient(135deg, ${THEME.emerald}, #34d399)`,
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            marginBottom: 24,
            paddingBottom: 14,
            borderBottom: `2px solid ${THEME.emerald}33`,
            flexShrink: 0,
          }}
        >
          {rightLabel}
        </div>
        {renderColumn(rightItems, THEME.emerald, "#34d399", 40, 18)}
      </div>
    </div>
  );
};

/* ─── 网格布局 ─── */
const GridLayout: React.FC<{ bullets: string[] }> = ({ bullets }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const cols = bullets.length <= 4 ? 2 : 3;

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(${cols}, 1fr)`,
        gridAutoRows: "1fr",
        gap: 22,
        height: "100%",
      }}
    >
      {bullets.map((bp, i) => {
        const row = Math.floor(i / cols);
        const col = i % cols;
        const delay = 10 + (row + col) * 5;
        const prog = spring({
          frame: Math.max(0, frame - delay),
          fps,
          config: SPRING_BOUNCY,
          durationInFrames: 22,
        });
        const opacity = interpolate(frame, [delay, delay + 6], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        const color = colorAt(i);

        const [label, ...descParts] = bp.split(/[：:]/);
        const description = descParts.join("：");

        return (
          <GlassCard
            key={i}
            accentColor={color}
            glowOnEnter
            enterProgress={prog}
            style={{
              padding: "36px 32px",
              opacity,
              transform: `scale(${interpolate(prog, [0, 1], [0.7, 1])}) rotate(${interpolate(prog, [0, 1], [-2, 0])}deg)`,
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
            }}
          >
            {/* 角落渐变 */}
            <div
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: 100,
                height: 100,
                background: `radial-gradient(circle at top left, ${color}20, transparent 70%)`,
                borderRadius: "18px 0 0 0",
              }}
            />
            {/* 编号水印 */}
            <div
              style={{
                position: "absolute",
                top: 14,
                right: 20,
                fontSize: 52,
                fontWeight: 900,
                color,
                opacity: interpolate(frame, [delay + 5, delay + 15], [0, 0.12], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                }),
              }}
            >
              {String(i + 1).padStart(2, "0")}
            </div>
            {/* 图标 */}
            <div
              style={{
                width: 44,
                height: 44,
                borderRadius: 12,
                background: `linear-gradient(135deg, ${color}44, ${color}22)`,
                border: `1px solid ${color}33`,
                marginBottom: 18,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <div
                style={{
                  width: 14,
                  height: 14,
                  borderRadius: 4,
                  background: color,
                }}
              />
            </div>
            {/* 标签 */}
            <div
              style={{
                fontSize: 34,
                fontWeight: 700,
                color,
                marginBottom: 10,
              }}
            >
              {label}
            </div>
            {description && (
              <div style={{ fontSize: 26, color: THEME.textSecondary, lineHeight: 1.6 }}>
                {description}
              </div>
            )}
          </GlassCard>
        );
      })}
    </div>
  );
};

/* ─── 代码块布局: 撑满全屏 ─── */
const CodeBlockLayout: React.FC<{ bullets: string[] }> = ({ bullets }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const windowProg = spring({
    frame,
    fps,
    config: SPRING_SMOOTH,
    durationInFrames: 15,
  });

  return (
    <div
      style={{
        background: "linear-gradient(180deg, #0d1117, #161b22)",
        border: "1px solid rgba(48,54,61,0.8)",
        borderRadius: 18,
        overflow: "hidden",
        opacity: interpolate(windowProg, [0, 1], [0, 1]),
        transform: `scale(${interpolate(windowProg, [0, 1], [0.96, 1])})`,
        boxShadow: "0 20px 60px rgba(0,0,0,0.5), 0 0 1px rgba(255,255,255,0.1)",
        height: "100%",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* macOS 标题栏 */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          padding: "16px 24px",
          background:
            "linear-gradient(180deg, rgba(30,36,44,0.95), rgba(22,27,34,0.95))",
          borderBottom: "1px solid rgba(48,54,61,0.6)",
          gap: 8,
          flexShrink: 0,
        }}
      >
        <div style={{ width: 14, height: 14, borderRadius: "50%", background: "#ff5f57" }} />
        <div style={{ width: 14, height: 14, borderRadius: "50%", background: "#febc2e" }} />
        <div style={{ width: 14, height: 14, borderRadius: "50%", background: "#28c840" }} />
        <div
          style={{
            marginLeft: 20,
            padding: "5px 18px",
            background: "rgba(255,255,255,0.05)",
            borderRadius: 6,
            border: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          <span style={{ fontSize: 16, color: "#8b949e", fontFamily: "monospace" }}>
            ~/project
          </span>
        </div>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 14, color: "#484f58", fontFamily: "monospace" }}>zsh</span>
      </div>

      {/* 代码内容 — 居中 */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          justifyContent: bullets.length <= 4 ? "center" : "flex-start",
          padding: bullets.length <= 4 ? "0 0" : "32px 0",
        }}
      >
        {bullets.map((bp, i) => {
          const delay = 8 + i * 10;
          const opacity = interpolate(frame, [delay, delay + 4], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          const maxChars = bp.length;
          const charsVisible = Math.floor(
            interpolate(
              frame,
              [delay, delay + Math.max(15, maxChars * 0.5)],
              [0, maxChars],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            )
          );

          const isCommand =
            /^[$>❯]\s/.test(bp) ||
            /^(npm|git|claude|pip|cd|ls|cat|curl|v2g|node)\s/.test(bp);
          const displayText = bp.slice(0, charsVisible);
          // 少量行时字更大
          const bigMode = bullets.length <= 4;

          return (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "flex-start",
                padding: bigMode ? "8px 36px" : "0 36px",
                opacity,
              }}
            >
              {/* 行号 */}
              <span
                style={{
                  fontFamily: "'SF Mono', 'JetBrains Mono', monospace",
                  fontSize: bigMode ? 28 : 24,
                  color: "#484f58",
                  width: 48,
                  textAlign: "right",
                  marginRight: 24,
                  lineHeight: bigMode ? 2.6 : 2.2,
                  flexShrink: 0,
                  userSelect: "none",
                }}
              >
                {i + 1}
              </span>
              <div
                style={{
                  fontFamily: "'SF Mono', 'Fira Code', 'JetBrains Mono', monospace",
                  fontSize: bigMode ? 34 : 28,
                  lineHeight: bigMode ? 2.6 : 2.2,
                  color: isCommand ? "#79c0ff" : "#c9d1d9",
                  whiteSpace: "pre-wrap",
                  flex: 1,
                }}
              >
                {isCommand && (
                  <span style={{ color: "#7ee787", marginRight: 10 }}>❯</span>
                )}
                {displayText.split(/(`[^`]+`|--\w+|\/[\w./]+)/).map((part, j) => {
                  if (part.startsWith("`") && part.endsWith("`")) {
                    return (
                      <span
                        key={j}
                        style={{
                          color: "#ffa657",
                          background: "rgba(255,166,87,0.1)",
                          padding: "1px 8px",
                          borderRadius: 4,
                        }}
                      >
                        {part.slice(1, -1)}
                      </span>
                    );
                  }
                  if (part.startsWith("--")) {
                    return (
                      <span key={j} style={{ color: "#ffa657" }}>
                        {part}
                      </span>
                    );
                  }
                  if (part.startsWith("/") || part.startsWith("./")) {
                    return (
                      <span key={j} style={{ color: "#7ee787" }}>
                        {part}
                      </span>
                    );
                  }
                  return <span key={j}>{part}</span>;
                })}
                {charsVisible < maxChars && (
                  <span
                    style={{
                      display: "inline-block",
                      width: 2,
                      height: bigMode ? 28 : 22,
                      background: "#58a6ff",
                      marginLeft: 1,
                      verticalAlign: "middle",
                      opacity: frame % 20 < 12 ? 1 : 0,
                    }}
                  />
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* 底部装饰 */}
      <div
        style={{
          height: 1,
          background:
            "linear-gradient(90deg, transparent, rgba(88,166,255,0.15), transparent)",
          margin: "0 36px 14px",
          flexShrink: 0,
        }}
      />
    </div>
  );
};

/* ─── 步骤流程布局 ─── */
const StepsLayout: React.FC<{ bullets: string[] }> = ({ bullets }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const colors = [THEME.cyan, "#7c3aed", THEME.amber, THEME.emerald, THEME.rose, THEME.primary[0]];

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        justifyContent: bullets.length <= 3 ? "center" : "flex-start",
        gap: 0,
        paddingLeft: 10,
        height: "100%",
      }}
    >
      {bullets.map((bp, i) => {
        const delay = 10 + i * 9;
        const prog = spring({
          frame: Math.max(0, frame - delay),
          fps,
          config: SPRING_SNAPPY,
          durationInFrames: 20,
        });
        const opacity = interpolate(frame, [delay, delay + 6], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });

        const text = bp.replace(
          /^(第[一二三四五六七八九十\d]+步|Step\s*\d|[\d①②③④⑤⑥⑦⑧⑨⑩])\s*[.、)）:：]\s*/i,
          ""
        );
        const color = colors[i % colors.length];

        const isLatest =
          frame >= delay &&
          (i === bullets.length - 1 || frame < 10 + (i + 1) * 9);
        const pulseScale = isLatest ? 1 + 0.15 * Math.sin(frame * 0.15) : 1;
        const pulseOpacity = isLatest
          ? interpolate(Math.sin(frame * 0.15), [-1, 1], [0.05, 0.2])
          : 0;

        const bigMode = bullets.length <= 3;

        return (
          <div
            key={i}
            style={{
              display: "flex",
              opacity,
              flex: bigMode ? 1 : undefined,
              minHeight: bigMode ? 0 : 90,
            }}
          >
            {/* 时间线 */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                width: 80,
                flexShrink: 0,
              }}
            >
              <div style={{ position: "relative" }}>
                <div
                  style={{
                    position: "absolute",
                    inset: -10,
                    borderRadius: "50%",
                    border: `2px solid ${color}`,
                    opacity: pulseOpacity,
                    transform: `scale(${pulseScale})`,
                  }}
                />
                <div
                  style={{
                    width: bigMode ? 58 : 50,
                    height: bigMode ? 58 : 50,
                    borderRadius: "50%",
                    border: `2px solid ${color}55`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    transform: `scale(${interpolate(prog, [0, 1], [0.3, 1])})`,
                  }}
                >
                  <div
                    style={{
                      width: bigMode ? 42 : 36,
                      height: bigMode ? 42 : 36,
                      borderRadius: "50%",
                      background: `linear-gradient(135deg, ${color}, ${color}bb)`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: bigMode ? 20 : 17,
                      fontWeight: 800,
                      color: "#fff",
                      boxShadow: `0 0 24px ${color}55`,
                    }}
                  >
                    {i + 1}
                  </div>
                </div>
              </div>
              {i < bullets.length - 1 && (
                <div
                  style={{
                    width: 2,
                    flex: 1,
                    minHeight: 12,
                    background: `linear-gradient(180deg, ${color}66, ${colors[(i + 1) % colors.length]}33)`,
                    transformOrigin: "top",
                    transform: `scaleY(${prog})`,
                  }}
                />
              )}
            </div>

            {/* 内容卡片 */}
            <GlassCard
              accentColor={color}
              glowOnEnter
              enterProgress={prog}
              style={{
                flex: 1,
                padding: bigMode ? "30px 36px" : "24px 30px",
                marginBottom: bigMode ? 0 : 14,
                marginLeft: 18,
                borderLeft: `4px solid ${color}`,
                transform: `translateX(${interpolate(prog, [0, 1], [50, 0])}px)`,
                display: "flex",
                alignItems: "center",
              }}
            >
              <span
                style={{
                  fontSize: bigMode ? 36 : 31,
                  color: THEME.textPrimary,
                  lineHeight: 1.6,
                }}
              >
                {text}
              </span>
            </GlassCard>
          </div>
        );
      })}
    </div>
  );
};

/* ─── 数据指标布局 ─── */
const MetricLayout: React.FC<{ bullets: string[] }> = ({ bullets }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const metrics = useMemo(
    () =>
      bullets.map((bp) => {
        const numMatch = bp.match(
          /([<>≤≥~]?\s*\d+[\d.,]*\s*[%倍x×秒sms秒MBGBK次个项+\-]?)/
        );
        const value = numMatch ? numMatch[1].trim() : "";
        const label = bp
          .replace(numMatch?.[0] || "", "")
          .replace(/^[：:,，\s]+|[：:,，\s]+$/g, "")
          .trim();
        const pureNum = parseFloat(value.replace(/[^0-9.]/g, ""));
        const prefix = value.match(/^[<>≤≥~]/)?.[0] || "";
        const suffix = value.replace(/^[<>≤≥~]?\s*[\d.,]+/, "").trim();
        return { value, label, pureNum, prefix, suffix };
      }),
    [bullets]
  );

  const cols = metrics.length <= 3 ? metrics.length : metrics.length <= 4 ? 2 : 3;

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(${cols}, 1fr)`,
        gridAutoRows: "1fr",
        gap: 28,
        height: "100%",
      }}
    >
      {metrics.map((m, i) => {
        const delay = 10 + i * 7;
        const prog = spring({
          frame: Math.max(0, frame - delay),
          fps,
          config: SPRING_BOUNCY,
          durationInFrames: 26,
        });
        const opacity = interpolate(frame, [delay, delay + 6], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        const color = colorAt(i);

        const countUpVal = !isNaN(m.pureNum)
          ? Math.round(interpolate(prog, [0, 1], [0, m.pureNum]))
          : null;
        const displayValue =
          countUpVal !== null
            ? `${m.prefix}${countUpVal}${m.suffix}`
            : m.value || "—";

        const percentage =
          m.suffix === "%" && !isNaN(m.pureNum) ? m.pureNum : null;
        const ringAngle = percentage
          ? interpolate(prog, [0, 1], [0, (percentage / 100) * 360])
          : 0;

        return (
          <GlassCard
            key={i}
            accentColor={color}
            glowOnEnter
            enterProgress={prog}
            style={{
              padding: "40px 28px",
              textAlign: "center",
              opacity,
              transform: `scale(${interpolate(prog, [0, 1], [0.75, 1])}) translateY(${interpolate(prog, [0, 1], [20, 0])}px)`,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {/* 背景渐变 */}
            <div
              style={{
                position: "absolute",
                inset: 0,
                background: `radial-gradient(ellipse at center top, ${color}0d, transparent 70%)`,
              }}
            />

            {/* 进度环 */}
            {percentage !== null && (
              <div
                style={{
                  position: "absolute",
                  top: 24,
                  right: 24,
                  width: 52,
                  height: 52,
                  borderRadius: "50%",
                  background: `conic-gradient(${color}66 ${ringAngle}deg, rgba(255,255,255,0.05) ${ringAngle}deg)`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <div
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: "50%",
                    background: "#0d1117",
                  }}
                />
              </div>
            )}

            {/* 大数字 */}
            <div
              style={{
                fontSize: 72,
                fontWeight: 900,
                color,
                letterSpacing: 2,
                marginBottom: 16,
                fontFamily: "'SF Mono', 'JetBrains Mono', monospace",
                textShadow: `0 0 40px ${color}55, 0 0 80px ${color}22`,
                position: "relative",
              }}
            >
              {displayValue}
            </div>

            {/* 发光条 */}
            <div
              style={{
                width: "60%",
                height: 3,
                margin: "0 auto 18px",
                borderRadius: 2,
                background: `linear-gradient(90deg, transparent, ${color}88, transparent)`,
                boxShadow: `0 0 10px ${color}44`,
              }}
            />

            {/* 标签 */}
            <div
              style={{
                fontSize: 28,
                color: THEME.textSecondary,
                lineHeight: 1.5,
                position: "relative",
              }}
            >
              {m.label}
            </div>
          </GlassCard>
        );
      })}
    </div>
  );
};

/* ════════════════════════════════════════════════
   主组件
   ════════════════════════════════════════════════ */

export const SlideSegment: React.FC<SlideSegmentProps> = ({ slideContent }) => {
  const layout = detectLayout(slideContent);
  const accentColor = THEME.palette[0];

  return (
    <AbsoluteFill
      style={{
        background: THEME.bg,
        fontFamily:
          "'PingFang SC', 'Hiragino Sans GB', 'Noto Sans CJK SC', sans-serif",
        padding: "55px 75px",
        overflow: "hidden",
      }}
    >
      <AnimatedBackground accentColor={accentColor} />

      <div
        style={{
          position: "relative",
          zIndex: 1,
          height: "100%",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <AnimatedTitle text={slideContent.title} accentColor={accentColor} />

        {/* 内容区域 — flex:1 撑满 */}
        <div style={{ flex: 1, minHeight: 0 }}>
          {layout === "compare" && (
            <CompareLayout
              bullets={slideContent.bullet_points}
              chartHint={slideContent.chart_hint}
            />
          )}
          {layout === "grid" && <GridLayout bullets={slideContent.bullet_points} />}
          {layout === "code" && <CodeBlockLayout bullets={slideContent.bullet_points} />}
          {layout === "steps" && <StepsLayout bullets={slideContent.bullet_points} />}
          {layout === "metric" && <MetricLayout bullets={slideContent.bullet_points} />}
          {layout === "standard" && (
            <StandardLayout
              bullets={slideContent.bullet_points}
              chartHint={slideContent.chart_hint}
            />
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};
