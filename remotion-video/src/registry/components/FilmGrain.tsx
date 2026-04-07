/**
 * FilmGrain — 后期质感层
 *
 * 叠加在所有内容最上层，不受运镜影响。
 * 三合一效果：动态噪点 + 暗角 + 色差，让所有组件"长在同一个世界里"。
 *
 * 性能优化：预生成 12 帧噪点纹理循环使用，避免每帧实时计算。
 */

import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import alea from "alea";

interface FilmGrainProps {
  enabled?: boolean;
  /** 噪点不透明度，默认 0.03 */
  grainOpacity?: number;
  /** 暗角强度 0-1，默认 0.35 */
  vignetteStrength?: number;
  /** 色差偏移量 px，默认 1.5 */
  aberrationOffset?: number;
  seed?: string;
}

/** 预生成噪点纹理帧数 */
const GRAIN_FRAME_COUNT = 12;
/** 噪点分辨率（降采样以提升性能） */
const GRAIN_W = 480;
const GRAIN_H = 270;

/**
 * 预生成噪点纹理 data URL 数组
 * 在组件首次挂载时生成，之后按 frame % 12 循环取用
 */
function generateGrainFrames(seed: string): string[] {
  const frames: string[] = [];

  // 服务端渲染时可能没有 document，用 OffscreenCanvas 兜底
  const createCanvas = (): HTMLCanvasElement | OffscreenCanvas => {
    if (typeof OffscreenCanvas !== "undefined") {
      return new OffscreenCanvas(GRAIN_W, GRAIN_H);
    }
    const c = document.createElement("canvas");
    c.width = GRAIN_W;
    c.height = GRAIN_H;
    return c;
  };

  for (let f = 0; f < GRAIN_FRAME_COUNT; f++) {
    const rng = alea(`${seed}-grain-${f}`);
    const canvas = createCanvas();
    const ctx = canvas.getContext("2d") as
      | CanvasRenderingContext2D
      | OffscreenCanvasRenderingContext2D;
    if (!ctx) continue;

    const imageData = ctx.createImageData(GRAIN_W, GRAIN_H);
    const data = imageData.data;

    for (let i = 0; i < data.length; i += 4) {
      const v = Math.floor(rng() * 255);
      data[i] = v;       // R
      data[i + 1] = v;   // G
      data[i + 2] = v;   // B
      data[i + 3] = 255; // A (opacity 由 CSS 控制)
    }

    ctx.putImageData(imageData, 0, 0);

    if (canvas instanceof OffscreenCanvas) {
      // OffscreenCanvas 不支持 toDataURL，转 blob 太重，直接用 canvas 引用
      // 改用 transferToImageBitmap 方案不太行，还是用 document.createElement
      // 兜底：如果在 Node (Remotion render) 环境直接跳过噪点
      try {
        const tmpCanvas = document.createElement("canvas");
        tmpCanvas.width = GRAIN_W;
        tmpCanvas.height = GRAIN_H;
        const tmpCtx = tmpCanvas.getContext("2d")!;
        tmpCtx.putImageData(imageData, 0, 0);
        frames.push(tmpCanvas.toDataURL("image/png"));
      } catch {
        // SSR 环境，跳过
        frames.push("");
      }
    } else {
      frames.push(canvas.toDataURL("image/png"));
    }
  }

  return frames;
}

export const FilmGrain: React.FC<FilmGrainProps> = ({
  enabled = true,
  grainOpacity = 0.03,
  vignetteStrength = 0.35,
  aberrationOffset = 1.5,
  seed = "film-grain",
}) => {
  const frame = useCurrentFrame();

  // 预生成噪点纹理（只在首次渲染时计算）
  const grainFrames = React.useMemo(
    () => (enabled ? generateGrainFrames(seed) : []),
    [enabled, seed],
  );

  if (!enabled) return null;

  const currentGrain = grainFrames[frame % GRAIN_FRAME_COUNT] || "";

  return (
    <AbsoluteFill style={{ pointerEvents: "none", zIndex: 9998 }}>
      {/* ── 动态噪点（Film Grain） ── */}
      {currentGrain && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundImage: `url(${currentGrain})`,
            backgroundSize: "cover",
            opacity: grainOpacity,
            mixBlendMode: "overlay",
          }}
        />
      )}

      {/* ── 暗角（Vignette） ── */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(ellipse at center, transparent 50%, rgba(0,0,0,${vignetteStrength}) 100%)`,
        }}
      />

      {/* ── 色差（Chromatic Aberration）—— 红/蓝双影 ── */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          boxShadow: `inset ${aberrationOffset}px 0 ${aberrationOffset * 2}px rgba(255,0,0,0.04), inset ${-aberrationOffset}px 0 ${aberrationOffset * 2}px rgba(0,100,255,0.04)`,
        }}
      />
    </AbsoluteFill>
  );
};
