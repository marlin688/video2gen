/**
 * code-block.default — 代码高亮卡片
 *
 * VS Code Dark+ 配色，支持：
 * - 文件名标题栏
 * - 行号 + 语法着色
 * - 高亮行（黄色背景条）
 * - 行注释气泡
 * - 逐行出现动画
 */

import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import React, { useMemo } from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";
import { FloatingCode } from "../../components/FloatingCode";
import { GridBackground } from "../../components/GridBackground";

/* ═══════════════ 颜色系统 ═══════════════ */
const C = {
  bg: "#1e1e1e",
  titleBar: "#2d2d2d",
  titleBorder: "#404040",
  gutter: "#1e1e1e",
  gutterText: "#858585",
  lineHighlight: "rgba(255, 213, 79, 0.10)",
  lineHighlightBorder: "rgba(255, 213, 79, 0.40)",
  text: "#d4d4d4",
  // 语法高亮 (VS Code Dark+ 近似)
  keyword: "#569cd6",
  string: "#ce9178",
  comment: "#6a9955",
  func: "#dcdcaa",
  type: "#4ec9b0",
  number: "#b5cea8",
  operator: "#d4d4d4",
  punctuation: "#808080",
  variable: "#9cdcfe",
  // 注释气泡
  annotationBg: "rgba(74, 158, 255, 0.15)",
  annotationBorder: "#4a9eff",
  annotationText: "#82b1ff",
  // 字体
  mono: "'SF Mono', 'Fira Code', 'JetBrains Mono', 'Cascadia Code', monospace",
};

/* ═══════════════ 语法着色（简化版） ═══════════════ */

