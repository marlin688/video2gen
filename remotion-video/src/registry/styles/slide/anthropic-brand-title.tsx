/**
 * slide.anthropic-brand-title — Anthropic 品牌片场景 9
 *
 * 纯米白背景 + 居中偏上一行超大衬线 "Claude Managed Agents,"
 * 带逐词缓慢淡入效果。复刻 50-55s 帧。
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

const DEFAULT_WORDS = ["Claude", "Managed", "Agents,"];

/**
 * scene_data shape (可选)：
 *   { words?: string[] }   // 覆盖默认的 ["Claude", "Managed", "Agents,"]
 * 或者直接用 slide_content.title = "Your Title Here"（按空格拆词）
 */
const AnthropicBrandTitle: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  const sceneData = (data.scene_data || {}) as { words?: string[] };
  const words =
    sceneData.words && sceneData.words.length > 0
      ? sceneData.words
      : data.title
        ? data.title.split(/\s+/).filter(Boolean)
        : DEFAULT_WORDS;

  const perWord = words.map((_, i) =>
    spring({
      frame: Math.max(0, frame - 8 - i * 10),
      fps,
      config: { damping: 22, stiffness: 60 },
      durationInFrames: 50,
    }),
  );

  return (
    <AbsoluteFill>
      <WavyPaperBg lineColor="rgba(80,70,50,0.04)" />

      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "0 80px",
        }}
      >
        <div
          style={{
            display: "flex",
            gap: 24,
            fontFamily: t.titleFont,
            fontSize: 96,
            fontWeight: 500,
            color: t.text,
            letterSpacing: "-0.02em",
          }}
        >
          {words.map((word, i) => (
            <span
              key={i}
              style={{
                opacity: interpolate(perWord[i], [0, 1], [0, 1]),
                transform: `translateY(${interpolate(perWord[i], [0, 1], [24, 0])}px)`,
                display: "inline-block",
              }}
            >
              {word}
            </span>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};

registry.register(
  {
    id: "slide.anthropic-brand-title",
    schema: "slide",
    name: "Anthropic 品牌大字标题",
    description:
      "Anthropic 品牌片场景 9：纯米白背景 + 居中超大衬线 'Claude Managed Agents,'，三个词依次缓慢淡入。复刻 50-55s 帧。",
    isDefault: false,
    tags: ["anthropic", "品牌", "大字", "标题"],
  },
  AnthropicBrandTitle,
);
export { AnthropicBrandTitle };
