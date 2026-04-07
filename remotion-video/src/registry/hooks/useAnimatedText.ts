/**
 * useAnimatedText -- 逐字符显示 hook
 *
 * 按帧逐步显示文本字符，适合打字机效果。
 */

import { interpolate, useCurrentFrame } from "remotion";

export const useAnimatedText = (
  text: string,
  options: { startFrame?: number; speed?: number } = {},
): string => {
  const frame = useCurrentFrame();
  const { startFrame = 0, speed = 2 } = options;

  const elapsed = Math.max(0, frame - startFrame);
  const charCount = interpolate(
    elapsed,
    [0, text.length * speed],
    [0, text.length],
    { extrapolateRight: "clamp" },
  );

  return text.slice(0, Math.round(charCount));
};
