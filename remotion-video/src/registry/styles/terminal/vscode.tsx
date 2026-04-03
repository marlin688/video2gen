/**
 * terminal.vscode — VS Code 编辑器模拟风格
 *
 * 灵感来源: rVEoyx349Hk, B2Kh_ZoLVTM, vDVSGVpB2vc 中大量出现的
 * VS Code + Claude Code Extension 界面。
 *
 * 设计理念:
 * - 完整 VS Code Dark+ 主题色彩还原
 * - 左侧活动栏 (图标) + 文件树侧栏
 * - 主编辑区: 指令内容渲染为代码/Markdown
 * - 底部终端面板: Claude Code 输出模拟
 * - 状态栏: 分支名 + 语言 + 编码信息
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

/* ═══════════════ VS Code 颜色系统 ═══════════════ */
const V = {
  // 结构色
  activityBar: "#333333",
  sideBar: "#252526",
  editor: "#1e1e1e",
  editorGutter: "#1e1e1e",
  terminal: "#1e1e1e",
  titleBar: "#3c3c3c",
  tab: "#2d2d2d",
  tabActive: "#1e1e1e",
  tabBorder: "#252526",
  statusBar: "#007acc",
  statusBarItem: "#16825d",
  panelBorder: "#404040",
  // 文字色
  text: "#d4d4d4",
  textDim: "#808080",
  textBright: "#ffffff",
  // 语法高亮
  keyword: "#569cd6",     // blue
  string: "#ce9178",      // orange
  comment: "#6a9955",     // green
  func: "#dcdcaa",        // yellow
  type: "#4ec9b0",        // teal
  number: "#b5cea8",      // light green
  variable: "#9cdcfe",    // light blue
  operator: "#d4d4d4",
  // Claude Code 色
  claudeRed: "#cc6666",
  claudeGreen: "#5cba6e",
  claudeBlue: "#6cb6ff",
  claudeYellow: "#e5c07b",
  claudePurple: "#c678dd",
  // 字体
  mono: "'SF Mono', 'Fira Code', 'Cascadia Code', 'JetBrains Mono', 'Consolas', monospace",
  ui: "'Segoe WPC', 'Segoe UI', 'SF Pro Text', -apple-system, sans-serif",
};

/* ═══════════════ 工具函数 ═══════════════ */

function fadeIn(frame: number, fps: number, delay: number): React.CSSProperties {
  const p = spring({
    frame: Math.max(0, frame - delay), fps,
    config: { damping: 20, stiffness: 100 },
    durationInFrames: 15,
  });
  return { opacity: p };
}

/** 逐字打字动画 */
function typeChars(text: string, frame: number, fps: number, startFrame: number, charsPerFrame = 0.8): string {
  const elapsed = Math.max(0, frame - startFrame);
  const charCount = Math.min(text.length, Math.floor(elapsed * charsPerFrame));
  return text.slice(0, charCount);
}

/* ═══════════════ 解析指令为终端会话 ═══════════════ */

interface TermLine {
  type: "prompt" | "command" | "output" | "status" | "tool" | "blank";
  text: string;
  color?: string;
}

/** 从结构化 session 构建 TermLine（优先路径） */
function parseSession(steps: TerminalSessionStep[]): TermLine[] {
  const lines: TermLine[] = [];

  lines.push({ type: "prompt", text: "❯ claude", color: V.claudeGreen });
  lines.push({ type: "blank", text: "" });

  for (const step of steps) {
    switch (step.type) {
      case "input":
        lines.push({ type: "command", text: `❯ ${step.text || ""}`, color: V.text });
        lines.push({ type: "blank", text: "" });
        break;

      case "status":
        lines.push({ type: "status", text: `⠋ ${step.text || "Processing..."}`, color: step.color || V.claudeYellow });
        break;

      case "tool":
        lines.push({
          type: "tool",
          text: `● ${step.name || "Tool"}(${step.target || "..."})`,
          color: step.color || V.claudeBlue,
        });
        if (step.result) {
          lines.push({ type: "output", text: `  ${step.result}` });
        }
        lines.push({ type: "blank", text: "" });
        break;

      case "output": {
        const outputLines = step.lines || (step.text ? [step.text] : []);
        for (const line of outputLines) {
          lines.push({ type: "output", text: line, color: step.color || V.text });
        }
        break;
      }

      case "blank":
        lines.push({ type: "blank", text: "" });
        break;
    }
  }

  return lines;
}

