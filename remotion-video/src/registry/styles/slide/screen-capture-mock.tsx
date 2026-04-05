/**
 * slide.screen-capture-mock — 模拟录屏效果
 *
 * 带鼠标移动轨迹和点击动画的操作演示。
 * title = 应用名/场景，bullet_points = 操作步骤序列。
 * 每行是一个操作：点击、输入、选择等，带逐步动画。
 */

import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import React from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";

const ACTION_ICONS: Record<string, string> = {
  "点击": "🖱️", "click": "🖱️", "选择": "🖱️", "select": "🖱️",
  "输入": "⌨️", "type": "⌨️", "填写": "⌨️", "input": "⌨️",
  "滚动": "↕️", "scroll": "↕️",
  "打开": "📂", "open": "📂", "导航": "📂", "navigate": "📂",
  "等待": "⏳", "wait": "⏳", "加载": "⏳", "loading": "⏳",
  "完成": "✅", "done": "✅", "成功": "✅", "success": "✅",
};

function getActionIcon(text: string): string {
  const lower = text.toLowerCase();
  for (const [key, icon] of Object.entries(ACTION_ICONS)) {
    if (lower.includes(key)) return icon;
  }
  return "→";
}

const SlideScreenCaptureMock: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  const steps = data.bullet_points;
  const STEP_DURATION = 25; // 每步约 0.8 秒
  const currentStep = Math.floor(frame / STEP_DURATION);

  // 鼠标位置（在屏幕上移动）
  const baseY = 250;
  const cursorY = baseY + Math.min(currentStep, steps.length - 1) * 65;
  const cursorX = 500 + Math.sin(frame * 0.05) * 30;
  const clickPulse = frame % STEP_DURATION < 5 ? interpolate(frame % STEP_DURATION, [0, 2, 5], [0, 1, 0]) : 0;

  return (
    <AbsoluteFill style={{ background: "#000", display: "flex", alignItems: "center", justifyContent: "center" }}>
      {/* 模拟窗口 */}
      <div style={{
        width: 1600, height: 900, borderRadius: 12,
        background: t.bg, border: `1px solid ${t.surfaceBorder}`,
        overflow: "hidden", position: "relative" as const,
        boxShadow: "0 20px 60px rgba(0,0,0,0.8)",
      }}>
        {/* 窗口顶栏 */}
        <div style={{
          height: 40, background: t.surface,
          borderBottom: `1px solid ${t.surfaceBorder}`,
          display: "flex", alignItems: "center", padding: "0 16px", gap: 8,
        }}>
          <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#ff5f57" }} />
          <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#febc2e" }} />
          <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#28c840" }} />
          <span style={{ marginLeft: 20, fontSize: 14, color: t.textDim, fontFamily: t.monoFont }}>
            {data.title || "Screen Recording"}
          </span>
          {/* 录制指示灯 */}
          <div style={{
            marginLeft: "auto", display: "flex", alignItems: "center", gap: 6,
          }}>
            <div style={{
              width: 8, height: 8, borderRadius: "50%", background: "#ef4444",
              opacity: Math.sin(frame * 0.1) > 0 ? 1 : 0.3,
            }} />
            <span style={{ fontSize: 12, color: t.danger, fontFamily: t.monoFont }}>REC</span>
          </div>
        </div>

        {/* 操作步骤列表 */}
        <div style={{ padding: "40px 60px", display: "flex", flexDirection: "column", gap: 12 }}>
          {steps.map((step, i) => {
            const isActive = i === currentStep;
            const isDone = i < currentStep;
            const isFuture = i > currentStep;

            const stepP = isDone ? 1 : isActive ? spring({
              frame: Math.max(0, (frame % STEP_DURATION)),
              fps, config: { damping: 16, stiffness: 100 }, durationInFrames: 15,
            }) : 0;

            const icon = getActionIcon(step);

            return (
              <div key={i} style={{
                display: "flex", alignItems: "center", gap: 16,
                padding: "14px 20px", borderRadius: 10,
                background: isActive ? `${t.accent}15` : "transparent",
                border: isActive ? `1px solid ${t.accent}30` : "1px solid transparent",
                opacity: isFuture ? 0.3 : 1,
                transform: isActive ? `translateX(${interpolate(stepP, [0, 1], [20, 0])}px)` : "none",
              }}>
                <span style={{ fontSize: 24, opacity: isDone ? 0.5 : 1 }}>
                  {isDone ? "✅" : icon}
                </span>
                <span style={{
                  fontSize: 20, fontFamily: t.bodyFont,
                  color: isDone ? t.textMuted : isActive ? t.text : t.textDim,
                  fontWeight: isActive ? 600 : 400,
                  textDecoration: isDone ? "line-through" as const : "none" as const,
                }}>
                  {step}
                </span>
              </div>
            );
          })}
        </div>

        {/* 鼠标光标 */}
        <div style={{
          position: "absolute", left: cursorX, top: cursorY,
          pointerEvents: "none" as const,
          filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.5))",
          transition: "top 0.3s ease-out",
        }}>
          <svg width="24" height="30" viewBox="0 0 24 28" fill="none">
            <path d="M5.5 0L5.5 22.5L10.5 17.5L15.5 26L19.5 24L14.5 15.5L21.5 15.5L5.5 0Z" fill="white" stroke="black" strokeWidth="1.5" strokeLinejoin="round" />
          </svg>
          {/* 点击波纹 */}
          {clickPulse > 0 && (
            <div style={{
              position: "absolute", left: 0, top: 0,
              width: 40, height: 40, borderRadius: "50%",
              border: `2px solid ${t.accent}`,
              transform: `translate(-16px, -16px) scale(${1 + clickPulse})`,
              opacity: 1 - clickPulse,
            }} />
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};

registry.register({ id: "slide.screen-capture-mock", schema: "slide", name: "模拟录屏", description: "模拟录屏效果：操作步骤列表 + 鼠标移动 + 点击波纹 + REC 指示灯。每个 bullet_point 是一步操作，自动匹配图标（点击🖱️/输入⌨️/完成✅）。", isDefault: false, tags: ["录屏", "操作", "演示", "鼠标", "动态"] }, SlideScreenCaptureMock);
export { SlideScreenCaptureMock };
