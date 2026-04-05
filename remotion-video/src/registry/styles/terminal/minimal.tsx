/**
 * terminal.minimal — 极简终端
 *
 * 纯黑背景，无 aurora 光效，无 TUI 框架。
 * 适合纯命令行操作、简单演示、输出展示。对比 aurora 的华丽风格更朴素。
 */

import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import React from "react";
import type { StyleComponentProps, TerminalSessionStep } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";

const COLORS: Record<string, string> = {
  input: "#f8f8f2", output: "#8be9fd", status: "#bd93f9",
  tool: "#50fa7b", blank: "transparent", prompt: "#ff79c6",
};

const TerminalMinimal: React.FC<StyleComponentProps<"terminal">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();
  const steps = data.session || [];

  return (
    <AbsoluteFill style={{
      background: "#000000",
      padding: "50px 70px",
      fontFamily: t.monoFont,
      overflow: "hidden",
    }}>
      {/* 窗口按钮 */}
      <div style={{ display: "flex", gap: 8, marginBottom: 30 }}>
        <div style={{ width: 14, height: 14, borderRadius: "50%", background: "#ff5f56" }} />
        <div style={{ width: 14, height: 14, borderRadius: "50%", background: "#ffbd2e" }} />
        <div style={{ width: 14, height: 14, borderRadius: "50%", background: "#27c93f" }} />
      </div>

      {/* 终端内容 */}
      {steps.map((step: TerminalSessionStep, i: number) => {
        const delay = 5 + i * 8;
        const p = spring({ frame: Math.max(0, frame - delay), fps, config: { damping: 18, stiffness: 120 }, durationInFrames: 12 });

        if (step.type === "blank") {
          return <div key={i} style={{ height: 20 }} />;
        }

        if (step.type === "input") {
          return (
            <div key={i} style={{
              opacity: interpolate(p, [0, 1], [0, 1]),
              marginBottom: 8,
            }}>
              <span style={{ color: COLORS.prompt, fontSize: 20 }}>❯ </span>
              <span style={{ color: COLORS.input, fontSize: 20 }}>{step.text}</span>
            </div>
          );
        }

        if (step.type === "output") {
          return (
            <div key={i} style={{ opacity: interpolate(p, [0, 1], [0, 1]), marginBottom: 8 }}>
              {(step.lines || [step.text || ""]).map((line, j) => (
                <div key={j} style={{ color: COLORS.output, fontSize: 18, lineHeight: 1.6, opacity: 0.85 }}>
                  {line}
                </div>
              ))}
            </div>
          );
        }

        if (step.type === "status") {
          return (
            <div key={i} style={{
              opacity: interpolate(p, [0, 1], [0, 1]),
              fontSize: 18, color: COLORS.status, marginBottom: 8, fontStyle: "italic" as const,
            }}>
              {step.text}
            </div>
          );
        }

        if (step.type === "tool") {
          return (
            <div key={i} style={{
              opacity: interpolate(p, [0, 1], [0, 1]),
              fontSize: 18, color: COLORS.tool, marginBottom: 8,
            }}>
              <span style={{ opacity: 0.6 }}>● </span>
              <span style={{ fontWeight: 700 }}>{step.name}</span>
              {step.target && <span style={{ color: "#f1fa8c" }}>({step.target})</span>}
              {step.result && <span style={{ color: "#6272a4" }}> → {step.result}</span>}
            </div>
          );
        }

        return null;
      })}

      {/* 光标 */}
      <div style={{
        marginTop: 8,
        opacity: Math.sin(frame * 0.15) > 0 ? 1 : 0,
      }}>
        <span style={{ color: COLORS.prompt, fontSize: 20 }}>❯ </span>
        <span style={{ display: "inline-block", width: 10, height: 22, background: "#f8f8f2" }} />
      </div>
    </AbsoluteFill>
  );
};

registry.register({ id: "terminal.minimal", schema: "terminal", name: "极简终端", description: "纯黑背景极简终端，无 aurora 光效。红黄绿窗口按钮 + 简洁输出。适合纯命令行演示。", isDefault: false, tags: ["终端", "命令行", "极简", "黑色"] }, TerminalMinimal);
export { TerminalMinimal };
