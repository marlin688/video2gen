/**
 * slide.anthropic-feature-checklist — Anthropic 品牌片场景 6
 *
 * 白色圆角卡片正中：上半是蓝色实心勾 + 划掉的已完成项（Sandboxing / Error recovery / Auth / Memory），
 * 下半是蓝色描边圆号 + 待办项（Event state mgmt / File persistence / Checkpointing / Retry policies）。
 * 复刻 30-36s 帧。
 */

import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { WavyPaperBg } from "../../components/WavyPaperBg";

const DEFAULT_DONE = ["Sandboxing", "Error recovery", "Auth", "Memory"];
const DEFAULT_TODO = [
  "Event state mgmt",
  "File persistence",
  "Checkpointing",
  "Retry policies",
];

const BLUE = "#3b82f6";

/**
 * 数据来源（二选一）：
 *
 * A) slide_content.bullet_points 中，以 "✓ " 开头的视为已完成（划掉），
 *    以数字开头（如 "5. xxx"）或 "- " 开头的视为待办。
 *    示例：["✓ Sandboxing", "✓ Error recovery", "5. Event state mgmt", "6. File persistence"]
 *
 * B) slide_content.scene_data 提供 { done: string[], todo: string[], todoStartIndex?: number }
 */
const AnthropicFeatureChecklist: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const sceneData = (data.scene_data || {}) as {
    done?: string[];
    todo?: string[];
    todoStartIndex?: number;
  };

  let DONE: string[];
  let TODO: string[];
  let todoStart: number;

  if (sceneData.done || sceneData.todo) {
    DONE = sceneData.done || [];
    TODO = sceneData.todo || [];
    todoStart = sceneData.todoStartIndex ?? DONE.length + 1;
  } else if (data.bullet_points && data.bullet_points.length > 0) {
    DONE = [];
    TODO = [];
    for (const bp of data.bullet_points) {
      const stripped = bp.trim();
      if (stripped.startsWith("✓ ") || stripped.startsWith("✓")) {
        DONE.push(stripped.replace(/^✓\s*/, ""));
      } else if (/^\d+\.\s*/.test(stripped) || stripped.startsWith("- ")) {
        TODO.push(stripped.replace(/^\d+\.\s*/, "").replace(/^-\s*/, ""));
      }
    }
    todoStart = sceneData.todoStartIndex ?? DONE.length + 1;
    if (DONE.length === 0 && TODO.length === 0) {
      DONE = DEFAULT_DONE;
      TODO = DEFAULT_TODO;
      todoStart = DONE.length + 1;
    }
  } else {
    DONE = DEFAULT_DONE;
    TODO = DEFAULT_TODO;
    todoStart = DONE.length + 1;
  }

  const enter = spring({
    frame,
    fps,
    config: { damping: 18, stiffness: 80 },
    durationInFrames: 30,
  });

  // 已完成项逐个打勾
  const doneProgress = DONE.map((_, i) =>
    spring({
      frame: Math.max(0, frame - 20 - i * 5),
      fps,
      config: { damping: 14, stiffness: 120 },
    }),
  );

  // 待办项逐个出现
  const todoProgress = TODO.map((_, i) =>
    spring({
      frame: Math.max(0, frame - 50 - i * 5),
      fps,
      config: { damping: 18, stiffness: 95 },
    }),
  );

  return (
    <AbsoluteFill>
      <WavyPaperBg />

      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          opacity: interpolate(enter, [0, 1], [0, 1]),
          transform: `translateY(${interpolate(enter, [0, 1], [28, 0])}px)`,
        }}
      >
        <div
          style={{
            width: 720,
            backgroundColor: "#ffffff",
            borderRadius: 16,
            padding: "46px 60px",
            boxShadow:
              "0 30px 70px rgba(30,24,18,0.18), 0 10px 22px rgba(30,24,18,0.08)",
            fontFamily:
              "'SF Pro Text', -apple-system, sans-serif",
          }}
        >
          {/* 已完成项 */}
          {DONE.map((item, i) => {
            const p = doneProgress[i];
            return (
              <div
                key={`done-${i}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 22,
                  marginBottom: 24,
                  opacity: interpolate(p, [0, 1], [0.3, 1]),
                }}
              >
                <div
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: "50%",
                    backgroundColor: BLUE,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#fff",
                    fontSize: 22,
                    fontWeight: 700,
                    flexShrink: 0,
                  }}
                >
                  ✓
                </div>
                <div
                  style={{
                    fontSize: 38,
                    color: "#9a958d",
                    fontWeight: 500,
                    textDecoration: "line-through",
                    textDecorationThickness: 2,
                  }}
                >
                  {item}
                </div>
              </div>
            );
          })}

          {/* 待办项 */}
          {TODO.map((item, i) => {
            const p = todoProgress[i];
            return (
              <div
                key={`todo-${i}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 22,
                  marginBottom: 24,
                  opacity: interpolate(p, [0, 1], [0, 1]),
                  transform: `translateX(${interpolate(p, [0, 1], [-20, 0])}px)`,
                }}
              >
                <div
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: "50%",
                    border: `3px solid ${BLUE}`,
                    backgroundColor: "transparent",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: BLUE,
                    fontSize: 22,
                    fontWeight: 600,
                    flexShrink: 0,
                    fontFamily:
                      "'Fraunces', 'Playfair Display', Georgia, serif",
                  }}
                >
                  {todoStart + i}
                </div>
                <div
                  style={{
                    fontSize: 38,
                    color: "#1a1a1a",
                    fontWeight: 500,
                    fontFamily:
                      "'Fraunces', 'Playfair Display', Georgia, serif",
                  }}
                >
                  {item}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

registry.register(
  {
    id: "slide.anthropic-feature-checklist",
    schema: "slide",
    name: "Anthropic 功能清单",
    description:
      "Anthropic 品牌片场景 6：白色圆角卡片里，上半部分 4 个蓝色实心勾 + 划掉的已完成项 (Sandboxing / Error recovery / Auth / Memory)，下半部分 4 个蓝色描边圆号 + 待办项 (Event state mgmt / File persistence / Checkpointing / Retry policies)。复刻 30-36s 帧。",
    isDefault: false,
    tags: ["anthropic", "checklist", "清单", "分类"],
  },
  AnthropicFeatureChecklist,
);
export { AnthropicFeatureChecklist };