const KEYWORD_RE = /\b(const|let|var|function|return|if|else|for|while|import|export|from|class|interface|type|async|await|new|this|true|false|null|undefined|def|self|print|elif|raise|try|except|catch|throw|finally|yield)\b/g;
const STRING_RE = /("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`)/g;
const COMMENT_RE = /(\/\/.*$|#.*$|\/\*[\s\S]*?\*\/)/gm;
const NUMBER_RE = /\b(\d+\.?\d*)\b/g;
const FUNC_RE = /\b([a-zA-Z_]\w*)\s*(?=\()/g;
const TYPE_RE = /\b([A-Z][a-zA-Z0-9]*)\b/g;

interface Token {
  text: string;
  color: string;
}

function tokenize(line: string): Token[] {
  // 简化处理: 依次匹配，用占位替换防止重叠
  const tokens: { start: number; end: number; color: string }[] = [];

  const mark = (re: RegExp, color: string) => {
    let m: RegExpExecArray | null;
    const r = new RegExp(re.source, re.flags);
    while ((m = r.exec(line)) !== null) {
      const s = m.index + (m[1] ? m[0].indexOf(m[1]) : 0);
      const e = s + (m[1] || m[0]).length;
      // 检查是否与已有 token 重叠
      const overlap = tokens.some(t => s < t.end && e > t.start);
      if (!overlap) {
        tokens.push({ start: s, end: e, color });
      }
    }
  };

  mark(COMMENT_RE, C.comment);
  mark(STRING_RE, C.string);
  mark(KEYWORD_RE, C.keyword);
  mark(NUMBER_RE, C.number);
  mark(FUNC_RE, C.func);
  mark(TYPE_RE, C.type);

  tokens.sort((a, b) => a.start - b.start);

  const result: Token[] = [];
  let pos = 0;
  for (const t of tokens) {
    if (t.start > pos) {
      result.push({ text: line.slice(pos, t.start), color: C.text });
    }
    result.push({ text: line.slice(t.start, t.end), color: t.color });
    pos = t.end;
  }
  if (pos < line.length) {
    result.push({ text: line.slice(pos), color: C.text });
  }
  if (result.length === 0) {
    result.push({ text: line, color: C.text });
  }
  return result;
}

/* ═══════════════ 语言图标 ═══════════════ */

function langIcon(lang: string): { icon: string; color: string } {
  const map: Record<string, { icon: string; color: string }> = {
    typescript: { icon: "TS", color: "#3178c6" },
    ts: { icon: "TS", color: "#3178c6" },
    tsx: { icon: "TS", color: "#3178c6" },
    javascript: { icon: "JS", color: "#f7df1e" },
    js: { icon: "JS", color: "#f7df1e" },
    jsx: { icon: "JS", color: "#f7df1e" },
    python: { icon: "PY", color: "#3776ab" },
    py: { icon: "PY", color: "#3776ab" },
    rust: { icon: "RS", color: "#ce422b" },
    go: { icon: "GO", color: "#00add8" },
    json: { icon: "{ }", color: "#f5a623" },
    yaml: { icon: "YML", color: "#cb171e" },
    bash: { icon: "$_", color: "#4eaa25" },
    sh: { icon: "$_", color: "#4eaa25" },
    markdown: { icon: "MD", color: "#ffffff" },
    md: { icon: "MD", color: "#ffffff" },
  };
  return map[lang.toLowerCase()] || { icon: lang.slice(0, 2).toUpperCase(), color: "#808080" };
}

/* ═══════════════ 主组件 ═══════════════ */

const CodeBlockDefault: React.FC<StyleComponentProps<"code-block">> = ({ data, segmentId }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const theme = useTheme();

  const { fileName, language, code, highlightLines = [], annotations = {} } = data;
  const langInfo = langIcon(language);

  const tokenizedLines = useMemo(() => code.map(line => tokenize(line)), [code]);

  // 窗口入场动画
  const winP = spring({ frame, fps, config: { damping: 18, stiffness: 120 }, durationInFrames: 15 });

  // 每行出现的最大可见行数
  const maxVisible = Math.min(code.length, Math.floor(interpolate(
    frame, [8, 8 + code.length * 2.5], [0, code.length],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  )));

  const LINE_H = 42;
  const GUTTER_W = 70;
  const ANNO_W = 360;
  const codeAreaH = Math.min(code.length * LINE_H, 780);

  // 背景微弱光斑
  const { durationInFrames } = useVideoConfig();
  const t = frame / Math.max(durationInFrames, 1);
  const orbX = 50 + Math.sin(t * Math.PI * 2) * 15;
  const orbY = 50 + Math.cos(t * Math.PI * 2 * 0.6) * 10;

  return (
    <AbsoluteFill style={{
      background: theme.bg,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: "30px 60px",
    }}>
      <GridBackground opacity={0.06} animated />
      <FloatingCode opacity={0.1} seed="code-bg" count={14} />
      {/* 微弱漂浮光斑 */}
      <div style={{
        position: "absolute",
        left: `${orbX}%`, top: `${orbY}%`,
        width: 500, height: 500,
        borderRadius: "50%",
        background: `radial-gradient(circle, ${theme.orbColor1} 0%, transparent 70%)`,
        filter: "blur(60px)",
        transform: "translate(-50%, -50%)",
        pointerEvents: "none",
      }} />
      {/* 代码窗口 */}
      <div style={{
        width: "100%",
        maxWidth: 1600,
        borderRadius: 14,
        overflow: "hidden",
        border: `1px solid ${C.titleBorder}`,
        boxShadow: "0 20px 60px rgba(0,0,0,0.6)",
        opacity: interpolate(winP, [0, 1], [0, 1]),
        transform: `scale(${interpolate(winP, [0, 1], [0.95, 1])})`,
      }}>
        {/* 标题栏 */}
        <div style={{
          display: "flex",
          alignItems: "center",
          padding: "12px 20px",
          background: C.titleBar,
          borderBottom: `1px solid ${C.titleBorder}`,
        }}>
          {/* macOS 三色按钮 */}
          <div style={{ display: "flex", gap: 8, marginRight: 20 }}>
            {["#ff5f57", "#febc2e", "#28c840"].map((c, i) => (
              <div key={i} style={{ width: 14, height: 14, borderRadius: "50%", background: c }} />
            ))}
          </div>

          {/* 文件标签 */}
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "4px 16px",
            background: C.bg,
            borderRadius: "8px 8px 0 0",
            border: `1px solid ${C.titleBorder}`,
            borderBottom: "none",
          }}>
            <span style={{
              fontSize: 12,
              fontWeight: 700,
              color: langInfo.color,
              fontFamily: C.mono,
            }}>
              {langInfo.icon}
            </span>
            <span style={{
              fontSize: 14,
              color: C.text,
              fontFamily: C.mono,
            }}>
              {fileName}
            </span>
          </div>

          <div style={{ flex: 1 }} />
          <span style={{ fontSize: 13, color: C.gutterText, fontFamily: C.mono }}>
            {language}
          </span>
        </div>

        {/* 代码区 */}
        <div style={{
          background: C.bg,
          padding: "16px 0",
          minHeight: codeAreaH,
          fontFamily: C.mono,
          fontSize: 24,
          lineHeight: `${LINE_H}px`,
          overflow: "hidden",
          display: "flex",
        }}>
          {/* 行号列 */}
          <div style={{
            width: GUTTER_W,
            flexShrink: 0,
            textAlign: "right",
            paddingRight: 16,
            userSelect: "none",
          }}>
            {code.map((_, i) => {
              if (i >= maxVisible) return null;
              const lineNum = i + 1;
              const isHL = highlightLines.includes(lineNum);
              return (
                <div key={i} style={{
                  height: LINE_H,
                  color: isHL ? C.lineHighlightBorder : C.gutterText,
                  fontWeight: isHL ? 600 : 400,
                }}>
                  {lineNum}
                </div>
              );
            })}
          </div>

          {/* 代码列 */}
          <div style={{ flex: 1, overflow: "hidden" }}>
            {tokenizedLines.map((tokens, i) => {
              if (i >= maxVisible) return null;
              const lineNum = i + 1;
              const isHL = highlightLines.includes(lineNum);
              const anno = annotations[lineNum];
              const lineOpacity = interpolate(
                frame, [8 + i * 2.5, 10 + i * 2.5], [0, 1],
                { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
              );

              return (
                <div key={i} style={{
                  height: LINE_H,
                  display: "flex",
                  alignItems: "center",
                  paddingLeft: 8,
                  paddingRight: anno ? ANNO_W + 20 : 16,
                  background: isHL ? C.lineHighlight : "transparent",
                  borderLeft: isHL ? `3px solid ${C.lineHighlightBorder}` : "3px solid transparent",
                  opacity: lineOpacity,
                  position: "relative",
                  whiteSpace: "pre",
                }}>
                  {tokens.map((t, j) => (
                    <span key={j} style={{ color: t.color }}>{t.text}</span>
                  ))}

                  {/* 注释气泡 */}
                  {anno && (
                    <div style={{
                      position: "absolute",
                      right: 16,
                      top: "50%",
                      transform: "translateY(-50%)",
                      maxWidth: ANNO_W,
                      padding: "6px 14px",
                      background: C.annotationBg,
                      border: `1px solid ${C.annotationBorder}`,
                      borderRadius: 8,
                      fontSize: 18,
                      color: C.annotationText,
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}>
                      ← {anno}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ═══════════════ 注册 ═══════════════ */

registry.register(
  {
    id: "code-block.default",
    schema: "code-block",
    name: "代码高亮卡片",
    description:
      "VS Code Dark+ 风格代码展示。支持语法着色、行号、高亮行、行注释气泡、逐行出现动画。" +
      "适合展示代码片段、配置文件、命令输出。",
    isDefault: false,
    tags: ["代码", "code", "syntax", "highlight"],
  },
  CodeBlockDefault,
);

export { CodeBlockDefault };
