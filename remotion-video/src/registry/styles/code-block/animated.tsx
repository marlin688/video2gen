/**
 * code-block.animated — Fireship 风格动画代码展示
 *
 * prism-react-renderer 语法高亮 + 逐行弹入 + 高亮行脉冲 + 注释气泡
 */

import React, { useMemo } from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Highlight } from "prism-react-renderer";
import { oneDarkTheme } from "../../components/oneDarkTheme";
import { useTheme } from "../../theme";
import { registry } from "../../registry";
import type { StyleComponentProps } from "../../types";
import type { CodeBlockData } from "../../types";

/* ═══════════════ 语言图标 ═══════════════ */

const LANG_ICONS: Record<string, { icon: string; color: string }> = {
  typescript: { icon: "TS", color: "#3178C6" },
  javascript: { icon: "JS", color: "#F7DF1E" },
  python: { icon: "PY", color: "#3776AB" },
  rust: { icon: "RS", color: "#CE422B" },
  go: { icon: "GO", color: "#00ADD8" },
  bash: { icon: "$_", color: "#4EAA25" },
  json: { icon: "{}", color: "#999" },
  yaml: { icon: "YML", color: "#CB171E" },
  css: { icon: "CSS", color: "#1572B6" },
  html: { icon: "<>", color: "#E34F26" },
};

/* ═══════════════ 常量 ═══════════════ */

const STAGGER = 3; // 每行延迟帧数
const ANNO_W = 220; // 注释气泡宽度
const FONT_SIZE = 22;
const LINE_H = FONT_SIZE * 1.6;

/* ═══════════════ 主组件 ═══════════════ */

