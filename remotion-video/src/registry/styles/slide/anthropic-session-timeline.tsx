/**
 * slide.anthropic-session-timeline — Anthropic 品牌片场景 7
 *
 * Claude Agents session dashboard 主视图：
 * - 顶部：session 名 "Build investment thesis for BuyCo"
 * - 中部：活动时间线（彩色色块序列）
 * - 左栏：Agent 事件列表（Session start / Evaluate / Scanning / Opening / Reading...）
 * - 右栏：Glob 8 files found 数据分析任务面板
 * 复刻 36-44s 帧。
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

type LogKind = "agent" | "user" | "read" | "glob" | "web_search" | "web_fetch";

interface LogRow {
  kind: LogKind;
  label: string;
  toks?: string;
  time?: string;
}

const DEFAULT_AGENT_LOG: LogRow[] = [
  { kind: "agent", label: "Session start", toks: "", time: "0:00" },
  { kind: "user", label: "Evaluate an acquisition of BuyCo", toks: "780 toks", time: "0:01" },
  { kind: "agent", label: "Agent: Starting full acquisition analysis of BuyCo", toks: "1,878in / 100out", time: "0:02" },
  { kind: "glob", label: "Scanning data room file structure", toks: "", time: "0:05" },
  { kind: "glob", label: "8 files found in /workspace/data-room/", toks: "", time: "0:05" },
  { kind: "read", label: "Opening income statement FY2023-2025", toks: "", time: "0:09" },
  { kind: "read", label: "Income statement loaded — Rev $421M, EBITDA $59M", toks: "", time: "0:09" },
  { kind: "read", label: "Opening balance sheet FY2025", toks: "", time: "0:09" },
  { kind: "read", label: "Balance sheet loaded — Net Debt $124M", toks: "", time: "0:09" },
  { kind: "web_search", label: "Retail sector comp multiples", toks: "", time: "0:12" },
  { kind: "web_search", label: "Comp median 8.8x; 3 precedent transactions", toks: "", time: "0:12" },
  { kind: "web_fetch", label: "BuyCo expansion article", toks: "", time: "0:18" },
  { kind: "web_fetch", label: "187 stores, SSS +3.2%, $412 rev/sqft", toks: "", time: "0:18" },
];

const DEFAULT_SESSION_TITLE = "Build investment thesis for BuyCo";
const DEFAULT_BADGES = [
  "⌘ merges-and-acks",
  "⌖ env",
  "📄 1 file",
  "📄 production-vault",
  "⏱ 22 hours ago",
  "⏱ 5m 34s (2m 44s active)",
  "↳ 71.0k / 5.7k",
];
const DEFAULT_DATA_PANEL_TITLE = "Data Analysis Task";
const DEFAULT_DATA_PANEL_FILES = [
  "income_statement_FY2023-2025.csv,",
  "balance_sheet_FY2025.csv, cash_flow_FY2025.csv,",
  "store_performance_by_region.csv,",
  "inventory_metrics_Q4_2025.csv, lease_schedule.csv,",
  "management_presentation.pdf, customer_demographics.csv",
];
const DEFAULT_DATA_PANEL_FOOTER = [
  "Scanned /workspace/data-room/… done (142ms)",
  "Matched 8 of 11 entries against *.{csv,pdf,xlsx}",
];

const KIND_META: Record<
  string,
  { label: string; color: string; bg: string }
> = {
  agent: { label: "Agent", color: "#fff", bg: "#1a1a1a" },
  user: { label: "User", color: "#fff", bg: "#ef4444" },
  read: { label: "Read", color: "#555", bg: "#f0efea" },
  glob: { label: "Glob", color: "#555", bg: "#f0efea" },
  web_search: { label: "Web_search", color: "#555", bg: "#f0efea" },
  web_fetch: { label: "Web_fetch", color: "#555", bg: "#f0efea" },
};

// 顶部时间线的色条配色
const TIMELINE = [
  { color: "#d94d7a", w: 22 },
  { color: "#3b82f6", w: 22 },
  { color: "#e0ddd5", w: 22 },
  { color: "#e0ddd5", w: 22 },
  { color: "#e0ddd5", w: 22 },
  { color: "#e0ddd5", w: 22 },
  { color: "#e0ddd5", w: 22 },
  { color: "#e0ddd5", w: 22 },
  { color: "#d94d7a", w: 22 },
  { color: "#e0ddd5", w: 22 },
  { color: "#e0ddd5", w: 22 },
  { color: "#e0ddd5", w: 22 },
  { color: "#e0ddd5", w: 22 },
  { color: "#e0ddd5", w: 22 },
  { color: "#3b82f6", w: 22 },
  { color: "#e0ddd5", w: 22 },
  { color: "#e0ddd5", w: 22 },
  { color: "#e0ddd5", w: 22 },
];

/**
 * scene_data shape (可选)：
 * {
 *   sessionTitle?: string,
 *   sessionId?: string,       // 面包屑里 "Session …heC6T3Y" 的 ID
 *   badges?: string[],        // 元信息徽标
 *   agentLog?: LogRow[],      // 左栏 Agent 日志行
 *   panelTitle?: string,      // 右栏面板标题 "Data Analysis Task"
 *   panelFiles?: string[],    // 右栏文件名灰底框
 *   panelFooter?: string[],   // 右栏底部两行 "Scanned..." / "Matched..."
 * }
 */