function parseInstruction(instruction: string): TermLine[] {
  const lines: TermLine[] = [];
  const parts = instruction.split(/[;；。\n]/);

  lines.push({ type: "prompt", text: "❯ claude", color: V.claudeGreen });
  lines.push({ type: "blank", text: "" });

  for (const part of parts) {
    const trimmed = part.trim();
    if (!trimmed) continue;

    // 检测各种指令模式
    if (/读|read|查看|cat |open /i.test(trimmed)) {
      lines.push({ type: "tool", text: `● Read(${extractTarget(trimmed)})`, color: V.claudeBlue });
      lines.push({ type: "output", text: `  ✓ 读取完成 (ctrl+o to expand)` });
    } else if (/写|write|创建|create|新建/i.test(trimmed)) {
      lines.push({ type: "tool", text: `● Write(${extractTarget(trimmed)})`, color: V.claudeYellow });
      lines.push({ type: "output", text: `  ✓ 已写入文件` });
    } else if (/搜索|search|find|grep|查找/i.test(trimmed)) {
      lines.push({ type: "tool", text: `● Grep(pattern, ${extractTarget(trimmed)})`, color: V.claudePurple });
      lines.push({ type: "output", text: `  Found 3 matches` });
    } else if (/运行|run|执行|npm|node|python|bash|git/i.test(trimmed)) {
      lines.push({ type: "tool", text: `● Bash(${trimmed.slice(0, 50)})`, color: V.claudeRed });
      lines.push({ type: "status", text: `  ⠋ Running...`, color: V.claudeYellow });
      lines.push({ type: "output", text: `  ✓ Command completed successfully` });
    } else if (/编辑|edit|修改|改|更新|update/i.test(trimmed)) {
      lines.push({ type: "tool", text: `● Edit(${extractTarget(trimmed)})`, color: V.claudeBlue });
      lines.push({ type: "output", text: `  ✓ 已更新` });
    } else {
      lines.push({ type: "output", text: `● ${trimmed}`, color: V.text });
    }
    lines.push({ type: "blank", text: "" });
  }

  // 结尾
  lines.push({ type: "status", text: "⠋ Thinking...", color: V.claudeYellow });

  return lines;
}

function extractTarget(text: string): string {
  const fileMatch = text.match(/[\w./\-]+\.\w{1,6}/);
  if (fileMatch) return fileMatch[0];
  const pathMatch = text.match(/[\w./\-]{3,}/);
  if (pathMatch) return pathMatch[0];
  return "...";
}

/* ═══════════════ 生成伪文件树 ═══════════════ */

interface TreeNode {
  name: string;
  type: "folder" | "file";
  indent: number;
  icon: string;
  color: string;
}

function generateFileTree(): TreeNode[] {
  return [
    { name: ".claude", type: "folder", indent: 0, icon: "📁", color: V.textDim },
    { name: "settings.local.json", type: "file", indent: 1, icon: "{ }", color: V.claudeYellow },
    { name: "src", type: "folder", indent: 0, icon: "📁", color: V.text },
    { name: "index.ts", type: "file", indent: 1, icon: "TS", color: V.keyword },
    { name: "utils.ts", type: "file", indent: 1, icon: "TS", color: V.keyword },
    { name: "components", type: "folder", indent: 1, icon: "📁", color: V.text },
    { name: "App.tsx", type: "file", indent: 2, icon: "⚛", color: V.claudeBlue },
    { name: "tests", type: "folder", indent: 0, icon: "📁", color: V.text },
    { name: "package.json", type: "file", indent: 0, icon: "{ }", color: V.claudeGreen },
    { name: "CLAUDE.md", type: "file", indent: 0, icon: "📄", color: V.claudeRed },
    { name: "README.md", type: "file", indent: 0, icon: "📄", color: V.text },
  ];
}

/* ═══════════════ 子组件: 活动栏 ═══════════════ */

function ActivityBar() {
  const icons = ["📁", "🔍", "🔀", "🐛", "🧩", "⚙️"];
  return (
    <div style={{
      width: 48, background: V.activityBar,
      display: "flex", flexDirection: "column",
      alignItems: "center", paddingTop: 8,
      borderRight: `1px solid ${V.panelBorder}`,
    }}>
      {icons.map((icon, i) => (
        <div key={i} style={{
          width: 40, height: 40,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 18,
          opacity: i === 0 ? 1 : 0.5,
          borderLeft: i === 0 ? `2px solid ${V.textBright}` : "2px solid transparent",
        }}>
          {icon}
        </div>
      ))}
    </div>
  );
}