const AnimatedCodeBlock: React.FC<StyleComponentProps<"code-block">> = ({
  data,
  fps,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const theme = useTheme();

  const {
    fileName,
    language,
    code: codeLines,
    highlightLines = [],
    annotations = {},
  } = data;

  const codeString = codeLines.join("\n");
  const highlightSet = useMemo(() => new Set(highlightLines), [highlightLines]);
  const langInfo = LANG_ICONS[language] || { icon: language.slice(0, 2).toUpperCase(), color: theme.accent };

  // 面板入场动画
  const panelScale = spring({
    fps,
    frame,
    config: { damping: 100, mass: 0.8 },
  });
  const panelOpacity = interpolate(frame, [0, 8], [0, 1], {
    extrapolateRight: "clamp",
  });

  // 可见行数（留出最后 12 帧做 fade-out）
  const maxCodeH = 1080 - 180; // 上下留 padding
  const maxLines = Math.floor(maxCodeH / LINE_H);

  return (
    <AbsoluteFill style={{ backgroundColor: theme.bg }}>
      <div
        style={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: `translate(-50%, -50%) scale(${panelScale})`,
          opacity: panelOpacity,
          width: "88%",
          maxHeight: "85%",
          borderRadius: 16,
          overflow: "hidden",
          backgroundColor: oneDarkTheme.plain.backgroundColor,
          border: `1px solid ${theme.surfaceBorder}`,
          boxShadow: `0 0 60px ${theme.accentGlow}`,
        }}
      >
        {/* macOS 标题栏 */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "14px 20px",
            borderBottom: "1px solid #383c44",
          }}
        >
          {/* 交通灯 */}
          {["#FF5E57", "#FFBC30", "#29C93F"].map((c) => (
            <div
              key={c}
              style={{
                width: 14,
                height: 14,
                borderRadius: 7,
                backgroundColor: c,
              }}
            />
          ))}
          {/* 语言标签 */}
          <div
            style={{
              marginLeft: 12,
              padding: "2px 8px",
              borderRadius: 4,
              backgroundColor: `${langInfo.color}20`,
              color: langInfo.color,
              fontFamily: "'SF Mono', 'JetBrains Mono', monospace",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            {langInfo.icon}
          </div>
          {/* 文件名 */}
          <div
            style={{
              fontFamily: "'SF Mono', 'JetBrains Mono', monospace",
              fontSize: 14,
              color: "#abb2bf",
              opacity: 0.7,
            }}
          >
            {fileName}
          </div>
        </div>

        {/* 代码区 */}
        <div style={{ padding: "16px 20px", overflow: "hidden" }}>
          <Highlight code={codeString} language={language} theme={oneDarkTheme}>
            {({ tokens, getLineProps, getTokenProps }) => (
              <pre
                style={{
                  ...oneDarkTheme.plain,
                  fontSize: FONT_SIZE,
                  fontFamily: "'SF Mono', 'JetBrains Mono', monospace",
                  margin: 0,
                  lineHeight: 1.6,
                  whiteSpace: "pre-wrap",
                }}
              >
                {tokens.map((line, lineIndex) => {
                  if (lineIndex >= maxLines) return null;

                  const lineNum = lineIndex + 1;
                  const lineSpring = spring({
                    fps,
                    frame: frame - lineIndex * STAGGER,
                    config: { damping: 200 },
                  });

                  const isHL = highlightSet.has(lineNum);
                  const hlPulse = isHL
                    ? Math.sin(frame * 0.08) * 0.15 + 0.15
                    : 0;

                  const anno = annotations ? annotations[lineNum] : undefined;

                  const lineProps = getLineProps({ line });
                  return (
                    <div
                      key={lineIndex}
                      {...lineProps}
                      style={{
                        ...lineProps.style,
                        opacity: lineSpring,
                        transform: `translateX(${(1 - lineSpring) * 20}px)`,
                        display: "flex",
                        alignItems: "center",
                        backgroundColor: isHL
                          ? `rgba(255, 255, 255, ${hlPulse})`
                          : undefined,
                        borderLeft: isHL
                          ? `3px solid ${theme.accent}`
                          : "3px solid transparent",
                        borderRadius: isHL ? 4 : undefined,
                        padding: isHL ? "0 4px" : undefined,
                        paddingRight: anno ? ANNO_W + 20 : 16,
                        position: "relative",
                        height: LINE_H,
                      }}
                    >
                      {/* 行号 */}
                      <span
                        style={{
                          width: 40,
                          textAlign: "right",
                          marginRight: 16,
                          color: "#5c6370",
                          userSelect: "none",
                          flexShrink: 0,
                          fontSize: FONT_SIZE - 2,
                        }}
                      >
                        {lineNum}
                      </span>
                      {/* 代码 token */}
                      <span>
                        {line.map((token, tokenIndex) => {
                          const tokenProps = getTokenProps({ token });
                          return <span key={tokenIndex} {...tokenProps} />;
                        })}
                      </span>
                      {/* 注释气泡 */}
                      {anno && (
                        <div
                          style={{
                            position: "absolute",
                            right: 16,
                            top: "50%",
                            transform: "translateY(-50%)",
                            maxWidth: ANNO_W,
                            padding: "6px 14px",
                            background: `${theme.accent}15`,
                            border: `1px solid ${theme.accent}40`,
                            borderRadius: 8,
                            fontSize: 18,
                            color: theme.accent,
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            opacity: interpolate(
                              frame,
                              [lineIndex * STAGGER + 8, lineIndex * STAGGER + 16],
                              [0, 1],
                              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
                            ),
                          }}
                        >
                          {"\u2190 "}{anno}
                        </div>
                      )}
                    </div>
                  );
                })}
              </pre>
            )}
          </Highlight>
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ═══════════════ 注册 ═══════════════ */

registry.register(
  {
    id: "code-block.animated",
    schema: "code-block",
    name: "动画代码编辑器",
    description:
      "Fireship 风格代码展示。prism-react-renderer 语法高亮，逐行弹入动画，" +
      "高亮行脉冲效果，注释气泡。适合展示代码片段、API 示例、配置文件。",
    isDefault: true,
    tags: ["代码", "code", "animated", "fireship", "prism"],
  },
  AnimatedCodeBlock,
);

export { AnimatedCodeBlock };
