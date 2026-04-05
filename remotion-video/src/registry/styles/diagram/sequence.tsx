/**
 * diagram.sequence — 时序图
 *
 * 水平排列的参与者 + 垂直消息箭头。
 * nodes = 参与者（顶部方框），edges = 消息（从上到下的箭头，label = 消息内容）。
 * 适合 API 调用流程、请求/响应、微服务通信。
 */

import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import React, { useMemo } from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";

const NODE_COLORS = ["#4a9eff", "#a882ff", "#22c55e", "#eab308", "#f472b6"];

const DiagramSequence: React.FC<StyleComponentProps<"diagram">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  const nodes = data.nodes;
  const edges = data.edges;

  // 计算参与者位置
  const nodePositions = useMemo(() => {
    const gap = 1600 / Math.max(nodes.length, 1);
    return nodes.map((n, i) => ({
      ...n,
      x: 160 + i * gap + gap / 2,
    }));
  }, [nodes]);

  const nodeMap = useMemo(() => new Map(nodePositions.map(n => [n.id, n])), [nodePositions]);

  const HEADER_Y = 100;
  const MSG_START_Y = 180;
  const MSG_GAP = 70;

  return (
    <AbsoluteFill style={{ background: t.bg, fontFamily: t.monoFont }}>
      {/* 背景网格 */}
      <div style={{
        position: "absolute", inset: 0,
        backgroundImage: `linear-gradient(${t.gridLine} 1px, transparent 1px), linear-gradient(90deg, ${t.gridLine} 1px, transparent 1px)`,
        backgroundSize: "60px 60px",
      }} />

      {/* 标题 */}
      {data.title && (
        <div style={{
          position: "absolute", top: 30, width: "100%", textAlign: "center" as const,
          fontSize: 26, color: t.textDim, fontWeight: 600,
          opacity: interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp", extrapolateLeft: "clamp" }),
        }}>
          {data.title}
        </div>
      )}

      <svg width="1920" height="1080" style={{ position: "absolute", top: 0, left: 0 }}>
        {/* 生命线（虚线） */}
        {nodePositions.map((n, i) => {
          const p = spring({ frame: Math.max(0, frame - 5), fps, config: { damping: 18, stiffness: 100 }, durationInFrames: 15 });
          return (
            <line key={`life-${i}`} x1={n.x} y1={HEADER_Y + 50} x2={n.x} y2={1050}
              stroke={t.surfaceBorder} strokeWidth={1.5} strokeDasharray="8,6"
              opacity={interpolate(p, [0, 1], [0, 0.5])}
            />
          );
        })}

        {/* 消息箭头 */}
        {edges.map((edge, i) => {
          const fromNode = nodeMap.get(edge.from);
          const toNode = nodeMap.get(edge.to);
          if (!fromNode || !toNode) return null;

          const y = MSG_START_Y + i * MSG_GAP;
          const x1 = fromNode.x;
          const x2 = toNode.x;
          const isReturn = x2 < x1;
          const delay = 15 + i * 10;
          const p = spring({ frame: Math.max(0, frame - delay), fps, config: { damping: 16, stiffness: 100 }, durationInFrames: 15 });

          return (
            <g key={i} opacity={interpolate(p, [0, 1], [0, 1])}>
              {/* 箭头线 */}
              <line x1={x1} y1={y} x2={x2} y2={y}
                stroke={isReturn ? t.textMuted : t.accent}
                strokeWidth={2}
                strokeDasharray={isReturn ? "6,4" : "none"}
              />
              {/* 箭头头 */}
              <polygon
                points={x2 > x1
                  ? `${x2 - 10},${y - 5} ${x2},${y} ${x2 - 10},${y + 5}`
                  : `${x2 + 10},${y - 5} ${x2},${y} ${x2 + 10},${y + 5}`}
                fill={isReturn ? t.textMuted : t.accent}
              />
              {/* 标签 */}
              {edge.label && (
                <text x={(x1 + x2) / 2} y={y - 10}
                  textAnchor="middle" fontSize={16}
                  fill={isReturn ? t.textDim : t.text}
                  fontFamily={t.monoFont}>
                  {edge.label}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* 参与者方框 */}
      {nodePositions.map((n, i) => {
        const p = spring({ frame: Math.max(0, frame - 3 - i * 4), fps, config: { damping: 14, stiffness: 100 }, durationInFrames: 15 });
        const color = NODE_COLORS[i % NODE_COLORS.length];
        return (
          <div key={n.id} style={{
            position: "absolute",
            left: n.x - 80, top: HEADER_Y,
            width: 160, padding: "12px 16px",
            borderRadius: 10, textAlign: "center" as const,
            background: t.surface, border: `2px solid ${color}`,
            opacity: interpolate(p, [0, 1], [0, 1]),
            transform: `translateY(${interpolate(p, [0, 1], [-20, 0])}px)`,
          }}>
            <div style={{ fontSize: 18, fontWeight: 700, color }}>{n.label}</div>
            {n.subtitle && <div style={{ fontSize: 14, color: t.textDim, marginTop: 4 }}>{n.subtitle}</div>}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

registry.register({ id: "diagram.sequence", schema: "diagram", name: "时序图", description: "水平参与者 + 垂直消息箭头的时序图。nodes = 参与者，edges = 消息（label=消息内容）。实线=请求，虚线=返回(to<from)。适合 API 调用、微服务通信。", isDefault: false, tags: ["时序", "API", "请求", "通信"] }, DiagramSequence);
export { DiagramSequence };
