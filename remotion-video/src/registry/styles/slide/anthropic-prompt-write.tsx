/**
 * slide.anthropic-prompt-write — Anthropic 品牌片场景 4
 *
 * 同一个 Claude UI 窗口，左侧出现一组快捷选项 + 用户在底部输入 prompt：
 * "Build an agent that evaluates acquisition targets…"
 * 复刻 18-25s 帧，带 HumanTyping 效果。
 */

import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";
import { WavyPaperBg } from "../../components/WavyPaperBg";
import { MacosWindow } from "../../components/MacosWindow";

const DEFAULT_PROMPT_TEXT =
  "Build an agent that evaluates acquisition targets. It should research companies, pull financials, run competitive benchmarks, and draft an investment memo.";

const DEFAULT_TEMPLATES_MINI = [
  "Deep research",
  "Structured extractor",
  "RAG retrieval",
  "Intent router",
  "Draft generator",
  "Reflection loop",
  "Task planner",
  "Summarizer",
];

const DEFAULT_QUESTION = "What do you want to build?";

const DEFAULT_QUICK_ACTIONS = [
  { icon: "⤒", text: "Upload existing spec as context" },
  { icon: "◐", text: "/ to add skills or sub agents" },
  { icon: "|||", text: "Let Claude interview you" },
];

/**
 * scene_data shape (可选)：
 * {
 *   prompt?: string,            // 底部输入框要打出的 prompt 文本
 *   question?: string,          // 左上衬线大字问题
 *   quickActions?: { icon: string, text: string }[],
 *   templates?: string[],       // 右侧淡化的模板名列表
 * }
 */
const AnthropicPromptWrite: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const sceneData = (data.scene_data || {}) as {
    prompt?: string;
    question?: string;
    quickActions?: { icon: string; text: string }[];
    templates?: string[];
  };
  const PROMPT_TEXT = sceneData.prompt || DEFAULT_PROMPT_TEXT;
  const question = sceneData.question || data.title || DEFAULT_QUESTION;
  const QUICK_ACTIONS =
    sceneData.quickActions && sceneData.quickActions.length > 0
      ? sceneData.quickActions
      : DEFAULT_QUICK_ACTIONS;
  const TEMPLATES_MINI =
    sceneData.templates && sceneData.templates.length > 0
      ? sceneData.templates
      : DEFAULT_TEMPLATES_MINI;
  const frame = useCurrentFrame();
  const t = useTheme();

  // 关键：本场景延续 scene 3 的 template-picker 布局，主窗口不做任何
  // 入场 scale/opacity，否则会和 scene 3 的同布局在 fade 交叉溶解
  // 时产生文字亚像素错位（鬼影）。fade() 本身会处理跨段淡入，
  // 场景内只让新增元素（快捷选项、prompt 输入框）自己动起来。

  // Prompt 逐字打入（从 frame 20 开始，每 1.2 帧一个字符）
  const typedChars = Math.max(
    0,
    Math.min(PROMPT_TEXT.length, Math.floor((frame - 20) / 1.2)),
  );
  const typed = PROMPT_TEXT.slice(0, typedChars);
  const cursorOn = Math.floor(frame / 8) % 2 === 0;

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
          width={1440}
          height={880}
          showHeader={true}
          bodyStyle={{ backgroundColor: "#ffffff", padding: 0 }}
        >
          {/* Tab 栏 */}
          <div
            style={{
              padding: "28px 36px 14px 36px",
              borderBottom: "1px solid #eee",
              display: "flex",
              gap: 26,
              fontFamily: "'SF Pro Text', -apple-system, sans-serif",
              fontSize: 14,
              color: "#666",
              marginTop: 14,
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

          {/* 两栏 */}
          <div
            style={{
              display: "flex",
              padding: "32px 36px",
              gap: 28,
              height: "calc(100% - 250px)",
            }}
          >
            {/* 左栏 */}
            <div
              style={{
                width: 360,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                paddingTop: 40,
              }}
            >
              <div
                style={{
                  fontSize: 40,
                  fontFamily: t.titleFont,
                  fontWeight: 500,
                  color: "#1a1a1a",
                  lineHeight: 1.2,
                  marginBottom: 40,
                  letterSpacing: "-0.01em",
                  textAlign: "center",
                  whiteSpace: "pre-line",
                }}
              >
                {question}
              </div>

              {/* 三个圆角按钮 */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 14,
                  alignItems: "center",
                }}
              >
                {QUICK_ACTIONS.map((btn, i) => (
                  <div
                    key={i}
                    style={{
                      padding: "10px 18px",
                      borderRadius: 24,
                      border: "1px solid #e2ddd0",
                      backgroundColor: "#faf8f3",
                      fontSize: 13,
                      color: "#555",
                      fontFamily: "'SF Pro Text', -apple-system, sans-serif",
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                    }}
                  >
                    <span style={{ color: "#999", fontSize: 12 }}>{btn.icon}</span>
                    {btn.text}
                  </div>
                ))}
              </div>
            </div>

            {/* 右栏：模板网格（褪色淡化，让中心注意力在 prompt） */}
            <div style={{ flex: 1, opacity: 0.6 }}>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 12,
                  marginTop: 28,
                }}
              >
                {TEMPLATES_MINI.map((title, i) => (
                  <div
                    key={i}
                    style={{
                      border: "1px solid #e5e5e5",
                      borderRadius: 10,
                      padding: "14px 16px",
                      backgroundColor: "#fff",
                      fontFamily: "'SF Pro Text', -apple-system, sans-serif",
                      height: 88,
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
                      {title}
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        color: "#999",
                        lineHeight: 1.4,
                      }}
                    >
                      Template description goes here with a short summary…
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* 底部 prompt 输入框（大）— 关键视觉 */}
          <div
            style={{
              position: "absolute",
              bottom: 24,
              left: 36,
              right: 420,
              backgroundColor: "#ffffff",
              border: "1px solid #e0ddd5",
              borderRadius: 14,
              padding: "18px 22px",
              boxShadow: "0 6px 24px rgba(0,0,0,0.06)",
              fontFamily: "'SF Pro Text', -apple-system, sans-serif",
              fontSize: 17,
              color: "#1a1a1a",
              lineHeight: 1.45,
              display: "flex",
              alignItems: "flex-start",
              gap: 12,
            }}
          >
            <div style={{ flex: 1, minHeight: 70 }}>
              {typed}
              {typedChars > 0 && cursorOn && (
                <span style={{ display: "inline-block", width: 2, height: 20, backgroundColor: "#1a1a1a", verticalAlign: "middle", marginLeft: 2 }} />
              )}
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "flex-end",
                gap: 10,
                paddingTop: 44,
              }}
            >
              <div style={{ color: "#aaa", fontSize: 17 }}>◉</div>
              <div
                style={{
                  width: 34,
                  height: 34,
                  backgroundColor: "#d97757",
                  borderRadius: 8,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#fff",
                  fontSize: 16,
                  fontWeight: 700,
                }}
              >
                ↑
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
    id: "slide.anthropic-prompt-write",
    schema: "slide",
    name: "Anthropic Prompt 输入",
    description:
      "Anthropic 品牌片场景 4：同一个 Claude UI 窗口，底部大输入框里 'Build an agent that evaluates acquisition targets…' 逐字打入，左侧显示 3 个快捷选项，右侧模板网格淡化。复刻 18-25s 帧。",
    isDefault: false,
    tags: ["anthropic", "prompt", "打字", "产品 UI"],
  },
  AnthropicPromptWrite,
);
export { AnthropicPromptWrite };
