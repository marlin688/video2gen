/**
 * slide.anthropic-section-title — Anthropic 风格章节分隔卡
 *
 * 长视频的"Part 1" / "Part 2"章节切换。米白背景 + 衬线大字 + 两侧细装饰线。
 * 简单、节制，3 秒足够。
 *
 * scene_data shape:
 * {
 *   chapter?: string;   // 小字前缀 (如 "Part 1", "Chapter 2", "01 —")
 *   title: string;      // 主标题 (衬线大字，12-24 字最佳)
 *   subtitle?: string;  // 副标题 (小字，可选)
 * }
 *
 * 或用 slide_content.title 作为主标题（最简用法）。
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

interface SectionTitleSceneData {
  chapter?: string;
  title?: string;
  subtitle?: string;
}

const AnthropicSectionTitle: React.FC<StyleComponentProps<"slide">> = ({
  data,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  const sd = (data.scene_data || {}) as SectionTitleSceneData;
  const chapter = sd.chapter || "";
  const title = sd.title || data.title || "Section";
  const subtitle =
    sd.subtitle || (data.bullet_points && data.bullet_points[0]) || "";

  // 章节 chapter 先入场
  const chapterIn = spring({
    frame,
    fps,
    config: { damping: 20, stiffness: 85 },
    durationInFrames: 18,
  });
  // 主标题紧随
  const titleIn = spring({
    frame: Math.max(0, frame - 6),
    fps,
    config: { damping: 20, stiffness: 85 },
    durationInFrames: 22,
  });
  // 副标题最后
  const subtitleIn = spring({
    frame: Math.max(0, frame - 14),
    fps,
    config: { damping: 20, stiffness: 85 },
    durationInFrames: 20,
  });
  // 装饰线展开
  const lineIn = spring({
    frame: Math.max(0, frame - 4),
    fps,
    config: { damping: 22, stiffness: 60 },
    durationInFrames: 30,
  });

  return (
    <AbsoluteFill>
      <WavyPaperBg lineColor="rgba(80, 70, 50, 0.045)" />

      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "0 160px",
        }}
      >
        {chapter && (
          <div
            style={{
              fontFamily: "'SF Pro Text', -apple-system, sans-serif",
              fontSize: 22,
              fontWeight: 600,
              color: t.accent,
              letterSpacing: "0.15em",
              textTransform: "uppercase",
              marginBottom: 28,
              opacity: interpolate(chapterIn, [0, 1], [0, 1]),
              transform: `translateY(${interpolate(chapterIn, [0, 1], [12, 0])}px)`,
            }}
          >
            {chapter}
          </div>
        )}

        {/* 两侧细水平线装饰 */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 40,
            width: "100%",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              flex: 1,
              maxWidth: 240,
              height: 1,
              backgroundColor: "rgba(60, 50, 40, 0.25)",
              transform: `scaleX(${interpolate(lineIn, [0, 1], [0, 1])})`,
              transformOrigin: "right center",
            }}
          />
          <div
            style={{
              fontFamily: t.titleFont,
              fontSize: 80,
              fontWeight: 500,
              color: t.text,
              letterSpacing: "-0.02em",
              lineHeight: 1.12,
              textAlign: "center",
              maxWidth: 1200,
              opacity: interpolate(titleIn, [0, 1], [0, 1]),
              transform: `translateY(${interpolate(titleIn, [0, 1], [16, 0])}px)`,
              whiteSpace: "pre-line",
            }}
          >
            {title}
          </div>
          <div
            style={{
              flex: 1,
              maxWidth: 240,
              height: 1,
              backgroundColor: "rgba(60, 50, 40, 0.25)",
              transform: `scaleX(${interpolate(lineIn, [0, 1], [0, 1])})`,
              transformOrigin: "left center",
            }}
          />
        </div>

        {subtitle && (
          <div
            style={{
              marginTop: 28,
              fontFamily: t.bodyFont,
              fontSize: 26,
              color: t.textDim,
              fontStyle: "italic",
              textAlign: "center",
              maxWidth: 1000,
              opacity: interpolate(subtitleIn, [0, 1], [0, 1]),
              transform: `translateY(${interpolate(subtitleIn, [0, 1], [10, 0])}px)`,
            }}
          >
            {subtitle}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};

registry.register(
  {
    id: "slide.anthropic-section-title",
    schema: "slide",
    name: "Anthropic 章节分隔",
    description:
      "米白背景 + 衬线大字章节卡。小字 chapter 前缀 + 大字 title + 可选 subtitle + 两侧细装饰线。用于长技术视频的章节切换，3 秒足够。",
    isDefault: false,
    tags: ["anthropic", "section-title", "章节", "分隔"],
  },
  AnthropicSectionTitle,
);
export { AnthropicSectionTitle };
