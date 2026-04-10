/**
 * slide.anthropic-brand-outro — Anthropic 品牌片场景 10
 *
 * 纯米白背景 + 居中 Claude 星芒 logo + 衬线 "Claude" 文字。
 * 复刻 55-59s 帧的品牌收尾。
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
import { ClaudeLogo, ClaudeWordmark } from "../../components/ClaudeLogo";

/**
 * scene_data shape (可选)：
 *   { wordmark?: string, showLogo?: boolean }
 * 或用 slide_content.title = "YourBrand"
 */
const AnthropicBrandOutro: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  const sceneData = (data.scene_data || {}) as {
    wordmark?: string;
    showLogo?: boolean;
  };
  const wordmark = sceneData.wordmark || data.title || "Claude";
  const showLogo = sceneData.showLogo !== false;

  const logoIn = spring({
    frame,
    fps,
    config: { damping: 18, stiffness: 90 },
    durationInFrames: 30,
  });
  const wordIn = spring({
    frame: Math.max(0, frame - 12),
    fps,
    config: { damping: 20, stiffness: 80 },
    durationInFrames: 30,
  });

  return (
    <AbsoluteFill>
      <WavyPaperBg lineColor="rgba(80,70,50,0.035)" />
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 32,
        }}
      >
        {showLogo && (
          <div
            style={{
              opacity: interpolate(logoIn, [0, 1], [0, 1]),
              // 更温和的入场：小幅缩放 + 8° 轻微旋转，不再是 30° 甩动
              transform: `scale(${interpolate(logoIn, [0, 1], [0.85, 1])}) rotate(${interpolate(
                logoIn,
                [0, 1],
                [-8, 0],
              )}deg)`,
            }}
          >
            <ClaudeLogo size={110} color={t.accent} />
          </div>
        )}
        <div
          style={{
            opacity: interpolate(wordIn, [0, 1], [0, 1]),
            transform: `translateX(${interpolate(wordIn, [0, 1], [-20, 0])}px)`,
          }}
        >
          <ClaudeWordmark text={wordmark} size={110} color={t.text} />
        </div>
      </div>
    </AbsoluteFill>
  );
};

registry.register(
  {
    id: "slide.anthropic-brand-outro",
    schema: "slide",
    name: "Anthropic 品牌收尾",
    description:
      "Anthropic 品牌片场景 10：纯米白背景 + 居中 Claude 星芒 logo (珊瑚红) + 衬线 'Claude' 文字。logo 和文字依次淡入。复刻 55-59s 品牌收尾帧。",
    isDefault: false,
    tags: ["anthropic", "品牌", "收尾", "logo"],
  },
  AnthropicBrandOutro,
);
export { AnthropicBrandOutro };
