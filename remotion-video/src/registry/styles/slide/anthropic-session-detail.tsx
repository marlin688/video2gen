/**
 * slide.anthropic-session-detail — Anthropic 品牌片场景 8
 *
 * 延续 session dashboard，滚动显示更多日志 + 右侧弹出 agent 详情卡（merges-and-acks）
 * + 底部 Tip 提示。复刻 44-50s 帧。
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
import { MacosWindow } from "../../components/MacosWindow";

const monoFont = "'JetBrains Mono', 'SF Mono', monospace";

type LogRow = {
  k: string;
  bg: string;
  c: string;
  label: string;
  meta: string;
  active?: boolean;
};

const DEFAULT_LOG_ROWS: LogRow[] = [
  { k: "Agent", bg: "#1a1a1a", c: "#fff", label: "Agent: Starting full acquisition analysis of BuyCo", meta: "1,878in / 100out · 3s · 0:02" },
  { k: "Glob", bg: "#f0efea", c: "#555", label: "Scanning data room file structure", meta: "4s · 0:05" },
  { k: "Glob", bg: "#f0efea", c: "#555", label: "8 files found in /workspace/data-room/", meta: "4s · 0:05", active: true },
  { k: "Read", bg: "#f0efea", c: "#555", label: "Opening income statement FY2023-2025", meta: "3s · 0:09" },
  { k: "Read", bg: "#f0efea", c: "#555", label: "Income statement loaded — Rev $421M, EBITDA $59M", meta: "3s · 0:09" },
  { k: "Read", bg: "#f0efea", c: "#555", label: "Opening balance sheet FY2025", meta: "3s · 0:09" },
  { k: "Read", bg: "#f0efea", c: "#555", label: "Balance sheet loaded — Net Debt $124M", meta: "3s · 0:09" },
  { k: "Web_search", bg: "#f0efea", c: "#555", label: "Retail sector comp multiples", meta: "18s · 0:12" },
  { k: "Web_search", bg: "#f0efea", c: "#555", label: "Comp median 8.8x; 3 precedent transactions", meta: "18s · 0:12" },
  { k: "Web_fetch", bg: "#f0efea", c: "#555", label: "BuyCo expansion article", meta: "18s · 0:18" },
  { k: "Web_fetch", bg: "#f0efea", c: "#555", label: "187 stores, SSS +3.2%, $412 rev/sqft", meta: "18s · 0:18" },
];

const DEFAULT_SYSTEM_PROMPT = [
  "You are a senior M&A analyst specializing in retail",
  "sector transactions.  Assess whether a deal is worth",
  "pursuing based on financial statements, operating data,",
  "and market context.",
  " ",
  "## Framework",
  " ",
  "### 1. Financial Health",
  "- Revenue trajectory (3-year CAGR, YoY trends)",
  "- Gross margin and EBITDA margin vs. retail comps",
  "- Free cash flow conversion",
  "- Net Debt / EBITDA; interest coverage ratio",
  " ",
  "### 2. Retail-Specific Signals",
  "- Same-store sales growth (SSS)",
];

/**
 * scene_data shape (可选)：
 * {
 *   sessionTitle?: string,
 *   sessionId?: string,
 *   badges?: string[],
 *   badgeHighlightIndex?: number,   // 哪个 badge 有珊瑚红外框表示 hover
 *   agentLog?: LogRow[],
 *   popover?: { name?: string, model?: string, version?: string, updated?: string, agentId?: string },
 *   agentName?: string,
 *   systemPrompt?: string[],
 *   mcpTools?: { name: string, desc: string, count?: number }[],
 * }
 */
