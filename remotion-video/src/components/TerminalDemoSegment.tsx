/**
 * 素材 B 降级: 模拟 Claude Code 真实 TUI 界面
 *
 * 复刻 Claude Code 终端界面:
 *   - macOS 标题栏 "· Claude Code"
 *   - 用户 ❯ 输入 + Claude 树形响应
 *   - * Brewing/Enchanting 状态指示器
 *   - 底部 Tips 提示
 */

import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import React, { useMemo } from "react";

const EASE_OUT = Easing.bezier(0.16, 1, 0.3, 1);

/* ════════════════════════════════════════════════
   Claude Code UI 颜色系统
   ════════════════════════════════════════════════ */
const CC = {
  bg: "#1a1a1a",
  bgDarker: "#141414",
  titleBar: "#2a2a2a",
  border: "#333",
  textPrimary: "#d4d4d4",
  textSecondary: "#888",
  textMuted: "#555",
  userPrompt: "#d4d4d4",
  keyword: "#c9a0dc",     // 紫色 - Claude 关键字
  green: "#5cba6e",
  greenBright: "#7ee787",
  red: "#cc6666",
  orange: "#d19a66",
  blue: "#6cb6ff",
  yellow: "#e5c07b",
  magenta: "#c678dd",
  statusRed: "#cc6666",
  treeColor: "#555",
};

/* ════════════════════════════════════════════════
   会话数据结构
   ════════════════════════════════════════════════ */

interface UILine {
  type:
    | "user-input"      // ❯ 用户输入
    | "status"          // * Brewing... / ✓ Done
    | "response"        // Claude 正文
    | "tree-item"       // └─ 工具调用 / 子项
    | "tree-sub"        // 更深层嵌套
    | "blank"
    | "divider"         // 分隔线
    | "tip";            // └ Tip: ...
  text: string;
  color?: string;
  bold?: boolean;
  icon?: string;        // 行首图标
}

interface UIBlock {
  lines: UILine[];
  startDelay: number;   // 帧
}

/** 从 instruction 构建 Claude Code 风格会话 */
function buildClaudeSession(instruction: string): UIBlock[] {
  const blocks: UIBlock[] = [];
  let delay = 10;

  // 提取命令
  const slashCmds = instruction.match(/\/[a-zA-Z_]+/g) || [];
  const cliCmds = instruction.match(
    /\b(git|npm|claude|node)\s+[^\s，。；、]+(?:\s+[^\s，。；、]+)*/g
  ) || [];
  const hasEscape = /双击\s*Escape|按\s*Esc/i.test(instruction);

  const allCmds = [...slashCmds, ...cliCmds];
  if (hasEscape) allCmds.push("__escape__");

  if (allCmds.length === 0) {
    allCmds.push("/help");
  }

  for (const cmd of allCmds) {
    const block = buildCommandBlock(cmd, delay);
    blocks.push(block);
    delay = block.startDelay + block.lines.length * 5 + 20;
  }

  return blocks;
}

