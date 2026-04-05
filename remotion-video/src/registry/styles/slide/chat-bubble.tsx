/**
 * slide.chat-bubble — 聊天气泡
 *
 * 模拟 AI 对话界面的聊天气泡。
 * title = 顶部说明文字（如 "同一个模型，换一种说法，结果可能差很多"）。
 * bullet_points 格式：
 *   - 以 ">" 开头 = AI 回复（右侧紫色气泡）
 *   - 以 "?" 开头 = 系统提问（居中黄色气泡）
 *   - 其他 = 用户输入（左侧灰色气泡）
 *   - "---" = VS 分隔符
 *
 * 适合展示 prompt 示例、对话对比、用户指令。
 * 参考：code秘密花园视频中的 prompt 对比画面。
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

type BubbleType = "user" | "ai" | "question" | "vs";

function classifyLine(line: string): { type: BubbleType; text: string } {
  if (line.trim() === "---" || line.trim().toLowerCase() === "vs") return { type: "vs", text: "VS" };
  if (line.startsWith(">")) return { type: "ai", text: line.slice(1).trim() };
  if (line.startsWith("?")) return { type: "question", text: line.slice(1).trim() };
  return { type: "user", text: line };
}

const BUBBLE_STYLES: Record<BubbleType, {
  bg: string; border: string; color: string; align: string; radius: string; icon: string; iconBg: string;
}> = {
  user: {
    bg: "rgba(255,255,255,0.08)", border: "rgba(148,163,184,0.2)", color: "#e8edf5",
    align: "flex-start", radius: "18px 18px 18px 4px", icon: "👤", iconBg: "rgba(148,163,184,0.3)",
  },
  ai: {
    bg: "rgba(168,130,255,0.12)", border: "rgba(168,130,255,0.25)", color: "#e0d4ff",
    align: "flex-end", radius: "18px 18px 4px 18px", icon: "🤖", iconBg: "rgba(168,130,255,0.3)",
  },
  question: {
    bg: "rgba(234,179,8,0.12)", border: "rgba(234,179,8,0.25)", color: "#fde68a",
    align: "center", radius: "18px", icon: "❓", iconBg: "rgba(234,179,8,0.3)",
  },
  vs: { bg: "transparent", border: "transparent", color: "#94a3b8", align: "center", radius: "50%", icon: "", iconBg: "" },
};

const SlideConversation: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  const bubbles = data.bullet_points.map(classifyLine);

  return (
    <AbsoluteFill style={{
      background: t.bg,
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      padding: "50px 180px",
      fontFamily: t.bodyFont,
    }}>
      {/* 标题 */}
      {data.title && (
        <div style={{
          fontSize: 28,
          fontWeight: 700,
          color: t.text,
          marginBottom: 40,
          textAlign: "center" as const,
          fontFamily: t.titleFont,
          opacity: interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp", extrapolateLeft: "clamp" }),
        }}>
          {data.title}
        </div>
      )}

      {/* 气泡列表 */}
      <div style={{
        display: "flex",
        flexDirection: "column",
        gap: 16,
        width: "100%",
        maxWidth: 1100,
      }}>
        {bubbles.map((bubble, i) => {
          const delay = 8 + i * 10;
          const p = spring({
            frame: Math.max(0, frame - delay),
            fps,
            config: { damping: 14, stiffness: 100 },
            durationInFrames: 16,
          });
          const style = BUBBLE_STYLES[bubble.type];

          if (bubble.type === "vs") {
            return (
              <div key={i} style={{
                display: "flex", justifyContent: "center", padding: "8px 0",
                opacity: interpolate(p, [0, 1], [0, 1]),
              }}>
                <div style={{
                  width: 48, height: 48, borderRadius: "50%",
                  background: t.surface, border: `2px solid ${t.surfaceBorder}`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 18, fontWeight: 800, color: t.textDim,
                }}>
                  VS
                </div>
              </div>
            );
          }

          const isRight = bubble.type === "ai";
          const isCenter = bubble.type === "question";

          return (
            <div key={i} style={{
              display: "flex",
              justifyContent: isCenter ? "center" : isRight ? "flex-end" : "flex-start",
              alignItems: "flex-start",
              gap: 12,
              opacity: interpolate(p, [0, 1], [0, 1]),
              transform: isRight
                ? `translateX(${interpolate(p, [0, 1], [40, 0])}px)`
                : isCenter
                  ? `translateY(${interpolate(p, [0, 1], [20, 0])}px)`
                  : `translateX(${interpolate(p, [0, 1], [-40, 0])}px)`,
            }}>
              {/* 左侧头像（user / question） */}
              {!isRight && (
                <div style={{
                  width: 36, height: 36, borderRadius: "50%", flexShrink: 0,
                  background: style.iconBg,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 18,
                }}>
                  {style.icon}
                </div>
              )}

              {/* 气泡 */}
              <div style={{
                maxWidth: isCenter ? "80%" : "70%",
                padding: "14px 22px",
                borderRadius: style.radius,
                background: style.bg,
                border: `1px solid ${style.border}`,
                fontSize: 21,
                color: style.color,
                lineHeight: 1.6,
                fontFamily: t.bodyFont,
              }}>
                {bubble.text}
              </div>

              {/* 右侧头像（ai） */}
              {isRight && (
                <div style={{
                  width: 36, height: 36, borderRadius: "50%", flexShrink: 0,
                  background: style.iconBg,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 18,
                }}>
                  {style.icon}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/* ═══════════════ 注册 ═══════════════ */

registry.register(
  {
    id: "slide.chat-bubble",
    schema: "slide",
    name: "聊天气泡",
    description:
      "模拟 AI 对话界面。bullet_points 每行一个气泡：普通文字=用户（左灰），'>开头'=AI回复（右紫），" +
      "'?开头'=提问（居中黄），'---'=VS分隔符。title 为顶部说明。" +
      "适合展示 prompt 示例、对话对比、用户指令演示。",
    isDefault: false,
    tags: ["对话", "聊天", "prompt", "气泡", "对比"],
  },
  SlideConversation,
);

export { SlideConversation };
