/**
 * diagram.pipeline — 图标流程图
 *
 * 水平排列的步骤节点，每个节点有图标方块 + 标题 + 关键词，
 * 步骤间有彩色箭头，节点逐个出现带光晕效果。
 * 参考：Code AI Labs 视频 6:12-6:19 Skillify 流程 BRAINSTORM→REFINE→EXTRACT→skill.md。
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

/* ═══════════════ 箭头配色（按 index 轮换） ═══════════════ */
const ARROW_COLORS = ["#c084fc", "#d4a017", "#22d3ee", "#4ade80", "#f472b6"];

/* ═══════════════ 节点光晕色 ═══════════════ */
const GLOW_COLORS: Record<string, string> = {
  default: "rgba(148,163,184,0.3)",
  primary: "rgba(59,130,246,0.35)",
  success: "rgba(34,197,94,0.35)",
  warning: "rgba(234,179,8,0.4)",
  danger: "rgba(239,68,68,0.35)",
};

/* ═══════════════ 主组件 ═══════════════ */

const DiagramPipeline: React.FC<StyleComponentProps<"diagram">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  const nodes = data.nodes;
  const nodeCount = nodes.length;

  return (
    <AbsoluteFill style={{
      background: t.bg,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: "80px 60px",
    }}>
      {/* 标题 */}
      {data.title && (
        <div style={{
          position: "absolute",
          top: 60,
          fontSize: 28,
          color: t.textDim,
          fontFamily: t.monoFont,
          fontWeight: 600,
          opacity: interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp", extrapolateLeft: "clamp" }),
        }}>
          {data.title}
        </div>
      )}

      {/* 流程容器 */}
      <div style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 0,
      }}>
        {nodes.map((node, i) => {
          const delay = 8 + i * 18;
          const nodeP = spring({
            frame: Math.max(0, frame - delay),
            fps,
            config: { damping: 14, stiffness: 80 },
            durationInFrames: 20,
          });

          // 光晕呼吸
          const breathe = 1 + Math.sin((frame - delay) * 0.08) * 0.15;
          const glowColor = GLOW_COLORS[node.type || "default"] || GLOW_COLORS.default;
          const hasIcon = !!node.icon;
          const keywords = node.keywords || [];

          // 最后一个节点如果有 items，渲染为文件卡片样式
          const isFileCard = node.items && node.items.length > 0;

          return (
            <React.Fragment key={node.id}>
              {/* 节点 */}
              <div style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 12,
                opacity: interpolate(nodeP, [0, 1], [0, 1]),
                transform: `scale(${interpolate(nodeP, [0, 1], [0.7, 1])})`,
                minWidth: isFileCard ? 180 : 140,
              }}>
                {/* 图标方块 + 光晕 */}
                <div style={{ position: "relative" }}>
                  {/* 光晕 */}
                  <div style={{
                    position: "absolute",
                    inset: -20,
                    borderRadius: 24,
                    background: glowColor,
                    filter: "blur(25px)",
                    opacity: nodeP * breathe * 0.7,
                  }} />

                  {isFileCard ? (
                    /* 文件卡片样式 */
                    <div style={{
                      position: "relative",
                      width: 160,
                      padding: "20px 16px",
                      borderRadius: 16,
                      background: t.surface,
                      border: `1px solid ${t.surfaceBorder}`,
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: 8,
                    }}>
                      {hasIcon && (
                        <span style={{ fontSize: 36 }}>{node.icon}</span>
                      )}
                      <span style={{
                        fontSize: 18,
                        fontWeight: 700,
                        color: t.accent,
                        fontFamily: t.monoFont,
                      }}>
                        {node.label}
                      </span>
                      {keywords.map((kw, j) => (
                        <span key={j} style={{
                          fontSize: 15,
                          color: t.textDim,
                          fontFamily: t.bodyFont,
                        }}>
                          {kw}
                        </span>
                      ))}
                    </div>
                  ) : (
                    /* 标准图标方块 */
                    <div style={{
                      position: "relative",
                      width: 80,
                      height: 80,
                      borderRadius: 18,
                      background: t.surface,
                      border: `1px solid ${t.surfaceBorder}`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: hasIcon ? 36 : 28,
                    }}>
                      {hasIcon ? node.icon : node.label.charAt(0)}
                    </div>
                  )}
                </div>

                {/* 标题（非文件卡片才显示） */}
                {!isFileCard && (
                  <>
                    <span style={{
                      fontSize: 18,
                      fontWeight: 700,
                      color: t.text,
                      fontFamily: t.monoFont,
                      letterSpacing: "0.05em",
                      textTransform: "uppercase" as const,
                    }}>
                      {node.label}
                    </span>

                    {/* 关键词 */}
                    {keywords.map((kw, j) => (
                      <span key={j} style={{
                        fontSize: 16,
                        color: j === 0 ? ARROW_COLORS[i % ARROW_COLORS.length] : t.textDim,
                        fontWeight: j === 0 ? 600 : 400,
                        fontFamily: t.bodyFont,
                      }}>
                        {kw}
                      </span>
                    ))}
                  </>
                )}
              </div>

              {/* 箭头（最后一个节点后不加） */}
              {i < nodeCount - 1 && (() => {
                const arrowDelay = delay + 12;
                const arrowP = spring({
                  frame: Math.max(0, frame - arrowDelay),
                  fps,
                  config: { damping: 16, stiffness: 100 },
                  durationInFrames: 15,
                });
                const color = ARROW_COLORS[i % ARROW_COLORS.length];

                return (
                  <div style={{
                    display: "flex",
                    alignItems: "center",
                    padding: "0 16px",
                    marginTop: 28, // 对齐图标中心
                    opacity: interpolate(arrowP, [0, 1], [0, 1]),
                    transform: `scaleX(${interpolate(arrowP, [0, 1], [0, 1])})`,
                  }}>
                    <svg width="60" height="20" viewBox="0 0 60 20">
                      <line
                        x1="0" y1="10" x2="48" y2="10"
                        stroke={color}
                        strokeWidth="2.5"
                      />
                      <polygon
                        points="46,4 58,10 46,16"
                        fill={color}
                      />
                    </svg>
                  </div>
                );
              })()}
            </React.Fragment>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/* ═══════════════ 注册 ═══════════════ */

registry.register(
  {
    id: "diagram.pipeline",
    schema: "diagram",
    name: "图标流程图",
    description:
      "水平排列的步骤流程，每个节点有图标方块 + 标题 + 关键词，步骤间彩色箭头。" +
      "节点逐个出现带光晕效果。设置 icon（emoji）和 keywords（关键词数组）。" +
      "适合展示工作流、技能流程、Pipeline 阶段。",
    isDefault: false,
    tags: ["流程", "Pipeline", "工作流", "步骤"],
  },
  DiagramPipeline,
);

export { DiagramPipeline };
