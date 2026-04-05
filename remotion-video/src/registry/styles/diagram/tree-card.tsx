/**
 * diagram.tree-card — 树形卡片图
 *
 * 顶部标题节点向下分支到多个详情卡片，卡片内含条目列表 + 彩色 tag。
 * 适合架构总览、多项目对比、功能分解展示。
 * 参考：Code AI Labs 视频中 /tech-debt 的多项目分析卡片 + Agent worktree 架构图。
 *
 * 布局规则：
 * - 自动区分 root 节点（有 edge 指向子节点但无 incoming edge）和 card 节点（有 items）
 * - root 渲染为顶部 pill，card 渲染为详情卡片
 * - 普通节点（无 items）渲染为小 pill（类似 diagram.default）
 */

import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import React, { useMemo } from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";

/* ═══════════════ Tag 配色 ═══════════════ */

const TAG_PALETTE: Record<string, { bg: string; text: string }> = {
  duplication: { bg: "rgba(251,191,36,0.2)", text: "#fde047" },
  unused:      { bg: "rgba(244,114,182,0.2)", text: "#f9a8d4" },
  types:       { bg: "rgba(168,130,255,0.2)", text: "#c4a8ff" },
  pattern:     { bg: "rgba(56,189,248,0.2)",  text: "#7dd3fc" },
  deps:        { bg: "rgba(52,211,153,0.2)",  text: "#6ee7b7" },
  perf:        { bg: "rgba(248,113,113,0.2)", text: "#fca5a5" },
};

const TAG_FALLBACK_COLORS = [
  { bg: "rgba(168,130,255,0.2)", text: "#c4a8ff" },
  { bg: "rgba(56,189,248,0.2)",  text: "#7dd3fc" },
  { bg: "rgba(52,211,153,0.2)",  text: "#6ee7b7" },
  { bg: "rgba(251,191,36,0.2)",  text: "#fde047" },
  { bg: "rgba(244,114,182,0.2)", text: "#f9a8d4" },
];

function getTagColor(tag: string): { bg: string; text: string } {
  const lower = tag.toLowerCase();
  if (TAG_PALETTE[lower]) return TAG_PALETTE[lower];
  const hash = Array.from(lower).reduce((a, c) => a + c.charCodeAt(0), 0);
  return TAG_FALLBACK_COLORS[hash % TAG_FALLBACK_COLORS.length];
}

/* ═══════════════ Node 类型颜色圆点 ═══════════════ */

const NODE_DOT_COLORS: Record<string, string> = {
  default: "#94a3b8",
  primary: "#3b82f6",
  success: "#22c55e",
  warning: "#eab308",
  danger:  "#ef4444",
};

/* ═══════════════ 布局计算 ═══════════════ */

interface TreeNode {
  id: string;
  label: string;
  type: string;
  subtitle?: string;
  items?: Array<{ text: string; tag?: string }>;
  status?: string;
  isRoot: boolean;
  children: string[];
}

function buildTree(
  nodes: StyleComponentProps<"diagram">["data"]["nodes"],
  edges: StyleComponentProps<"diagram">["data"]["edges"],
): { roots: TreeNode[]; cards: TreeNode[] } {
  const incoming = new Set<string>();
  const childrenMap = new Map<string, string[]>();

  for (const e of edges) {
    incoming.add(e.to);
    const existing = childrenMap.get(e.from) || [];
    existing.push(e.to);
    childrenMap.set(e.from, existing);
  }

  const nodeMap = new Map(nodes.map((n) => [n.id, n]));
  const roots: TreeNode[] = [];
  const cards: TreeNode[] = [];

  for (const n of nodes) {
    const isRoot = !incoming.has(n.id) && (childrenMap.get(n.id)?.length ?? 0) > 0;
    const treeNode: TreeNode = {
      id: n.id,
      label: n.label,
      type: n.type || "default",
      subtitle: n.subtitle,
      items: n.items,
      status: n.status,
      isRoot,
      children: childrenMap.get(n.id) || [],
    };
    if (isRoot) {
      roots.push(treeNode);
    } else {
      cards.push(treeNode);
    }
  }

  return { roots, cards };
}

/* ═══════════════ 子组件: Root Pill ═══════════════ */

