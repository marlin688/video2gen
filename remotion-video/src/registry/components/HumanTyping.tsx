/**
 * HumanTyping -- 带"人性毛边"的代码/文本打字展示组件
 *
 * 与线性 typing-demo 不同，本组件模拟真人打字：
 * - 随机速度抖动
 * - 标点/空格处停顿
 * - 可选打错字→退格→重打
 * - 闪烁光标
 *
 * 内部使用 useHumanTypist hook，可独立在 Sequence 中使用。
 */

import React, { useMemo } from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { useHumanTypist, type TypoSpec } from "../hooks/useHumanTypist";

export interface HumanTypingProps {
  /** 要打的文本（支持多行 \n） */
  text: string;
  /** 打字开始帧偏移，默认 10 */
  startFrame?: number;
  /** typo 配置 */
  typos?: TypoSpec[];
  /** 随机种子 */
  seed?: string;
  /** 字体大小，默认 32 */
  fontSize?: number;
  /** 文字颜色，默认 #e2e8f0 */
  color?: string;
  /** 是否显示为代码风格（等宽字体 + 深色背景），默认 true */
  codeStyle?: boolean;
  /** 标题/提示文字（显示在输入框上方） */
  label?: string;
}

export const HumanTyping: React.FC<HumanTypingProps> = ({
  text,
  startFrame = 10,
  typos = [],
  seed = "human-typing",
  fontSize = 32,
  color = "#e2e8f0",
  codeStyle = true,
  label,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const { displayText, cursorVisible, isTyping, progress } = useHumanTypist({
    text,
    startFrame,
    typos,
    seed,
  });

  const lines = displayText.split("\n");

  const containerStyle: React.CSSProperties = useMemo(
    () => ({
      display: "flex",
      flexDirection: "column" as const,
      justifyContent: "center",
      alignItems: "center",
      padding: "60px 100px",
      backgroundColor: codeStyle ? "#0d1117" : "#0f172a",
    }),
    [codeStyle],
  );

  const boxStyle: React.CSSProperties = useMemo(
    () => ({
      width: "100%",
      maxWidth: 1400,
      borderRadius: 16,
      padding: "40px 48px",
      backgroundColor: codeStyle ? "#161b22" : "rgba(255,255,255,0.05)",
      border: `1px solid ${codeStyle ? "#30363d" : "rgba(255,255,255,0.1)"}`,
      fontFamily: codeStyle
        ? "'SF Mono', 'Fira Code', 'JetBrains Mono', monospace"
        : "'SF Pro Display', system-ui, sans-serif",
      fontSize,
      lineHeight: 1.7,
      color,
      whiteSpace: "pre-wrap" as const,
      wordBreak: "break-all" as const,
      position: "relative" as const,
    }),
    [codeStyle, fontSize, color],
  );

  const cursorStyle: React.CSSProperties = useMemo(
    () => ({
      display: "inline-block",
      width: codeStyle ? Math.round(fontSize * 0.55) : 2,
      height: Math.round(fontSize * 1.2),
      backgroundColor: codeStyle ? "rgba(56, 189, 248, 0.7)" : "#38bdf8",
      verticalAlign: "text-bottom",
      marginLeft: 1,
      opacity: cursorVisible ? 1 : 0,
    }),
    [codeStyle, fontSize, cursorVisible],
  );

  return (
    <AbsoluteFill style={containerStyle}>
      {label && (
        <div
          style={{
            fontSize: 24,
            color: "#64748b",
            marginBottom: 16,
            fontFamily: "'SF Pro Display', system-ui, sans-serif",
            width: "100%",
            maxWidth: 1400,
          }}
        >
          {label}
        </div>
      )}
      <div style={boxStyle}>
        {/* 行号（代码模式） */}
        {codeStyle && (
          <div
            style={{
              position: "absolute",
              left: 16,
              top: 40,
              color: "#484f58",
              fontSize: fontSize * 0.85,
              lineHeight: 1.7,
              fontFamily: "inherit",
              userSelect: "none",
              textAlign: "right",
              width: 24,
            }}
          >
            {lines.map((_, i) => (
              <div key={i}>{i + 1}</div>
            ))}
          </div>
        )}

        {/* 文本内容 */}
        <div style={{ marginLeft: codeStyle ? 40 : 0 }}>
          {displayText}
          <span style={cursorStyle} />
        </div>
      </div>

      {/* 底部进度指示 */}
      <div
        style={{
          marginTop: 24,
          width: "100%",
          maxWidth: 1400,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontSize: 18,
          color: "#475569",
          fontFamily: "'SF Mono', monospace",
        }}
      >
        <span>{isTyping ? "typing..." : "done"}</span>
        <span>{Math.round(progress * 100)}%</span>
      </div>
    </AbsoluteFill>
  );
};