const AnthropicSessionTimeline: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const sceneData = (data.scene_data || {}) as {
    sessionTitle?: string;
    sessionId?: string;
    badges?: string[];
    agentLog?: LogRow[];
    panelTitle?: string;
    panelFiles?: string[];
    panelFooter?: string[];
  };
  const sessionTitle = sceneData.sessionTitle || data.title || DEFAULT_SESSION_TITLE;
  const sessionId = sceneData.sessionId || "…heC6T3Y";
  const badges = sceneData.badges && sceneData.badges.length > 0 ? sceneData.badges : DEFAULT_BADGES;
  const AGENT_LOG = sceneData.agentLog && sceneData.agentLog.length > 0 ? sceneData.agentLog : DEFAULT_AGENT_LOG;
  const panelTitle = sceneData.panelTitle || DEFAULT_DATA_PANEL_TITLE;
  const panelFiles = sceneData.panelFiles && sceneData.panelFiles.length > 0 ? sceneData.panelFiles : DEFAULT_DATA_PANEL_FILES;
  const panelFooter = sceneData.panelFooter && sceneData.panelFooter.length > 0 ? sceneData.panelFooter : DEFAULT_DATA_PANEL_FOOTER;

  const enter = spring({
    frame,
    fps,
    config: { damping: 20, stiffness: 85 },
    durationInFrames: 30,
  });

  // 日志项逐条出现
  const rowsVisible = Math.max(
    0,
    Math.min(AGENT_LOG.length, Math.floor((frame - 18) / 4)),
  );

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
          opacity: interpolate(enter, [0, 1], [0, 1]),
          transform: `translateY(${interpolate(enter, [0, 1], [28, 0])}px)`,
        }}
      >
        <MacosWindow
          width={1560}
          height={900}
          showHeader={true}
          bodyStyle={{ backgroundColor: "#ffffff", padding: 0 }}
        >
          {/* 顶部：session 名 + actions */}
          <div
            style={{
              padding: "24px 36px 12px 36px",
              borderBottom: "1px solid #f0efea",
              fontFamily: "'SF Pro Text', -apple-system, sans-serif",
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
              <div
                style={{
                  marginLeft: "auto",
                  display: "flex",
                  gap: 10,
                  fontSize: 13,
                  color: "#555",
                }}
              >
                <div
                  style={{
                    padding: "6px 14px",
                    border: "1px solid #e5e5e5",
                    borderRadius: 6,
                  }}
                >
                  Actions ▾
                </div>
                <div
                  style={{
                    padding: "6px 14px",
                    border: "1px solid #e5e5e5",
                    borderRadius: 6,
                    backgroundColor: "#fff",
                  }}
                >
                  ✻ Ask Claude
                </div>
              </div>
            </div>
            {/* 元信息徽标 */}
            <div
              style={{
                display: "flex",
                gap: 10,
                fontSize: 12,
                color: "#555",
                fontFamily: "'SF Pro Text', -apple-system, sans-serif",
              }}
            >
              {badges.map((s, i) => (
                <div
                  key={i}
                  style={{
                    padding: "4px 10px",
                    border: "1px solid #e5e5e5",
                    borderRadius: 14,
                    backgroundColor: "#fafaf6",
                  }}
                >
                  {s}
                </div>
              ))}
            </div>
          </div>

          {/* 时间线彩色色条 */}
          <div
            style={{
              padding: "20px 36px 10px 36px",
              fontFamily: "'SF Pro Text', -apple-system, sans-serif",
            }}
          >
            <div
              style={{
                display: "flex",
                gap: 14,
                fontSize: 13,
                color: "#888",
                marginBottom: 12,
              }}
            >
              <div style={{ color: "#d97757", fontWeight: 600 }}>
                Transcript
              </div>
              <div>Debug</div>
              <div style={{ marginLeft: 14 }}>All events ▾</div>
              <div style={{ marginLeft: 6 }}>🔍</div>
              <div style={{ marginLeft: "auto", color: "#555" }}>
                Glob  8 files found in /workspace/d… 0:05
              </div>
            </div>
            <div
              style={{ display: "flex", gap: 2, height: 38, marginBottom: 16 }}
            >
              {TIMELINE.map((b, i) => (
                <div
                  key={i}
                  style={{
                    flex: 1,
                    backgroundColor: b.color,
                    borderRadius: 2,
                  }}
                />
              ))}
            </div>
          </div>

          {/* 主体两栏 */}
          <div
            style={{
              display: "flex",
              padding: "0 36px 24px 36px",
              gap: 28,
              height: "calc(100% - 290px)",
              overflow: "hidden",
            }}
          >
            {/* 左栏：Agent 日志 */}
            <div
              style={{
                flex: "0 0 56%",
                fontFamily: "'SF Pro Text', -apple-system, sans-serif",
                fontSize: 13,
                color: "#333",
              }}
            >
              <div
                style={{
                  fontSize: 15,
                  fontWeight: 700,
                  color: "#1a1a1a",
                  marginBottom: 10,
                }}
              >
                Agent
              </div>
              {AGENT_LOG.slice(0, rowsVisible).map((row, i) => {
                const meta = KIND_META[row.kind];
                return (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 12,
                      padding: "6px 0",
                      borderBottom: "1px solid #f5f3ef",
                    }}
                  >
                    <div
                      style={{
                        backgroundColor: meta.bg,
                        color: meta.color,
                        padding: "2px 8px",
                        borderRadius: 4,
                        fontSize: 11,
                        fontWeight: 600,
                        width: 78,
                        textAlign: "center",
                      }}
                    >
                      {meta.label}
                    </div>
                    <div style={{ flex: 1, color: "#222" }}>{row.label}</div>
                    <div style={{ color: "#888", fontSize: 11 }}>
                      {row.toks}
                    </div>
                    <div style={{ color: "#888", fontSize: 11, minWidth: 32 }}>
                      {row.time}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* 右栏：Glob 面板 + Data Analysis Task */}
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
                  fontSize: 12,
                  color: "#666",
                  marginBottom: 10,
                }}
              >
                <div
                  style={{
                    backgroundColor: "#f0efea",
                    padding: "2px 8px",
                    borderRadius: 4,
                    fontWeight: 600,
                  }}
                >
                  Glob
                </div>
                <span>·</span>
                <span>780 toks</span>
                <span>·</span>
                <span>1s</span>
                <span>·</span>
                <span>0:01</span>
                <div style={{ marginLeft: "auto" }}>✕</div>
              </div>
              <div
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  marginBottom: 14,
                  color: "#1a1a1a",
                }}
              >
                Found 8 files:
              </div>
              <div
                style={{
                  fontSize: 22,
                  fontWeight: 600,
                  color: "#1a1a1a",
                  marginBottom: 14,
                  fontFamily:
                    "'Fraunces', 'Playfair Display', Georgia, serif",
                }}
              >
                {panelTitle}
              </div>
              <div
                style={{
                  padding: 16,
                  backgroundColor: "#f7f5f0",
                  border: "1px solid #ebe7dc",
                  borderRadius: 8,
                  fontFamily: monoFont,
                  fontSize: 12,
                  color: "#333",
                  lineHeight: 1.6,
                  marginBottom: 16,
                }}
              >
                {panelFiles.map((f, i) => (
                  <div key={i}>{f}</div>
                ))}
              </div>
              {panelFooter.map((f, i) => (
                <div
                  key={i}
                  style={{
                    fontSize: 12,
                    color: "#555",
                    marginBottom: i < panelFooter.length - 1 ? 6 : 0,
                  }}
                >
                  {f}
                </div>
              ))}
            </div>
          </div>
        </MacosWindow>
      </div>
    </AbsoluteFill>
  );
};

registry.register(
  {
    id: "slide.anthropic-session-timeline",
    schema: "slide",
    name: "Anthropic Session Timeline",
    description:
      "Anthropic 品牌片场景 7：Claude Agents session dashboard 主视图，顶部 session 名 + Active 状态，中部彩色时间线，左栏 Agent 日志列表，右栏 Glob 8 files found 数据分析面板。复刻 36-44s 帧。",
    isDefault: false,
    tags: ["anthropic", "session", "dashboard", "timeline"],
  },
  AnthropicSessionTimeline,
);
export { AnthropicSessionTimeline };
