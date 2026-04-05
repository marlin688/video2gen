/**
 * diagram.dual-card — 双卡片流程
 *
 * 左右两个详情卡片 + 中间箭头，卡片内含标题、条目列表（带状态图标）。
 * 适合展示输入→输出、Agent→验证、代码→测试等因果关系。
 * 参考：Code AI Labs 视频 5:26-5:32 Agent→/verify 效果。
 *
 * 使用方式：定义 2 个有 items 的节点 + 1 条 edge 连接它们。
 * 节点 type 控制边框颜色（primary=蓝, warning=黄, danger=红, success=绿）。
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

/* ═══════════════ 边框颜色 ═══════════════ */
const BORDER_COLORS: Record<string, string> = {
  default: "rgba(148,163,184,0.4)",
  primary: "rgba(168,130,255,0.5)",   // 紫（Agent）
  success: "rgba(52,211,153,0.5)",
  warning: "rgba(234,179,8,0.5)",     // 黄（/verify）
  danger: "rgba(239,68,68,0.5)",
};

/* ═══════════════ 条目状态图标 ═══════════════ */
function StatusIcon({ tag }: { tag?: string }) {
  if (!tag) return <span style={{ width: 18, display: "inline-block" }} />;
  const t = tag.toLowerCase();
  if (t === "done" || t === "pass" || t === "✓")
    return <span style={{ color: "#4ade80", fontSize: 18 }}>✓</span>;
  if (t === "running" || t === "..." || t === "::")
    return <span style={{ color: "#fbbf24", fontSize: 18 }}>::</span>;
  if (t === "pending" || t === "□" || t === "todo")
    return <span style={{ color: "#64748b", fontSize: 18 }}>□</span>;
  if (t === "fail" || t === "error" || t === "✗")
    return <span style={{ color: "#ef4444", fontSize: 18 }}>✗</span>;
  // fallback: 显示为右侧 tag 文字
  return <span style={{ color: "#4ade80", fontSize: 14, fontFamily: "monospace" }}>{tag}</span>;
}

/* ═══════════════ 卡片组件 ═══════════════ */

function Card({ node, opacity, translateX, itemReveal, side }: {
  node: StyleComponentProps<"diagram">["data"]["nodes"][0];
  opacity: number;
  translateX: number;
  itemReveal: number;
  side: "left" | "right";
}) {
  const t = useTheme();
  const borderColor = BORDER_COLORS[node.type || "default"] || BORDER_COLORS.default;
  const dotColor = node.type === "primary" ? "#c084fc"
    : node.type === "warning" ? "#fbbf24"
    : node.type === "success" ? "#4ade80"
    : node.type === "danger" ? "#ef4444"
    : "#94a3b8";

  const items = node.items || [];

  return (
    <div style={{
      width: 420,
      borderRadius: 16,
      background: t.surface,
      border: `1.5px solid ${borderColor}`,
      padding: "24px 28px",
      display: "flex",
      flexDirection: "column",
      gap: 16,
      opacity,
      transform: `translateX(${translateX}px)`,
    }}>
      {/* 标题行 */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        paddingBottom: 12,
        borderBottom: `1px solid ${t.surfaceBorder}`,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 12, height: 12, borderRadius: "50%",
            background: dotColor,
          }} />
          <span style={{
            fontSize: 24, fontWeight: 700,
            color: dotColor,
            fontFamily: t.monoFont,
          }}>
            {node.label}
          </span>
        </div>
        {node.subtitle && (
          <span style={{
            fontSize: 16, color: t.textDim,
            fontFamily: t.bodyFont,
          }}>
            {node.subtitle}
          </span>
        )}
      </div>

      {/* 条目列表 */}
      {items.map((item, j) => {
        const itemOpacity = interpolate(
          itemReveal,
          [j / Math.max(items.length, 1), (j + 1) / Math.max(items.length, 1)],
          [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        );
        return (
          <div key={j} style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            opacity: itemOpacity,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <StatusIcon tag={item.tag} />
              <span style={{
                fontSize: 18, color: t.textDim,
                fontFamily: t.monoFont,
              }}>
                {item.text}
              </span>
            </div>
            {/* 如果 tag 不是状态符号，显示为右侧文字 */}
            {item.tag && !["done","pass","✓","running","...","::","pending","□","todo","fail","error","✗"].includes(item.tag.toLowerCase()) && (
              <span style={{
                fontSize: 15, color: "#4ade80",
                fontFamily: t.monoFont,
                fontWeight: 600,
              }}>
                {item.tag}
              </span>
            )}
          </div>
        );
      })}

      {/* 底部状态 */}
      {node.status && (
        <div style={{
          paddingTop: 8,
          borderTop: `1px solid ${t.surfaceBorder}`,
          fontSize: 16,
          color: t.textDim,
          fontFamily: t.monoFont,
          fontStyle: "italic" as const,
          opacity: itemReveal,
        }}>
          {node.status}
        </div>
      )}
    </div>
  );
}

