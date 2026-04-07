/**
 * WordReveal -- 逐词弹出动画组件
 *
 * 文字按词拆分，spring 驱动每个词的 opacity + translateY 入场。
 * 中文文本自动按 2-4 字分组。
 */

import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

interface WordRevealProps {
  text: string;
  startFrame?: number;
  staggerFrames?: number;
  style?: React.CSSProperties;
}

/** 将文本拆分为动画单元：英文按空格，中文按 2-3 字一组 */
function splitIntoUnits(text: string): string[] {
  // 如果含有空格（英文/混合），按空格拆分
  if (/\s/.test(text)) {
    return text.split(/\s+/).filter(Boolean);
  }
  // 纯中文：每 2-3 字一组
  const units: string[] = [];
  let i = 0;
  while (i < text.length) {
    const chunkSize = i + 3 <= text.length ? 3 : text.length - i;
    units.push(text.slice(i, i + chunkSize));
    i += chunkSize;
  }
  return units;
}

export const WordReveal: React.FC<WordRevealProps> = ({
  text,
  startFrame = 0,
  staggerFrames = 3,
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const units = splitIntoUnits(text);

  return (
    <span style={style}>
      {units.map((word, i) => {
        const wordProgress = spring({
          fps,
          frame: frame - startFrame - i * staggerFrames,
          config: { damping: 12, stiffness: 100, mass: 0.8 },
        });
        const translateY = interpolate(wordProgress, [0, 1], [40, 0]);
        const scale = interpolate(wordProgress, [0, 1], [0.7, 1]);

        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              opacity: interpolate(wordProgress, [0, 0.3], [0, 1], { extrapolateRight: "clamp" }),
              transform: `translateY(${translateY}px) scale(${scale})`,
              marginRight: /\s/.test(text) ? 8 : 0,
            }}
          >
            {word}
          </span>
        );
      })}
    </span>
  );
};
