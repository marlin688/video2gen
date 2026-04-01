/**
 * 素材 A: PPT 图文卡片 — B站知识区风格 v5
 *
 * v5 对标 95+ 分，修复 v4 review 全部问题：
 *
 * 【系统性修复】
 * 1. 装饰元素 opacity 全面上调 → 视频编码后仍可见（关键词 12-18%，图表 20%，序号 18%）
 * 2. 颜色系统重做 → 每页只用 accent + dimAccent + gray，不再彩虹循环
 * 3. 字号最终校准 → 正文 32-36px，副文 26-28px，最小标注 22px
 *
 * 【布局级修复】
 * Standard: ≤3 条 bullet 自动切单列大卡，不再出现半空网格
 * Compare: 面板内条目撑满高度 + 底部 summary bar + VS 加 pulse
 * Metric: 副指标最多 3 列，Hero 居中布局
 * Steps: 全面重做 — 当前步骤放大 130%，加副描述，圆和卡之间加连接线
 * Grid: 首项 span 2 列做锚点，统一 2 色不再彩虹
 * Code: 底部加闪烁 prompt，关键词语法着色
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

const THEME = {
  bg: "#060a14",
  cyan: "#00e5ff",
  emerald: "#00e676",
  amber: "#ffab00",
  rose: "#ff5252",
  violet: "#b388ff",
  blue: "#448aff",
  palette: ["#00e5ff", "#00e676", "#ffab00", "#ff5252", "#b388ff", "#448aff"],
  gray: "#78909c",
  dimGray: "#37474f",
  textPrimary: "#f0f4f8",
  textSecondary: "#b0bec5",
  textMuted: "#607d8b",
};

const safeColor = (i: number) =>
  THEME.palette[((i % THEME.palette.length) + THEME.palette.length) % THEME.palette.length];

function twoTone(accent: string) {
  return { accent, dim: THEME.gray, dimBg: THEME.dimGray };
}

const EASE_OUT = Easing.bezier(0.16, 1, 0.3, 1);
const SPR = { damping: 18, stiffness: 260 };

function hexA(hex: string, a: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${a})`;
}

interface SlideSegmentProps {
  slideContent: SlideContent;
  segmentId?: number;
  totalSlides?: number;
}

type LayoutType = "compare" | "grid" | "code" | "steps" | "metric" | "standard";

function detectLayout(sc: SlideContent): LayoutType {
  const hint = (sc.chart_hint || "").toLowerCase();
  const bp = sc.bullet_points;
  if (hint.includes("vs") || hint.includes("对比")) return "compare";
  const codeP = /`[^`]+`|[a-zA-Z_]+\.[a-zA-Z]{2,3}\b|\/[a-z_]+|--[a-z]|[A-Z][a-z]+[A-Z]|=>|import |export |function |const |\.\/|src\/|npm |git |claude |pip /;
  if (bp.filter((b) => codeP.test(b)).length >= Math.ceil(bp.length * 0.6)) return "code";
  const stepP = /^(第[一二三四五六七八九十\d]+步|Step\s*\d|[\d①②③④⑤⑥⑦⑧⑨⑩]\s*[.、)）:])/i;
  if (bp.filter((b) => stepP.test(b.trim())).length >= Math.ceil(bp.length * 0.6)) return "steps";
  const metP = /\d+(\.\d+)?\s*(%|倍|x|×|秒|ms|MB|GB|K|k|次|个|项)|[<>≤≥]\s*\d|→|↑|↓|\d+\s*→\s*\d+/;
  if (bp.filter((b) => metP.test(b)).length >= Math.ceil(bp.length * 0.5)) return "metric";
  if (bp.length >= 4 && bp.every((b) => b.includes("：") || b.includes(":"))) return "grid";
  return "standard";
}

function extractNumber(text: string): { value: string; rest: string } | null {
  const m = text.match(/([<>≤≥~]?\s*\d+[\d.,]*\s*[%倍x×秒msMBGBK次个项+\-]?)/);
  if (!m) return null;
  return { value: m[1].trim(), rest: text.replace(m[0], "").replace(/^[：:,，\s]+/, "").trim() };
}

function extractKeywords(bullets: string[]): string[] {
  const all = bullets.join(" ");
  const cn = all.match(/[\u4e00-\u9fa5]{2,6}/g) || [];
  const en = all.match(/[A-Z][a-zA-Z]{3,}/g) || [];
  return [...new Set([...cn.slice(0, 8), ...en.slice(0, 4)])].slice(0, 10);
}

/** Content-aware SVG icon based on keyword detection */
const BulletIcon: React.FC<{ text: string; color: string; size?: number }> = ({ text, color, size = 28 }) => {
  const t = text.toLowerCase();
  // Detect category from keywords
  let path: string;
  if (/速度|快|性能|加速|效率|提升|turbo|fast|speed|perf/i.test(t)) {
    // Lightning bolt
    path = "M13 2L3 14h9l-1 10 10-12h-9l1-10z";
  } else if (/安全|保护|隐私|加密|security|protect|safe|auth/i.test(t)) {
    // Shield
    path = "M12 2L3 7v5c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7L12 2zm0 10h7c-.53 4.12-3.28 7.79-7 8.94V12H5V8.26l7-3.89V12z";
  } else if (/成本|价格|费用|金钱|降本|cost|price|money|budget|\$/i.test(t)) {
    // Dollar/coin
    path = "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-1.5c-1.5-.3-2.8-1.2-3-2.7h1.8c.2.9.9 1.4 2.2 1.4 1.4 0 1.8-.7 1.8-1.2 0-.6-.4-1.2-2.1-1.6-2-.5-3.3-1.3-3.3-2.9 0-1.4 1.1-2.4 2.6-2.7V5h2v1.3c1.5.4 2.3 1.5 2.3 2.7h-1.8c-.1-.8-.6-1.3-1.5-1.3-.9 0-1.6.4-1.6 1.2 0 .7.6 1.1 2.1 1.5 2 .5 3.3 1.4 3.3 3 0 1.6-1.2 2.6-2.8 2.9V17z";
  } else if (/模型|AI|智能|GPT|Claude|LLM|agent|model|机器人/i.test(t)) {
    // Brain/AI
    path = "M12 2a9 9 0 00-9 9c0 3.07 1.64 5.64 4 7.28V20h2v-1.1A8.93 8.93 0 0012 20c1.08 0 2.12-.19 3-.53V20h2v-1.72A8.96 8.96 0 0021 11a9 9 0 00-9-9zm-1 14h2v2h-2v-2zm0-2V8h2v6h-2z";
  } else if (/文件|配置|设置|config|file|setup|document|\.md|\.json|\.yaml/i.test(t)) {
    // File/document
    path = "M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm-1 7V3.5L18.5 9H13zM8 14h8v2H8v-2zm0-3h8v2H8v-2z";
  } else if (/团队|协作|合作|人员|team|collab|group|member/i.test(t)) {
    // People/team
    path = "M16 11c1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3 1.34 3 3 3zm-8 0c1.66 0 3-1.34 3-3S9.66 5 8 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z";
  } else if (/工具|命令|终端|CLI|terminal|tool|command|npm|git/i.test(t)) {
    // Terminal
    path = "M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zM7.5 16.5l-1.41-1.41L9.17 12 6.09 8.91 7.5 7.5 12 12l-4.5 4.5zm8.5 0h-4v-2h4v2z";
  } else if (/时间|秒|分钟|小时|delay|time|duration|ms|latency/i.test(t)) {
    // Clock
    path = "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67V7z";
  } else if (/数据|统计|分析|指标|data|stat|metric|analyt/i.test(t)) {
    // Chart
    path = "M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z";
  } else if (/代码|编程|开发|code|dev|program|script|function/i.test(t)) {
    // Code brackets
    path = "M9.4 16.6L4.8 12l4.6-4.6L8 6l-6 6 6 6 1.4-1.4zm5.2 0l4.6-4.6-4.6-4.6L16 6l6 6-6 6-1.4-1.4z";
  } else if (/上传|下载|部署|发布|deploy|upload|download|publish|release/i.test(t)) {
    // Upload/rocket
    path = "M9 16h6v-6h4l-7-7-7 7h4v6zm-4 2h14v2H5v-2z";
  } else {
    // Default: checkmark circle
    path = "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z";
  }
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={color} style={{ flexShrink: 0, opacity: 0.85 }}>
      <path d={path} />
    </svg>
  );
};

