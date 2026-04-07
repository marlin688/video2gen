/**
 * FlashMeme -- 闪现梗图叠加层
 *
 * 在专业内容中突然闪现一张低画质 Meme 图，
 * 制造视觉反差和幽默感。
 *
 * 核心设计：
 * - 无动画，第 0 帧瞬间出现，最后一帧瞬间消失
 * - 高对比度 + 过曝滤镜 → 粗糙的"人性毛边"质感
 * - zIndex 9999 压在所有内容之上
 * - 可选轻微随机旋转 + 噪点纹理增强手工感
 */

import React, { useMemo } from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame } from "remotion";

export interface FlashMemeProps {
  /** public/ 下的图片文件名，如 "doge.png" */
  imageFileName: string;
  /** 显示模式: cover 全屏铺满 / contain 完整显示 / raw 原始尺寸居中 */
  displayMode?: "cover" | "contain" | "raw";
  /** 轻微随机旋转角度上限（度），默认 3。设 0 禁用 */
  maxRotation?: number;
  /** 对比度倍数，默认 2.5 */
  contrast?: number;
  /** 亮度倍数，默认 1.2 */
  brightness?: number;
  /** 是否叠加扫描线噪点纹理，默认 true */
  scanlines?: boolean;
  /** 背景色（半透明黑底让图更突出），默认 "rgba(0,0,0,0.3)" */
  backdropColor?: string;
}

export const FlashMeme: React.FC<FlashMemeProps> = ({
  imageFileName,
  displayMode = "contain",
  maxRotation = 3,
  contrast = 2.5,
  brightness = 1.2,
  scanlines = true,
  backdropColor = "rgba(0,0,0,0.3)",
}) => {
  const frame = useCurrentFrame();

  // 用第一帧的 frame 值作为确定性随机种子（每次渲染相同）
  const rotation = useMemo(() => {
    if (maxRotation === 0) return 0;
    // 简单确定性 hash
    const seed = imageFileName.length * 7 + 13;
    const angle = ((seed * 9301 + 49297) % 233280) / 233280;
    return (angle - 0.5) * 2 * maxRotation;
  }, [imageFileName, maxRotation]);

  const imgStyle: React.CSSProperties = useMemo(() => {
    const base: React.CSSProperties = {
      filter: `contrast(${contrast * 100}%) brightness(${brightness * 100}%)`,
      transform: rotation !== 0 ? `rotate(${rotation}deg)` : undefined,
      imageRendering: "auto",
    };

    if (displayMode === "cover") {
      return {
        ...base,
        width: "100%",
        height: "100%",
        objectFit: "cover" as const,
      };
    }
    if (displayMode === "contain") {
      return {
        ...base,
        maxWidth: "85%",
        maxHeight: "85%",
        objectFit: "contain" as const,
      };
    }
    // raw: 原始尺寸
    return base;
  }, [displayMode, contrast, brightness, rotation]);

  const scanlineStyle: React.CSSProperties = useMemo(
    () => ({
      position: "absolute",
      inset: 0,
      backgroundImage:
        "repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,0,0,0.12) 3px, rgba(0,0,0,0.12) 4px)",
      pointerEvents: "none",
      mixBlendMode: "multiply" as const,
    }),
    [],
  );

  return (
    <AbsoluteFill
      style={{
        zIndex: 9999,
        backgroundColor: backdropColor,
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <Img src={staticFile(imageFileName)} style={imgStyle} />
      {scanlines && <div style={scanlineStyle} />}
    </AbsoluteFill>
  );
};
