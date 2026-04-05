/**
 * image-overlay.default — 图片叠加文字
 *
 * 全屏图片展示 + 底部渐变遮罩 + 文字说明 + Ken Burns 动效。
 * 适合展示产品截图、推文截图、新闻配图、数据图表等真实画面。
 */

import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import React from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";

/* ═══════════════ Ken Burns 参数 ═══════════════ */

const KB_CONFIGS = {
  "zoom-in": {
    scaleFrom: 1.0,
    scaleTo: 1.06,
    translateX: [0, 0] as [number, number],
    translateY: [0, 0] as [number, number],
  },
  "zoom-out": {
    scaleFrom: 1.06,
    scaleTo: 1.0,
    translateX: [0, 0] as [number, number],
    translateY: [0, 0] as [number, number],
  },
  "pan-left": {
    scaleFrom: 1.05,
    scaleTo: 1.05,
    translateX: [1, -1] as [number, number],
    translateY: [0, 0] as [number, number],
  },
  "pan-right": {
    scaleFrom: 1.05,
    scaleTo: 1.05,
    translateX: [-1, 1] as [number, number],
    translateY: [0, 0] as [number, number],
  },
};

/* ═══════════════ 主组件 ═══════════════ */

const ImageOverlayDefault: React.FC<StyleComponentProps<"image-overlay">> = ({
  data,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = useTheme();

  const kb = KB_CONFIGS[data.kenBurns || "zoom-in"];
  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateRight: "clamp",
  });

  const scale = interpolate(progress, [0, 1], [kb.scaleFrom, kb.scaleTo]);
  const tx = interpolate(progress, [0, 1], kb.translateX);
  const ty = interpolate(progress, [0, 1], kb.translateY);

  // 文字入场动画
  const textP = spring({
    frame: Math.max(0, frame - 8),
    fps,
    config: { damping: 16, stiffness: 90 },
    durationInFrames: 20,
  });

  const position = data.overlayPosition || "bottom";

  return (
    <AbsoluteFill style={{ backgroundColor: "#000", overflow: "hidden" }}>
      {/* 图片层 + Ken Burns */}
      <AbsoluteFill
        style={{
          transform: `scale(${scale}) translate(${tx}%, ${ty}%)`,
        }}
      >
        <Img
          src={staticFile(data.imagePath)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
          }}
        />
      </AbsoluteFill>

      {/* 渐变遮罩层 */}
      {data.overlayText && (
        <AbsoluteFill
          style={{
            background:
              position === "top"
                ? "linear-gradient(to bottom, rgba(0,0,0,0.75) 0%, rgba(0,0,0,0.3) 35%, transparent 60%)"
                : position === "center"
                  ? "radial-gradient(ellipse at center, rgba(0,0,0,0.6) 0%, rgba(0,0,0,0.2) 70%)"
                  : "linear-gradient(to top, rgba(0,0,0,0.75) 0%, rgba(0,0,0,0.3) 35%, transparent 60%)",
            pointerEvents: "none",
          }}
        />
      )}

      {/* 文字叠加层 */}
      {data.overlayText && (
        <AbsoluteFill
          style={{
            display: "flex",
            flexDirection: "column",
            justifyContent:
              position === "top"
                ? "flex-start"
                : position === "center"
                  ? "center"
                  : "flex-end",
            alignItems: "center",
            padding:
              position === "top" ? "80px 120px 0" : "0 120px 80px",
          }}
        >
          <div
            style={{
              fontSize: 36,
              fontWeight: 700,
              color: "#fff",
              fontFamily: t.titleFont,
              textAlign: "center" as const,
              lineHeight: 1.5,
              maxWidth: 1400,
              textShadow: "0 2px 12px rgba(0,0,0,0.5)",
              opacity: interpolate(textP, [0, 1], [0, 1]),
              transform: `translateY(${interpolate(
                textP,
                [0, 1],
                [position === "top" ? -20 : 20, 0],
              )}px)`,
            }}
          >
            {data.overlayText}
          </div>
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};

/* ═══════════════ 注册 ═══════════════ */

registry.register(
  {
    id: "image-overlay.default",
    schema: "image-overlay",
    name: "图片叠加文字",
    description:
      "全屏图片展示，带 Ken Burns 缓慢缩放/平移动效 + 底部渐变遮罩 + 白色文字说明。" +
      "适合展示产品截图、推文截图、新闻配图、数据图表、界面截图等真实画面素材。" +
      "需要提供 image_content 字段，包含 image_path（图片文件路径）和可选的 overlay_text。",
    isDefault: true,
    tags: ["图片", "截图", "叠加", "Ken Burns", "真实素材"],
  },
  ImageOverlayDefault,
);

export { ImageOverlayDefault };
