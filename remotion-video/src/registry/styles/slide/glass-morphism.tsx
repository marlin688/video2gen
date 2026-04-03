/**
 * slide.glass-morphism — 毛玻璃渐变风 PPT 卡片
 *
 * 灵感来源: 现代 UI 趋势 + 视频中看到的产品界面 (Claude.ai, NeuralFlow 等)
 *
 * 设计理念:
 * - 暖色渐变背景 (紫 → 珊瑚 → 琥珀)，缓慢动画流动
 * - 毛玻璃卡片: backdrop-blur + 半透明白填充
 * - 干净的现代排版: 大标题 + 轻量正文
 * - 柔和阴影 + 大圆角
 * - 与 tech-dark 形成鲜明的明暗对比
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

/* ═══════════════ 颜色系统：暖色毛玻璃 ═══════════════ */
const C = {
  // 渐变色停
  grad1: "#6c3ce0",  // 深紫
  grad2: "#e0558e",  // 珊瑚粉
  grad3: "#f5a623",  // 琥珀
  grad4: "#3b82f6",  // 蓝 (辅助)
  // 卡片
  cardBg: "rgba(255, 255, 255, 0.12)",
  cardBorder: "rgba(255, 255, 255, 0.22)",
  cardBgHover: "rgba(255, 255, 255, 0.18)",
  // 文字
  white: "#ffffff",
  whiteOff: "rgba(255,255,255,0.88)",
  whiteDim: "rgba(255,255,255,0.60)",
  accent: "#fbbf24",   // 金色高亮
  accentAlt: "#a78bfa", // 淡紫高亮
  // 字体
  titleFont: "'Inter', 'SF Pro Display', -apple-system, sans-serif",
  bodyFont:  "'Inter', 'SF Pro Text', -apple-system, sans-serif",
};

/* ═══════════════ 工具函数 ═══════════════ */

function stag(
  frame: number, fps: number, index: number,
  base = 10, interval = 7,
): React.CSSProperties {
  const delay = base + index * interval;
  const p = spring({
    frame: Math.max(0, frame - delay), fps,
    config: { damping: 14, stiffness: 110 },
    durationInFrames: 20,
  });
  return {
    opacity: p,
    transform: `translateY(${interpolate(p, [0, 1], [40, 0])}px)`,
  };
}

function titleAnim(frame: number, fps: number): React.CSSProperties {
  const p = spring({
    frame, fps,
    config: { damping: 16, stiffness: 80 },
    durationInFrames: 24,
  });
  return {
    opacity: p,
    transform: `translateY(${interpolate(p, [0, 1], [-20, 0])}px)`,
  };
}