const AnthropicSessionDetail: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const sceneData = (data.scene_data || {}) as {
    sessionTitle?: string;
    sessionId?: string;
    badges?: string[];
    badgeHighlightIndex?: number;
    agentLog?: LogRow[];
    popover?: { name?: string; model?: string; version?: string; updated?: string; agentId?: string };
    agentName?: string;
    systemPrompt?: string[];
    mcpTools?: { name: string; desc: string; count?: number }[];
  };
  const sessionTitle = sceneData.sessionTitle || data.title || "Build investment thesis for BuyCo";
  const sessionId = sceneData.sessionId || "…heC6T3Y";
  const badges = sceneData.badges && sceneData.badges.length > 0 ? sceneData.badges : [
    "⌘ merges-and-acks",
    "⌖ env",
    "📄 1 file",
    "📄 production-vault",
    "⏱ 22 hours ago",
    "⏱ 5m 34s (2m 44s active)",
    "↳ 71.0k / 5.7k",
  ];
  const badgeHighlightIndex = sceneData.badgeHighlightIndex ?? 0;
  const LOG_ROWS = sceneData.agentLog && sceneData.agentLog.length > 0 ? sceneData.agentLog : DEFAULT_LOG_ROWS;
  const popoverData = sceneData.popover || {
    name: "merges-and-acks",
    model: "claude-opus-4-6",
    version: "17748465448... 05178271",
    updated: "22 hours ago",
    agentId: "agent_011CZ…_Gvfh7gfN",
  };
  const agentName = sceneData.agentName || "merges-and-acks";
  const systemPrompt = sceneData.systemPrompt && sceneData.systemPrompt.length > 0 ? sceneData.systemPrompt : DEFAULT_SYSTEM_PROMPT;
  const mcpTools = sceneData.mcpTools && sceneData.mcpTools.length > 0 ? sceneData.mcpTools : [
    { name: "agent_toolset", desc: "Read and write", count: 9 },
  ];

  // 关键：这一幕是"延续 scene 7 + popover 浮现"，主窗口完全静态，
  // 不做任何 scale 动画，避免和前一幕 session-timeline 的相同布局
  // 在 fade 交叉溶解时发生亚像素抖动（text shimmer）。
  // 只让 popover 和 hover 鼠标淡入。
  const popover = spring({
    frame: Math.max(0, frame - 20),
    fps,
    config: { damping: 15, stiffness: 120 },
  });
  const cursorIn = spring({
    frame: Math.max(0, frame - 10),
    fps,
    config: { damping: 16, stiffness: 110 },
  });

  return (
    <AbsoluteFill>
      <WavyPaperBg />

      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <MacosWindow
          width={1560}
          height={900}
          showHeader={true}
          bodyStyle={{ backgroundColor: "#ffffff", padding: 0 }}
        >
          {/* 顶栏（带鼠标悬停 merges-and-acks 的效果） */}
          <div
            style={{
              padding: "24px 36px 12px 36px",
              borderBottom: "1px solid #f0efea",
              fontFamily: "'SF Pro Text', -apple-system, sans-serif",
              position: "relative",
            }}
          >
            <div style={{ fontSize: 13, color: "#888", marginBottom: 8 }}>
              ⟵  Sessions  /  Session {sessionId}  ▾ ▿
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 14,
                marginBottom: 14,
              }}
            >
              <div
                style={{
                  fontSize: 30,
                  fontWeight: 700,
                  color: "#1a1a1a",
                  fontFamily:
                    "'Fraunces', 'Playfair Display', Georgia, serif",
                  letterSpacing: "-0.01em",
                }}
              >
                {sessionTitle}
              </div>
              <div
                style={{
                  padding: "3px 10px",
                  backgroundColor: "#dcfce7",
                  color: "#166534",
                  borderRadius: 12,
                  fontSize: 12,
                  fontWeight: 600,
                }}
              >
                Active
              </div>
            </div>
            {/* 元信息徽标 */}
            <div
              style={{
                display: "flex",
                gap: 10,
                fontSize: 12,
                color: "#555",
              }}
            >
              {badges.map((s, i) => (
                <div
                  key={i}
                  style={{
                    padding: "4px 10px",
                    border:
                      i === badgeHighlightIndex
                        ? "2px solid #d97757"
                        : "1px solid #e5e5e5",
                    borderRadius: 14,
                    backgroundColor: "#fafaf6",
                  }}
                >
                  {s}
                </div>
              ))}
            </div>

            {/* Popover card: merges-and-acks */}
            <div
              style={{
                position: "absolute",
                top: 88,
                left: 36,
                width: 280,
                backgroundColor: "#ffffff",
                border: "1px solid #e5e5e5",
                borderRadius: 10,
                padding: "16px 18px",
                boxShadow: "0 24px 50px rgba(30,24,18,0.15)",
                fontSize: 13,
                color: "#333",
                opacity: interpolate(popover, [0, 1], [0, 1]),
                transform: `translateY(${interpolate(popover, [0, 1], [10, 0])}px)`,
                zIndex: 10,
              }}
            >
              <div style={{ fontWeight: 700, marginBottom: 10 }}>
                {popoverData.name}
                <span
                  style={{
                    fontWeight: 600,
                    color: "#166534",
                    backgroundColor: "#dcfce7",
                    padding: "1px 6px",
                    borderRadius: 8,
                    fontSize: 11,
                    marginLeft: 8,
                  }}
                >
                  Active
                </span>
              </div>
              <div style={{ fontSize: 11, color: "#666", lineHeight: 1.8 }}>
                <div>Model {popoverData.model}</div>
                <div>Version {popoverData.version}</div>
                <div>Status Active</div>
                <div>Updated {popoverData.updated}</div>
              </div>
              <div
                style={{
                  marginTop: 10,
                  fontSize: 11,
                  color: "#888",
                }}
              >
                {popoverData.agentId}   View details →
              </div>
            </div>
          </div>

          {/* 主体：左栏日志 + 右栏 System prompt 详情 */}
          <div
            style={{
              display: "flex",
              padding: "20px 36px 24px 36px",
              gap: 28,
              height: "calc(100% - 200px)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                flex: "0 0 56%",
                fontFamily: "'SF Pro Text', -apple-system, sans-serif",
                fontSize: 13,
                color: "#333",
              }}
            >
              {/* 模拟一个正在 hover 的白色圆点鼠标 */}
              <div
                style={{
                  position: "absolute",
                  top: 110,
                  left: 80,
                  width: 22,
                  height: 22,
                  borderRadius: "50%",
                  backgroundColor: "rgba(0,0,0,0.85)",
                  border: "2px solid rgba(255,255,255,0.9)",
                  zIndex: 5,
                  opacity: interpolate(cursorIn, [0, 1], [0, 1]),
                  transform: `scale(${interpolate(cursorIn, [0, 1], [0.3, 1])})`,
                }}
              />

              {LOG_ROWS.map((row, i) => (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    padding: "7px 0",
                    borderBottom: "1px solid #f5f3ef",
                    backgroundColor: row.active ? "#fff8f2" : "transparent",
                  }}
                >
                  <div
                    style={{
                      backgroundColor: row.bg,
                      color: row.c,
                      padding: "2px 8px",
                      borderRadius: 4,
                      fontSize: 11,
                      fontWeight: 600,
                      width: 86,
                      textAlign: "center",
                    }}
                  >
                    {row.k}
                  </div>
                  <div style={{ flex: 1, color: "#222" }}>{row.label}</div>
                  <div style={{ color: "#888", fontSize: 11 }}>{row.meta}</div>
                </div>
              ))}
            </div>

            {/* 右栏 agent 详情 */}
            <div
              style={{
                flex: 1,
                fontFamily: "'SF Pro Text', -apple-system, sans-serif",
                fontSize: 13,
                color: "#333",
                borderLeft: "1px solid #f0efea",
                paddingLeft: 24,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  marginBottom: 14,
                }}
              >
                <div
                  style={{
                    fontSize: 18,
                    fontWeight: 700,
                    color: "#1a1a1a",
                    fontFamily:
                      "'Fraunces', 'Playfair Display', Georgia, serif",
                  }}
                >
                  {agentName}
                </div>
                <div
                  style={{
                    padding: "2px 8px",
                    backgroundColor: "#dcfce7",
                    color: "#166534",
                    borderRadius: 10,
                    fontSize: 11,
                    fontWeight: 600,
                  }}
                >
                  Active
                </div>
                <div style={{ marginLeft: "auto", fontSize: 14, color: "#888" }}>
                  ✕
                </div>
              </div>
              <div
                style={{
                  fontSize: 11,
                  color: "#666",
                  marginBottom: 6,
                }}
              >
                {popoverData.agentId}
              </div>
              <div
                style={{
                  fontSize: 11,
                  color: "#888",
                  marginBottom: 16,
                }}
              >
                v17748465444…
              </div>
              <div
                style={{
                  fontSize: 11,
                  color: "#d97757",
                  marginBottom: 16,
                }}
              >
                View agent details ↗
              </div>

              <div
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: "#333",
                  marginBottom: 8,
                }}
              >
                System prompt
              </div>
              <div
                style={{
                  padding: 14,
                  backgroundColor: "#f7f5f0",
                  border: "1px solid #ebe7dc",
                  borderRadius: 8,
                  fontFamily: monoFont,
                  fontSize: 11,
                  color: "#333",
                  lineHeight: 1.6,
                  marginBottom: 16,
                }}
              >
                {systemPrompt.map((line, i) => (
                  <div key={i}>{line.trim() === "" ? "\u00a0" : line}</div>
                ))}
              </div>

              <div
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: "#333",
                  marginBottom: 8,
                }}
              >
                MCPs and tools  ({mcpTools.reduce((sum, t) => sum + (t.count || 1), 0)})
              </div>
              {mcpTools.map((tool, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "center",
                  padding: "10px 14px",
                  border: "1px solid #e5e5e5",
                  borderRadius: 8,
                  fontSize: 12,
                  color: "#333",
                  backgroundColor: "#fff",
                  marginBottom: 10,
                }}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600 }}>{tool.name}</div>
                  <div style={{ color: "#888", fontSize: 11 }}>
                    {tool.desc}
                  </div>
                </div>
                <div
                  style={{
                    color: "#166534",
                    backgroundColor: "#dcfce7",
                    padding: "2px 8px",
                    borderRadius: 10,
                    fontSize: 11,
                    fontWeight: 600,
                  }}
                >
                  Connected  {tool.count || ""}
                </div>
              </div>
              ))}
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: "#333",
                }}
              >
                Skills
              </div>
            </div>
          </div>
        </MacosWindow>
      </div>
    </AbsoluteFill>
  );
};

registry.register(
  {
    id: "slide.anthropic-session-detail",
    schema: "slide",
    name: "Anthropic Session 详情",
    description:
      "Anthropic 品牌片场景 8：延续 session dashboard，鼠标悬停 merges-and-acks 标签弹出 agent 详情 popover，右侧展开 System prompt + MCPs and tools 面板。复刻 44-50s 帧。",
    isDefault: false,
    tags: ["anthropic", "session", "popover", "详情"],
  },
  AnthropicSessionDetail,
);
export { AnthropicSessionDetail };
