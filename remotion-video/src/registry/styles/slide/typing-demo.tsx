/**
 * slide.typing-demo — 模拟实时打字输入
 *
 * 逐字出现的 prompt 输入效果，带光标闪烁。
 * title = 输入框标签（如"Prompt"），bullet_points = 逐行输入的文本。
 * 比 terminal 更有"视频感"，适合展示 prompt、命令输入。
 */

import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import React from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";
import { FloatingCode } from "../../components/FloatingCode";

const SlideTypingDemo: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  const fullText = data.bullet_points.join("\n");
  const charsPerFrame = 1.2; // ~36 字/秒
  const typedLength = Math.min(Math.floor(frame * charsPerFrame), fullText.length);
  const typedText = fullText.slice(0, typedLength);
  const isTyping = typedLength < fullText.length;
  const cursorVisible = isTyping ? true : Math.sin(frame * 0.15) > 0;

  // 输入框入场
  const boxOpacity = interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp", extrapolateLeft: "clamp" });

  return (
    <AbsoluteFill style={{ background: t.bg, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "60px 120px" }}>
      <FloatingCode opacity={0.15} seed="typing-bg" count={16} />
      {/* 标签 */}
      <div style={{
        fontSize: 20, color: t.textDim, fontWeight: 600, fontFamily: t.monoFont,
        marginBottom: 16, alignSelf: "flex-start", maxWidth: 1200, width: "100%",
        paddingLeft: 160,
        opacity: boxOpacity,
      }}>
        {data.title || "Prompt"}
      </div>

      {/* 输入框 */}
      <div style={{
        width: "100%", maxWidth: 1200,
        minHeight: 200,
        padding: "32px 36px",
        borderRadius: 16,
        background: t.surface,
        border: `1.5px solid ${t.surfaceBorder}`,
        boxShadow: `0 0 40px ${t.accentGlow}`,
        fontFamily: t.monoFont,
        fontSize: 26,
        color: t.text,
        lineHeight: 1.7,
        whiteSpace: "pre-wrap" as const,
        wordBreak: "break-word" as const,
        opacity: boxOpacity,
        position: "relative" as const,
      }}>
        {typedText}
        {/* 光标 */}
        <span style={{
          display: "inline-block",
          width: 3, height: 32,
          background: t.accent,
          marginLeft: 2,
          verticalAlign: "text-bottom",
          opacity: cursorVisible ? 1 : 0,
        }} />
      </div>

      {/* 底部提示 */}
      {!isTyping && (
        <div style={{
          marginTop: 20, fontSize: 16, color: t.textMuted,
          fontFamily: t.bodyFont,
          opacity: interpolate(frame, [fullText.length / charsPerFrame, fullText.length / charsPerFrame + 15], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
        }}>
          ⏎ Enter to send
        </div>
      )}
    </AbsoluteFill>
  );
};

registry.register({ id: "slide.typing-demo", schema: "slide", name: "打字演示", description: "模拟实时打字输入效果，逐字出现 + 光标闪烁。title = 输入框标签，bullet_points = 逐行输入的文本。比终端组件更适合展示 prompt 输入。", isDefault: false, tags: ["打字", "输入", "prompt", "演示", "动态"] }, SlideTypingDemo);
export { SlideTypingDemo };