/* ═══════════════ 子组件: 侧栏文件树 ═══════════════ */

function SideBar({ frame, fps }: { frame: number; fps: number }) {
  const tree = generateFileTree();
  return (
    <div style={{
      width: 220, background: V.sideBar,
      borderRight: `1px solid ${V.panelBorder}`,
      fontSize: 13, fontFamily: V.ui,
      overflow: "hidden",
    }}>
      {/* 标题 */}
      <div style={{
        padding: "8px 16px",
        color: V.textDim, fontSize: 11,
        textTransform: "uppercase",
        letterSpacing: "0.5px",
        fontWeight: 600,
      }}>
        Explorer
      </div>
      <div style={{
        padding: "4px 16px 8px",
        color: V.text, fontSize: 11,
        fontWeight: 600,
        textTransform: "uppercase",
      }}>
        ▼ PROJECT
      </div>

      {/* 文件列表 */}
      {tree.map((node, i) => (
        <div key={i} style={{
          padding: "2px 16px",
          paddingLeft: 16 + node.indent * 16,
          color: node.color,
          display: "flex", alignItems: "center", gap: 6,
          height: 22,
          background: node.name === "CLAUDE.md" ? "rgba(255,255,255,0.05)" : "transparent",
          ...fadeIn(frame, fps, 3 + i * 2),
        }}>
          <span style={{ fontSize: 10, width: 18, textAlign: "center" }}>
            {node.type === "folder" ? "▶" : node.icon}
          </span>
          <span style={{ fontSize: 13 }}>{node.name}</span>
        </div>
      ))}
    </div>
  );
}

/* ═══════════════ 子组件: 标签栏 ═══════════════ */

function TabBar() {
  return (
    <div style={{
      height: 35, background: V.tab,
      display: "flex", alignItems: "stretch",
      borderBottom: `1px solid ${V.panelBorder}`,
    }}>
      <div style={{
        display: "flex", alignItems: "center",
        padding: "0 16px", gap: 8,
        background: V.tabActive,
        borderTop: `2px solid ${V.statusBar}`,
        borderRight: `1px solid ${V.panelBorder}`,
        fontSize: 13, fontFamily: V.ui,
        color: V.text,
      }}>
        <span style={{ color: V.claudeRed, fontSize: 16 }}>✻</span>
        <span>Claude Code</span>
        <span style={{ color: V.textDim, fontSize: 12 }}>×</span>
      </div>
    </div>
  );
}

/* ═══════════════ 子组件: 终端面板 ═══════════════ */

