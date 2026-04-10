/**
 * slide.anthropic-template-picker — Anthropic 品牌片场景 3
 *
 * "New agent" 界面：左侧 "What do you want to build?" 大标题 + 上传按钮，
 * 右侧 "Get started with a template" 网格卡片列表。
 * 复刻 11-18s 帧。
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
import { useTheme } from "../../theme";
import { WavyPaperBg } from "../../components/WavyPaperBg";
import { MacosWindow } from "../../components/MacosWindow";

const DEFAULT_TEMPLATES: { title: string; desc: string }[] = [
  {
    title: "Deep research",
    desc: "Multi-step web research with source synthesis and citation. Use as a standalone step or feed into downstream agents.",
  },
  {
    title: "Structured extractor",
    desc: "Parses unstructured text into a typed JSON schema. Define your schema, drop in documents, get structured data.",
  },
  {
    title: "RAG retrieval",
    desc: "Retrieves relevant chunks from a vector store or document collection. Pair with a drafting step for grounded output.",
  },
  {
    title: "Intent router",
    desc: "Classifies an incoming request and routes to the right sub-agent. Define your routing logic declaratively.",
  },
  {
    title: "Draft generator",
    desc: "Produces a structured first draft — email, doc, summary, report — from a template and a set of variables.",
  },
  {
    title: "Reflection loop",
    desc: "Iteratively critiques and revises its own output until a quality threshold is met or max iterations.",
  },
  {
    title: "Task planner",
    desc: "Breaks a high-level goal down into an ordered list of sub-tasks. Output is a structured plan and assignees.",
  },
  {
    title: "Summarizer",
    desc: "Condenses long documents, transcripts, or thread history. Configurable output length and tone.",
  },
];

const DEFAULT_QUESTION = "What do you\nwant to build?";
const DEFAULT_TAGS = [
  { label: "All", active: true },
  { label: "Research & retrieval" },
  { label: "Evaluate & judge" },
  { label: "Transform & extract" },
  { label: "Plan & route" },
];

/**
 * scene_data shape (可选)：
 * {
 *   question?: string,     // 左侧衬线大字问题（支持 \n）
 *   templates?: { title: string, desc: string }[],
 *   tags?: { label: string, active?: boolean }[],
 *   appName?: string,      // 顶部 "New agent" → 可改成其他
 * }
 * 或用 slide_content.title 作为左侧问题。
 */