/** 高亮 `backtick` 内容 */
function hl(text: string): React.ReactNode {
  return text.split(/(`[^`]+`)/).map((p, j) => {
    if (p.startsWith("`") && p.endsWith("`"))
      return (
        <span key={j} style={{
          color: C.accent,
          background: "rgba(251,191,36,0.15)",
          padding: "2px 8px",
          borderRadius: 6,
          fontFamily: "'SF Mono','Fira Code',monospace",
          fontSize: "0.88em",
        }}>
          {p.slice(1, -1)}
        </span>
      );
    return <span key={j}>{p}</span>;
  });
}

/* ═══════════════ 布局检测 ═══════════════ */

type LayoutType = "compare" | "metric" | "grid" | "standard";

interface SlideShape {
  bullet_points: string[];
  chart_hint?: string;
}

function detectLayout(sc: SlideShape): LayoutType {
  const hint = (sc.chart_hint || "").toLowerCase();
  const bp = sc.bullet_points;

  if (hint.includes("vs") || hint.includes("对比") || hint.includes("compare")) return "compare";

  const metP = /\d+(\.\d+)?\s*(%|倍|x|×|秒|ms|MB|GB|K|k|次|个|项|M\+?|B\+?)|[<>≤≥]\s*\d|→|↑|↓|\d+\s*→\s*\d+/;
  if (bp.filter(b => metP.test(b)).length >= Math.ceil(bp.length * 0.5)) return "metric";

  if (bp.length >= 3 && bp.length <= 6 && bp.some(b => /[：:]/.test(b))) return "grid";

  return "standard";
}

/* ═══════════════ 毛玻璃卡片基础 ═══════════════ */

function GlassCard({ children, style, animStyle }: {
  children: React.ReactNode;
  style?: React.CSSProperties;
  animStyle?: React.CSSProperties;
}) {
  return (
    <div style={{
      background: C.cardBg,
      backdropFilter: "blur(20px) saturate(1.4)",
      WebkitBackdropFilter: "blur(20px) saturate(1.4)",
      border: `1px solid ${C.cardBorder}`,
      borderRadius: 20,
      padding: "20px 28px",
      boxShadow: "0 8px 32px rgba(0,0,0,0.15)",
      ...style,
      ...animStyle,
    }}>
      {children}
    </div>
  );
}

/* ═══════════════ 布局: 对比 ═══════════════ */

function CompareLayout({ title, bullets, frame, fps }: {
  title: string; bullets: string[]; frame: number; fps: number;
}) {
  const mid = Math.ceil(bullets.length / 2);
  const left = bullets.slice(0, mid);
  const right = bullets.slice(mid);

  return (
    <div style={{
      display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
      width: "100%", height: "100%", padding: "60px 80px",
    }}>
      <div style={{
        fontFamily: C.titleFont,
        fontSize: 48, fontWeight: 800,
        color: C.white,
        textAlign: "center",
        marginBottom: 40,
        letterSpacing: "-1px",
        ...titleAnim(frame, fps),
      }}>
        {title}
      </div>

      <div style={{ display: "flex", gap: 32, width: "100%", justifyContent: "center" }}>
        <GlassCard
          style={{ flex: 1, maxWidth: 480, borderLeft: `3px solid ${C.accentAlt}` }}
          animStyle={stag(frame, fps, 0)}
        >
          {left.map((b, i) => (
            <div key={i} style={{
              fontFamily: C.bodyFont,
              fontSize: 20, color: C.whiteOff,
              padding: "10px 0",
              borderBottom: i < left.length - 1 ? `1px solid ${C.cardBorder}` : "none",
              lineHeight: 1.5,
            }}>
              {hl(b)}
            </div>
          ))}
        </GlassCard>

        <GlassCard
          style={{ flex: 1, maxWidth: 480, borderLeft: `3px solid ${C.accent}` }}
          animStyle={stag(frame, fps, 1)}
        >
          {right.map((b, i) => (
            <div key={i} style={{
              fontFamily: C.bodyFont,
              fontSize: 20, color: C.whiteOff,
              padding: "10px 0",
              borderBottom: i < right.length - 1 ? `1px solid ${C.cardBorder}` : "none",
              lineHeight: 1.5,
            }}>
              {hl(b)}
            </div>
          ))}
        </GlassCard>
      </div>
    </div>
  );
}

/* ═══════════════ 布局: 大数字指标 ═══════════════ */

function MetricLayout({ title, bullets, frame, fps }: {
  title: string; bullets: string[]; frame: number; fps: number;
}) {
  return (
    <div style={{
      display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
      width: "100%", height: "100%", padding: "60px 80px",
    }}>
      <div style={{
        fontFamily: C.titleFont,
        fontSize: 44, fontWeight: 800,
        color: C.white,
        textAlign: "center",
        marginBottom: 50,
        letterSpacing: "-1px",
        ...titleAnim(frame, fps),
      }}>
        {title}
      </div>

      <div style={{
        display: "flex", gap: 28,
        justifyContent: "center", flexWrap: "wrap",
      }}>
        {bullets.map((b, i) => {
          // 提取数字部分
          const numMatch = b.match(/[\d.]+\s*(%|倍|x|×|秒|ms|MB|GB|K|k|次|个|项|M\+?|B\+?)?/);
          const numPart = numMatch ? numMatch[0] : "";
          const labelPart = b.replace(numPart, "").replace(/[：:]/g, "").trim();

          // 动画计数
          const delay = 12 + i * 8;
          const countP = spring({
            frame: Math.max(0, frame - delay), fps,
            config: { damping: 20, stiffness: 60 },
            durationInFrames: 30,
          });

          const targetNum = parseFloat(numPart) || 0;
          const unit = numPart.replace(/[\d.]/g, "");
          const displayNum = interpolate(countP, [0, 1], [0, targetNum]);
          const isFloat = numPart.includes(".");
          const formatted = isFloat ? displayNum.toFixed(1) : Math.round(displayNum).toString();

          return (
            <GlassCard
              key={i}
              style={{ textAlign: "center", minWidth: 200, padding: "28px 32px" }}
              animStyle={stag(frame, fps, i, 10, 6)}
            >
              <div style={{
                fontFamily: C.titleFont,
                fontSize: i === 0 ? 64 : 52,
                fontWeight: 900,
                color: C.accent,
                lineHeight: 1.1,
                letterSpacing: "-2px",
              }}>
                {formatted}{unit}
              </div>
              <div style={{
                fontFamily: C.bodyFont,
                fontSize: 16,
                color: C.whiteDim,
                marginTop: 10,
                textTransform: "uppercase",
                letterSpacing: "1px",
              }}>
                {labelPart}
              </div>
            </GlassCard>
          );
        })}
      </div>
    </div>
  );
}

/* ═══════════════ 布局: 网格卡 ═══════════════ */

function GridLayout({ title, bullets, frame, fps }: {
  title: string; bullets: string[]; frame: number; fps: number;
}) {
  const cols = bullets.length <= 4 ? 2 : 3;

  return (
    <div style={{
      display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
      width: "100%", height: "100%", padding: "60px 80px",
    }}>
      <div style={{
        fontFamily: C.titleFont,
        fontSize: 48, fontWeight: 800,
        color: C.white,
        textAlign: "center",
        marginBottom: 40,
        letterSpacing: "-1px",
        ...titleAnim(frame, fps),
      }}>
        {title}
      </div>

      <div style={{
        display: "flex", flexWrap: "wrap",
        gap: 20, justifyContent: "center",
        maxWidth: 1100,
      }}>
        {bullets.map((b, i) => {
          const sepIdx = b.search(/[：:]/);
          const label = sepIdx > 0 ? b.slice(0, sepIdx) : undefined;
          const desc = sepIdx > 0 ? b.slice(sepIdx + 1).trim() : b;

          return (
            <GlassCard
              key={i}
              style={{
                width: `calc(${100 / cols}% - ${(cols - 1) * 20 / cols}px)`,
                minWidth: 220,
              }}
              animStyle={stag(frame, fps, i, 10, 5)}
            >
              {label && (
                <div style={{
                  fontFamily: C.titleFont,
                  fontSize: 20, fontWeight: 700,
                  color: C.accent,
                  marginBottom: 8,
                }}>
                  {label}
                </div>
              )}
              <div style={{
                fontFamily: C.bodyFont,
                fontSize: 18,
                color: C.whiteOff,
                lineHeight: 1.5,
              }}>
                {hl(desc)}
              </div>
            </GlassCard>
          );
        })}
      </div>
    </div>
  );
}

/* ═══════════════ 布局: 标准 ═══════════════ */

function StandardLayout({ title, bullets, frame, fps }: {
  title: string; bullets: string[]; frame: number; fps: number;
}) {
  return (
    <div style={{
      display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
      width: "100%", height: "100%", padding: "60px 100px",
    }}>
      <div style={{
        fontFamily: C.titleFont,
        fontSize: 48, fontWeight: 800,
        color: C.white,
        textAlign: "center",
        marginBottom: 36,
        letterSpacing: "-1px",
        ...titleAnim(frame, fps),
      }}>
        {title}
      </div>

      <div style={{
        display: "flex", flexDirection: "column",
        gap: 16, maxWidth: 880, width: "100%",
      }}>
        {bullets.map((b, i) => (
          <GlassCard key={i} animStyle={stag(frame, fps, i, 10, 6)}>
            <div style={{
              display: "flex", alignItems: "baseline", gap: 14,
            }}>
              <span style={{
                fontFamily: C.titleFont,
                fontSize: 28, fontWeight: 800,
                color: C.accent,
                lineHeight: 1,
                minWidth: 28,
              }}>
                {i + 1}
              </span>
              <span style={{
                fontFamily: C.bodyFont,
                fontSize: 20,
                color: C.whiteOff,
                lineHeight: 1.5,
              }}>
                {hl(b)}
              </span>
            </div>
          </GlassCard>
        ))}
      </div>
    </div>
  );
}

/* ═══════════════ 主组件 ═══════════════ */

const SlideGlassMorphism: React.FC<StyleComponentProps<"slide">> = ({ data, segmentId, fps }) => {
  const frame = useCurrentFrame();
  const { fps: vFps } = useVideoConfig();
  const f = fps || vFps;

  const sc = {
    bullet_points: data.bullet_points || [],
    chart_hint: data.chart_hint,
  };
  const layout = detectLayout(sc);

  // 渐变动画: 缓慢旋转
  const gradAngle = interpolate(frame, [0, 300], [135, 195], {
    extrapolateRight: "extend",
  });

  // 使用 segmentId 做渐变色偏移，不同段落看起来不同
  const hueShift = (segmentId * 37) % 360;

  const layoutProps = { title: data.title, bullets: sc.bullet_points, frame, fps: f };

  return (
    <AbsoluteFill style={{ backgroundColor: "#1a0a2e" }}>
      {/* 动态渐变背景 */}
      <div style={{
        position: "absolute", inset: 0,
        background: `linear-gradient(${gradAngle}deg, ${C.grad1}, ${C.grad2}, ${C.grad3})`,
        opacity: 0.85,
      }} />

      {/* 光斑装饰 */}
      <div style={{
        position: "absolute",
        width: 600, height: 600,
        borderRadius: "50%",
        background: `radial-gradient(circle, ${C.grad4}40, transparent 70%)`,
        top: -200, right: -100,
        filter: "blur(60px)",
        opacity: interpolate(frame, [0, 150, 300], [0.3, 0.6, 0.3], { extrapolateRight: "extend" }),
      }} />

      <div style={{
        position: "absolute",
        width: 500, height: 500,
        borderRadius: "50%",
        background: `radial-gradient(circle, ${C.grad3}30, transparent 70%)`,
        bottom: -150, left: -100,
        filter: "blur(50px)",
        opacity: interpolate(frame, [0, 200, 400], [0.4, 0.2, 0.4], { extrapolateRight: "extend" }),
      }} />

      {/* 噪声纹理 */}
      <div style={{
        position: "absolute", inset: 0,
        backgroundImage: `radial-gradient(rgba(255,255,255,0.03) 1px, transparent 1px)`,
        backgroundSize: "20px 20px",
      }} />

      {layout === "compare" && <CompareLayout {...layoutProps} />}
      {layout === "metric" && <MetricLayout {...layoutProps} />}
      {layout === "grid" && <GridLayout {...layoutProps} />}
      {layout === "standard" && <StandardLayout {...layoutProps} />}
    </AbsoluteFill>
  );
};

/* ═══════════════ 注册 ═══════════════ */

registry.register(
  {
    id: "slide.glass-morphism",
    schema: "slide",
    name: "毛玻璃渐变风",
    description:
      "暖色渐变背景 + 毛玻璃卡片 (backdrop-blur) + 现代排版。" +
      "适合产品介绍、数据指标展示、功能概览等场景。" +
      "视觉风格明亮现代，与 tech-dark 形成鲜明对比。",
    isDefault: false,
    tags: ["modern", "gradient", "product", "metrics"],
  },
  SlideGlassMorphism,
);

export { SlideGlassMorphism };
