/**
 * slide.anthropic-agent-config — Anthropic 品牌片场景 5
 *
 * 左侧 Agent config 生成面板（显示用户 prompt + 生成的 agent_toolset + curl API 调用示例），
 * 右侧漂浮一个运行中的 terminal（import client / session = client.agents.sessions.create(…)）。
 * 复刻 25-30s 帧。
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

const YAML_KEY_COLOR = "#0550ae";

/**
 * 把"yaml raw 行"渲染成带 key 高亮的 ReactNode。
 * 规则：如果一行首个非空白 token 紧接 ":"，则认为是 yaml key，着色为蓝色。
 */
function renderYamlLine(line: string): React.ReactNode {
  const m = line.match(/^(\s*)([A-Za-z_][A-Za-z0-9_-]*)(\s*:)(.*)$/);
  if (!m) return line;
  const [, indent, key, colon, rest] = m;
  return (
    <>
      {indent}
      <span style={{ color: YAML_KEY_COLOR }}>{key}</span>
      {colon}
      {rest}
    </>
  );
}

const DEFAULT_YAML_LINES = [
  "name: merges-and-acks",
  "model: claude-opus-4-6",
  "tools:",
  "  - type: agent_toolset_2026-04-01",
  "system: |",
  "  You are a senior M&A analyst specializing in",
  "  retail sector transactions. Assess whether a deal",
  "  is worth pursuing based on financial,",
  "  operating data, and market context.",
  " ",
  "  ## Framework",
  " ",
  "  ### 1. Financial Health",
  "  - Revenue trajectory (3-year CAGR, YoY trends)",
  "  - Gross margin and EBITDA margin vs. retail comps",
  "  - Free cash flow conversion",
  "  - Net Debt / EBITDA; interest coverage ratio",
  " ",
  "  ### 2. Retail-Specific Signals",
  "  - Same-store sales growth (SSS)",
  "  - Inventory turnover and days-on-hand",
  "  - Revenue per square foot",
  " ",
  "  ### 3. Valuation",
  "  - EV/EBITDA, EV/Revenue, P/E vs. comps",
  "  - LTM vs. NTM multiples",
  "  - Implied IRR under base / downside",
];

const DEFAULT_USER_PROMPT =
  "Build an agent that evaluates acquisition targets. It should research companies, pull financials, run competitive benchmarks, and draft an investment memo.";

const DEFAULT_API_CALL = [
  'curl -X POST https://api.anthropic.com/v1/agents \\',
  '  -H "x-api-key: $ANTHROPIC_API_KEY" \\',
  '  -H "anthropic-version: 2023-06-01" \\',
  '  -H "anthropic-beta: managed-agents-2026-04-01" \\',
  '  -H "content-type: application/json" \\',
  "  -d '{",
  '    "name": "deal-analyst",',
  '    "model": "claude-opus-4-6",',
];

const DEFAULT_TERMINAL_LINES: { kind: "code" | "blank" | "comment" | "status"; text: string }[] = [
  { kind: "code", text: "import" },
  { kind: "code", text: "client" },
  { kind: "code", text: "session = client.agents.sessions.create(" },
  { kind: "blank", text: "" },
  { kind: "comment", text: "// 2. Network outage — `web_search` tool" },
  { kind: "comment", text: "// can't reach `api.search.brave.com`." },
  { kind: "blank", text: "" },
  { kind: "status", text: "✻ Cogitating (26s · ↑ 570 tokens)" },
  { kind: "status", text: ">> accept edits on (shift+tab to cycle)" },
];

/**
 * scene_data shape (可选)：
 * {
 *   breadcrumb?: string,      // 顶部面包屑路径 (e.g. "Agents / My Agent")
 *   agentName?: string,       // 右侧 agent_id 徽章文字
 *   nextStep?: string,        // "Next: Create environment"
 *   userPrompt?: string,      // 左侧圆角框内的用户 prompt
 *   apiCall?: string[],       // 下方 curl API 调用示例每一行
 *   yamlLines?: string[],     // 右侧 yaml 源码每一行（key 自动蓝色高亮）
 *   terminalTitle?: string,
 *   terminalLines?: { kind: "code"|"comment"|"status"|"blank", text: string }[],
 * }
 */
