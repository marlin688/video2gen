/**
 * diagram.default — 流程/架构图
 *
 * 节点 + 箭头的流程图，支持 LR（左到右）和 TB（上到下）布局。
 * 节点逐个出现 + 连线绘制动画。
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
import { ParticleBackground } from "../../components/ParticleBackground";

/* ═══════════════ 颜色系统 ═══════════════ */

const NODE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  default:  { bg: "rgba(30,40,65,0.9)",   border: "#4a5568", text: "#e2e8f0" },
  primary:  { bg: "rgba(37,99,235,0.25)",  border: "#3b82f6", text: "#93c5fd" },
  success:  { bg: "rgba(22,163,74,0.25)",  border: "#22c55e", text: "#86efac" },
  warning:  { bg: "rgba(234,179,8,0.25)",  border: "#eab308", text: "#fde047" },
  danger:   { bg: "rgba(220,38,38,0.25)",  border: "#ef4444", text: "#fca5a5" },
};

const C = {
  bg: "#0a0e1a",
  edge: "#475569",
  edgeLabel: "#94a3b8",
  title: "#e2e8f0",
  gridLine: "rgba(100,116,139,0.08)",
};

/* ═══════════════ 布局计算 ═══════════════ */

interface LayoutNode {
  id: string;
  label: string;
  type: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

interface LayoutEdge {
  from: LayoutNode;
  to: LayoutNode;
  label?: string;
}

function computeLayout(
  nodes: StyleComponentProps<"diagram">["data"]["nodes"],
  edges: StyleComponentProps<"diagram">["data"]["edges"],
  direction: "LR" | "TB",
  canvasW: number,
  canvasH: number,
): { nodes: LayoutNode[]; edges: LayoutEdge[] } {
  const NODE_W = 260;
  const NODE_H = 72;

  // 简单拓扑排序确定层级
  const adj = new Map<string, string[]>();
  const indeg = new Map<string, number>();
  for (const n of nodes) {
    adj.set(n.id, []);
    indeg.set(n.id, 0);
  }
  for (const e of edges) {
    adj.get(e.from)?.push(e.to);
    indeg.set(e.to, (indeg.get(e.to) || 0) + 1);
  }

  const layers: string[][] = [];
  const visited = new Set<string>();
  let queue = nodes.filter(n => (indeg.get(n.id) || 0) === 0).map(n => n.id);
  if (queue.length === 0 && nodes.length > 0) queue = [nodes[0].id];

  while (queue.length > 0) {
    layers.push([...queue]);
    queue.forEach(id => visited.add(id));
    const next: string[] = [];
    for (const id of queue) {
      for (const to of adj.get(id) || []) {
        if (!visited.has(to) && !next.includes(to)) {
          next.push(to);
        }
      }
    }
    queue = next;
  }
  // 加入未访问的节点
  for (const n of nodes) {
    if (!visited.has(n.id)) {
      layers.push([n.id]);
    }
  }

  const nodeMap = new Map<string, typeof nodes[0]>();
  for (const n of nodes) nodeMap.set(n.id, n);

  const isLR = direction === "LR";
  const gapMajor = isLR ? canvasW / (layers.length + 1) : canvasH / (layers.length + 1);

  const layoutNodes: LayoutNode[] = [];
  const nodeById = new Map<string, LayoutNode>();

  for (let li = 0; li < layers.length; li++) {
    const layer = layers[li];
    const gapMinor = isLR
      ? canvasH / (layer.length + 1)
      : canvasW / (layer.length + 1);

    for (let ni = 0; ni < layer.length; ni++) {
      const id = layer[ni];
      const src = nodeMap.get(id);
      const x = isLR ? gapMajor * (li + 1) - NODE_W / 2 : gapMinor * (ni + 1) - NODE_W / 2;
      const y = isLR ? gapMinor * (ni + 1) - NODE_H / 2 : gapMajor * (li + 1) - NODE_H / 2;
      const ln: LayoutNode = {
        id,
        label: src?.label || id,
        type: src?.type || "default",
        x, y, w: NODE_W, h: NODE_H,
      };
      layoutNodes.push(ln);
      nodeById.set(id, ln);
    }
  }

  const layoutEdges: LayoutEdge[] = edges
    .filter(e => nodeById.has(e.from) && nodeById.has(e.to))
    .map(e => ({
      from: nodeById.get(e.from)!,
      to: nodeById.get(e.to)!,
      label: e.label,
    }));

  return { nodes: layoutNodes, edges: layoutEdges };
}

/* ═══════════════ 箭头渲染 ═══════════════ */

function Arrow({ from, to, label, progress }: {
  from: LayoutNode;
  to: LayoutNode;
  label?: string;
  progress: number;
}) {
  const theme = useTheme();
  const x1 = from.x + from.w / 2;
  const y1 = from.y + from.h / 2;
  const x2 = to.x + to.w / 2;
  const y2 = to.y + to.h / 2;

  // 线段裁剪到节点边缘
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len = Math.sqrt(dx * dx + dy * dy) || 1;
  const ux = dx / len;
  const uy = dy / len;

  const sx = x1 + ux * (from.w / 2 + 8);
  const sy = y1 + uy * (from.h / 2 + 8);
  const ex = x2 - ux * (to.w / 2 + 14);
  const ey = y2 - uy * (to.h / 2 + 14);

  const mx = (sx + ex) / 2;
  const my = (sy + ey) / 2;

  const arrowSize = 10;
  const ax1 = ex - ux * arrowSize - uy * arrowSize * 0.5;
  const ay1 = ey - uy * arrowSize + ux * arrowSize * 0.5;
  const ax2 = ex - ux * arrowSize + uy * arrowSize * 0.5;
  const ay2 = ey - uy * arrowSize - ux * arrowSize * 0.5;

  return (
    <g opacity={progress}>
      <line x1={sx} y1={sy} x2={ex} y2={ey}
        stroke={C.edge} strokeWidth={2.5}
        strokeDasharray={`${len}`}
        strokeDashoffset={len * (1 - progress)}
      />
      <polygon
        points={`${ex},${ey} ${ax1},${ay1} ${ax2},${ay2}`}
        fill={C.edge}
      />
      {label && (
        <text x={mx} y={my - 10}
          textAnchor="middle" fontSize={18}
          fill={theme.textDim} fontFamily="'Inter', sans-serif"
        >
          {label}
        </text>
      )}
    </g>
  );
}

/* ═══════════════ 主组件 ═══════════════ */

const DiagramDefault: React.FC<StyleComponentProps<"diagram">> = ({ data, segmentId }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const theme = useTheme();

  const CANVAS_W = 1700;
  const CANVAS_H = 900;

  const layout = useMemo(
    () => computeLayout(data.nodes, data.edges, data.direction || "LR", CANVAS_W, CANVAS_H),
    [data.nodes, data.edges, data.direction],
  );

  const titleP = spring({ frame, fps, config: { damping: 16, stiffness: 120 }, durationInFrames: 15 });

  return (
    <AbsoluteFill style={{
      background: theme.bg,
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      padding: "20px 40px",
    }}>
      {/* 网格背景 */}
      <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", zIndex: 0 }}>
        <defs>
          <pattern id={`grid-${segmentId}`} width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke={theme.gridLine} strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill={`url(#grid-${segmentId})`} />
      </svg>
      <ParticleBackground count={20} opacity={0.4} seed={`diagram-${segmentId}`} />

      {/* 标题 */}
      {data.title && (
        <div style={{
          position: "relative", zIndex: 1,
          fontSize: 40, fontWeight: 700, color: theme.text,
          marginBottom: 20,
          opacity: interpolate(titleP, [0, 1], [0, 1]),
          transform: `translateY(${interpolate(titleP, [0, 1], [-20, 0])}px)`,
          fontFamily: "'Inter', -apple-system, sans-serif",
        }}>
          {data.title}
        </div>
      )}

      {/* 图表 SVG */}
      <svg
        width={CANVAS_W}
        height={CANVAS_H}
        viewBox={`0 0 ${CANVAS_W} ${CANVAS_H}`}
        style={{ position: "relative", zIndex: 1 }}
      >
        {/* 连线 */}
        {layout.edges.map((edge, i) => {
          const edgeDelay = 15 + layout.nodes.length * 8 + i * 6;
          const p = spring({
            frame: Math.max(0, frame - edgeDelay),
            fps, config: { damping: 20, stiffness: 100 }, durationInFrames: 15,
          });
          return <Arrow key={i} from={edge.from} to={edge.to} label={edge.label} progress={p} />;
        })}

        {/* 节点 */}
        {layout.nodes.map((node, i) => {
          const delay = 8 + i * 8;
          const p = spring({
            frame: Math.max(0, frame - delay),
            fps, config: { damping: 14, stiffness: 120 }, durationInFrames: 18,
          });
          const colors = NODE_COLORS[node.type] || NODE_COLORS.default;

          return (
            <g key={node.id}
              opacity={interpolate(p, [0, 1], [0, 1])}
              transform={`translate(0, ${interpolate(p, [0, 1], [20, 0])})`}
            >
              <rect
                x={node.x} y={node.y} width={node.w} height={node.h}
                rx={14} ry={14}
                fill={colors.bg}
                stroke={colors.border}
                strokeWidth={2}
              />
              <text
                x={node.x + node.w / 2}
                y={node.y + node.h / 2 + 1}
                textAnchor="middle"
                dominantBaseline="central"
                fontSize={22}
                fontWeight={600}
                fill={colors.text}
                fontFamily="'Inter', 'SF Pro', -apple-system, sans-serif"
              >
                {node.label}
              </text>
            </g>
          );
        })}
      </svg>
    </AbsoluteFill>
  );
};

/* ═══════════════ 注册 ═══════════════ */

registry.register(
  {
    id: "diagram.default",
    schema: "diagram",
    name: "流程/架构图",
    description:
      "节点+箭头流程图，支持 LR（左到右）和 TB（上到下）布局。" +
      "节点有 5 种语义色（default/primary/success/warning/danger）。" +
      "适合展示系统架构、数据流、调用链、工作流程。",
    isDefault: true,
    tags: ["流程图", "架构", "diagram", "flow", "architecture"],
  },
  DiagramDefault,
);

export { DiagramDefault };