/* ═══════════════ 主组件 ═══════════════ */

const DiagramDualCard: React.FC<StyleComponentProps<"diagram">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  const nodes = data.nodes;
  const leftNode = nodes[0];
  const rightNode = nodes.length > 1 ? nodes[1] : null;

  // 动画
  const leftP = spring({ frame: Math.max(0, frame - 5), fps, config: { damping: 14, stiffness: 80 }, durationInFrames: 20 });
  const leftItemP = spring({ frame: Math.max(0, frame - 15), fps, config: { damping: 18, stiffness: 60 }, durationInFrames: 30 });
  const arrowP = spring({ frame: Math.max(0, frame - 30), fps, config: { damping: 16, stiffness: 100 }, durationInFrames: 15 });
  const rightP = spring({ frame: Math.max(0, frame - 40), fps, config: { damping: 14, stiffness: 80 }, durationInFrames: 20 });
  const rightItemP = spring({ frame: Math.max(0, frame - 50), fps, config: { damping: 18, stiffness: 60 }, durationInFrames: 30 });

  return (
    <AbsoluteFill style={{
      background: t.bg,
      display: "flex",
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 0,
      padding: "60px 80px",
      flexWrap: "nowrap" as const,
    }}>
      {/* 背景网格 */}
      <div style={{
        position: "absolute", inset: 0,
        backgroundImage:
          `linear-gradient(${t.gridLine} 1px, transparent 1px),` +
          `linear-gradient(90deg, ${t.gridLine} 1px, transparent 1px)`,
        backgroundSize: "60px 60px",
      }} />

      {/* 左卡片 */}
      {leftNode && (
        <Card
          node={leftNode}
          opacity={interpolate(leftP, [0, 1], [0, 1])}
          translateX={interpolate(leftP, [0, 1], [-60, 0])}
          itemReveal={leftItemP}
          side="left"
        />
      )}

      {/* 箭头 */}
      <div style={{
        position: "relative",
        zIndex: 1,
        padding: "0 28px",
        opacity: interpolate(arrowP, [0, 1], [0, 1]),
        transform: `scaleX(${interpolate(arrowP, [0, 1], [0, 1])})`,
      }}>
        <svg width="80" height="24" viewBox="0 0 80 24">
          <line x1="0" y1="12" x2="64" y2="12" stroke={t.textMuted} strokeWidth="2.5" />
          <polygon points="62,5 78,12 62,19" fill={t.textMuted} />
        </svg>
      </div>

      {/* 右卡片 */}
      {rightNode && (
        <Card
          node={rightNode}
          opacity={interpolate(rightP, [0, 1], [0, 1])}
          translateX={interpolate(rightP, [0, 1], [60, 0])}
          itemReveal={rightItemP}
          side="right"
        />
      )}
    </AbsoluteFill>
  );
};

/* ═══════════════ 注册 ═══════════════ */

registry.register(
  {
    id: "diagram.dual-card",
    schema: "diagram",
    name: "双卡片流程",
    description:
      "左右两个详情卡片 + 中间箭头。卡片内含标题、条目列表（带状态图标 ✓/□/::/✗）和底部状态。" +
      "节点 type 控制边框颜色（primary=紫, warning=黄）。条目的 tag 字段支持状态符号。" +
      "适合展示输入→输出、Agent→验证、代码→测试等因果关系。定义 2 个节点 + 1 条 edge。",
    isDefault: false,
    tags: ["对比", "因果", "验证", "Agent", "双栏"],
  },
  DiagramDualCard,
);

export { DiagramDualCard };
