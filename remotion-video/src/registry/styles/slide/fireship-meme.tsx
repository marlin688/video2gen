/**
 * slide.fireship-meme — Fireship 风格全屏 meme/截图卡
 *
 * 全屏图片 + 可选顶部/底部白色粗体文字（Impact 风格黑色描边）。
 * 用于展示截图、meme、Logo 等视觉素材。
 *
 * 数据约定（复用 SlideData）：
 *   title            — 覆盖文字（可选，留空则纯图片）
 *   bullet_points[0] — 图片文件名（images/ 下的文件，如 "hn_post.png"）
 *   chart_hint       — 文字位置: "top" | "bottom" | "center"（默认 "bottom"）
 */

import React from "react";
import {
  AbsoluteFill, Img, staticFile,
  useCurrentFrame, useVideoConfig, interpolate,
} from "remotion";
import alea from "alea";
import { registry } from "../../registry";
import type { StyleComponentProps } from "../../types";

const FireshipMeme: React.FC<StyleComponentProps<"slide">> = ({ data, segmentId }) => {
  const { title, bullet_points, chart_hint } = data;
  const imageFile = bullet_points?.[0] || "";
  const textPosition = (chart_hint as "top" | "bottom" | "center") || "bottom";
  const hasText = title && title.trim().length > 0;

  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // 确定性 Ken Burns 方向（基于 segmentId 轮换）
  const rng = alea(`meme-kb-${segmentId}`);
  const kbType = Math.floor(rng() * 4); // 0-3

  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateRight: "clamp",
  });

  // 微妙的 Ken Burns：缩放 1.0→1.08 或反向，平移 0→±15px
  let scale: number;
  let tx: number;
  let ty: number;

  switch (kbType) {
    case 0: // zoom in
      scale = interpolate(progress, [0, 1], [1.0, 1.08]);
      tx = 0; ty = 0;
      break;
    case 1: // zoom out
      scale = interpolate(progress, [0, 1], [1.08, 1.0]);
      tx = 0; ty = 0;
      break;
    case 2: // pan right + slight zoom
      scale = interpolate(progress, [0, 1], [1.02, 1.06]);
      tx = interpolate(progress, [0, 1], [-12, 12]);
      ty = 0;
      break;
    default: // pan up + slight zoom
      scale = interpolate(progress, [0, 1], [1.02, 1.06]);
      tx = 0;
      ty = interpolate(progress, [0, 1], [10, -10]);
      break;
  }

  // 文字位置映射
  const textPositionStyle: React.CSSProperties =
    textPosition === "top"
      ? { top: 40, left: 0, right: 0 }
      : textPosition === "center"
        ? { top: "50%", left: 0, right: 0, transform: "translateY(-50%)" }
        : { bottom: 40, left: 0, right: 0 };

  return (
    <AbsoluteFill style={{ backgroundColor: "#000", overflow: "hidden" }}>
      {/* 全屏图片 + Ken Burns 推镜 */}
      {imageFile && (
        <Img
          src={staticFile(`images/${imageFile}`)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "contain",
            transform: `scale(${scale}) translate(${tx}px, ${ty}px)`,
            transformOrigin: "center center",
          }}
        />
      )}

      {/* 可选暗化遮罩（有文字时加上） */}
      {hasText && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background:
              textPosition === "bottom"
                ? "linear-gradient(transparent 60%, rgba(0,0,0,0.7))"
                : textPosition === "top"
                  ? "linear-gradient(rgba(0,0,0,0.7), transparent 40%)"
                  : "rgba(0,0,0,0.3)",
          }}
        />
      )}

      {/* 覆盖文字 */}
      {hasText && (
        <div
          style={{
            position: "absolute",
            ...textPositionStyle,
            display: "flex",
            justifyContent: "center",
            padding: "0 60px",
          }}
        >
          <div
            style={{
              fontSize: title!.length <= 20 ? 72 : title!.length <= 40 ? 52 : 40,
              fontWeight: 900,
              fontFamily: "'Impact', 'Arial Black', 'Noto Sans SC', sans-serif",
              color: "#ffffff",
              textAlign: "center",
              textTransform: "uppercase",
              lineHeight: 1.2,
              // 黑色描边效果
              textShadow:
                "3px 3px 0 #000, -3px -3px 0 #000, 3px -3px 0 #000, -3px 3px 0 #000, 0 3px 0 #000, 0 -3px 0 #000, 3px 0 0 #000, -3px 0 0 #000",
            }}
          >
            {title}
          </div>
        </div>
      )}
    </AbsoluteFill>
  );
};

registry.register(
  {
    id: "slide.fireship-meme",
    schema: "slide",
    name: "Fireship Meme/截图卡",
    description: "全屏图片 + 可选粗体覆盖文字，Impact 描边风格",
    isDefault: false,
    tags: ["meme", "截图", "快节奏"],
  },
  FireshipMeme,
);
