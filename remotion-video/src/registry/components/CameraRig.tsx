/**
 * CameraRig — 全局运镜组件
 *
 * 包裹所有内容，施加极其缓慢的 transform（推、拉、平移），
 * 赋予画面纪录片般的微动感。人眼几乎察觉不到，但下意识感受到"活"的画面。
 *
 * 段落级运镜：每个 segment 切换运镜方向，避免单调。
 * 运镜模式循环：push-in → drift-right → pull-out → drift-left
 */

import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { GLOBAL_EASE } from "../utils/easing";

/** 运镜模式 */
type CameraMove = "push-in" | "drift-right" | "pull-out" | "drift-left";

const CAMERA_SEQUENCE: CameraMove[] = [
  "push-in",
  "drift-right",
  "pull-out",
  "drift-left",
];

interface SegmentFrameInfo {
  start: number;
  duration: number;
  gap: number;
}

interface CameraRigProps {
  children: React.ReactNode;
  segmentFrameInfo: SegmentFrameInfo[];
  enabled?: boolean;
  /** 最大缩放量（硬性上限 1.02） */
  maxScale?: number;
  /** 最大平移量 px */
  maxTranslate?: number;
}

export const CameraRig: React.FC<CameraRigProps> = ({
  children,
  segmentFrameInfo,
  enabled = true,
  maxScale = 1.02,
  maxTranslate = 12,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // 硬性上限
  const scale = Math.min(maxScale, 1.02);
  const translate = Math.min(maxTranslate, 12);

  const transform = React.useMemo(() => {
    if (!enabled || segmentFrameInfo.length === 0) {
      return "none";
    }

    // 找到当前帧所在的 segment
    let currentSegIdx = 0;
    for (let i = 0; i < segmentFrameInfo.length; i++) {
      const info = segmentFrameInfo[i];
      if (frame >= info.start && frame < info.start + info.duration + info.gap) {
        currentSegIdx = i;
        break;
      }
      // 超过最后一段
      if (i === segmentFrameInfo.length - 1) {
        currentSegIdx = i;
      }
    }

    const info = segmentFrameInfo[currentSegIdx];
    if (!info || info.duration === 0) return "none";

    const segEnd = info.start + info.duration + info.gap;
    // 段内进度 0→1
    const progress = interpolate(
      frame,
      [info.start, segEnd],
      [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: GLOBAL_EASE },
    );

    const move = CAMERA_SEQUENCE[currentSegIdx % CAMERA_SEQUENCE.length];

    let sx = 1;
    let sy = 1;
    let tx = 0;
    let ty = 0;

    switch (move) {
      case "push-in":
        // 从 1.0 缓慢放大到 maxScale
        sx = sy = interpolate(progress, [0, 1], [1, scale]);
        break;
      case "pull-out":
        // 从 maxScale 缓慢缩回 1.0
        sx = sy = interpolate(progress, [0, 1], [scale, 1]);
        break;
      case "drift-right":
        // 从左向右平移
        tx = interpolate(progress, [0, 1], [-translate, translate]);
        break;
      case "drift-left":
        // 从右向左平移
        tx = interpolate(progress, [0, 1], [translate, -translate]);
        break;
    }

    return `scale(${sx}, ${sy}) translate(${tx}px, ${ty}px)`;
  }, [enabled, frame, segmentFrameInfo, scale, translate]);

  if (!enabled) {
    return <AbsoluteFill>{children}</AbsoluteFill>;
  }

  return (
    <AbsoluteFill
      style={{
        transform,
        transformOrigin: "center center",
        willChange: "transform",
      }}
    >
      {children}
    </AbsoluteFill>
  );
};
