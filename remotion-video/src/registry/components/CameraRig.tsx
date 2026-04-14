/**
 * CameraRig — 全局运镜组件
 *
 * 包裹所有内容，施加极其缓慢的 transform（推、拉、平移），
 * 赋予画面纪录片般的微动感。人眼几乎察觉不到，但下意识感受到"活"的画面。
 *
 * 段落级运镜：每个 segment 切换运镜方向，避免单调。
 *
 * 关键设计：每段运镜走"0 → 峰值 → 0"的钟形曲线（sin-bell），
 * 确保每个段边界都回到 identity (scale=1, translate=0)，
 * 段切换零断层，不会出现运镜"瞬移"跳跃。
 *
 * 运镜模式循环：push-in → drift-right → subtle-zoom → drift-left
 */

import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
} from "remotion";
import { GLOBAL_EASE } from "../utils/easing";

/** 运镜模式 */
type CameraMove = "push-in" | "drift-right" | "subtle-zoom" | "drift-left";
type CameraMoveTag = CameraMove | "static";

const CAMERA_SEQUENCE: CameraMove[] = [
  "push-in",
  "drift-right",
  "subtle-zoom",
  "drift-left",
];

interface SegmentFrameInfo {
  segmentId: number;
  start: number;
  duration: number;
  gap: number;
}

interface SegmentCameraPlan {
  camera_move?: CameraMoveTag;
  camera_intensity?: number;
}

interface BeatCameraPlan {
  beatId?: number;
  segmentId: number;
  startFrame: number;
  endFrame: number;
  camera_move?: CameraMoveTag;
  camera_intensity?: number;
}

interface CameraRigProps {
  children: React.ReactNode;
  segmentFrameInfo: SegmentFrameInfo[];
  segmentCameraPlans?: Record<number, SegmentCameraPlan>;
  beatCameraPlans?: BeatCameraPlan[];
  enabled?: boolean;
  /** 最大缩放量（硬性上限 1.02） */
  maxScale?: number;
  /** 最大平移量 px */
  maxTranslate?: number;
}

export const CameraRig: React.FC<CameraRigProps> = ({
  children,
  segmentFrameInfo,
  segmentCameraPlans,
  beatCameraPlans,
  enabled = true,
  maxScale = 1.02,
  maxTranslate = 12,
}) => {
  const frame = useCurrentFrame();

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

    const activeBeat = beatCameraPlans?.find(
      (b) => frame >= b.startFrame && frame < b.endFrame,
    );
    const windowStart = activeBeat ? activeBeat.startFrame : info.start;
    const windowEnd = activeBeat
      ? Math.max(activeBeat.startFrame + 1, activeBeat.endFrame)
      : info.start + info.duration + info.gap;

    // 当前时间窗内进度 0→1（优先逐句，否则按段）
    const progress = interpolate(
      frame,
      [windowStart, windowEnd],
      [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: GLOBAL_EASE },
    );

    const planned = segmentCameraPlans?.[info.segmentId];
    const plannedMove = activeBeat?.camera_move ?? planned?.camera_move;
    const move: CameraMoveTag =
      plannedMove && (plannedMove === "static" || CAMERA_SEQUENCE.includes(plannedMove as CameraMove))
        ? plannedMove
        : CAMERA_SEQUENCE[currentSegIdx % CAMERA_SEQUENCE.length];
    const rawIntensity = Number(activeBeat?.camera_intensity ?? planned?.camera_intensity ?? 0.75);
    const intensity = Number.isFinite(rawIntensity)
      ? Math.max(0, Math.min(rawIntensity, 1.2))
      : 0.75;
    if (move === "static" || intensity <= 0) return "none";

    // 钟形曲线 (sin bell)：progress 0 → 0, 0.5 → 1, 1 → 0
    // 保证每段起止都回到 identity，段边界零断层
    const bell = Math.sin(progress * Math.PI);

    let sx = 1;
    let sy = 1;
    let tx = 0;
    let ty = 0;

    switch (move) {
      case "push-in":
        // scale 在段中间峰值到 maxScale，两端均为 1.0
        sx = sy = 1 + (scale - 1) * bell * intensity;
        break;
      case "subtle-zoom":
        // 更温和的推进（40% 力度），与 push-in 形成强弱对比
        sx = sy = 1 + (scale - 1) * bell * 0.6 * intensity;
        break;
      case "drift-right":
        // tx 在段中间峰值到 +translate，两端均为 0
        tx = translate * bell * intensity;
        break;
      case "drift-left":
        // tx 在段中间峰值到 -translate，两端均为 0
        tx = -translate * bell * intensity;
        break;
    }

    return `scale(${sx}, ${sy}) translate(${tx}px, ${ty}px)`;
  }, [enabled, frame, segmentFrameInfo, segmentCameraPlans, beatCameraPlans, scale, translate]);

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
