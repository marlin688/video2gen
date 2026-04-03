/**
 * slide.chalk-board — 黑板手绘风 PPT 卡片
 *
 * 灵感来源: Nate (vDVSGVpB2vc, B2Kh_ZoLVTM) 的白板图解风格
 *
 * 设计理念:
 * - 纯黑背景 + 手绘感白色标题
 * - 语义色卡系统: 红(负面) / 金(中性) / 绿(积极) / 蓝(信息) / 紫(管理)
 * - 卡片有 2-3px 略粗糙的手绘风边框 + 半透明色填充 + 大圆角
 * - 布局: 左右对比 / 三列网格 / 水平流程 / 标准堆叠
 * - SVG filter 模拟手绘笔触的不完美感
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

/* ═══════════════ 颜色系统：黑板语义色 ═══════════════ */
const C = {
  bg: "#0a0a0a",
  // 语义色 — 填充 (半透明) + 边框 (不透明)
  red:       { fill: "rgba(139,34,82,0.55)", border: "#c94070", text: "#ffb3cc" },
  gold:      { fill: "rgba(139,125,60,0.50)", border: "#c9a832", text: "#ffe599" },
  green:     { fill: "rgba(45,90,61,0.55)",  border: "#4caf50", text: "#a5d6a7" },
  blue:      { fill: "rgba(50,80,140,0.50)", border: "#5b9bd5", text: "#90caf9" },
  purple:    { fill: "rgba(90,50,120,0.50)", border: "#9b59b6", text: "#ce93d8" },
  // 通用
  white: "#f0ece4",       // 粉笔白（略暖）
  gray: "#8a8578",        // 粉笔灰
  chalkDim: "#5a564e",    // 暗淡粉笔
  titleFont: "'Caveat', 'Segoe Print', 'Comic Sans MS', cursive",
  bodyFont:  "'Inter', 'Helvetica Neue', sans-serif",
};

/** 语义色列表，按顺序分配给各卡片 */
const PALETTE = [C.green, C.blue, C.gold, C.purple, C.red];

/** 对比布局专用色 */
const CMP_LEFT  = C.green;
const CMP_RIGHT = C.red;

/* ═══════════════ 工具函数 ═══════════════ */

/** 弹簧动画: 依次入场 */
function stag(
  frame: number, fps: number, index: number,
  base = 8, interval = 6,
): React.CSSProperties {
  const delay = base + index * interval;
  const p = spring({
    frame: Math.max(0, frame - delay), fps,
    config: { damping: 12, stiffness: 100 },
    durationInFrames: 18,
  });
  return {
    opacity: p,
    transform: `translateY(${interpolate(p, [0, 1], [30, 0])}px) scale(${interpolate(p, [0, 1], [0.92, 1])})`,
  };
}

/** 标题弹入 */
function titleAnim(frame: number, fps: number): React.CSSProperties {
  const p = spring({
    frame, fps,
    config: { damping: 14, stiffness: 90 },
    durationInFrames: 20,
  });
  return {
    opacity: p,
    transform: `scale(${interpolate(p, [0, 1], [0.8, 1])})`,
  };
}

/** 手绘风 SVG filter (让边框看起来不完美) */
function ChalkFilter() {
  return (
    <svg width="0" height="0" style={{ position: "absolute" }}>
      <defs>
        <filter id="chalk-rough">
          <feTurbulence type="turbulence" baseFrequency="0.04" numOctaves="4" result="noise" />
          <feDisplacementMap in="SourceGraphic" in2="noise" scale="1.5" />
        </filter>
      </defs>
    </svg>
  );
}

/* ═══════════════ 布局检测 ═══════════════ */

type LayoutType = "compare" | "grid" | "flow" | "standard";

interface SlideShape {
  bullet_points: string[];
  chart_hint?: string;
}