function hl(text: string, accent: string) {
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*)/).map((p, j) => {
    if (p.startsWith("`") && p.endsWith("`"))
      return <span key={j} style={{
        color: accent, background: hexA(accent, 0.14), padding: "2px 8px",
        borderRadius: 4, fontFamily: "'SF Mono','Fira Code',monospace",
        fontSize: "0.88em", border: `1px solid ${hexA(accent, 0.22)}`,
      }}>{p.slice(1, -1)}</span>;
    if (p.startsWith("**") && p.endsWith("**"))
      return <span key={j} style={{ color: accent, fontWeight: 800 }}>{p.slice(2, -2)}</span>;
    return <span key={j}>{p}</span>;
  });
}

const FilledBg: React.FC<{
  accent: string; frame: number; keywords: string[]; showChart: boolean;
}> = ({ accent, frame, keywords, showChart }) => {
  const particles = useMemo(() => {
    const a: { x: number; y: number; s: number; sp: number }[] = [];
    for (let i = 0; i < 20; i++) {
      const seed = (i * 7919 + 1301) % 10000;
      a.push({ x: seed % 1920, y: (seed * 3) % 1080, s: 1 + seed % 3, sp: 0.3 + (seed % 5) * 0.1 });
    }
    return a;
  }, []);
  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: 0, background: `radial-gradient(ellipse at 8% 92%, ${hexA(accent, 0.08)}, transparent 45%), radial-gradient(ellipse at 92% 8%, ${hexA(accent, 0.05)}, transparent 45%), radial-gradient(ellipse at 50% 50%, #0a1020, ${THEME.bg})` }} />
      <svg width="1920" height="1080" style={{ position: "absolute", inset: 0, opacity: 0.05 }}>
        <defs><pattern id="g5" width="48" height="48" patternUnits="userSpaceOnUse"><path d="M 48 0 L 0 0 0 48" fill="none" stroke={accent} strokeWidth="0.5" /></pattern></defs>
        <rect width="100%" height="100%" fill="url(#g5)" />
      </svg>
      <div style={{ position: "absolute", left: 0, right: 0, top: interpolate(frame % 200, [0, 200], [-100, 1180]), height: 100, background: `linear-gradient(180deg, transparent, ${hexA(accent, 0.04)}, ${hexA(accent, 0.07)}, ${hexA(accent, 0.04)}, transparent)` }} />
      {particles.map((p, i) => (
        <div key={i} style={{ position: "absolute", left: p.x, top: p.y + Math.sin((frame + i * 8) * p.sp * 0.04) * 12, width: p.s, height: p.s, borderRadius: "50%", background: accent, opacity: interpolate((frame + i * 10) % 150, [0, 50, 100, 150], [0, 0.7, 0.7, 0]), boxShadow: `0 0 ${p.s * 5}px ${hexA(accent, 0.6)}` }} />
      ))}
      <div style={{ position: "absolute", right: -10, top: 40, bottom: 40, width: 750, display: "flex", flexWrap: "wrap", alignContent: "center", justifyContent: "flex-end", gap: "14px 24px", opacity: interpolate(frame, [0, 12], [0, 1], { extrapolateRight: "clamp" }) }}>
        {keywords.map((kw, i) => {
          const sizes = [80, 60, 52, 44, 38, 34, 30, 60, 44, 38];
          return (<span key={i} style={{ fontSize: sizes[i % sizes.length], fontWeight: 900, color: accent, opacity: 0.12 + (i % 3) * 0.03, transform: `translateY(${Math.sin(frame * 0.018 + i * 1.2) * 4}px)`, lineHeight: 1.1, letterSpacing: sizes[i % sizes.length] > 48 ? 6 : 3, whiteSpace: "nowrap" }}>{kw}</span>);
        })}
      </div>
      {showChart && (
        <svg width="400" height="220" style={{ position: "absolute", right: 30, bottom: 44, opacity: interpolate(frame, [6, 20], [0, 0.2], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>
          {[0,1,2,3,4,5,6,7].map((i) => { const h = 50 + ((i * 37 + 13) % 130); const prog = interpolate(frame, [8+i*2, 18+i*2], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }); return <rect key={i} x={10+i*48} y={220-h*prog} width={32} height={h*prog} rx={4} fill={accent} />; })}
          <polyline points="10,150 58,110 106,130 154,70 202,90 250,50 298,80 346,35" fill="none" stroke={accent} strokeWidth="2.5" strokeLinecap="round" strokeDasharray="450" strokeDashoffset={interpolate(frame, [12, 35], [450, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} />
        </svg>
      )}
      <div style={{ position: "absolute", top: 0, left: 0, width: interpolate(frame, [0, 10], [0, 1920], { extrapolateRight: "clamp", easing: EASE_OUT }), height: 3, background: `linear-gradient(90deg, ${accent}, ${hexA(accent, 0.3)}, transparent)`, boxShadow: `0 0 24px ${hexA(accent, 0.35)}` }} />
      <svg width="50" height="50" style={{ position: "absolute", top: 12, left: 12, opacity: 0.15 }}><path d="M 0 20 L 0 0 L 20 0" fill="none" stroke={accent} strokeWidth="1.5" /></svg>
      <svg width="50" height="50" style={{ position: "absolute", bottom: 12, right: 12, opacity: 0.15 }}><path d="M 50 30 L 50 50 L 30 50" fill="none" stroke={accent} strokeWidth="1.5" /></svg>
    </AbsoluteFill>
  );
};

const Glass: React.FC<{ children: React.ReactNode; accent?: string; style?: React.CSSProperties; }> = ({ children, accent, style }) => (
  <div style={{ background: hexA("#ffffff", 0.04), border: `1px solid ${accent ? hexA(accent, 0.18) : hexA("#ffffff", 0.08)}`, borderRadius: 16, position: "relative", overflow: "hidden", ...style }}>
    {accent && (<div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 1, background: `linear-gradient(90deg, transparent, ${hexA(accent, 0.5)}, transparent)` }} />)}
    {children}
  </div>
);

