/**
 * terminal.aurora — Claude Code TUI 模拟（极光背景）
 *
 * 从 components/TerminalDemoSegment.tsx 迁移，适配 StyleComponentProps。
 * 视觉: 极光渐变背景 + 像素角色 + 毛玻璃终端窗口
 */

import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import React, { useMemo } from "react";
import type { StyleComponentProps, TerminalSessionStep } from "../../types";
import { registry } from "../../registry";

/* ═══════════════ 颜色系统 ═══════════════ */
const CC = {
  bg: "#1a1a1a",
  bgDarker: "#141414",
  titleBar: "#2a2a2a",
  border: "#333",
  textPrimary: "#d4d4d4",
  textSecondary: "#888",
  textMuted: "#555",
  userPrompt: "#d4d4d4",
  keyword: "#c9a0dc",
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

/* ═══════════════ 会话数据结构 ═══════════════ */
interface UILine {
  type: "user-input" | "status" | "response" | "tree-item" | "tree-sub" | "blank" | "divider" | "tip";
  text: string;
  color?: string;
  bold?: boolean;
  icon?: string;
}

interface UIBlock {
  lines: UILine[];
  startDelay: number;
}

/** 从 LLM 生成的结构化 session 构建 UIBlock（优先路径） */
function buildFromSession(steps: TerminalSessionStep[]): UIBlock[] {
  const blocks: UIBlock[] = [];
  let delay = 10;

  // 将连续的非 input 步骤聚合到上一个 input 的 block 中
  let currentLines: UILine[] = [];

  const flushBlock = () => {
    if (currentLines.length > 0) {
      blocks.push({ lines: currentLines, startDelay: delay });
      delay += currentLines.length * 5 + 15;
      currentLines = [];
    }
  };

  for (const step of steps) {
    switch (step.type) {
      case "input":
        flushBlock();
        currentLines.push({ type: "user-input", text: step.text || "" });
        currentLines.push({ type: "blank", text: "" });
        break;

      case "status":
        currentLines.push({
          type: "status",
          text: step.text || "Processing...",
          icon: "*",
          color: step.color || CC.statusRed,
        });
        currentLines.push({ type: "blank", text: "" });
        break;

      case "tool":
        currentLines.push({
          type: "tree-item",
          text: `${step.name || "Tool"}(${step.target || "..."})`,
          color: step.color || CC.blue,
        });
        if (step.result) {
          currentLines.push({
            type: "tree-sub",
            text: step.result,
            color: CC.green,
          });
        }
        break;

      case "output": {
        const outputLines = step.lines || (step.text ? [step.text] : []);
        for (const line of outputLines) {
          currentLines.push({
            type: "response",
            text: line,
            color: step.color || CC.textPrimary,
          });
        }
        if (outputLines.length > 0) {
          currentLines.push({ type: "blank", text: "" });
        }
        break;
      }

      case "blank":
        currentLines.push({ type: "blank", text: "" });
        break;
    }
  }

  flushBlock();
  return blocks;
}

function buildClaudeSession(instruction: string): UIBlock[] {
  const blocks: UIBlock[] = [];
  let delay = 10;

  const slashCmds = instruction.match(/\/[a-zA-Z_]+/g) || [];
  const cliCmds = instruction.match(
    /\b(git|npm|claude|node)\s+[^\s，。；、]+(?:\s+[^\s，。；、]+)*/g
  ) || [];
  const hasEscape = /双击\s*Escape|按\s*Esc/i.test(instruction);

  const allCmds = [...slashCmds, ...cliCmds];
  if (hasEscape) allCmds.push("__escape__");
  if (allCmds.length === 0) allCmds.push("/help");

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
      { type: "response", text: "✓ Done", color: CC.green },
    );
  }

  return { lines, startDelay: baseDelay };
}

