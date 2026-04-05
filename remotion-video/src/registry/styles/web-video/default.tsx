/**
 * web-video.default — 网络视频片段播放
 *
 * 播放下载后的外部视频片段（产品 demo、发布会等），
 * 带底部文字叠加说明 + 可选滤镜统一视觉风格。
 * 用于 C 类引用素材。
 */

import {
  AbsoluteFill,
  OffthreadVideo,
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

const WebVideoDefault: React.FC<StyleComponentProps<"web-video">> = ({
  data,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  // 文字入场动画
  const textP = spring({
    frame: Math.max(0, frame - 6),
    fps,
    config: { damping: 16, stiffness: 90 },
    durationInFrames: 18,
  });

  // 滤镜样式
  const filterStyle: React.CSSProperties = (() => {
    switch (data.filter) {
      case "desaturate":
        return { filter: "saturate(0.7) contrast(1.05)" };
      case "tint":
        return { filter: "saturate(0.8) sepia(0.1)" };
      default:
        return {};
    }
  })();

  const position = data.overlayPosition || "bottom";

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* 视频播放层 */}
      <AbsoluteFill style={filterStyle}>
        <OffthreadVideo
          src={staticFile(data.videoFile)}
          muted
          style={{
            width: "100%",
            height: "100%",
            objectFit: "contain",
          }}
        />
      </AbsoluteFill>

      {/* 渐变遮罩 + 文字叠加 */}
      {data.overlayText && (
        <>
          <AbsoluteFill
            style={{
              background:
                position === "top"
                  ? "linear-gradient(to bottom, rgba(0,0,0,0.7) 0%, rgba(0,0,0,0.25) 30%, transparent 55%)"
                  : "linear-gradient(to top, rgba(0,0,0,0.7) 0%, rgba(0,0,0,0.25) 30%, transparent 55%)",
              pointerEvents: "none",
            }}
          />
          <AbsoluteFill
            style={{
              display: "flex",
              flexDirection: "column",
              justifyContent: position === "top" ? "flex-start" : "flex-end",
              alignItems: "center",
              padding: position === "top" ? "60px 100px 0" : "0 100px 60px",
            }}
          >
            <div
              style={{
                fontSize: 32,
                fontWeight: 600,
                color: "#fff",
                fontFamily: t.titleFont,
                textAlign: "center" as const,
                lineHeight: 1.5,
                maxWidth: 1400,
                textShadow: "0 2px 10px rgba(0,0,0,0.6)",
                opacity: interpolate(textP, [0, 1], [0, 1]),
                transform: `translateY(${interpolate(
                  textP,
                  [0, 1],
                  [position === "top" ? -15 : 15, 0],
                )}px)`,
              }}
            >
              {data.overlayText}
            </div>
          </AbsoluteFill>
        </>
      )}
    </AbsoluteFill>
  );
};

/* ═══════════════ 注册 ═══════════════ */

registry.register(
  {
    id: "web-video.default",
    schema: "web-video",
    name: "网络视频片段",
    description:
      "播放下载后的外部视频片段（产品 demo、发布会、开源项目演示等），" +
      "带底部文字叠加说明和可选滤镜（desaturate/tint）统一视觉风格。" +
      "用于 C 类引用素材。需要提供 web_video 字段，包含已下载的视频文件路径。",
    isDefault: true,
    tags: ["视频", "外部素材", "Demo", "引用"],
  },
  WebVideoDefault,
);

export { WebVideoDefault };