function buildCommandBlock(cmd: string, baseDelay: number): UIBlock {
  const lines: UILine[] = [];

  if (cmd === "/context") {
    lines.push(
      { type: "user-input", text: "/context" },
      { type: "blank", text: "" },
      { type: "status", text: "Inspecting context window...", icon: "*", color: CC.statusRed },
      { type: "blank", text: "" },
      { type: "response", text: "Context Window Usage", bold: true, color: CC.textPrimary },
      { type: "blank", text: "" },
      { type: "tree-item", text: "System prompt        2,847 tokens", color: CC.textSecondary },
      { type: "tree-sub",  text: "████░░░░░░░░░░  12.0%", color: CC.textMuted },
      { type: "tree-item", text: "CLAUDE.md            1,203 tokens", color: CC.textSecondary },
      { type: "tree-sub",  text: "██░░░░░░░░░░░░   5.1%", color: CC.textMuted },
      { type: "tree-item", text: "Conversation        14,502 tokens", color: CC.yellow },
      { type: "tree-sub",  text: "█████████░░░░░  61.3%", color: CC.yellow },
      { type: "tree-item", text: "MCP servers          3,218 tokens", color: CC.textSecondary },
      { type: "tree-sub",  text: "████░░░░░░░░░░  13.6%", color: CC.textMuted },
      { type: "tree-item", text: "Tool results         1,892 tokens", color: CC.textSecondary },
      { type: "tree-sub",  text: "███░░░░░░░░░░░   8.0%", color: CC.textMuted },
      { type: "blank", text: "" },
      { type: "divider", text: "" },
      { type: "response", text: "Total: 23,662 / 200,000 tokens (11.8%)", bold: true, color: CC.green },
      { type: "blank", text: "" },
      { type: "tip", text: "Tip: Use /clear to reset context when it gets too large" },
    );
  } else if (cmd === "/clear") {
    lines.push(
      { type: "user-input", text: "/clear" },
      { type: "blank", text: "" },
      { type: "status", text: "Clearing context...", icon: "*", color: CC.statusRed },
      { type: "blank", text: "" },
      { type: "response", text: "✓ Context cleared. Starting fresh conversation.", color: CC.green, bold: true },
      { type: "tree-item", text: "Removed 23,662 tokens", color: CC.textSecondary },
      { type: "tree-item", text: "Session history preserved", color: CC.textSecondary },
    );
  } else if (cmd === "/init") {
    lines.push(
      { type: "user-input", text: "/init" },
      { type: "blank", text: "" },
      { type: "status", text: "Scanning project...", icon: "*", color: CC.statusRed },
      { type: "blank", text: "" },
      { type: "tree-item", text: "Read(package.json)", color: CC.blue },
      { type: "tree-item", text: "Read(tsconfig.json)", color: CC.blue },
      { type: "tree-item", text: "Glob(**/*.ts) → 142 files", color: CC.blue },
      { type: "blank", text: "" },
      { type: "response", text: "✅ Generated .claude/claude.md", color: CC.green, bold: true },
      { type: "tree-item", text: "287 lines · TypeScript 68% · Python 24%", color: CC.textSecondary },
    );
  } else if (cmd === "/resume") {
    lines.push(
      { type: "user-input", text: "/resume" },
      { type: "blank", text: "" },
      { type: "response", text: "Recent sessions:", bold: true, color: CC.textPrimary },
      { type: "blank", text: "" },
      { type: "tree-item", text: "1. Fix auth middleware          2 min ago  ●", color: CC.green },
      { type: "tree-item", text: "2. Add unit tests              15 min ago", color: CC.textSecondary },
      { type: "tree-item", text: "3. Refactor API routes          1 hour ago", color: CC.textSecondary },
      { type: "blank", text: "" },
      { type: "status", text: "Resuming session...", icon: "*", color: CC.statusRed },
      { type: "blank", text: "" },
      { type: "response", text: "✓ Resumed: Fix auth middleware", color: CC.green, bold: true },
      { type: "tree-item", text: "Restored 12,450 tokens of context", color: CC.textSecondary },
    );
  } else if (cmd.startsWith("git status")) {
    lines.push(
      { type: "user-input", text: "run git status in the terminal" },
      { type: "blank", text: "" },
      { type: "status", text: "Brewing...", icon: "*", color: CC.statusRed },
      { type: "blank", text: "" },
      { type: "tree-item", text: "Bash(git status)", color: CC.blue },
      { type: "blank", text: "" },
      { type: "response", text: "On branch feature/auth-middleware", color: CC.blue },
      { type: "blank", text: "" },
      { type: "response", text: "Changes to be committed:", color: CC.green },
      { type: "tree-item", text: "modified:  src/middleware/auth.ts", color: CC.green },
      { type: "tree-item", text: "modified:  src/config/routes.ts", color: CC.green },
      { type: "blank", text: "" },
      { type: "response", text: "Changes not staged:", color: CC.red },
      { type: "tree-item", text: "modified:  tests/auth.test.ts", color: CC.red },
    );
  } else if (cmd === "__escape__") {
    lines.push(
      { type: "user-input", text: "这是一个很长的输入内容正在编写中..." },
      { type: "blank", text: "" },
      { type: "response", text: "⎋ ESC × 2", color: CC.yellow, bold: true },
      { type: "blank", text: "" },
      { type: "response", text: "✓ Input cleared", color: CC.green },
      { type: "blank", text: "" },
      { type: "tip", text: "Tip: Double-press Escape to quickly clear your input" },
    );
  } else {
    lines.push(
      { type: "user-input", text: cmd },
      { type: "blank", text: "" },
      { type: "status", text: "Brewing...", icon: "*", color: CC.statusRed },
      { type: "blank", text: "" },
      { type: "response", text: `✓ Done`, color: CC.green },
    );
  }

  return { lines, startDelay: baseDelay };
}