function detectLayout(sc: SlideShape): LayoutType {
  const hint = (sc.chart_hint || "").toLowerCase();
  const bp = sc.bullet_points;

  // 对比: chart_hint 包含 vs/对比/compare, 或 DO/DON'T 模式
  if (hint.includes("vs") || hint.includes("对比") || hint.includes("compare")) return "compare";
  if (bp.some(b => /^(DO|DON'?T|✓|✗|优势|劣势|优点|缺点|Pros?|Cons?)\b/i.test(b.trim()))) return "compare";

  // 流程: 步骤模式
  const stepP = /^(第[一二三四五六七八九十\d]+步|Step\s*\d|Phase\s*\d|[\d①②③④⑤⑥⑦⑧⑨⑩]\s*[.、)）:]|→)/i;
  if (bp.filter(b => stepP.test(b.trim())).length >= Math.ceil(bp.length * 0.5)) return "flow";

  // 网格: 3+ 要点且有分隔符或短文本
  if (bp.length >= 3 && bp.every(b => b.length < 80)) return "grid";

  return "standard";
}

/* ═══════════════ 子组件: 手绘卡片 ═══════════════ */

interface ChalkCardProps {
  color: typeof C.red;
  title?: string;
  items?: string[];
  text?: string;
  style?: React.CSSProperties;
  animStyle?: React.CSSProperties;
}

function ChalkCard({ color, title, items, text, style, animStyle }: ChalkCardProps) {
  return (
    <div style={{
      background: color.fill,
      border: `2.5px solid ${color.border}`,
      borderRadius: 16,
      padding: "20px 24px",
      filter: "url(#chalk-rough)",
      ...style,
      ...animStyle,
    }}>
      {title && (
        <div style={{
          fontFamily: C.titleFont,
          fontSize: 28,
          color: C.white,
          marginBottom: items || text ? 14 : 0,
          lineHeight: 1.2,
        }}>
          {title}
        </div>
      )}
      {text && (
        <div style={{
          fontFamily: C.bodyFont,
          fontSize: 18,
          color: color.text,
          lineHeight: 1.5,
        }}>
          {text}
        </div>
      )}
      {items && items.map((item, i) => (
        <div key={i} style={{
          background: `${color.border}33`,
          border: `1.5px solid ${color.border}88`,
          borderRadius: 10,
          padding: "8px 14px",
          marginTop: 8,
          fontFamily: C.bodyFont,
          fontSize: 16,
          color: color.text,
          lineHeight: 1.4,
        }}>
          {item}
        </div>
      ))}
    </div>
  );
}

/* ═══════════════ 布局: 左右对比 ═══════════════ */

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
      {/* 标题 */}
      <div style={{
        fontFamily: C.titleFont,
        fontSize: 52,
        color: C.white,
        textAlign: "center",
        marginBottom: 40,
        ...titleAnim(frame, fps),
      }}>
        {title}
      </div>

      {/* 左右对比区 */}
      <div style={{
        display: "flex", gap: 40, width: "100%",
        justifyContent: "center", alignItems: "flex-start",
      }}>
        {/* 左列 */}
        <div style={{ flex: 1, maxWidth: 500, ...stag(frame, fps, 0) }}>
          <div style={{
            fontFamily: C.titleFont,
            fontSize: 30,
            color: CMP_LEFT.text,
            marginBottom: 16,
            textAlign: "center",
          }}>
            ✓ {left[0]?.includes("：") ? left[0].split("：")[0] : "优势"}
          </div>
          <ChalkCard
            color={CMP_LEFT}
            items={left.map(b => {
              const parts = b.split(/[：:]/);
              return parts.length > 1 ? parts.slice(1).join(":").trim() : b;
            })}
          />
        </div>

        {/* 竖线分隔 */}
        <div style={{
          width: 2, alignSelf: "stretch",
          background: `linear-gradient(180deg, transparent, ${C.chalkDim}, transparent)`,
          ...stag(frame, fps, 1),
        }} />

        {/* 右列 */}
        <div style={{ flex: 1, maxWidth: 500, ...stag(frame, fps, 2) }}>
          <div style={{
            fontFamily: C.titleFont,
            fontSize: 30,
            color: CMP_RIGHT.text,
            marginBottom: 16,
            textAlign: "center",
          }}>
            ✗ {right[0]?.includes("：") ? right[0].split("：")[0] : "劣势"}
          </div>
          <ChalkCard
            color={CMP_RIGHT}
            items={right.map(b => {
              const parts = b.split(/[：:]/);
              return parts.length > 1 ? parts.slice(1).join(":").trim() : b;
            })}
          />
        </div>
      </div>
    </div>
  );
}

/* ═══════════════ 布局: 三列网格卡 ═══════════════ */

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
        fontSize: 52,
        color: C.white,
        textAlign: "center",
        marginBottom: 40,
        ...titleAnim(frame, fps),
      }}>
        {title}
      </div>

      <div style={{
        display: "flex", flexWrap: "wrap",
        gap: 24, justifyContent: "center",
        maxWidth: 1200,
      }}>
        {bullets.map((b, i) => {
          const color = PALETTE[i % PALETTE.length];
          // 尝试解析 "标题：描述" 格式
          const sepIdx = b.search(/[：:]/);
          const cardTitle = sepIdx > 0 ? b.slice(0, sepIdx) : undefined;
          const cardText = sepIdx > 0 ? b.slice(sepIdx + 1).trim() : b;

          return (
            <ChalkCard
              key={i}
              color={color}
              title={cardTitle}
              text={cardText}
              style={{
                width: cols === 2 ? "calc(50% - 12px)" : "calc(33.3% - 16px)",
                minWidth: 240,
              }}
              animStyle={stag(frame, fps, i, 10, 5)}
            />
          );
        })}
      </div>
    </div>
  );
}

/* ═══════════════ 布局: 水平流程 ═══════════════ */