function renderHighlights(text: string): React.ReactNode {
  const parts = text.split(/((?:src|tests|\.claude)\/[\w./]+|\b\d[\d,.]+\s*(?:tokens?|%|files?|lines?|min|hour|ago|s)\b|Read|Write|Bash|Glob|Grep|Agent|Edit)/);
  return parts.map((part, i) => {
    if (/^(Read|Write|Bash|Glob|Grep|Agent|Edit)$/.test(part))
      return <span key={i} style={{ color: CC.blue, fontWeight: 600 }}>{part}</span>;
    if (/^(src|tests|\.claude)\//.test(part))
      return <span key={i} style={{ color: CC.orange }}>{part}</span>;
    if (/^\d/.test(part))
      return <span key={i} style={{ color: CC.yellow }}>{part}</span>;
    return <span key={i}>{part}</span>;
  });
}

/* ═══════════════ 主组件 ═══════════════ */

const TerminalAurora: React.FC<StyleComponentProps<"terminal">> = ({ data, segmentId }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const blocks = useMemo(
    () => data.session?.length ? buildFromSession(data.session) : buildClaudeSession(data.instruction),
    [data.session, data.instruction],
  );

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
          f += typeFrames + 10;
        } else if (line.type === "status") {
          rows.push({ ...line, frameStart: f, typeEnd: f });
          f += 18;
        } else {
          rows.push({ ...line, frameStart: f, typeEnd: f });
          f += 4;
        }
      }
    }
    return rows;
  }, [blocks]);

  const winProg = spring({ frame, fps, config: { damping: 18, stiffness: 120 }, durationInFrames: 15 });
  const mascotProg = spring({ frame: Math.max(0, frame - 5), fps, config: { damping: 12, stiffness: 100 }, durationInFrames: 20 });

  const mascotColor = "#c0614a";
  const mascotHighlight = "#d4826e";

  const particles = useMemo(() => {
    const seed = segmentId * 37;
    return Array.from({ length: 12 }, (_, i) => ({
      x: 860 + ((seed + i * 73) % 200) - 100,
      y: 20 + ((seed + i * 41) % 60),
      size: 4 + ((seed + i * 17) % 6),
      color: ["#f78166", "#e06c75", "#e5c07b", "#56b6c2", "#c678dd", "#98c379"][i % 6],
      speed: 0.3 + ((seed + i * 29) % 20) / 20,
      phase: (seed + i * 53) % 100,
    }));
  }, [segmentId]);

  const idleTips = [
    "whatever you've been putting off — now's a good time.",
    "the best code is the code you didn't have to write.",
    "measure twice, cut once. or just let me handle it.",
    "bugs are just features with commitment issues.",
  ];
  const idleTip = idleTips[segmentId % idleTips.length];

  const auroraShift = frame * 0.3;

  return (
    <AbsoluteFill style={{
      background: "#0a0a1a",
      overflow: "hidden",
      display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
      padding: "20px 60px",
    }}>
      {/* 极光渐变背景 */}
      <div style={{
        position: "absolute", inset: 0, zIndex: 0,
        background: `
          radial-gradient(ellipse 120% 60% at 30% 20%, rgba(56,189,248,0.25) 0%, transparent 60%),
          radial-gradient(ellipse 100% 50% at 70% 80%, rgba(139,92,246,0.2) 0%, transparent 55%),
          radial-gradient(ellipse 80% 40% at 50% 50%, rgba(59,130,246,0.15) 0%, transparent 50%)
        `,
        filter: "blur(40px)",
        transform: `translateX(${Math.sin(auroraShift * 0.02) * 30}px) translateY(${Math.cos(auroraShift * 0.015) * 20}px)`,
      }} />
      <div style={{
        position: "absolute", top: "5%", left: "-10%", width: "120%", height: "35%", zIndex: 0,
        background: `linear-gradient(${100 + Math.sin(auroraShift * 0.01) * 15}deg, transparent 20%, rgba(56,189,248,0.08) 35%, rgba(99,102,241,0.12) 50%, rgba(139,92,246,0.08) 65%, transparent 80%)`,
        filter: "blur(20px)",
        transform: `translateX(${Math.sin(auroraShift * 0.008) * 50}px)`,
      }} />
      <div style={{
        position: "absolute", bottom: "0%", left: "-10%", width: "120%", height: "40%", zIndex: 0,
        background: `linear-gradient(${260 + Math.cos(auroraShift * 0.012) * 10}deg, transparent 25%, rgba(59,130,246,0.1) 40%, rgba(14,165,233,0.08) 55%, transparent 75%)`,
        filter: "blur(30px)",
        transform: `translateX(${Math.cos(auroraShift * 0.01) * 40}px)`,
      }} />

      {/* 粒子 */}
      {particles.map((p, i) => {
        const yOffset = Math.sin((frame * p.speed + p.phase) * 0.1) * 15;
        const xOffset = Math.cos((frame * p.speed * 0.7 + p.phase) * 0.08) * 10;
        const opacity = interpolate(Math.sin((frame * 0.05 + p.phase) * 0.5), [-1, 1], [0.3, 0.9]);
        return (
          <div key={i} style={{
            position: "absolute", left: p.x + xOffset, top: p.y + yOffset,
            width: p.size, height: p.size,
            borderRadius: p.size > 6 ? 2 : "50%",
            background: p.color,
            opacity: opacity * interpolate(mascotProg, [0, 1], [0, 1]),
            transform: `rotate(${frame * p.speed * 2}deg)`,
            zIndex: 1,
          }} />
        );
      })}

      {/* 像素角色 */}
      <div style={{
        position: "relative", zIndex: 2, marginBottom: 12,
        opacity: interpolate(mascotProg, [0, 1], [0, 1]),
        transform: `translateY(${interpolate(mascotProg, [0, 1], [-30, 0]) + Math.sin(frame * 0.08) * 3}px) scale(${interpolate(mascotProg, [0, 1], [0.5, 1])})`,
      }}>
        <svg width="56" height="56" viewBox="0 0 8 8" style={{ imageRendering: "pixelated" }}>
          <rect x="2" y="0" width="4" height="1" fill={mascotColor} />
          <rect x="1" y="1" width="6" height="1" fill={mascotColor} />
          <rect x="1" y="2" width="6" height="1" fill={mascotColor} />
          <rect x="2" y="2" width="1" height="1" fill="#1a1a1a" />
          <rect x="5" y="2" width="1" height="1" fill="#1a1a1a" />
          <rect x="1" y="3" width="6" height="1" fill={mascotHighlight} />
          <rect x="2" y="4" width="4" height="1" fill={mascotColor} />
          <rect x="2" y="5" width="4" height="1" fill={mascotColor} />
          <rect x="2" y="6" width="1" height="1" fill={mascotColor} />
          <rect x="5" y="6" width="1" height="1" fill={mascotColor} />
        </svg>
      </div>

      {/* 终端窗口 */}
      <div style={{
        position: "relative", zIndex: 2,
        width: "100%", maxWidth: 1500, flex: 1,
        display: "flex", flexDirection: "column",
        background: "rgba(22,22,30,0.92)",
        backdropFilter: "blur(20px)",
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: 14, overflow: "hidden",
        opacity: interpolate(winProg, [0, 1], [0, 1]),
        transform: `scale(${interpolate(winProg, [0, 1], [0.95, 1])}) translateY(${interpolate(winProg, [0, 1], [20, 0])}px)`,
        boxShadow: "0 20px 60px rgba(0,0,0,0.5), 0 0 1px rgba(255,255,255,0.1)",
      }}>
        {/* macOS 标题栏 */}
        <div style={{
          display: "flex", alignItems: "center", padding: "14px 20px",
          background: CC.titleBar, borderBottom: `1px solid ${CC.border}`, flexShrink: 0,
        }}>
          <div style={{ display: "flex", gap: 8, marginRight: 20 }}>
            {["#ff5f57", "#febc2e", "#28c840"].map((c, j) => (
              <div key={j} style={{ width: 14, height: 14, borderRadius: "50%", background: c }} />
            ))}
          </div>
          <div style={{ flex: 1 }} />
          <span style={{ fontSize: 16, color: CC.textSecondary, fontFamily: "'SF Mono', monospace", fontWeight: 600 }}>
            Claude Code v2.1.9
          </span>
          <div style={{ flex: 1 }} />
          <div style={{ width: 60 }} />
        </div>

        {/* tmux tab */}
        <div style={{
          display: "flex", alignItems: "center", padding: "6px 16px",
          background: CC.bgDarker, borderBottom: `1px solid ${CC.border}`, flexShrink: 0, gap: 4,
        }}>
          <span style={{ fontSize: 12, color: CC.textMuted, fontFamily: "monospace" }}>✕</span>
          <div style={{ padding: "4px 14px", background: CC.bg, borderRadius: 4, border: `1px solid ${CC.border}` }}>
            <span style={{ fontSize: 13, color: CC.textSecondary, fontFamily: "monospace" }}>✱ Claude Code (caffeinate)</span>
          </div>
          <div style={{ flex: 1 }} />
          <span style={{ fontSize: 12, color: CC.textMuted, fontFamily: "monospace" }}>⌘1</span>
        </div>

        {/* 主内容区 */}
        <div style={{
          flex: 1, display: "flex", flexDirection: "column",
          justifyContent: allRows.length <= 18 ? "center" : "flex-start",
          padding: "24px 0", overflow: "hidden",
          fontFamily: "'SF Mono', 'Fira Code', 'JetBrains Mono', monospace",
        }}>
          {allRows.map((row, i) => {
            if (frame < row.frameStart) return null;

            if (row.type === "blank") return <div key={i} style={{ height: 10 }} />;

            if (row.type === "divider") {
              return (
                <div key={i} style={{
                  height: 1, margin: "4px 44px",
                  background: `linear-gradient(90deg, ${CC.border}, transparent 70%)`,
                  opacity: interpolate(frame, [row.frameStart, row.frameStart + 3], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
                }} />
              );
            }

            if (row.type === "user-input") {
              const chars = Math.floor(interpolate(
                frame, [row.frameStart, row.typeEnd], [0, row.text.length],
                { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
              ));
              const done = frame >= row.typeEnd;
              return (
                <div key={i} style={{ display: "flex", alignItems: "center", padding: "8px 44px", fontSize: 28, lineHeight: 1.8 }}>
                  <span style={{ color: CC.green, fontWeight: 700, marginRight: 12 }}>❯</span>
                  <span style={{ color: CC.userPrompt, fontWeight: 500 }}>{row.text.slice(0, chars)}</span>
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

            const fadeIn = interpolate(frame, [row.frameStart, row.frameStart + 4], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

            if (row.type === "status") {
              const dots = ".".repeat(1 + Math.floor((frame - row.frameStart) / 6) % 3);
              if (frame >= row.frameStart + 16) return null;
              return (
                <div key={i} style={{ padding: "6px 44px", fontSize: 26, lineHeight: 1.8, opacity: fadeIn, display: "flex", alignItems: "center" }}>
                  <span style={{ color: row.color || CC.statusRed, marginRight: 10, fontWeight: 700 }}>{row.icon || "*"}</span>
                  <span style={{ color: row.color || CC.statusRed, fontStyle: "italic" }}>{row.text.replace(/\.+$/, "")}{dots}</span>
                  <span style={{ marginLeft: 16, fontSize: 22, color: CC.textMuted }}>({Math.floor((frame - row.frameStart) / 30 * 10) / 10}s)</span>
                </div>
              );
            }

            if (row.type === "tree-item") {
              return (
                <div key={i} style={{ padding: "2px 44px 2px 68px", fontSize: 26, lineHeight: 1.8, opacity: fadeIn, display: "flex", alignItems: "center" }}>
                  <span style={{ color: CC.treeColor, marginRight: 10 }}>├─</span>
                  <span style={{ color: row.color || CC.textSecondary }}>{renderHighlights(row.text)}</span>
                </div>
              );
            }

            if (row.type === "tree-sub") {
              return (
                <div key={i} style={{ padding: "0px 44px 0px 96px", fontSize: 24, lineHeight: 1.6, opacity: fadeIn * 0.8 }}>
                  <span style={{ color: row.color || CC.textMuted }}>{row.text}</span>
                </div>
              );
            }

            if (row.type === "tip") {
              return (
                <div key={i} style={{ padding: "4px 44px 4px 68px", fontSize: 23, lineHeight: 1.7, opacity: fadeIn, display: "flex", alignItems: "flex-start" }}>
                  <span style={{ color: CC.treeColor, marginRight: 10 }}>└</span>
                  <span style={{ color: CC.textMuted, fontStyle: "italic" }}>{row.text}</span>
                </div>
              );
            }

            return (
              <div key={i} style={{
                padding: "4px 44px 4px 44px", fontSize: 27, lineHeight: 1.8,
                opacity: fadeIn, color: row.color || CC.textPrimary,
                fontWeight: row.bold ? 600 : 400,
              }}>
                {renderHighlights(row.text)}
              </div>
            );
          })}
        </div>

        {/* 底部状态栏 */}
        <div style={{
          display: "flex", alignItems: "center", padding: "10px 24px",
          borderTop: `1px solid ${CC.border}`, background: CC.bgDarker, flexShrink: 0, gap: 20,
        }}>
          <span style={{ fontSize: 14, color: CC.textMuted, fontFamily: "monospace", fontStyle: "italic" }}>{idleTip}</span>
          <div style={{ flex: 1 }} />
          <span style={{ fontSize: 13, color: CC.textMuted, fontFamily: "monospace" }}>{String(segmentId)}</span>
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ═══════════════ 注册 ═══════════════ */

registry.register(
  {
    id: "terminal.aurora",
    schema: "terminal",
    name: "Claude Code 终端模拟（极光）",
    description: "模拟 Claude Code TUI 界面，自动从 instruction 提取命令生成交互动画。极光背景 + 毛玻璃终端窗口。适合展示 CLI 命令、斜杠命令操作。",
    isDefault: true,
    tags: ["终端", "CLI", "命令行", "Claude Code"],
  },
  TerminalAurora,
);

export { TerminalAurora };