/* ════════════════════════════════════════════════
   渲染组件
   ════════════════════════════════════════════════ */

interface TerminalDemoSegmentProps {
  instruction: string;
  segmentId?: number;
  narrationText?: string;
}

/** 从 instruction 中提取核心命令作为标题 */
function extractHeadline(instruction: string): { title: string; subtitle: string } {
  // 提取 slash 命令
  const slashMatch = instruction.match(/\/([\w_]+)/);
  // 提取关键动作描述
  const actionMatch = instruction.match(/(?:演示|展示|查看|输入|运行|使用)(.*?)(?:[，,。；]|$)/);

  if (slashMatch) {
    const cmd = `/${slashMatch[1]}`;
    const subtitle = actionMatch
      ? actionMatch[1].trim().replace(/^如何/, "")
      : instruction.replace(/[。，；]/g, " ").trim().slice(0, 50);
    return { title: cmd, subtitle };
  }

  // 提取 CLI 命令
  const cliMatch = instruction.match(/\b(git\s+\w+|npm\s+\w+|claude\s+\w+)/);
  if (cliMatch) {
    return {
      title: cliMatch[1],
      subtitle: actionMatch ? actionMatch[1].trim() : instruction.slice(0, 50),
    };
  }

  // 提取关键词作为标题
  const keyAction = instruction.match(/(?:演示|展示|查看)(.*?)(?:[，,。；]|$)/);
  return {
    title: keyAction ? keyAction[1].trim().slice(0, 20) : "Demo",
    subtitle: instruction.replace(/[。，；]/g, " ").trim().slice(0, 60),
  };
}

