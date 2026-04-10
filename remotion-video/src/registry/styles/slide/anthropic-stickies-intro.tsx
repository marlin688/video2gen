/**
 * slide.anthropic-stickies-intro — Anthropic 品牌片开场 1
 *
 * 米白纸张 + 两张便利贴 + 偏右一个运行中的 terminal 窗口特写。
 * 复刻 "Introducing Claude Managed Agents" 0-5s 帧。
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
import { StickyNote } from "../../components/StickyNote";
import { MacosWindow } from "../../components/MacosWindow";

const monoFont = "'JetBrains Mono', 'SF Mono', 'Fira Code', monospace";

type TermLine =
  | { kind: "tool"; name: string; args: string; result: string }
  | { kind: "status"; text: string }
  | { kind: "spacer" };

const DEFAULT_TERM_LINES: TermLine[] = [
  { kind: "tool", name: "Read", args: "(src/agent/sandbox.py) 112 lines", result: "done" },
  { kind: "spacer" },
  {
    kind: "tool",
    name: "Bash",
    args: "(mcp connect hubspot --agent\n  agent_01JR4kW9 --scope\n  deals,contacts,companies)",
    result: "connected\ndone",
  },
  { kind: "spacer" },
  {
    kind: "tool",
    name: "Bash",
    args: "(mcp hubspot search-contacts --query\n  'Jamie Park NovaTech')",
    result: "1 result\ndone",
  },
  { kind: "spacer" },
  {
    kind: "tool",
    name: "Bash",
    args: "(mcp hubspot get-deal --id D-29481 --\n  include rfp-attachments)",
    result: "deal loaded\ndone",
  },
  { kind: "spacer" },
  { kind: "status", text: "Cogitating  (26s  570 tokens)" },
  { kind: "status", text: ">> accept edits on (shift+tab to cycle)" },
];

const DEFAULT_STICKIES: { color: "yellow" | "blue" | "pink" | "green"; text: string; rotation?: number }[] = [
  { color: "yellow", text: "FIX AUTH FLOW by next week", rotation: -3 },
  { color: "blue", text: "Don't forget\nto eat\ndinner", rotation: 3 },
];

/**
 * scene_data shape (可选)：
 * {
 *   stickies?: [{ color: "yellow"|"blue"|"pink"|"green", text: string, rotation?: number }, ...],
 *   terminalTitle?: string,
 *   terminalLines?: TermLine[],   // TermLine 参见代码内类型定义
 * }
 * 或用 slide_content.bullet_points 作为便利贴的文字（前 2 条）。
 */