const AnthropicTemplatePicker: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const sceneData = (data.scene_data || {}) as {
    question?: string;
    templates?: { title: string; desc: string }[];
    tags?: { label: string; active?: boolean }[];
    appName?: string;
  };
  const question = sceneData.question || data.title || DEFAULT_QUESTION;
  const TEMPLATES =
    sceneData.templates && sceneData.templates.length > 0
      ? sceneData.templates
      : DEFAULT_TEMPLATES;
  const TAGS =
    sceneData.tags && sceneData.tags.length > 0 ? sceneData.tags : DEFAULT_TAGS;
  const appName = sceneData.appName || "New agent";
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  const enter = spring({
    frame,
    fps,
    config: { damping: 20, stiffness: 85 },
    durationInFrames: 34,
  });

  return (
    <AbsoluteFill>
      <WavyPaperBg />

      {/* 中心放置 Claude UI 窗口 */}
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
          width={1440}
          height={880}
          title=""
          showHeader={true}
          bodyStyle={{ backgroundColor: "#ffffff", padding: 0 }}
        >
          {/* 顶部工具栏：New agent / Templates / Source code / Config / Preview */}
          <div
            style={{
              padding: "22px 36px 0 36px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              fontFamily: "'SF Pro Text', -apple-system, sans-serif",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <div style={{ fontSize: 16, color: "#555" }}>⟵</div>
              <div style={{ fontSize: 20, fontWeight: 600, color: "#1a1a1a" }}>
                {appName}  ▾
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <div
                style={{
                  fontSize: 14,
                  color: "#555",
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                ▶ Test run
              </div>
              <div
                style={{
                  padding: "8px 16px",
                  backgroundColor: "#1a1a1a",
                  color: "#fff",
                  borderRadius: 6,
                  fontSize: 14,
                  fontWeight: 500,
                }}
              >
                Save agent
              </div>
              <div style={{ fontSize: 16, color: "#555" }}>⤓</div>
            </div>
          </div>

          {/* Tabs: Templates / Source code / Config / Preview */}
          <div
            style={{
              padding: "28px 36px 14px 36px",
              borderBottom: "1px solid #eee",
              display: "flex",
              gap: 26,
              fontFamily: "'SF Pro Text', -apple-system, sans-serif",
              fontSize: 14,
              color: "#666",
            }}
          >
            <div
              style={{
                color: "#d97757",
                fontWeight: 600,
                borderBottom: "2px solid #d97757",
                paddingBottom: 10,
              }}
            >
              Templates
            </div>
            <div style={{ paddingBottom: 10 }}>Source code</div>
            <div style={{ paddingBottom: 10 }}>Config</div>
            <div style={{ paddingBottom: 10 }}>Preview</div>
          </div>

          {/* 两栏：左问题 + 右模板网格 */}
          <div
            style={{
              display: "flex",
              padding: "32px 36px",
              gap: 28,
              height: "calc(100% - 140px)",
            }}
          >
            {/* 左栏 */}
            <div
              style={{
                width: 360,
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
                paddingTop: 20,
              }}
            >
              <div
                style={{
                  fontSize: 44,
                  fontFamily: t.titleFont,
                  fontWeight: 500,
                  color: "#1a1a1a",
                  lineHeight: 1.2,
                  marginBottom: 28,
                  letterSpacing: "-0.01em",
                  whiteSpace: "pre-line",
                }}
              >
                {question}
              </div>
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "10px 14px",
                  border: "1px solid #e2ddd0",
                  borderRadius: 24,
                  fontSize: 14,
                  color: "#555",
                  backgroundColor: "#faf8f3",
                  width: "fit-content",
                }}
              >
                ⤒ Upload existing spec as context
              </div>
            </div>

            {/* 右栏：Get started with a template + 搜索 + 类别标签 + 卡片网格 */}
            <div style={{ flex: 1 }}>
              <div
                style={{
                  fontSize: 15,
                  color: "#555",
                  marginBottom: 12,
                  fontFamily: "'SF Pro Text', -apple-system, sans-serif",
                }}
              >
                Get started with a template
              </div>
              <div
                style={{
                  border: "1px solid #e5e5e5",
                  borderRadius: 8,
                  padding: "10px 14px",
                  marginBottom: 14,
                  fontSize: 14,
                  color: "#aaa",
                  fontFamily: "'SF Pro Text', -apple-system, sans-serif",
                }}
              >
                Search templates
              </div>
              <div
                style={{
                  display: "flex",
                  gap: 8,
                  marginBottom: 18,
                  fontFamily: "'SF Pro Text', -apple-system, sans-serif",
                  fontSize: 13,
                }}
              >
                {TAGS.map((tag, i) => (
                  <div
                    key={i}
                    style={{
                      padding: "6px 12px",
                      border: "1px solid #e2ddd0",
                      borderRadius: 20,
                      backgroundColor: tag.active ? "#f5f0e6" : "#fff",
                      color: tag.active ? "#333" : "#666",
                      fontWeight: tag.active ? 600 : 400,
                    }}
                  >
                    {tag.label}
                  </div>
                ))}
              </div>

              {/* 模板网格 2 列 × 4 行 */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 12,
                }}
              >
                {TEMPLATES.map((tpl, i) => (
                  <div
                    key={i}
                    style={{
                      border: "1px solid #e5e5e5",
                      borderRadius: 10,
                      padding: "14px 16px",
                      backgroundColor: "#fff",
                      fontFamily: "'SF Pro Text', -apple-system, sans-serif",
                    }}
                  >
                    <div
                      style={{
                        fontSize: 15,
                        fontWeight: 600,
                        color: "#1a1a1a",
                        marginBottom: 6,
                      }}
                    >
                      {tpl.title}
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        color: "#666",
                        lineHeight: 1.4,
                      }}
                    >
                      {tpl.desc}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* 底部输入框 */}
          <div
            style={{
              position: "absolute",
              bottom: 14,
              left: 36,
              right: 36,
              height: 46,
              border: "1px solid #e5e5e5",
              borderRadius: 10,
              display: "flex",
              alignItems: "center",
              padding: "0 16px",
              fontSize: 13,
              color: "#aaa",
              fontFamily: "'SF Pro Text', -apple-system, sans-serif",
              backgroundColor: "#fff",
            }}
          >
            <span style={{ marginLeft: "auto", color: "#888", fontSize: 14 }}>
              ◎ ▸
            </span>
          </div>
        </MacosWindow>
      </div>
    </AbsoluteFill>
  );
};

registry.register(
  {
    id: "slide.anthropic-template-picker",
    schema: "slide",
    name: "Anthropic 模板选择器",
    description:
      "Anthropic 品牌片场景 3：Claude Agents 产品 UI，左侧衬线大字问 'What do you want to build?'，右侧 8 个模板卡片网格（Deep research / RAG retrieval / Intent router 等）。复刻 11-18s 帧。",
    isDefault: false,
    tags: ["anthropic", "产品 UI", "模板选择", "网格"],
  },
  AnthropicTemplatePicker,
);
export { AnthropicTemplatePicker };