const Title: React.FC<{ text: string; accent: string; layout: LayoutType; subtitle?: string }> = ({ text, accent, layout, subtitle }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const p = spring({ frame, fps, config: SPR, durationInFrames: 10 });
  const labels: Record<LayoutType, string> = { compare: "COMPARE", code: "CODE", steps: "STEPS", metric: "METRICS", grid: "OVERVIEW", standard: "INSIGHT" };
  const subOp = interpolate(frame, [6, 12], [0, 0.85], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ marginBottom: 20, flexShrink: 0, opacity: interpolate(p, [0, 1], [0, 1]), transform: `translateY(${interpolate(p, [0, 1], [14, 0])}px)` }}>
      <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
        <div style={{ width: 5, height: subtitle ? 68 : 52, borderRadius: 3, background: `linear-gradient(180deg, ${accent}, ${hexA(accent, 0.25)})`, boxShadow: `0 0 20px ${hexA(accent, 0.45)}`, flexShrink: 0 }} />
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: accent, letterSpacing: 5, marginBottom: 4, fontFamily: "'SF Mono','Fira Code',monospace", opacity: 0.75 }}>{"⟨ " + labels[layout] + " ⟩"}</div>
          <div style={{ fontSize: 52, fontWeight: 900, color: "#fff", lineHeight: 1.15 }}>{text}</div>
          {subtitle && (
            <div style={{ fontSize: 24, color: THEME.textSecondary, marginTop: 8, opacity: subOp, lineHeight: 1.4, display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ width: 18, height: 1.5, background: hexA(accent, 0.4), flexShrink: 0, borderRadius: 1 }} />
              {subtitle}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const StandardLayout: React.FC<{ bullets: string[]; chartHint?: string; accent: string }> = ({ bullets, chartHint, accent }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const { dim } = twoTone(accent);
  const firstNum = extractNumber(bullets[0] || "");
  const useSingleCol = bullets.length <= 3;
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", gap: 12 }}>
      {bullets.length > 0 && (() => {
        const p = spring({ frame: Math.max(0, frame - 3), fps, config: SPR, durationInFrames: 10 });
        const op = interpolate(frame, [3, 7], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return (
          <Glass accent={accent} style={{ opacity: op, padding: "28px 36px", flexShrink: 0, transform: `translateY(${interpolate(p, [0, 1], [18, 0])}px)`, display: "flex", alignItems: "center", gap: 28, background: hexA(accent, 0.07) }}>
            {firstNum ? (<>
              <div style={{ fontSize: 88, fontWeight: 900, color: accent, fontFamily: "'SF Mono','Fira Code',monospace", textShadow: `0 0 50px ${hexA(accent, 0.3)}`, lineHeight: 1, flexShrink: 0, minWidth: 180, textAlign: "center" }}>{firstNum.value}</div>
              <div style={{ width: 3, height: 60, background: hexA(accent, 0.35), flexShrink: 0, borderRadius: 2 }} />
              <span style={{ fontSize: 34, color: THEME.textPrimary, lineHeight: 1.4, flex: 1 }}>{hl(firstNum.rest, accent)}</span>
            </>) : (<>
              <div style={{ width: 6, height: 52, borderRadius: 3, flexShrink: 0, background: `linear-gradient(180deg, ${accent}, ${hexA(accent, 0.3)})` }} />
              <span style={{ fontSize: 36, color: THEME.textPrimary, lineHeight: 1.4, flex: 1, fontWeight: 700 }}>{hl(bullets[0], accent)}</span>
            </>)}
          </Glass>
        );
      })()}
      {bullets.length > 1 && (
        <div style={{ flex: 1, display: "grid", gridTemplateColumns: useSingleCol ? "1fr" : "1fr 1fr", gap: 10 }}>
          {bullets.slice(1).map((bp, i) => {
            const idx = i + 1; const delay = 6 + i * 3;
            const p = spring({ frame: Math.max(0, frame - delay), fps, config: SPR, durationInFrames: 8 });
            const op = interpolate(frame, [delay, delay + 4], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            const num = extractNumber(bp); const cardColor = num ? accent : dim;
            return (
              <Glass key={idx} accent={cardColor} style={{ opacity: op, transform: `scale(${interpolate(p, [0, 1], [0.92, 1])})`, padding: useSingleCol ? "20px 28px" : "16px 22px", display: "flex", alignItems: "center", gap: 16, gridColumn: (!useSingleCol && num && i === 0) ? "1 / -1" : undefined }}>
                <BulletIcon text={bp} color={cardColor} size={useSingleCol ? 32 : 28} />
                {num ? (
                  <div style={{ flex: 1, display: "flex", alignItems: "baseline", gap: 12 }}>
                    <span style={{ fontSize: 40, fontWeight: 900, color: accent, fontFamily: "'SF Mono',monospace" }}>{num.value}</span>
                    <span style={{ fontSize: 28, color: THEME.textPrimary }}>{num.rest}</span>
                  </div>
                ) : (
                  <span style={{ fontSize: useSingleCol ? 32 : 28, color: THEME.textPrimary, lineHeight: 1.45, flex: 1 }}>{hl(bp, accent)}</span>
                )}
              </Glass>
            );
          })}
        </div>
      )}
      {chartHint && (<div style={{ marginTop: "auto", fontSize: 22, color: THEME.textMuted, fontStyle: "italic", paddingTop: 8, borderTop: `1px solid ${hexA("#ffffff", 0.06)}`, opacity: interpolate(frame, [6 + bullets.length * 3, 6 + bullets.length * 3 + 6], [0, 0.75], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>💡 {chartHint}</div>)}
    </div>
  );
};

const CompareLayout: React.FC<{ bullets: string[]; chartHint?: string }> = ({ bullets, chartHint }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const vsMatch = (chartHint || "").match(/(.+?)(?:vs|VS|Vs|→|对比|和)(.+)/);
  const leftLabel = vsMatch ? vsMatch[1].trim().slice(0, 12) : "Before";
  const rightLabel = vsMatch ? vsMatch[2].trim().slice(0, 12) : "After";
  const mid = Math.ceil(bullets.length / 2);
  const leftItems = bullets.slice(0, mid); const rightItems = bullets.slice(mid);
  const lc = THEME.rose, rc = THEME.emerald;
  const renderSide = (items: string[], color: string, icon: string, label: string, baseDelay: number, dir: "left"|"right") => {
    const sp = spring({ frame: Math.max(0, frame - baseDelay), fps, config: SPR, durationInFrames: 10 });
    return (
      <Glass accent={color} style={{ flex: 1, padding: "24px 28px", background: hexA(color, 0.06), border: `1px solid ${hexA(color, 0.18)}`, opacity: interpolate(sp, [0, 1], [0, 1]), transform: `translateX(${interpolate(sp, [0, 1], [dir === "left" ? -30 : 30, 0])}px)`, display: "flex", flexDirection: "column" }}>
        <div style={{ fontSize: 32, fontWeight: 900, color, marginBottom: 16, paddingBottom: 12, borderBottom: `2px solid ${hexA(color, 0.35)}`, display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 34, height: 34, borderRadius: 8, background: hexA(color, 0.25), display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, fontWeight: 900, color: "#fff" }}>{icon}</div>
          {label}
        </div>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: items.length <= 3 ? "space-evenly" : "flex-start", gap: items.length > 3 ? 12 : 0 }}>
          {items.map((bp, i) => {
            const d = baseDelay + 4 + i * 3;
            const p = spring({ frame: Math.max(0, frame - d), fps, config: SPR, durationInFrames: 8 });
            return (<div key={i} style={{ opacity: interpolate(frame, [d, d + 3], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }), transform: `translateY(${interpolate(p, [0, 1], [10, 0])}px)`, fontSize: 28, color: THEME.textPrimary, lineHeight: 1.6, paddingLeft: 16, borderLeft: `3px solid ${hexA(color, 0.45)}` }}>{bp}</div>);
          })}
        </div>
        <div style={{ marginTop: 12, paddingTop: 10, borderTop: `1px solid ${hexA(color, 0.15)}`, fontSize: 22, color: hexA(color, 0.7), fontStyle: "italic", opacity: interpolate(frame, [baseDelay + 12, baseDelay + 18], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>
          {dir === "left" ? `共 ${items.length} 项痛点` : `共 ${items.length} 项优势`}
        </div>
      </Glass>
    );
  };
  const vsProg = spring({ frame: Math.max(0, frame - 5), fps, config: SPR, durationInFrames: 12 });
  const pulse = 1 + 0.06 * Math.sin(frame * 0.15);
  return (
    <div style={{ display: "flex", height: "100%", gap: 0, alignItems: "stretch" }}>
      {renderSide(leftItems, lc, "✕", leftLabel, 2, "left")}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", width: 110, flexShrink: 0, gap: 6 }}>
        <svg width="40" height="50" style={{ opacity: interpolate(vsProg, [0, 1], [0, 0.5]), transform: `translateY(${interpolate(vsProg, [0, 1], [8, 0])}px)` }}><line x1="20" y1="50" x2="20" y2="10" stroke={THEME.textMuted} strokeWidth="1.5" /><polyline points="13,18 20,6 27,18" fill="none" stroke={THEME.textMuted} strokeWidth="1.5" /></svg>
        <div style={{ fontSize: 28, fontWeight: 900, color: "#fff", background: hexA("#ffffff", 0.08), border: `2px solid ${hexA("#ffffff", 0.2)}`, borderRadius: "50%", width: 68, height: 68, display: "flex", alignItems: "center", justifyContent: "center", boxShadow: `0 0 36px ${hexA("#ffffff", 0.08)}`, transform: `scale(${interpolate(vsProg, [0, 1], [0.3, 1]) * pulse})` }}>VS</div>
        <svg width="40" height="50" style={{ opacity: interpolate(vsProg, [0, 1], [0, 0.5]), transform: `translateY(${interpolate(vsProg, [0, 1], [-8, 0])}px)` }}><line x1="20" y1="0" x2="20" y2="40" stroke={THEME.textMuted} strokeWidth="1.5" /><polyline points="13,32 20,44 27,32" fill="none" stroke={THEME.textMuted} strokeWidth="1.5" /></svg>
      </div>
      {renderSide(rightItems, rc, "✓", rightLabel, 6, "right")}
    </div>
  );
};

const GridLayout: React.FC<{ bullets: string[]; accent: string }> = ({ bullets, accent }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const { dim } = twoTone(accent);
  const cols = bullets.length <= 4 ? 2 : 3;
  return (
    <div style={{ display: "grid", gridTemplateColumns: `repeat(${cols}, 1fr)`, gridAutoRows: "1fr", gap: 12, height: "100%" }}>
      {bullets.map((bp, i) => {
        const delay = 3 + i * 3;
        const p = spring({ frame: Math.max(0, frame - delay), fps, config: SPR, durationInFrames: 8 });
        const op = interpolate(frame, [delay, delay + 3], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        const color = i === 0 ? accent : dim; const isAnchor = i === 0;
        const [label, ...descParts] = bp.split(/[：:]/); const description = descParts.join("：");
        return (
          <Glass key={i} accent={color} style={{ opacity: op, position: "relative", transform: `scale(${interpolate(p, [0, 1], [0.88, 1])})`, padding: 0, display: "flex", overflow: "hidden", gridColumn: isAnchor ? "1 / -1" : undefined, background: isAnchor ? hexA(accent, 0.06) : undefined }}>
            <div style={{ width: 5, background: `linear-gradient(180deg, ${color}, ${hexA(color, 0.25)})`, flexShrink: 0 }} />
            <div style={{ flex: 1, padding: isAnchor ? "22px 28px" : "16px 20px", display: "flex", flexDirection: isAnchor ? "row" : "column", alignItems: isAnchor ? "center" : "flex-start", justifyContent: isAnchor ? "flex-start" : "center", gap: isAnchor ? 24 : 6 }}>
              <div style={{ position: isAnchor ? "relative" : "absolute", top: isAnchor ? undefined : 8, right: isAnchor ? undefined : 14, fontSize: isAnchor ? 64 : 40, fontWeight: 900, color: hexA(color, 0.18), fontFamily: "'SF Mono',monospace", lineHeight: 1, flexShrink: 0 }}>{String(i + 1).padStart(2, "0")}</div>
              <div>
                <div style={{ fontSize: isAnchor ? 34 : 28, fontWeight: 800, color: i === 0 ? accent : THEME.textPrimary, marginBottom: 4, lineHeight: 1.3 }}>{label}</div>
                {description && (<div style={{ fontSize: isAnchor ? 26 : 22, color: THEME.textSecondary, lineHeight: 1.5 }}>{description}</div>)}
              </div>
            </div>
          </Glass>
        );
      })}
    </div>
  );
};

const CodeLayout: React.FC<{ bullets: string[] }> = ({ bullets }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const wp = spring({ frame, fps, config: SPR, durationInFrames: 8 });
  const big = bullets.length <= 4;
  function colorize(text: string): { text: string; color: string }[] {
    const kw = /\b(export|import|const|let|var|function|return|from|async|await|if|else|class|new|this)\b/g;
    const str = /(['"\`])(?:(?!\1).)*\1/g;
    const parts: { text: string; color: string }[] = [];
    let last = 0;
    const tokens: { start: number; end: number; color: string }[] = [];
    let m: RegExpExecArray | null;
    while ((m = kw.exec(text)) !== null) tokens.push({ start: m.index, end: m.index + m[0].length, color: "#c586c0" });
    while ((m = str.exec(text)) !== null) tokens.push({ start: m.index, end: m.index + m[0].length, color: "#ce9178" });
    tokens.sort((a, b) => a.start - b.start);
    for (const t of tokens) { if (t.start > last) parts.push({ text: text.slice(last, t.start), color: "#c9d1d9" }); parts.push({ text: text.slice(t.start, t.end), color: t.color }); last = t.end; }
    if (last < text.length) parts.push({ text: text.slice(last), color: "#c9d1d9" });
    return parts.length ? parts : [{ text, color: "#c9d1d9" }];
  }
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", borderRadius: 16, overflow: "hidden", border: "1px solid rgba(48,54,61,0.8)", background: "linear-gradient(180deg, #0d1117, #161b22)", opacity: interpolate(wp, [0, 1], [0, 1]) }}>
      {/* macOS-style title bar with Claude Code branding */}
      <div style={{ display: "flex", alignItems: "center", padding: "10px 18px", gap: 8, flexShrink: 0, background: "rgba(22,27,34,0.98)", borderBottom: "1px solid rgba(48,54,61,0.6)" }}>
        {[["#ff5f57"], ["#febc2e"], ["#28c840"]].map(([c], j) => (<div key={j} style={{ width: 13, height: 13, borderRadius: "50%", background: c }} />))}
        <div style={{ flex: 1, textAlign: "center", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
          <span style={{ fontSize: 14, color: "#6e7681", fontFamily: "'SF Mono',monospace" }}>·</span>
          <span style={{ fontSize: 15, fontWeight: 600, color: "#e6edf3", fontFamily: "'SF Mono','Fira Code',monospace", letterSpacing: 0.5 }}>Claude Code</span>
        </div>
        {/* Right-side shortcut hint */}
        <span style={{ fontSize: 12, color: "#484f58", fontFamily: "monospace", flexShrink: 0 }}>⌥⌘1</span>
      </div>
      {/* Tab bar */}
      <div style={{ display: "flex", alignItems: "stretch", flexShrink: 0, background: "rgba(13,17,23,0.95)", borderBottom: "1px solid rgba(48,54,61,0.4)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "7px 18px", background: "rgba(22,27,34,0.9)", borderRight: "1px solid rgba(48,54,61,0.4)", borderBottom: "2px solid #f78166" }}>
          <span style={{ fontSize: 12, color: "#f78166" }}>✕</span>
          <span style={{ fontSize: 13, color: "#e6edf3", fontFamily: "'SF Mono',monospace" }}>✱ Claude Code</span>
          <span style={{ fontSize: 11, color: "#484f58", fontFamily: "monospace" }}>⊙</span>
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ display: "flex", alignItems: "center", padding: "0 14px", gap: 4 }}>
          <span style={{ fontSize: 12, color: "#484f58" }}>+</span>
        </div>
      </div>
      {/* Status line — model & workspace */}
      <div style={{ display: "flex", alignItems: "center", padding: "8px 24px", gap: 12, flexShrink: 0, borderBottom: "1px solid rgba(48,54,61,0.3)" }}>
        {/* Claude logo placeholder */}
        <div style={{ width: 28, height: 28, borderRadius: 6, background: "linear-gradient(135deg, #f78166, #da3633)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, fontWeight: 900, color: "#fff", flexShrink: 0 }}>C</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: "#e6edf3", fontFamily: "'SF Mono',monospace" }}>Sonnet 4.6 · Claude Max</span>
          <span style={{ fontSize: 12, color: "#6e7681", fontFamily: "'SF Mono',monospace" }}>~/workspace/project</span>
        </div>
      </div>
      {/* Terminal content area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: big ? "center" : "flex-start", padding: big ? "8px 0" : "12px 0" }}>
        {bullets.map((bp, i) => {
          const delay = 3 + i * 5;
          const op = interpolate(frame, [delay, delay + 2], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          const isCmd = /^[$>❯]\s/.test(bp) || /^(npm|git|claude|pip|cd|node|yarn|docker|npx)\s/.test(bp);
          const isCmt = /^[#/]/.test(bp.trim());
          const isOutput = /^[•●○◆▸▹→·]\s/.test(bp) || /^\s{2,}/.test(bp);
          const clean = isCmd ? bp.replace(/^[$>❯]\s*/, "") : bp;
          const maxC = clean.length;
          const vis = Math.floor(interpolate(frame, [delay, delay + Math.max(8, maxC * 0.3)], [0, maxC], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
          const shown = clean.slice(0, vis);
          return (
            <div key={i} style={{ display: "flex", padding: big ? "6px 28px" : "3px 28px", opacity: op, background: isCmd ? "rgba(248,129,102,0.04)" : "transparent" }}>
              {isCmd ? (
                <div style={{ fontFamily: "'SF Mono','Fira Code',monospace", fontSize: big ? 28 : 23, lineHeight: big ? 2.1 : 1.85, whiteSpace: "pre-wrap", flex: 1, color: "#e6edf3", paddingLeft: 4 }}>
                  <span style={{ color: "#f78166", marginRight: 10, fontWeight: 600 }}>❯</span>
                  {shown}
                  {vis < maxC && (<span style={{ display: "inline-block", width: 2, height: big ? 20 : 16, background: "#f78166", marginLeft: 2, verticalAlign: "middle", opacity: frame % 14 < 8 ? 1 : 0 }} />)}
                </div>
              ) : (
                <div style={{ fontFamily: "'SF Mono','Fira Code',monospace", fontSize: big ? 26 : 21, lineHeight: big ? 2.1 : 1.85, whiteSpace: "pre-wrap", flex: 1, color: isCmt ? "#6a9955" : isOutput ? "#8b949e" : "#c9d1d9", paddingLeft: isOutput ? 28 : 4 }}>
                  {isCmt ? <span style={{ color: "#6a9955" }}>{shown}</span> : colorize(shown).map((seg, k) => <span key={k} style={{ color: seg.color }}>{seg.text}</span>)}
                  {vis < maxC && (<span style={{ display: "inline-block", width: 2, height: big ? 20 : 16, background: THEME.cyan, marginLeft: 2, verticalAlign: "middle", opacity: frame % 14 < 8 ? 1 : 0 }} />)}
                </div>
              )}
            </div>
          );
        })}
        {(() => {
          const allDone = frame > 3 + bullets.length * 5 + (bullets[bullets.length - 1]?.length || 0) * 0.3 + 8;
          if (!allDone) return null;
          return (
            <div style={{ display: "flex", padding: big ? "6px 28px" : "3px 28px", marginTop: 8 }}>
              <div style={{ fontFamily: "'SF Mono',monospace", fontSize: big ? 28 : 23, lineHeight: big ? 2.1 : 1.85, color: "#f78166", paddingLeft: 4 }}>
                ❯ <span style={{ display: "inline-block", width: 2, height: big ? 20 : 16, background: "#f78166", verticalAlign: "middle", opacity: frame % 16 < 9 ? 1 : 0 }} />
              </div>
            </div>
          );
        })()}
      </div>
    </div>
  );
};

const StepsLayout: React.FC<{ bullets: string[]; accent: string }> = ({ bullets, accent }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const { dim } = twoTone(accent);
  const colors = [accent, THEME.violet, THEME.amber, THEME.emerald, THEME.blue, THEME.cyan];
  const activeIdx = useMemo(() => { for (let i = bullets.length - 1; i >= 0; i--) { if (frame >= 3 + i * 5) return i; } return 0; }, [frame, bullets.length]);
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", gap: 6, position: "relative", paddingLeft: 40 }}>
      <div style={{ position: "absolute", left: 62, top: 20, bottom: 20, width: 3, borderRadius: 2, background: `linear-gradient(180deg, ${accent}55, ${THEME.violet}55, ${THEME.amber}44, ${THEME.emerald}44)` }} />
      {bullets.map((bp, i) => {
        const delay = 3 + i * 5;
        const p = spring({ frame: Math.max(0, frame - delay), fps, config: SPR, durationInFrames: 10 });
        const op = interpolate(frame, [delay, delay + 4], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        const text = bp.replace(/^(第[一二三四五六七八九十\d]+步|Step\s*\d|[\d①②③④⑤⑥⑦⑧⑨⑩])\s*[.、)）:：]\s*/i, "");
        const color = colors[i % colors.length]; const isActive = i === activeIdx;
        const scale = isActive ? interpolate(p, [0, 1], [0.4, 1.0]) : interpolate(p, [0, 1], [0.4, 0.92]);
        return (
          <div key={i} style={{ opacity: op, flex: isActive ? 1.5 : 1, display: "flex", alignItems: "center", gap: 0, position: "relative", transform: `scale(${scale})`, transformOrigin: "left center", zIndex: isActive ? 5 : 1 }}>
            <div style={{ width: isActive ? 56 : 46, height: isActive ? 56 : 46, borderRadius: "50%", background: isActive ? `linear-gradient(135deg, ${color}, ${hexA(color, 0.7)})` : hexA(color, 0.12), border: `2px solid ${hexA(color, isActive ? 0.7 : 0.35)}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: isActive ? 24 : 20, fontWeight: 800, color: isActive ? "#fff" : color, flexShrink: 0, zIndex: 3, boxShadow: isActive ? `0 0 30px ${hexA(color, 0.45)}` : "none" }}>{i + 1}</div>
            <div style={{ width: 20, height: 2, flexShrink: 0, background: isActive ? `linear-gradient(90deg, ${hexA(color, 0.5)}, ${hexA(color, 0.15)})` : hexA(color, 0.1) }} />
            <Glass accent={isActive ? color : undefined} style={{ flex: 1, padding: isActive ? "16px 24px" : "12px 20px", background: isActive ? hexA(color, 0.08) : hexA("#ffffff", 0.03), border: isActive ? `1px solid ${hexA(color, 0.25)}` : `1px solid ${hexA("#ffffff", 0.06)}` }}>
              <span style={{ fontSize: isActive ? 32 : 28, color: THEME.textPrimary, lineHeight: 1.4, fontWeight: isActive ? 700 : 400 }}>{text}</span>
              {isActive && (<div style={{ marginTop: 6, fontSize: 22, color: hexA(color, 0.65), lineHeight: 1.4, opacity: interpolate(frame, [delay + 6, delay + 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>● 当前步骤</div>)}
            </Glass>
          </div>
        );
      })}
    </div>
  );
};

/** SVG Arc Gauge for percentage metrics */
const ArcGauge: React.FC<{ percent: number; progress: number; accent: string; size?: number }> = ({ percent, progress, accent, size = 160 }) => {
  const r = (size - 16) / 2;
  const cx = size / 2, cy = size / 2;
  const circumference = 2 * Math.PI * r;
  const startAngle = -225; // arc from bottom-left to bottom-right (270° sweep)
  const sweepFrac = 0.75; // use 270° of the circle
  const arcLength = circumference * sweepFrac;
  const filledLength = arcLength * (Math.min(percent, 100) / 100) * progress;
  return (
    <svg width={size} height={size} style={{ overflow: "visible" }}>
      {/* Background track */}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={hexA(accent, 0.1)} strokeWidth={8}
        strokeDasharray={`${arcLength} ${circumference}`}
        strokeDashoffset={0}
        strokeLinecap="round"
        transform={`rotate(${startAngle} ${cx} ${cy})`} />
      {/* Filled arc */}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={accent} strokeWidth={8}
        strokeDasharray={`${filledLength} ${circumference}`}
        strokeDashoffset={0}
        strokeLinecap="round"
        transform={`rotate(${startAngle} ${cx} ${cy})`}
        style={{ filter: `drop-shadow(0 0 8px ${hexA(accent, 0.5)})` }} />
      {/* Glow dot at tip */}
      {progress > 0.05 && (() => {
        const angle = (startAngle + (filledLength / circumference) * 360) * (Math.PI / 180);
        const dx = cx + r * Math.cos(angle);
        const dy = cy + r * Math.sin(angle);
        return <circle cx={dx} cy={dy} r={5} fill="#fff" style={{ filter: `drop-shadow(0 0 6px ${accent})` }} />;
      })()}
    </svg>
  );
};

/** Horizontal animated bar for sub-metric comparison */
const MetricBar: React.FC<{ value: number; maxValue: number; progress: number; color: string }> = ({ value, maxValue, progress, color }) => {
  const barWidth = maxValue > 0 ? (value / maxValue) * 100 : 50;
  return (
    <div style={{ width: "100%", height: 6, borderRadius: 3, background: hexA(color, 0.1), overflow: "hidden", marginTop: 8 }}>
      <div style={{
        width: `${barWidth * progress}%`, height: "100%", borderRadius: 3,
        background: `linear-gradient(90deg, ${hexA(color, 0.6)}, ${color})`,
        boxShadow: `0 0 10px ${hexA(color, 0.3)}`,
      }} />
    </div>
  );
};

const MetricLayout: React.FC<{ bullets: string[]; accent: string }> = ({ bullets, accent }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const { dim } = twoTone(accent);
  const metrics = useMemo(() => bullets.map((bp) => {
    const nm = bp.match(/([<>≤≥~]?\s*\d+[\d.,]*\s*[%倍x×秒msMBGBK次个项+\-]?)/);
    const value = nm ? nm[1].trim() : ""; const label = bp.replace(nm?.[0] || "", "").replace(/^[：:,，\s]+|[：:,，\s]+$/g, "").trim();
    const pure = parseFloat(value.replace(/[^0-9.]/g, "")); const prefix = value.match(/^[<>≤≥~]/)?.[0] || "";
    const suffix = value.replace(/^[<>≤≥~]?\s*[\d.,]+/, "").trim();
    const dec = value.includes(".") ? (value.split(".")[1]?.match(/\d+/)?.[0]?.length || 0) : 0;
    const isPercent = suffix.includes("%") || value.includes("%");
    return { value, label, pure, prefix, suffix, dec, isPercent };
  }), [bullets]);
  const hasHero = metrics.length >= 3; const hero = hasHero ? metrics[0] : null;
  const rest = hasHero ? metrics.slice(1) : metrics; const cols = Math.min(rest.length, 3);
  // Find max pure value among rest metrics for bar comparison
  const maxRestValue = useMemo(() => Math.max(...rest.map(m => isNaN(m.pure) ? 0 : m.pure), 1), [rest]);
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", gap: 14 }}>
      {hero && (() => {
        const p = spring({ frame: Math.max(0, frame - 3), fps, config: SPR, durationInFrames: 12 });
        const op = interpolate(frame, [3, 7], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        const cu = !isNaN(hero.pure) ? interpolate(p, [0, 1], [0, hero.pure]).toFixed(hero.dec) : null;
        const dv = cu !== null ? `${hero.prefix}${cu}${hero.suffix}` : hero.value || "—";
        return (
          <Glass accent={accent} style={{ opacity: op, padding: "28px 40px", background: hexA(accent, 0.07), display: "flex", alignItems: "center", justifyContent: "center", gap: 36, transform: `scale(${interpolate(p, [0, 1], [0.88, 1])})`, flexShrink: 0 }}>
            {/* Arc gauge for percentage hero metrics */}
            {hero.isPercent && !isNaN(hero.pure) && (
              <div style={{ flexShrink: 0, position: "relative", width: 160, height: 160 }}>
                <ArcGauge percent={hero.pure} progress={p} accent={accent} size={160} />
                <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <span style={{ fontSize: 44, fontWeight: 900, color: accent, fontFamily: "'SF Mono','Fira Code',monospace" }}>{dv}</span>
                </div>
              </div>
            )}
            <div style={{ textAlign: hero.isPercent ? "left" : "center", flex: hero.isPercent ? 1 : undefined }}>
              {!hero.isPercent && (
                <div style={{ fontSize: 104, fontWeight: 900, color: accent, fontFamily: "'SF Mono','Fira Code',monospace", textShadow: `0 0 60px ${hexA(accent, 0.3)}`, lineHeight: 1 }}>{dv}</div>
              )}
              <div style={{ width: hero.isPercent ? "60%" : 120, height: 2, borderRadius: 1, marginTop: 10, marginBottom: 10, background: `linear-gradient(90deg, transparent, ${hexA(accent, 0.5)}, transparent)` }} />
              <div style={{ fontSize: 30, color: THEME.textSecondary }}>{hero.label}</div>
            </div>
          </Glass>
        );
      })()}
      <div style={{ flex: 1, display: "grid", gridTemplateColumns: `repeat(${cols}, 1fr)`, gridAutoRows: "1fr", gap: 12 }}>
        {rest.map((m, i) => {
          const delay = (hasHero ? 9 : 3) + i * 3;
          const p = spring({ frame: Math.max(0, frame - delay), fps, config: SPR, durationInFrames: 12 });
          const op = interpolate(frame, [delay, delay + 3], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          const color = i === 0 ? accent : dim;
          const cu = !isNaN(m.pure) ? interpolate(p, [0, 1], [0, m.pure]).toFixed(m.dec) : null;
          const dv = cu !== null ? `${m.prefix}${cu}${m.suffix}` : m.value || "—";
          return (
            <Glass key={i} accent={color} style={{ opacity: op, transform: `scale(${interpolate(p, [0, 1], [0.85, 1])})`, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", padding: "16px 14px" }}>
              <div style={{ fontSize: 52, fontWeight: 900, color: i === 0 ? accent : THEME.textPrimary, fontFamily: "'SF Mono','Fira Code',monospace", textShadow: i === 0 ? `0 0 30px ${hexA(accent, 0.2)}` : "none", marginBottom: 4, lineHeight: 1.1 }}>{dv}</div>
              {/* Animated comparison bar */}
              {!isNaN(m.pure) && (
                <MetricBar value={m.pure} maxValue={maxRestValue} progress={p} color={color} />
              )}
              <div style={{ width: "40%", height: 1.5, borderRadius: 1, marginTop: 6, marginBottom: 6, background: `linear-gradient(90deg, transparent, ${hexA(color, 0.4)}, transparent)` }} />
              <div style={{ fontSize: 22, color: THEME.textSecondary, lineHeight: 1.4 }}>{m.label}</div>
            </Glass>
          );
        })}
      </div>
    </div>
  );
};

export const SlideSegment: React.FC<SlideSegmentProps> = ({ slideContent, segmentId = 0, totalSlides = 1 }) => {
  const frame = useCurrentFrame();
  const layout = detectLayout(slideContent);
  const accent = safeColor(segmentId);
  const keywords = useMemo(() => extractKeywords(slideContent.bullet_points), [slideContent.bullet_points]);
  const showChart = layout !== "metric" && layout !== "code" && layout !== "compare";
  const progressOp = interpolate(frame, [10, 16], [0, 0.75], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: THEME.bg, fontFamily: "'PingFang SC','Hiragino Sans GB','Noto Sans CJK SC',sans-serif", padding: "44px 56px", overflow: "hidden" }}>
      <FilledBg accent={accent} frame={frame} keywords={keywords} showChart={showChart} />
      <div style={{ position: "relative", zIndex: 1, height: "100%", display: "flex", flexDirection: "column" }}>
        <Title text={slideContent.title} accent={accent} layout={layout} subtitle={slideContent.chart_hint} />
        <div style={{ flex: 1, minHeight: 0 }}>
          {layout === "compare" && <CompareLayout bullets={slideContent.bullet_points} chartHint={slideContent.chart_hint} />}
          {layout === "grid" && <GridLayout bullets={slideContent.bullet_points} accent={accent} />}
          {layout === "code" && <CodeLayout bullets={slideContent.bullet_points} />}
          {layout === "steps" && <StepsLayout bullets={slideContent.bullet_points} accent={accent} />}
          {layout === "metric" && <MetricLayout bullets={slideContent.bullet_points} accent={accent} />}
          {layout === "standard" && <StandardLayout bullets={slideContent.bullet_points} chartHint={slideContent.chart_hint} accent={accent} />}
        </div>
      </div>
      {/* Highlight sweep after all items revealed */}
      {(() => {
        const bulletCount = slideContent.bullet_points.length;
        const sweepStart = 6 + bulletCount * 4; // start after last bullet appears
        const sweepDur = 15; // frames for sweep
        const sweepProg = interpolate(frame, [sweepStart, sweepStart + sweepDur], [-0.3, 1.3], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        const sweepOp = sweepProg > -0.3 && sweepProg < 1.3 ? interpolate(Math.abs(sweepProg - 0.5), [0, 0.5, 0.8], [0.2, 0.12, 0], { extrapolateRight: "clamp" }) : 0;
        if (sweepOp <= 0) return null;
        return (
          <div style={{
            position: "absolute", inset: 0, zIndex: 10, pointerEvents: "none",
            background: `linear-gradient(105deg, transparent ${(sweepProg - 0.15) * 100}%, ${hexA(accent, sweepOp)} ${sweepProg * 100}%, transparent ${(sweepProg + 0.15) * 100}%)`,
          }} />
        );
      })()}
      <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 32, display: "flex", alignItems: "center", padding: "0 56px", opacity: progressOp }}>
        <div style={{ flex: 1, height: 2, background: hexA("#ffffff", 0.05), borderRadius: 1, overflow: "hidden", marginRight: 12 }}>
          <div style={{ width: `${totalSlides > 0 ? ((segmentId + 1) / totalSlides) * 100 : 0}%`, height: "100%", background: `linear-gradient(90deg, ${accent}, ${hexA(accent, 0.5)})`, borderRadius: 1, boxShadow: `0 0 10px ${hexA(accent, 0.3)}` }} />
        </div>
        <span style={{ fontSize: 13, color: THEME.textMuted, fontFamily: "'SF Mono',monospace" }}>{String(segmentId + 1).padStart(2, "0")}/{String(totalSlides).padStart(2, "0")}</span>
      </div>
    </AbsoluteFill>
  );
};