function FlowLayout({ title, bullets, frame, fps }: {
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
        fontSize: 52,
        color: C.white,
        textAlign: "center",
        marginBottom: 50,
        ...titleAnim(frame, fps),
      }}>
        {title}
      </div>

      <div style={{
        display: "flex", alignItems: "center",
        gap: 0, justifyContent: "center",
      }}>
        {bullets.map((b, i) => {
          const color = PALETTE[i % PALETTE.length];
          // 去除步骤前缀
          const clean = b.replace(/^(第[一二三四五六七八九十\d]+步|Step\s*\d+|Phase\s*\d+|[\d①②③④⑤⑥⑦⑧⑨⑩]\s*[.、)）:]\s*)/i, "").trim();

          return (
            <React.Fragment key={i}>
              <div style={{
                display: "flex", flexDirection: "column",
                alignItems: "center", ...stag(frame, fps, i, 10, 7),
              }}>
                {/* 步骤编号圆 */}
                <div style={{
                  width: 36, height: 36,
                  borderRadius: "50%",
                  background: color.border,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontFamily: C.bodyFont,
                  fontSize: 18, fontWeight: 700,
                  color: "#000",
                  marginBottom: 12,
                }}>
                  {i + 1}
                </div>
                {/* 卡片 */}
                <div style={{
                  background: color.fill,
                  border: `2.5px solid ${color.border}`,
                  borderRadius: 14,
                  padding: "16px 20px",
                  width: Math.min(200, 900 / bullets.length),
                  textAlign: "center",
                  filter: "url(#chalk-rough)",
                }}>
                  <div style={{
                    fontFamily: C.bodyFont,
                    fontSize: 16, color: color.text,
                    lineHeight: 1.4,
                  }}>
                    {clean}
                  </div>
                </div>
              </div>

              {/* 箭头 */}
              {i < bullets.length - 1 && (
                <div style={{
                  fontSize: 28, color: C.chalkDim,
                  margin: "18px 8px 0",
                  ...stag(frame, fps, i, 14, 7),
                }}>
                  →
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

/* ═══════════════ 布局: 标准堆叠 ═══════════════ */

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
        fontSize: 52,
        color: C.white,
        textAlign: "center",
        marginBottom: 36,
        ...titleAnim(frame, fps),
      }}>
        {title}
      </div>

      <div style={{
        display: "flex", flexDirection: "column",
        gap: 14, maxWidth: 900, width: "100%",
      }}>
        {bullets.map((b, i) => {
          const color = PALETTE[i % PALETTE.length];
          return (
            <div key={i} style={{
              background: color.fill,
              border: `2px solid ${color.border}`,
              borderRadius: 12,
              padding: "14px 24px",
              fontFamily: C.bodyFont,
              fontSize: 20,
              color: color.text,
              lineHeight: 1.5,
              filter: "url(#chalk-rough)",
              ...stag(frame, fps, i, 10, 6),
            }}>
              <span style={{
                display: "inline-block",
                width: 28, height: 28,
                borderRadius: "50%",
                background: `${color.border}55`,
                textAlign: "center",
                lineHeight: "28px",
                fontSize: 14,
                fontWeight: 700,
                color: C.white,
                marginRight: 12,
                verticalAlign: "middle",
              }}>
                {i + 1}
              </span>
              {b}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ═══════════════ 主组件 ═══════════════ */

const SlideChalkBoard: React.FC<StyleComponentProps<"slide">> = ({ data, fps }) => {
  const frame = useCurrentFrame();
  const { fps: vFps } = useVideoConfig();
  const f = fps || vFps;

  const sc = {
    bullet_points: data.bullet_points || [],
    chart_hint: data.chart_hint,
  };
  const layout = detectLayout(sc);

  const layoutProps = { title: data.title, bullets: sc.bullet_points, frame, fps: f };

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <ChalkFilter />

      {/* 微妙的黑板纹理 — 极细网格 */}
      <div style={{
        position: "absolute", inset: 0,
        backgroundImage: `
          linear-gradient(${C.chalkDim}08 1px, transparent 1px),
          linear-gradient(90deg, ${C.chalkDim}08 1px, transparent 1px)
        `,
        backgroundSize: "40px 40px",
      }} />

      {/* 黑板边框装饰 */}
      <div style={{
        position: "absolute", inset: 16,
        border: `1.5px solid ${C.chalkDim}30`,
        borderRadius: 8,
        pointerEvents: "none",
      }} />

      {layout === "compare" && <CompareLayout {...layoutProps} />}
      {layout === "grid" && <GridLayout {...layoutProps} />}
      {layout === "flow" && <FlowLayout {...layoutProps} />}
      {layout === "standard" && <StandardLayout {...layoutProps} />}
    </AbsoluteFill>
  );
};

/* ═══════════════ 注册 ═══════════════ */

registry.register(
  {
    id: "slide.chalk-board",
    schema: "slide",
    name: "黑板手绘风",
    description:
      "纯黑背景 + 语义色卡 (红/金/绿/蓝/紫) + 手绘粗糙边框。" +
      "适合架构对比、流程图解、概念分类等结构化内容。" +
      "chart_hint 支持 vs/对比 → 左右对比布局。",
    isDefault: false,
    tags: ["diagram", "comparison", "architecture", "whiteboard"],
  },
  SlideChalkBoard,
);

export { SlideChalkBoard };
