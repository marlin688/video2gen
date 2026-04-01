/**
 * slide.tech-dark — 极简深色 PPT 卡片
 *
 * 设计理念: "less is more"
 * - 深海军蓝背景 + 细网格
 * - 单色系: 蓝色 #4a9eff 为主色，白/灰辅助
 * - 大量留白，元素居中只占画面 40-50%
 * - 交错弹入动画 (staggered spring)
 * - 6 种布局自动检测
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

/* ═══════════════ 颜色系统：单色蓝 ═══════════════ */
const C = {
  bg: "#0f1729",
  blue: "#4a9eff",
  blueDim: "#2a5a9e",
  white: "#e8edf5",
  gray: "#8899aa",
  grayDim: "#4a5568",
  cardBg: "rgba(20, 35, 65, 0.7)",
  cardBorder: "rgba(74, 158, 255, 0.15)",
  gridLine: "rgba(74, 158, 255, 0.06)",
};

/* ═══════════════ 工具函数 ═══════════════ */

function hexA(hex: string, a: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${a})`;
}

function stag(frame: number, fps: number, index: number, base = 12, interval = 10): React.CSSProperties {
  const delay = base + index * interval;
  const p = spring({ frame: Math.max(0, frame - delay), fps, config: { damping: 14, stiffness: 120 }, durationInFrames: 20 });
  return {
    opacity: p,
    transform: `translateY(${interpolate(p, [0, 1], [35, 0])}px)`,
  };
}

function hl(text: string): React.ReactNode {
  return text.split(/(`[^`]+`)/).map((p, j) => {
    if (p.startsWith("`") && p.endsWith("`"))
      return <span key={j} style={{ color: C.blue, background: hexA(C.blue, 0.12), padding: "2px 8px", borderRadius: 4, fontFamily: "'SF Mono','Fira Code',monospace", fontSize: "0.9em" }}>{p.slice(1, -1)}</span>;
    return <span key={j}>{p}</span>;
  });
}

/* ═══════════════ 布局检测 ═══════════════ */

type LayoutType = "compare" | "grid" | "code" | "steps" | "metric" | "standard";

interface SlideContentShape {
  bullet_points: string[];
  chart_hint?: string;
}