const AnthropicStickiesIntro: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // 解析 scene_data / bullet_points
  const sceneData = (data.scene_data || {}) as {
    stickies?: { color?: "yellow" | "blue" | "pink" | "green"; text: string; rotation?: number }[];
    terminalTitle?: string;
    terminalLines?: TermLine[];
  };

  const stickies = (() => {
    if (sceneData.stickies && sceneData.stickies.length > 0) {
      return sceneData.stickies.map((s, i) => ({
        color: s.color || (["yellow", "blue", "pink", "green"] as const)[i % 4],
        text: s.text,
        rotation: s.rotation ?? (i % 2 === 0 ? -3 : 3),
      }));
    }
    if (data.bullet_points && data.bullet_points.length > 0) {
      return data.bullet_points.slice(0, 4).map((text, i) => ({
        color: (["yellow", "blue", "pink", "green"] as const)[i % 4],
        text,
        rotation: i % 2 === 0 ? -3 : 3,
      }));
    }
    return DEFAULT_STICKIES;
  })();

  const terminalTitle = sceneData.terminalTitle || "agent-runtime — claude — 84×34";
  const TERM_LINES: TermLine[] = sceneData.terminalLines || DEFAULT_TERM_LINES;

  // 便利贴弹入（带轻微交错）
  const stickySprings = stickies.map((_, i) =>
    spring({
      frame: Math.max(0, frame - 4 - i * 8),
      fps,
      config: { damping: 14, stiffness: 90 },
    }),
  );
  // 终端淡入
  const term = spring({ frame: Math.max(0, frame - 18), fps, config: { damping: 18, stiffness: 80 } });

  // 终端内容按行渐进淡入：每行相隔 4 帧出现，单行淡入 6 帧
  const lineOpacity = (i: number) => {
    const start = 30 + i * 4;
    return interpolate(frame, [start, start + 6], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
  };

  return (
    <AbsoluteFill>
      <WavyPaperBg />

      {/* 便利贴 — 左上集群 */}
      {stickies.map((sticky, i) => {
        const p = stickySprings[i];
        // 简单排列：横向等距摆放
        const left = 90 + i * 210;
        const top = 70 + (i % 2) * 25;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              top,
              left,
              opacity: interpolate(p, [0, 1], [0, 1]),
              transform: `translateY(${interpolate(p, [0, 1], [-40, 0])}px)`,
            }}
          >
            <StickyNote
              color={sticky.color}
              text={sticky.text}
              rotation={sticky.rotation}
              width={180}
              height={180}
              fontSize={22}
            />
          </div>
        );
      })}

      {/* 终端窗口 — 右半边，占据画面主视觉 */}
      <div
        style={{
          position: "absolute",
          top: 150,
          left: 820,
          opacity: interpolate(term, [0, 1], [0, 1]),
          transform: `translateY(${interpolate(term, [0, 1], [50, 0])}px)`,
        }}
      >
        <MacosWindow
          width={960}
          height={780}
          title={terminalTitle}
          variant="dark"
          bodyStyle={{
            padding: "28px 34px",
            fontSize: 22,
            fontFamily: monoFont,
            color: "#d4d4d4",
            lineHeight: 1.5,
            overflow: "hidden",
          }}
        >
          {TERM_LINES.map((ln, i) => {
            const op = lineOpacity(i);
            if (op <= 0) return null;
            if (ln.kind === "spacer") {
              return <div key={i} style={{ height: 10 }} />;
            }
            if (ln.kind === "status") {
              const isCogitating = ln.text.startsWith("Cogitating");
              return (
                <div
                  key={i}
                  style={{
                    color: isCogitating ? "#d97757" : "#a885d9",
                    marginTop: 8,
                    opacity: op,
                  }}
                >
                  {isCogitating ? "✻ " : ""}
                  {ln.text}
                </div>
              );
            }
            return (
              <div key={i} style={{ opacity: op }}>
                <div>
                  <span style={{ color: "#3fb950" }}>●</span>{" "}
                  <span style={{ color: "#e8e8e8", fontWeight: 600 }}>
                    {ln.name}
                  </span>
                  <span style={{ color: "#888" }}>({ln.args})</span>{" "}
                  <span style={{ color: "#d4d4d4" }}>{ln.result.split("\n")[0]}</span>
                </div>
                {ln.result.includes("\n") && (
                  <div style={{ color: "#6fa86f", paddingLeft: 24 }}>
                    ✓ {ln.result.split("\n")[1]}
                  </div>
                )}
                {!ln.result.includes("\n") && (
                  <div style={{ color: "#6fa86f", paddingLeft: 24 }}>✓ done</div>
                )}
              </div>
            );
          })}
        </MacosWindow>
      </div>
    </AbsoluteFill>
  );
};

registry.register(
  {
    id: "slide.anthropic-stickies-intro",
    schema: "slide",
    name: "Anthropic 开场便利贴+终端",
    description:
      "Anthropic 品牌片开场：米白纸张背景 + 两张便利贴 (FIX AUTH FLOW / Don't forget to eat dinner) + 右侧 macOS 终端窗口运行 agent-runtime 的工具调用日志。场景 1/10。",
    isDefault: false,
    tags: ["anthropic", "开场", "便利贴", "终端"],
  },
  AnthropicStickiesIntro,
);
export { AnthropicStickiesIntro };