function RootPill({ node, opacity, translateY }: {
  node: TreeNode;
  opacity: number;
  translateY: number;
}) {
  const t = useTheme();
  return (
    <div style={{
      padding: "14px 36px",
      borderRadius: 40,
      background: t.surface,
      border: `1.5px solid ${t.surfaceBorder}`,
      display: "flex",
      alignItems: "center",
      gap: 12,
      opacity,
      transform: `translateY(${translateY}px)`,
    }}>
      <span style={{
        fontSize: 24,
        fontWeight: 700,
        color: t.text,
        fontFamily: t.monoFont,
      }}>
        {node.label}
      </span>
      {node.subtitle && (
        <span style={{
          fontSize: 18,
          color: t.textDim,
          fontFamily: t.bodyFont,
        }}>
          {node.subtitle}
        </span>
      )}
    </div>
  );
}

/* ═══════════════ 子组件: Detail Card ═══════════════ */

function DetailCard({ node, opacity, translateY, itemReveal }: {
  node: TreeNode;
  opacity: number;
  translateY: number;
  itemReveal: number; // 0-1, items 逐行显示进度
}) {
  const t = useTheme();
  const dotColor = NODE_DOT_COLORS[node.type] || NODE_DOT_COLORS.default;

  return (
    <div style={{
      flex: 1,
      minWidth: 320,
      maxWidth: 420,
      borderRadius: 16,
      background: t.surface,
      border: `1px solid ${t.surfaceBorder}`,
      padding: "20px 24px",
      display: "flex",
      flexDirection: "column",
      gap: 14,
      opacity,
      transform: `translateY(${translateY}px)`,
    }}>
      {/* 卡片标题行 */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 10, height: 10, borderRadius: "50%",
            background: dotColor,
          }} />
          <span style={{
            fontSize: 22, fontWeight: 700, color: t.text,
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
      {node.items && node.items.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {node.items.map((item, j) => {
            const itemOpacity = interpolate(
              itemReveal,
              [j / node.items!.length, (j + 1) / node.items!.length],
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
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ color: t.textMuted, fontSize: 14 }}>▸</span>
                  <span style={{
                    fontSize: 17, color: t.textDim,
                    fontFamily: t.bodyFont,
                  }}>
                    {item.text}
                  </span>
                </div>
                {item.tag && (
                  <span style={{
                    padding: "2px 10px",
                    borderRadius: 6,
                    fontSize: 13,
                    fontWeight: 600,
                    fontFamily: t.monoFont,
                    background: getTagColor(item.tag).bg,
                    color: getTagColor(item.tag).text,
                    whiteSpace: "nowrap" as const,
                  }}>
                    {item.tag}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* 状态行 */}
      {node.status && (
        <div style={{
          fontSize: 15, color: t.success,
          fontFamily: t.monoFont,
          fontWeight: 600,
          marginTop: 4,
          opacity: itemReveal,
        }}>
          {node.status}
        </div>
      )}
    </div>
  );
}

/* ═══════════════ 主组件 ═══════════════ */

const DiagramTreeCard: React.FC<StyleComponentProps<"diagram">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  const { roots, cards } = useMemo(
    () => buildTree(data.nodes, data.edges),
    [data.nodes, data.edges],
  );

  // 动画阶段
  const rootDelay = 5;
  const lineDelay = 18;
  const cardBaseDelay = 28;

  const rootP = spring({
    frame: Math.max(0, frame - rootDelay),
    fps, config: { damping: 14, stiffness: 100 },
    durationInFrames: 20,
  });

  const lineP = spring({
    frame: Math.max(0, frame - lineDelay),
    fps, config: { damping: 20, stiffness: 80 },
    durationInFrames: 25,
  });

  // 底部 footnote pills (从 edges 中没有 from/to 对应的孤立 label 提取，或用 title 后半段)
  const footnotePills = data.edges
    .filter((e) => e.label)
    .map((e) => e.label!);

  return (
    <AbsoluteFill style={{
      background: t.bg,
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      padding: "50px 80px",
      gap: 0,
    }}>
      {/* 背景网格 */}
      <div style={{
        position: "absolute",
        inset: 0,
        backgroundImage:
          `linear-gradient(${t.gridLine} 1px, transparent 1px),` +
          `linear-gradient(90deg, ${t.gridLine} 1px, transparent 1px)`,
        backgroundSize: "60px 60px",
      }} />

      {/* 标题 */}
      {data.title && (
        <div style={{
          position: "relative",
          zIndex: 1,
          marginBottom: 20,
          fontSize: 26,
          color: t.textDim,
          fontFamily: t.monoFont,
          fontWeight: 600,
          padding: "10px 30px",
          borderRadius: 30,
          background: t.surface,
          border: `1px solid ${t.surfaceBorder}`,
          opacity: interpolate(rootP, [0, 1], [0, 1]),
        }}>
          {data.title}
        </div>
      )}

      {/* Root 节点 */}
      <div style={{
        position: "relative",
        zIndex: 1,
        display: "flex",
        gap: 20,
        marginBottom: 0,
      }}>
        {roots.map((r) => (
          <RootPill
            key={r.id}
            node={r}
            opacity={interpolate(rootP, [0, 1], [0, 1])}
            translateY={interpolate(rootP, [0, 1], [-30, 0])}
          />
        ))}
      </div>

      {/* 连线区域（SVG） */}
      <svg
        width="100%"
        height={60}
        style={{
          position: "relative",
          zIndex: 1,
          overflow: "visible",
        }}
      >
        {cards.length > 0 && (() => {
          const centerX = 50; // percent
          const totalWidth = Math.min(cards.length * 25, 80); // percent
          const startX = centerX - totalWidth / 2;
          const stepX = cards.length > 1 ? totalWidth / (cards.length - 1) : 0;

          return (
            <>
              {/* 垂直主干 */}
              <line
                x1={`${centerX}%`} y1="0"
                x2={`${centerX}%`} y2="30"
                stroke={t.surfaceBorder}
                strokeWidth={2}
                strokeDasharray="200"
                strokeDashoffset={interpolate(lineP, [0, 1], [200, 0])}
              />
              {/* 水平横线 */}
              {cards.length > 1 && (
                <line
                  x1={`${startX}%`} y1="30"
                  x2={`${startX + totalWidth}%`} y2="30"
                  stroke={t.surfaceBorder}
                  strokeWidth={2}
                  strokeDasharray="1000"
                  strokeDashoffset={interpolate(lineP, [0, 1], [1000, 0])}
                />
              )}
              {/* 向下分支 */}
              {cards.map((_, i) => {
                const x = cards.length === 1 ? centerX : startX + i * stepX;
                return (
                  <line
                    key={i}
                    x1={`${x}%`} y1="30"
                    x2={`${x}%`} y2="60"
                    stroke={t.surfaceBorder}
                    strokeWidth={2}
                    strokeDasharray="200"
                    strokeDashoffset={interpolate(lineP, [0, 1], [200, 0])}
                  />
                );
              })}
            </>
          );
        })()}
      </svg>

      {/* 子卡片 */}
      <div style={{
        position: "relative",
        zIndex: 1,
        display: "flex",
        gap: 24,
        justifyContent: "center",
        flexWrap: "wrap" as const,
        maxWidth: 1500,
      }}>
        {cards.map((card, i) => {
          const delay = cardBaseDelay + i * 8;
          const cardP = spring({
            frame: Math.max(0, frame - delay),
            fps, config: { damping: 14, stiffness: 100 },
            durationInFrames: 20,
          });
          const itemP = spring({
            frame: Math.max(0, frame - delay - 10),
            fps, config: { damping: 18, stiffness: 60 },
            durationInFrames: 30,
          });
          return (
            <DetailCard
              key={card.id}
              node={card}
              opacity={interpolate(cardP, [0, 1], [0, 1])}
              translateY={interpolate(cardP, [0, 1], [40, 0])}
              itemReveal={itemP}
            />
          );
        })}
      </div>

      {/* 底部 footnote pills */}
      {footnotePills.length > 0 && (
        <div style={{
          position: "relative",
          zIndex: 1,
          display: "flex",
          gap: 16,
          marginTop: 32,
        }}>
          {footnotePills.map((pill, i) => (
            <div key={i} style={{
              padding: "10px 24px",
              borderRadius: 12,
              background: t.surface,
              border: `1px solid ${t.surfaceBorder}`,
              fontSize: 18,
              color: t.textDim,
              fontFamily: t.bodyFont,
              fontWeight: 500,
              opacity: interpolate(
                frame, [50, 60], [0, 1],
                { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
              ),
            }}>
              {pill}
            </div>
          ))}
        </div>
      )}
    </AbsoluteFill>
  );
};

/* ═══════════════ 注册 ═══════════════ */

registry.register(
  {
    id: "diagram.tree-card",
    schema: "diagram",
    name: "树形卡片图",
    description:
      "顶部标题节点向下分支到多个详情卡片。卡片内含条目列表（text + 彩色 tag pill）和状态行。" +
      "适合架构总览、多项目对比、功能分解展示。节点需设置 items 数组。" +
      "root 节点自动识别（有出边无入边），其余为子卡片。",
    isDefault: false,
    tags: ["架构", "对比", "卡片", "分析", "树形"],
  },
  DiagramTreeCard,
);

export { DiagramTreeCard };