function detectLayout(sc: SlideContentShape): LayoutType {
  const hint = (sc.chart_hint || "").toLowerCase();
  const bp = sc.bullet_points;
  if (hint.includes("vs") || hint.includes("对比")) return "compare";
  const codeP = /`[^`]+`|[a-zA-Z_]+\.[a-zA-Z]{2,3}\b|\/[a-z_]+|--[a-z]|=>|import |export |function |const |\.\/|src\/|npm |git |claude |pip /;
  if (bp.filter((b) => codeP.test(b)).length >= Math.ceil(bp.length * 0.6)) return "code";
  const stepP = /^(第[一二三四五六七八九十\d]+步|Step\s*\d|[\d①②③④⑤⑥⑦⑧⑨⑩]\s*[.、)）:])/i;
  if (bp.filter((b) => stepP.test(b.trim())).length >= Math.ceil(bp.length * 0.6)) return "steps";
  const metP = /\d+(\.\d+)?\s*(%|倍|x|×|秒|ms|MB|GB|K|k|次|个|项)|[<>≤≥]\s*\d|→|↑|↓|\d+\s*→\s*\d+/;
  if (bp.filter((b) => metP.test(b)).length >= Math.ceil(bp.length * 0.5)) return "metric";
  if (bp.length >= 4 && bp.every((b) => b.includes("：") || b.includes(":"))) return "grid";
  return "standard";
}

/* ═══════════════ 背景 ═══════════════ */

const GridBg: React.FC = () => (
  <AbsoluteFill style={{ overflow: "hidden" }}>
    <div style={{ position: "absolute", inset: 0, background: C.bg }} />
    <svg width="1920" height="1080" style={{ position: "absolute", inset: 0 }}>
      <defs>
        <pattern id="gridMin" width="60" height="60" patternUnits="userSpaceOnUse">
          <path d="M 60 0 L 0 0 0 60" fill="none" stroke={C.gridLine} strokeWidth="0.5" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#gridMin)" />
    </svg>
  </AbsoluteFill>
);

/* ═══════════════ 标题 ═══════════════ */

const Title: React.FC<{ text: string; subtitle?: string }> = ({ text, subtitle }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame, fps, config: { damping: 16, stiffness: 140 }, durationInFrames: 18 });
  return (
    <div style={{
      textAlign: "center", marginBottom: 48,
      opacity: p,
      transform: `translateY(${interpolate(p, [0, 1], [20, 0])}px)`,
    }}>
      <div style={{
        fontSize: 48, fontWeight: 800, color: C.white, lineHeight: 1.3,
        letterSpacing: 1,
      }}>
        {text}
      </div>
      {subtitle && (
        <div style={{ fontSize: 22, color: C.gray, marginTop: 10, fontStyle: "italic" }}>
          {subtitle}
        </div>
      )}
    </div>
  );
};

/* ═══════════════ Standard: 居中堆叠卡片 ═══════════════ */

const StandardLayout: React.FC<{ bullets: string[] }> = ({ bullets }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14 }}>
      {bullets.map((bp, i) => (
        <div key={i} style={{
          ...stag(frame, fps, i),
          background: C.cardBg,
          border: `1px solid ${C.cardBorder}`,
          borderRadius: 12,
          padding: "18px 36px",
          minWidth: 500, maxWidth: 900,
          fontSize: 30, color: C.white, lineHeight: 1.6,
          textAlign: "center",
          backdropFilter: "blur(8px)",
        }}>
          {hl(bp)}
        </div>
      ))}
    </div>
  );
};

/* ═══════════════ Grid: 2x2 居中网格 ═══════════════ */

const GridLayout: React.FC<{ bullets: string[] }> = ({ bullets }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const cols = bullets.length <= 4 ? 2 : 3;
  return (
    <div style={{
      display: "grid", gridTemplateColumns: `repeat(${cols}, 1fr)`,
      gap: 16, maxWidth: 1000, margin: "0 auto",
    }}>
      {bullets.map((bp, i) => {
        const [label, ...descParts] = bp.split(/[：:]/);
        const desc = descParts.join("：");
        return (
          <div key={i} style={{
            ...stag(frame, fps, i),
            background: C.cardBg,
            border: `1px solid ${C.cardBorder}`,
            borderRadius: 12,
            padding: "22px 24px",
            display: "flex", flexDirection: "column", gap: 6,
          }}>
            <span style={{ fontSize: 26, fontWeight: 700, color: C.blue }}>{label}</span>
            {desc && <span style={{ fontSize: 20, color: C.gray, lineHeight: 1.5 }}>{desc}</span>}
          </div>
        );
      })}
    </div>
  );
};

/* ═══════════════ Metric: 大数字居中 ═══════════════ */

const MetricLayout: React.FC<{ bullets: string[] }> = ({ bullets }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const metrics = bullets.map((bp) => {
    const m = bp.match(/([<>≤≥~]?\s*\d+[\d.,]*\s*[%倍x×秒msMBGBK次个项+\-]?)/);
    if (m) return { value: m[1].trim(), label: bp.replace(m[0], "").replace(/^[：:,，\s]+/, "").trim() };
    return { value: "", label: bp };
  });
  const hasValues = metrics.some(m => m.value);

  if (!hasValues) {
    return <StandardLayout bullets={bullets} />;
  }

  return (
    <div style={{
      display: "flex", justifyContent: "center", alignItems: "center",
      gap: 60, flexWrap: "wrap",
    }}>
      {metrics.map((m, i) => {
        const s = stag(frame, fps, i, 10, 12);
        const numProg = spring({ frame: Math.max(0, frame - 10 - i * 12), fps, config: { damping: 20, stiffness: 100 }, durationInFrames: 25 });
        const pure = parseFloat(m.value.replace(/[^0-9.]/g, ""));
        const animated = !isNaN(pure) ? interpolate(numProg, [0, 1], [0, pure]).toFixed(m.value.includes(".") ? 1 : 0) : m.value;
        const prefix = m.value.match(/^[<>≤≥~]/)?.[0] || "";
        const suffix = m.value.match(/[%倍x×秒msMBGBK次个项+\-]$/)?.[0] || "";
        const display = m.value ? `${prefix}${animated}${suffix}` : "—";

        return (
          <div key={i} style={{
            ...s, textAlign: "center", minWidth: 180,
          }}>
            <div style={{
              fontSize: i === 0 ? 80 : 64, fontWeight: 900, color: C.blue,
              fontFamily: "'SF Mono','Fira Code',monospace",
              lineHeight: 1,
            }}>
              {display}
            </div>
            <div style={{
              fontSize: 22, color: C.gray, marginTop: 12, lineHeight: 1.4,
            }}>
              {m.label}
            </div>
          </div>
        );
      })}
    </div>
  );
};

/* ═══════════════ Code: 终端风格 ═══════════════ */

const CodeLayout: React.FC<{ bullets: string[] }> = ({ bullets }) => {
  const frame = useCurrentFrame();
  return (
    <div style={{
      background: "rgba(10, 15, 28, 0.9)",
      border: `1px solid ${hexA(C.blue, 0.12)}`,
      borderRadius: 12,
      maxWidth: 1000, margin: "0 auto",
      overflow: "hidden",
    }}>
      <div style={{
        display: "flex", alignItems: "center", padding: "12px 18px",
        borderBottom: `1px solid ${hexA(C.blue, 0.08)}`,
        gap: 8,
      }}>
        {["#ff5f57", "#febc2e", "#28c840"].map((c, j) => (
          <div key={j} style={{ width: 12, height: 12, borderRadius: "50%", background: c }} />
        ))}
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 14, color: C.grayDim, fontFamily: "'SF Mono',monospace" }}>Claude Code</span>
        <div style={{ flex: 1 }} />
      </div>
      <div style={{ padding: "20px 28px", display: "flex", flexDirection: "column", gap: 4 }}>
        {bullets.map((bp, i) => {
          const delay = 8 + i * 8;
          const op = interpolate(frame, [delay, delay + 5], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          const isCmd = /^[$>❯]\s/.test(bp) || /^(npm|git|claude|pip|node)\s/.test(bp);
          return (
            <div key={i} style={{
              opacity: op, fontSize: 24, lineHeight: 1.8,
              fontFamily: "'SF Mono','Fira Code',monospace",
              color: isCmd ? C.blue : C.white,
              paddingLeft: isCmd ? 0 : 24,
            }}>
              {isCmd && <span style={{ color: "#28c840", marginRight: 10 }}>$</span>}
              {hl(bp)}
            </div>
          );
        })}
      </div>
    </div>
  );
};

/* ═══════════════ Steps: 水平 pipeline ═══════════════ */

const StepsLayout: React.FC<{ bullets: string[] }> = ({ bullets }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const cleaned = bullets.map(bp =>
    bp.replace(/^(第[一二三四五六七八九十\d]+步|Step\s*\d|[\d①②③④⑤⑥⑦⑧⑨⑩])\s*[.、)）:：]\s*/i, "")
  );

  if (cleaned.length <= 5) {
    return (
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "center",
        gap: 0, flexWrap: "wrap",
      }}>
        {cleaned.map((text, i) => {
          const s = stag(frame, fps, i, 10, 10);
          return (
            <React.Fragment key={i}>
              <div style={{
                ...s,
                background: C.cardBg,
                border: `1px solid ${C.cardBorder}`,
                borderRadius: 10,
                padding: "16px 24px",
                fontSize: 24, color: C.blue, fontWeight: 600,
                fontFamily: "'SF Mono','Fira Code',monospace",
                textAlign: "center",
                minWidth: 140,
              }}>
                {text}
              </div>
              {i < cleaned.length - 1 && (
                <span style={{
                  ...stag(frame, fps, i, 14, 10),
                  fontSize: 22, color: C.grayDim, margin: "0 10px",
                  fontFamily: "monospace",
                }}>{">"}</span>
              )}
            </React.Fragment>
          );
        })}
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14 }}>
      {cleaned.map((text, i) => (
        <div key={i} style={{
          ...stag(frame, fps, i),
          display: "flex", alignItems: "center", gap: 16,
          background: C.cardBg,
          border: `1px solid ${C.cardBorder}`,
          borderRadius: 10,
          padding: "14px 28px",
          minWidth: 400,
        }}>
          <div style={{
            width: 36, height: 36, borderRadius: "50%",
            background: hexA(C.blue, 0.15), border: `2px solid ${hexA(C.blue, 0.4)}`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 18, fontWeight: 800, color: C.blue, flexShrink: 0,
          }}>{i + 1}</div>
          <span style={{ fontSize: 26, color: C.white, lineHeight: 1.4 }}>{text}</span>
        </div>
      ))}
    </div>
  );
};

/* ═══════════════ Compare: 左右分栏 ═══════════════ */

const CompareLayout: React.FC<{ bullets: string[]; chartHint?: string }> = ({ bullets, chartHint }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const vsMatch = (chartHint || "").match(/(.+?)(?:vs|VS|→|对比|和)(.+)/);
  const leftLabel = vsMatch ? vsMatch[1].trim() : "Before";
  const rightLabel = vsMatch ? vsMatch[2].trim() : "After";
  const mid = Math.ceil(bullets.length / 2);
  const left = bullets.slice(0, mid);
  const right = bullets.slice(mid);

  const vsProg = spring({ frame: Math.max(0, frame - 8), fps, config: { damping: 16, stiffness: 140 }, durationInFrames: 15 });

  return (
    <div style={{ display: "flex", alignItems: "stretch", gap: 0, maxWidth: 1100, margin: "0 auto" }}>
      <div style={{
        flex: 1, display: "flex", flexDirection: "column", gap: 12,
        ...stag(frame, fps, 0, 6, 0),
      }}>
        <div style={{ fontSize: 28, fontWeight: 700, color: "#ff6b6b", marginBottom: 8, textAlign: "center" }}>
          {leftLabel}
        </div>
        {left.map((bp, i) => (
          <div key={i} style={{
            ...stag(frame, fps, i, 12, 8),
            background: hexA("#ff6b6b", 0.06),
            border: `1px solid ${hexA("#ff6b6b", 0.15)}`,
            borderRadius: 10, padding: "14px 20px",
            fontSize: 24, color: C.white, lineHeight: 1.5,
          }}>
            {bp}
          </div>
        ))}
      </div>

      <div style={{
        display: "flex", alignItems: "center", justifyContent: "center",
        width: 80, flexShrink: 0,
        opacity: interpolate(vsProg, [0, 1], [0, 1]),
        transform: `scale(${interpolate(vsProg, [0, 1], [0.5, 1])})`,
      }}>
        <div style={{
          fontSize: 24, fontWeight: 900, color: C.white,
          background: hexA(C.white, 0.08),
          border: `1px solid ${hexA(C.white, 0.15)}`,
          borderRadius: "50%", width: 52, height: 52,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>VS</div>
      </div>

      <div style={{
        flex: 1, display: "flex", flexDirection: "column", gap: 12,
        ...stag(frame, fps, 0, 10, 0),
      }}>
        <div style={{ fontSize: 28, fontWeight: 700, color: "#51cf66", marginBottom: 8, textAlign: "center" }}>
          {rightLabel}
        </div>
        {right.map((bp, i) => (
          <div key={i} style={{
            ...stag(frame, fps, i, 16, 8),
            background: hexA("#51cf66", 0.06),
            border: `1px solid ${hexA("#51cf66", 0.15)}`,
            borderRadius: 10, padding: "14px 20px",
            fontSize: 24, color: C.white, lineHeight: 1.5,
          }}>
            {bp}
          </div>
        ))}
      </div>
    </div>
  );
};

/* ═══════════════ 主组件 ═══════════════ */

const SlideTechDark: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const layout = detectLayout(data);

  return (
    <AbsoluteFill style={{
      fontFamily: "'PingFang SC','Hiragino Sans GB','Noto Sans CJK SC',sans-serif",
      overflow: "hidden",
    }}>
      <GridBg />
      <div style={{
        position: "relative", zIndex: 1,
        height: "100%",
        display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center",
        padding: "60px 120px",
      }}>
        <Title text={data.title} subtitle={data.chart_hint} />
        {layout === "standard" && <StandardLayout bullets={data.bullet_points} />}
        {layout === "grid" && <GridLayout bullets={data.bullet_points} />}
        {layout === "metric" && <MetricLayout bullets={data.bullet_points} />}
        {layout === "code" && <CodeLayout bullets={data.bullet_points} />}
        {layout === "steps" && <StepsLayout bullets={data.bullet_points} />}
        {layout === "compare" && <CompareLayout bullets={data.bullet_points} chartHint={data.chart_hint} />}
      </div>
    </AbsoluteFill>
  );
};

/* ═══════════════ 注册 ═══════════════ */

registry.register(
  {
    id: "slide.tech-dark",
    schema: "slide",
    name: "极简深色卡片",
    description: "深色背景 PPT 卡片，适合数据展示、架构总览、多组对比。支持 6 种自动检测布局（标准/网格/指标/代码/步骤/对比）。需要 title 和 bullet_points。",
    isDefault: true,
    tags: ["数据密集", "架构", "对比", "指标"],
  },
  SlideTechDark,
);

export { SlideTechDark };