export const TerminalDemoSegment: React.FC<TerminalDemoSegmentProps> = ({
  instruction,
  segmentId = 1,
  narrationText,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const blocks = useMemo(() => buildClaudeSession(instruction), [instruction]);
  const headline = useMemo(() => extractHeadline(instruction), [instruction]);

  // 展平所有行 + 计算时序
  const allRows = useMemo(() => {
    const rows: (UILine & { frameStart: number; typeEnd: number })[] = [];

    for (const block of blocks) {
      let f = block.startDelay;

      for (const line of block.lines) {
        if (line.type === "blank") {
          rows.push({ ...line, frameStart: f, typeEnd: f });
          f += 2;
        } else if (line.type === "user-input") {
          const typeFrames = Math.ceil(line.text.length * 0.7);
          rows.push({ ...line, frameStart: f, typeEnd: f + typeFrames });
          f += typeFrames + 10; // 打完后停顿
        } else if (line.type === "status") {
          rows.push({ ...line, frameStart: f, typeEnd: f });
          f += 18; // 状态持续显示
        } else {
          rows.push({ ...line, frameStart: f, typeEnd: f });
          f += 4;
        }
      }
    }

    return rows;
  }, [blocks]);

  // 进场动画
  const winProg = spring({ frame, fps, config: { damping: 18, stiffness: 120 }, durationInFrames: 15 });
  const titleProg = spring({ frame, fps, config: { damping: 20, stiffness: 200 }, durationInFrames: 10 });
  const subtitleOp = interpolate(frame, [8, 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  // 标题颜色
  const accentOrange = "#f78166";

  return (
    <AbsoluteFill
      style={{
        background: "#111",
        padding: "30px 50px",
        overflow: "hidden",
      }}
    >
      {/* 背景 */}
      <div style={{
        position: "absolute", top: -200, left: -100, width: 500, height: 500, borderRadius: "50%",
        background: "radial-gradient(circle, rgba(150,80,200,0.06) 0%, transparent 70%)", filter: "blur(60px)",
      }} />

      <div style={{
        position: "relative", zIndex: 1, height: "100%",
        display: "flex", flexDirection: "column", gap: 16,
      }}>
        {/* ─── 标题区域: 序号 + 一级标题 + 副标题 ─── */}
        <div style={{
          flexShrink: 0, display: "flex", alignItems: "flex-start", gap: 24,
          padding: "8px 0",
          opacity: interpolate(titleProg, [0, 1], [0, 1]),
          transform: `translateY(${interpolate(titleProg, [0, 1], [20, 0])}px)`,
        }}>
          {/* 序号 */}
          <div style={{
            fontSize: 72, fontWeight: 900, color: accentOrange, fontFamily: "'SF Mono','Fira Code',monospace",
            lineHeight: 1, flexShrink: 0, minWidth: 80, opacity: 0.9,
          }}>
            {String(segmentId).padStart(2, "0")}
          </div>
          <div style={{ flex: 1 }}>
            {/* 类型标签 */}
            <div style={{
              fontSize: 12, fontWeight: 700, color: accentOrange, letterSpacing: 4,
              marginBottom: 6, fontFamily: "'SF Mono','Fira Code',monospace", opacity: 0.7,
            }}>
              TIP
            </div>
            {/* 一级标题 */}
            <div style={{
              fontSize: 44, fontWeight: 900, color: "#f0f4f8", lineHeight: 1.2,
              fontFamily: "'PingFang SC','Hiragino Sans GB','Noto Sans CJK SC',sans-serif",
            }}>
              {headline.title}
            </div>
            {/* 二级副标题 */}
            <div style={{
              fontSize: 24, color: "#b0bec5", lineHeight: 1.5, marginTop: 8, opacity: subtitleOp,
              fontFamily: "'PingFang SC','Hiragino Sans GB',sans-serif",
            }}>
              {headline.subtitle}
            </div>
          </div>
        </div>

        {/* ─── 终端窗口 ─── */}
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            background: CC.bg,
            border: `1px solid ${CC.border}`,
            borderRadius: 12,
            overflow: "hidden",
            opacity: interpolate(winProg, [0, 1], [0, 1]),
            transform: `scale(${interpolate(winProg, [0, 1], [0.97, 1])})`,
            boxShadow: "0 20px 60px rgba(0,0,0,0.7)",
          }}
        >
        {/* ─── macOS 标题栏 ─── */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            padding: "14px 20px",
            background: CC.titleBar,
            borderBottom: `1px solid ${CC.border}`,
            flexShrink: 0,
          }}
        >
          <div style={{ display: "flex", gap: 8, marginRight: 20 }}>
            <div style={{ width: 14, height: 14, borderRadius: "50%", background: "#ff5f57" }} />
            <div style={{ width: 14, height: 14, borderRadius: "50%", background: "#febc2e" }} />
            <div style={{ width: 14, height: 14, borderRadius: "50%", background: "#28c840" }} />
          </div>
          <div style={{ flex: 1 }} />
          <span style={{
            fontSize: 16, color: CC.textSecondary,
            fontFamily: "'SF Mono', monospace",
          }}>
            · Claude Code
          </span>
          <div style={{ flex: 1 }} />
          <div style={{ width: 60 }} />
        </div>

        {/* ─── tmux 风格 tab ─── */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            padding: "6px 16px",
            background: CC.bgDarker,
            borderBottom: `1px solid ${CC.border}`,
            flexShrink: 0,
            gap: 4,
          }}
        >
          <span style={{ fontSize: 12, color: CC.textMuted, fontFamily: "monospace" }}>
            ✕
          </span>
          <div
            style={{
              padding: "4px 14px",
              background: CC.bg,
              borderRadius: 4,
              border: `1px solid ${CC.border}`,
            }}
          >
            <span style={{ fontSize: 13, color: CC.textSecondary, fontFamily: "monospace" }}>
              ✱ Claude Code (caffeinate)
            </span>
          </div>
          <div style={{ flex: 1 }} />
          <span style={{ fontSize: 12, color: CC.textMuted, fontFamily: "monospace" }}>⌘1</span>
        </div>

        {/* ─── 主内容区 ─── */}
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            justifyContent: allRows.length <= 18 ? "center" : "flex-start",
            padding: "24px 0",
            overflow: "hidden",
            fontFamily: "'SF Mono', 'Fira Code', 'JetBrains Mono', monospace",
          }}
        >
          {allRows.map((row, i) => {
            if (frame < row.frameStart) return null;

            if (row.type === "blank") {
              return <div key={i} style={{ height: 10 }} />;
            }

            if (row.type === "divider") {
              return (
                <div key={i} style={{
                  height: 1, margin: "4px 44px",
                  background: `linear-gradient(90deg, ${CC.border}, transparent 70%)`,
                  opacity: interpolate(frame, [row.frameStart, row.frameStart + 3], [0, 1], {
                    extrapolateLeft: "clamp", extrapolateRight: "clamp",
                  }),
                }} />
              );
            }

            if (row.type === "user-input") {
              const chars = Math.floor(interpolate(
                frame, [row.frameStart, row.typeEnd], [0, row.text.length],
                { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
              ));
              const done = frame >= row.typeEnd;
              const display = row.text.slice(0, chars);

              return (
                <div key={i} style={{
                  display: "flex", alignItems: "center",
                  padding: "8px 44px",
                  fontSize: 28, lineHeight: 1.8,
                }}>
                  <span style={{ color: CC.green, fontWeight: 700, marginRight: 12 }}>❯</span>
                  <span style={{ color: CC.userPrompt, fontWeight: 500 }}>{display}</span>
                  {!done && (
                    <span style={{
                      display: "inline-block", width: 2, height: 24,
                      background: CC.green, marginLeft: 2, borderRadius: 1,
                      opacity: frame % 18 < 11 ? 1 : 0,
                    }} />
                  )}
                </div>
              );
            }

            // 淡入
            const fadeIn = interpolate(
              frame, [row.frameStart, row.frameStart + 4], [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            );

            if (row.type === "status") {
              // * Brewing... 风格状态, 带闪烁动画
              const dots = ".".repeat(1 + Math.floor((frame - row.frameStart) / 6) % 3);
              const statusVisible = frame < row.frameStart + 16; // 状态行会被后续内容"替换"

              if (!statusVisible) return null;

              return (
                <div key={i} style={{
                  padding: "6px 44px", fontSize: 26, lineHeight: 1.8, opacity: fadeIn,
                  display: "flex", alignItems: "center",
                }}>
                  <span style={{ color: row.color || CC.statusRed, marginRight: 10, fontWeight: 700 }}>
                    {row.icon || "*"}
                  </span>
                  <span style={{ color: row.color || CC.statusRed, fontStyle: "italic" }}>
                    {row.text.replace(/\.+$/, "")}{dots}
                  </span>
                  <span style={{
                    marginLeft: 16, fontSize: 22, color: CC.textMuted,
                  }}>
                    ({Math.floor((frame - row.frameStart) / 30 * 10) / 10}s)
                  </span>
                </div>
              );
            }

            if (row.type === "tree-item") {
              return (
                <div key={i} style={{
                  padding: "2px 44px 2px 68px", fontSize: 26, lineHeight: 1.8,
                  opacity: fadeIn, display: "flex", alignItems: "center",
                }}>
                  <span style={{ color: CC.treeColor, marginRight: 10 }}>├─</span>
                  <span style={{ color: row.color || CC.textSecondary }}>
                    {renderHighlights(row.text)}
                  </span>
                </div>
              );
            }

            if (row.type === "tree-sub") {
              return (
                <div key={i} style={{
                  padding: "0px 44px 0px 96px", fontSize: 24, lineHeight: 1.6,
                  opacity: fadeIn * 0.8,
                }}>
                  <span style={{ color: row.color || CC.textMuted }}>{row.text}</span>
                </div>
              );
            }

            if (row.type === "tip") {
              return (
                <div key={i} style={{
                  padding: "4px 44px 4px 68px", fontSize: 23, lineHeight: 1.7,
                  opacity: fadeIn, display: "flex", alignItems: "flex-start",
                }}>
                  <span style={{ color: CC.treeColor, marginRight: 10 }}>└</span>
                  <span style={{ color: CC.textMuted, fontStyle: "italic" }}>{row.text}</span>
                </div>
              );
            }

            // response (正文)
            return (
              <div key={i} style={{
                padding: "4px 44px 4px 44px", fontSize: 27, lineHeight: 1.8,
                opacity: fadeIn,
                color: row.color || CC.textPrimary,
                fontWeight: row.bold ? 600 : 400,
              }}>
                {renderHighlights(row.text)}
              </div>
            );
          })}
        </div>

        {/* ─── 底部状态栏 ─── */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            padding: "10px 24px",
            borderTop: `1px solid ${CC.border}`,
            background: CC.bgDarker,
            flexShrink: 0,
            gap: 20,
          }}
        >
          <span style={{ fontSize: 13, color: CC.green, fontFamily: "monospace", display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: CC.green, display: "inline-block" }} />
            Claude Code v2.1.74
          </span>
          <span style={{ fontSize: 13, color: CC.textMuted, fontFamily: "monospace" }}>
            Sonnet 4.6
          </span>
          <span style={{ fontSize: 13, color: CC.textMuted, fontFamily: "monospace" }}>
            ~/workspace/project
          </span>
          <div style={{ flex: 1 }} />
          <span style={{ fontSize: 13, color: CC.textMuted, fontFamily: "monospace" }}>
            23.7k tokens
          </span>
        </div>
      </div>
      </div>
    </AbsoluteFill>
  );
};

/** 高亮文本中的特殊元素 */
function renderHighlights(text: string): React.ReactNode {
  // 高亮: 文件路径、命令名、数字
  const parts = text.split(/((?:src|tests|\.claude)\/[\w./]+|\b\d[\d,.]+\s*(?:tokens?|%|files?|lines?|min|hour|ago|s)\b|Read|Write|Bash|Glob|Grep|Agent|Edit)/);

  return parts.map((part, i) => {
    if (/^(Read|Write|Bash|Glob|Grep|Agent|Edit)$/.test(part)) {
      return <span key={i} style={{ color: CC.blue, fontWeight: 600 }}>{part}</span>;
    }
    if (/^(src|tests|\.claude)\//.test(part)) {
      return <span key={i} style={{ color: CC.orange }}>{part}</span>;
    }
    if (/^\d/.test(part)) {
      return <span key={i} style={{ color: CC.yellow }}>{part}</span>;
    }
    return <span key={i}>{part}</span>;
  });
}