function TerminalPanel({ lines, frame, fps }: {
  lines: TermLine[]; frame: number; fps: number;
}) {
  // 逐行出现
  const visibleCount = Math.min(lines.length, Math.floor((frame - 10) * 0.4));

  return (
    <div style={{
      flex: 1, background: V.terminal,
      borderTop: `1px solid ${V.panelBorder}`,
      display: "flex", flexDirection: "column",
      overflow: "hidden",
    }}>
      {/* 面板标签 */}
      <div style={{
        height: 30, display: "flex", alignItems: "center",
        padding: "0 12px", gap: 16,
        borderBottom: `1px solid ${V.panelBorder}`,
        fontSize: 12, fontFamily: V.ui,
      }}>
        {["PROBLEMS", "OUTPUT", "TERMINAL", "PORTS"].map((tab, i) => (
          <span key={i} style={{
            color: i === 2 ? V.textBright : V.textDim,
            borderBottom: i === 2 ? `1px solid ${V.textBright}` : "none",
            paddingBottom: 6,
          }}>
            {tab}
          </span>
        ))}
        <span style={{
          marginLeft: "auto", color: V.textDim, fontSize: 11,
        }}>
          ✻ claude
        </span>
      </div>

      {/* 终端内容 */}
      <div style={{
        flex: 1, padding: "8px 16px",
        fontFamily: V.mono, fontSize: 13,
        lineHeight: 1.6, overflow: "hidden",
      }}>
        {lines.slice(0, visibleCount).map((line, i) => {
          if (line.type === "blank") return <div key={i} style={{ height: 6 }} />;

          return (
            <div key={i} style={{
              color: line.color || V.text,
              fontWeight: line.type === "prompt" ? 700 : 400,
              ...fadeIn(frame, fps, 10 + i * 3),
            }}>
              {line.type === "prompt" && (
                <span style={{ color: V.claudeGreen }}>❯ </span>
              )}
              {line.text}
              {/* 光标 */}
              {i === visibleCount - 1 && line.type === "status" && (
                <span style={{
                  display: "inline-block",
                  width: 7, height: 15,
                  background: V.text,
                  marginLeft: 2,
                  opacity: frame % 30 < 15 ? 1 : 0,
                  verticalAlign: "text-bottom",
                }} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ═══════════════ 子组件: 状态栏 ═══════════════ */

function StatusBar() {
  return (
    <div style={{
      height: 22, background: V.statusBar,
      display: "flex", alignItems: "center",
      padding: "0 12px",
      fontFamily: V.ui, fontSize: 12,
      color: V.textBright,
      gap: 16,
    }}>
      <span style={{
        background: V.statusBarItem,
        padding: "0 8px",
        borderRadius: 2,
        fontSize: 11,
      }}>
        ⟐ main
      </span>
      <span>✓ 0  ⚠ 0</span>
      <span style={{ marginLeft: "auto" }}>Ln 1, Col 1</span>
      <span>Spaces: 2</span>
      <span>UTF-8</span>
      <span>LF</span>
      <span style={{ color: V.claudeYellow }}>{ } JSON</span>
    </div>
  );
}

/* ═══════════════ 主组件 ═══════════════ */

const TerminalVSCode: React.FC<StyleComponentProps<"terminal">> = ({ data, fps }) => {
  const frame = useCurrentFrame();
  const { fps: vFps } = useVideoConfig();
  const f = fps || vFps;

  const termLines = useMemo(
    () => data.session?.length ? parseSession(data.session) : parseInstruction(data.instruction || ""),
    [data.session, data.instruction],
  );

  return (
    <AbsoluteFill style={{
      backgroundColor: V.editor,
      fontFamily: V.ui,
    }}>
      {/* 标题栏 */}
      <div style={{
        height: 30, background: V.titleBar,
        display: "flex", alignItems: "center",
        padding: "0 12px",
        borderBottom: `1px solid ${V.panelBorder}`,
      }}>
        {/* 红绿黄按钮 */}
        <div style={{ display: "flex", gap: 8 }}>
          {["#ff5f57", "#febc2e", "#28c840"].map((c, i) => (
            <div key={i} style={{
              width: 12, height: 12, borderRadius: "50%",
              background: c,
            }} />
          ))}
        </div>
        <div style={{
          flex: 1, textAlign: "center",
          fontSize: 12, color: V.textDim,
        }}>
          Claude Code — Project
        </div>
      </div>

      {/* 主体 */}
      <div style={{
        flex: 1, display: "flex",
        height: "calc(100% - 52px)",
      }}>
        {/* 活动栏 */}
        <ActivityBar />

        {/* 侧栏 */}
        <SideBar frame={frame} fps={f} />

        {/* 编辑器 + 终端 */}
        <div style={{
          flex: 1, display: "flex", flexDirection: "column",
        }}>
          <TabBar />

          {/* 编辑区域 — Claude Code 欢迎界面 */}
          <div style={{
            flex: 1, background: V.editor,
            display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center",
            padding: 40,
            ...fadeIn(frame, f, 5),
          }}>
            <div style={{
              fontSize: 16, color: V.claudeRed,
              marginBottom: 8,
            }}>
              ✻
            </div>
            <div style={{
              fontSize: 20, fontWeight: 600,
              color: V.text,
              fontFamily: V.ui,
            }}>
              Claude Code
            </div>
            <div style={{
              fontSize: 12, color: V.textDim,
              marginTop: 4, fontFamily: V.mono,
            }}>
              v2.1 · Opus 4.6 (1M context)
            </div>
          </div>

          {/* 终端面板 */}
          <TerminalPanel lines={termLines} frame={frame} fps={f} />
        </div>
      </div>

      {/* 状态栏 */}
      <StatusBar />
    </AbsoluteFill>
  );
};

/* ═══════════════ 注册 ═══════════════ */

registry.register(
  {
    id: "terminal.vscode",
    schema: "terminal",
    name: "VS Code 编辑器风格",
    description:
      "完整 VS Code Dark+ 主题界面模拟，含侧栏文件树 + Claude Code 终端面板。" +
      "适合展示编码操作、文件编辑、命令执行等开发者工作流场景。" +
      "与 aurora 的纯终端风格形成差异化。",
    isDefault: false,
    tags: ["editor", "vscode", "coding", "developer"],
  },
  TerminalVSCode,
);

export { TerminalVSCode };