const AnthropicAgentConfig: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const sceneData = (data.scene_data || {}) as {
    breadcrumb?: string;
    agentName?: string;
    nextStep?: string;
    userPrompt?: string;
    apiCall?: string[];
    yamlLines?: string[];
    terminalTitle?: string;
    terminalLines?: { kind: "code" | "comment" | "status" | "blank"; text: string }[];
  };
  const breadcrumb = sceneData.breadcrumb || "Agents  /  Merges & Acks";
  const agentName = sceneData.agentName || "agent_01JR4kW9";
  const nextStep = sceneData.nextStep || "Next: Create environment";
  const userPrompt = sceneData.userPrompt || DEFAULT_USER_PROMPT;
  const apiCall = sceneData.apiCall || DEFAULT_API_CALL;
  const yamlLines = sceneData.yamlLines || DEFAULT_YAML_LINES;
  const terminalTitle = sceneData.terminalTitle || "proposal-system — claude — 80×34";
  const terminalLines = sceneData.terminalLines || DEFAULT_TERMINAL_LINES;

  const enter = spring({
    frame,
    fps,
    config: { damping: 20, stiffness: 85 },
    durationInFrames: 30,
  });
  const termEnter = spring({
    frame: Math.max(0, frame - 18),
    fps,
    config: { damping: 18, stiffness: 80 },
  });

  return (
    <AbsoluteFill>
      <WavyPaperBg />

      {/* 左：Config 面板窗口 */}
      <div
        style={{
          position: "absolute",
          top: 90,
          left: 80,
          opacity: interpolate(enter, [0, 1], [0, 1]),
          transform: `translateY(${interpolate(enter, [0, 1], [30, 0])}px)`,
        }}
      >
        <MacosWindow
          width={960}
          height={900}
          showHeader={true}
          bodyStyle={{ backgroundColor: "#ffffff", padding: 0 }}
        >
          {/* 顶部路径面包屑 + 步骤指示器 */}
          <div
            style={{
              padding: "18px 26px",
              borderBottom: "1px solid #eee",
              fontFamily: "'SF Pro Text', -apple-system, sans-serif",
            }}
          >
            <div
              style={{
                fontSize: 13,
                color: "#888",
                marginBottom: 12,
              }}
            >
              ⟵  {breadcrumb}
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 24,
                fontSize: 14,
                color: "#777",
              }}
            >
              {[
                { n: 1, text: "Create agent", active: true },
                { n: 2, text: "Configure environment" },
                { n: 3, text: "Start session" },
                { n: 4, text: "Integrate" },
              ].map((step, i) => (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    color: step.active ? "#1a1a1a" : "#999",
                    fontWeight: step.active ? 600 : 400,
                  }}
                >
                  <div
                    style={{
                      width: 18,
                      height: 18,
                      borderRadius: "50%",
                      border: step.active
                        ? "2px solid #1a1a1a"
                        : "1px solid #bbb",
                      backgroundColor: step.active ? "#1a1a1a" : "transparent",
                      color: step.active ? "#fff" : "#999",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 10,
                      fontWeight: 700,
                    }}
                  >
                    {step.active ? "✓" : step.n}
                  </div>
                  {step.text}
                </div>
              ))}
              <div style={{ marginLeft: "auto", display: "flex", gap: 10 }}>
                <div
                  style={{
                    padding: "7px 14px",
                    backgroundColor: "#f5f3ef",
                    border: "1px solid #e0ddd5",
                    borderRadius: 6,
                    fontSize: 13,
                  }}
                >
                  Publish
                </div>
                <div
                  style={{
                    padding: "7px 14px",
                    backgroundColor: "#1a1a1a",
                    color: "#fff",
                    borderRadius: 6,
                    fontSize: 13,
                  }}
                >
                  ▶
                </div>
              </div>
            </div>
          </div>

          {/* 两栏：左用户 prompt + 生成 API 调用 / 右 YAML */}
          <div
            style={{
              display: "flex",
              padding: 26,
              gap: 24,
              height: "calc(100% - 86px)",
            }}
          >
            {/* 左：prompt + 生成结果 */}
            <div
              style={{
                flex: 1,
                fontFamily: "'SF Pro Text', -apple-system, sans-serif",
                fontSize: 13,
                color: "#333",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  padding: "14px 18px",
                  border: "1px solid #e5e5e5",
                  borderRadius: 10,
                  marginBottom: 16,
                  lineHeight: 1.55,
                  backgroundColor: "#fff",
                }}
              >
                {userPrompt}
              </div>
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  fontSize: 12,
                  color: "#3fb950",
                  marginBottom: 14,
                }}
              >
                ✓ Generated agent config
              </div>
              <div style={{ fontSize: 12, color: "#666", marginBottom: 10 }}>
                Here's your agent. This is the API call that created it:
              </div>
              <div
                style={{
                  padding: 14,
                  backgroundColor: "#f7f5f0",
                  borderRadius: 8,
                  fontFamily: monoFont,
                  fontSize: 11,
                  color: "#333",
                  lineHeight: 1.55,
                  border: "1px solid #ebe7dc",
                }}
              >
                <div style={{ color: "#666", marginBottom: 4 }}>
                  POST /v1/agents
                </div>
                {apiCall.map((line, i) => (
                  <div key={i} style={{ whiteSpace: "pre" }}>
                    {line}
                  </div>
                ))}
              </div>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  marginTop: 14,
                  fontSize: 12,
                  color: "#666",
                }}
              >
                <span>agent_id:</span>
                <span
                  style={{
                    fontFamily: monoFont,
                    padding: "2px 8px",
                    backgroundColor: "#f0efe9",
                    borderRadius: 4,
                  }}
                >
                  {agentName}
                </span>
              </div>
              <div
                style={{
                  marginTop: 18,
                  fontSize: 13,
                  color: "#333",
                  fontWeight: 500,
                }}
              >
                {nextStep}
              </div>
              <div
                style={{
                  marginTop: 10,
                  width: 30,
                  height: 30,
                  backgroundColor: "#d97757",
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#fff",
                  fontSize: 18,
                  fontWeight: 700,
                }}
              >
                ✻
              </div>
              <div
                style={{
                  marginTop: 26,
                  padding: "10px 14px",
                  border: "1px solid #e5e5e5",
                  borderRadius: 24,
                  fontSize: 13,
                  color: "#aaa",
                }}
              >
                + Describe what you'd like to achieve.   🎤
              </div>
            </div>

            {/* 右：Config YAML */}
            <div
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  display: "flex",
                  gap: 18,
                  marginBottom: 10,
                  fontSize: 13,
                  fontFamily: "'SF Pro Text', -apple-system, sans-serif",
                  color: "#666",
                }}
              >
                <div>Config</div>
                <div style={{ color: "#d97757", fontWeight: 600 }}>
                  Source code
                </div>
                <div>Preview</div>
                <div style={{ marginLeft: "auto", fontSize: 11 }}>yaml ▾</div>
              </div>
              <div
                style={{
                  flex: 1,
                  padding: 14,
                  backgroundColor: "#fafaf6",
                  border: "1px solid #ebe7dc",
                  borderRadius: 8,
                  fontFamily: monoFont,
                  fontSize: 11,
                  color: "#333",
                  lineHeight: 1.55,
                  overflow: "hidden",
                }}
              >
                {yamlLines.map((line, i) => (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      whiteSpace: "pre",
                    }}
                  >
                    <span
                      style={{
                        color: "#b8b3a8",
                        width: 22,
                        textAlign: "right",
                        paddingRight: 10,
                        flexShrink: 0,
                        userSelect: "none",
                      }}
                    >
                      {i + 1}
                    </span>
                    <span style={{ color: "#333" }}>{renderYamlLine(line)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </MacosWindow>
      </div>

      {/* 右边漂浮终端 */}
      <div
        style={{
          position: "absolute",
          top: 230,
          right: 30,
          opacity: interpolate(termEnter, [0, 1], [0, 1]),
          transform: `translate(${interpolate(termEnter, [0, 1], [80, 0])}px, 0)`,
          zIndex: 5,
        }}
      >
        <MacosWindow
          width={780}
          height={560}
          title={terminalTitle}
          variant="dark"
          bodyStyle={{
            padding: "28px 34px",
            fontFamily: monoFont,
            fontSize: 20,
            color: "#e4e4e4",
            lineHeight: 1.55,
          }}
        >
          {terminalLines.map((ln, i) => {
            if (ln.kind === "blank") return <div key={i} style={{ height: 16 }} />;
            const color =
              ln.kind === "comment"
                ? "#888"
                : ln.kind === "status"
                  ? ln.text.startsWith("✻") || ln.text.startsWith(">>")
                    ? ln.text.startsWith("✻")
                      ? "#d97757"
                      : "#a885d9"
                    : "#e4e4e4"
                  : "#e4e4e4";
            return (
              <div key={i} style={{ color, whiteSpace: "pre" }}>
                {ln.text}
              </div>
            );
          })}
        </MacosWindow>
      </div>
    </AbsoluteFill>
  );
};

registry.register(
  {
    id: "slide.anthropic-agent-config",
    schema: "slide",
    name: "Anthropic Agent Config",
    description:
      "Anthropic 品牌片场景 5：Claude Agents 配置窗口，左侧显示用户 prompt + 生成的 curl API 调用 + agent_id，右侧是 YAML config 源码；右上漂一个独立终端窗口显示 client.agents.sessions.create(...)。复刻 25-30s 帧。",
    isDefault: false,
    tags: ["anthropic", "agent config", "YAML", "API"],
  },
  AnthropicAgentConfig,
);
export { AnthropicAgentConfig };
