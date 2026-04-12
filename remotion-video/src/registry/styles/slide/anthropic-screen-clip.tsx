/**
 * slide.anthropic-screen-clip — Anthropic 风格屏幕录制片段播放
 *
 * 从项目源视频里裁一段屏幕录制，嵌进米白 macOS 窗框里，支持归一化坐标
 * 的高亮区标注（红框 / 圆圈），默认静音以配合 TTS 中文旁白叠层。
 *
 * 使用场景：技术解说片里播用户自己录的 demo 片段。和 talking-head 组件
 * 配对使用，构成 [人讲解 ↔ 屏幕演示] 的解说片标准结构。
 *
 * 数据来源（任一即可）：
 *
 * A) scene_data.videoFile 直接指定相对路径（推荐）：
 *    { videoFile: "recordings/demo-1.mov", clipStart: 0, clipEnd: 30 }
 *    render.mjs 会在 sources/{project_id}/ 递归扫描所有视频，保持目录结构
 *    拷到 public/ （并转码 AV1/VP9/MOV → H.264）。组件通过 __source.videoFileMap
 *    查到实际落地路径。
 *
 * B) 退化到顶层 source_video_index/start/end（兼容旧脚本）：
 *    segment.source_video_index = 0, source_start = 5, source_end = 20
 */

import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Video } from "@remotion/media";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";
import { WavyPaperBg } from "../../components/WavyPaperBg";
import { MacosWindow } from "../../components/MacosWindow";

/**
 * 高亮区（矩形或圆圈标注）。坐标用归一化 0-1，相对 16:9 视频显示区域。
 *
 * 示例：
 *   { x: 0.47, y: 0.56, w: 0.18, h: 0.08, start: 60, end: 180, label: "关键按钮" }
 *   → 视频的中下偏右一个矩形框，在 clip 内第 60-180 帧之间显示
 */
interface HighlightBox {
  /** 左上角归一化 x (0-1) */
  x: number;
  /** 左上角归一化 y (0-1) */
  y: number;
  /** 宽度归一化 (0-1) */
  w: number;
  /** 高度归一化 (0-1) */
  h: number;
  /** 相对 clip 起始的开始帧，默认 0（clip 一开始就出现）*/
  start?: number;
  /** 相对 clip 起始的结束帧，默认 clip 结束（一直保留） */
  end?: number;
  /** 形状：rect=矩形 / circle=圆圈（半径 = min(w,h)/2）*/
  kind?: "rect" | "circle";
  /** 边框颜色，默认主题珊瑚红 */
  color?: string;
  /** 可选的标注文字（显示在框旁边） */
  label?: string;
}

interface ScreenClipSceneData {
  // 视频源
  videoFile?: string;
  clipStart?: number;
  clipEnd?: number;
  muted?: boolean;

  // 画面装饰
  windowTitle?: string;
  label?: string;        // 左下小卡片说明
  cornerNote?: string;   // 右上角徽标
  framePadding?: number; // 窗口外边距（默认 100）

  // 高亮区
  highlights?: HighlightBox[];

  // dispatcher 注入（不用手填）
  __source?: {
    videoFile?: string;
    videoFiles?: string[];
    videoFileMap?: Record<string, string>;
    start?: number;
    end?: number;
  };
}

/** 用 scene_data.__source.videoFileMap 把用户写的相对路径解析到实际落地路径 */
function resolveVideoPath(
  userPath: string,
  map?: Record<string, string>,
): string {
  if (!map || !userPath) return userPath;
  // 直接命中
  if (map[userPath]) return map[userPath];
  // 尝试替换扩展名（用户写 .mov 但实际落地是 .mp4）
  const mp4 = userPath.replace(/\.(mov|webm|mkv|avi)$/i, ".mp4");
  if (map[mp4]) return map[mp4];
  return userPath;
}

const AnthropicScreenClip: React.FC<StyleComponentProps<"slide">> = ({
  data,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  const sd = (data.scene_data || {}) as ScreenClipSceneData;
  const src = sd.__source || {};

  // 视频源决议
  const rawPath = sd.videoFile || src.videoFile || "";
  const videoFile = resolveVideoPath(rawPath, src.videoFileMap);
  const clipStart = sd.clipStart ?? src.start ?? 0;
  const clipEnd = sd.clipEnd ?? src.end ?? clipStart + 30;
  const muted = sd.muted !== false;

  const windowTitle = sd.windowTitle || "";
  const label = sd.label || "";
  const cornerNote = sd.cornerNote || "";
  const framePadding = sd.framePadding ?? 100;
  const highlights = sd.highlights || [];

  // 整体轻微淡入（硬切风格不做 scale，避免文字抖动）
  const enter = spring({
    frame,
    fps,
    config: { damping: 20, stiffness: 120 },
    durationInFrames: 6,
  });

  // 降级：没视频文件时显示提示
  if (!videoFile) {
    return (
      <AbsoluteFill>
        <WavyPaperBg />
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: t.titleFont,
            fontSize: 42,
            color: t.textDim,
          }}
        >
          （缺少屏幕录制源视频）
        </div>
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill>
      <WavyPaperBg />

      <div
        style={{
          position: "absolute",
          inset: framePadding,
          opacity: interpolate(enter, [0, 1], [0, 1]),
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <MacosWindow
          width={1920 - framePadding * 2}
          height={1080 - framePadding * 2}
          title={windowTitle}
          variant="light"
          bodyStyle={{
            backgroundColor: "#0f0f10",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {/* 16:9 视频容器 —— 高亮区坐标相对这个容器 */}
          <div
            style={{
              width: "100%",
              aspectRatio: "16 / 9",
              position: "relative",
              overflow: "hidden",
              backgroundColor: "#000",
            }}
          >
            <Video
              src={staticFile(videoFile)}
              trimBefore={Math.round(clipStart * fps)}
              trimAfter={Math.round(clipEnd * fps)}
              playbackRate={1}
              muted={muted}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
              }}
            />

            {/* 高亮区叠层 */}
            {highlights.map((box, i) => {
              const startFrame = box.start ?? 0;
              const endFrame =
                box.end ?? Math.round((clipEnd - clipStart) * fps);
              if (frame < startFrame || frame >= endFrame) return null;

              const color = box.color || t.accent;
              const kind = box.kind || "rect";

              // 入场 spring (12 帧)
              const appear = spring({
                frame: frame - startFrame,
                fps,
                config: { damping: 14, stiffness: 140 },
                durationInFrames: 12,
              });

              // 珊瑚红脉冲呼吸 (整个显示期间)
              const pulseT = (frame - startFrame) * 0.08;
              const pulse = 1 + Math.sin(pulseT) * 0.04;

              const leftPct = `${box.x * 100}%`;
              const topPct = `${box.y * 100}%`;
              const widthPct = `${box.w * 100}%`;
              const heightPct = `${box.h * 100}%`;

              const commonStyle: React.CSSProperties = {
                position: "absolute",
                left: leftPct,
                top: topPct,
                width: widthPct,
                height: heightPct,
                pointerEvents: "none",
                opacity: interpolate(appear, [0, 1], [0, 1]),
                transform: `scale(${interpolate(appear, [0, 1], [0.6, 1]) * pulse})`,
                transformOrigin: "center center",
              };

              return (
                <div key={i}>
                  {kind === "rect" ? (
                    <div
                      style={{
                        ...commonStyle,
                        border: `4px solid ${color}`,
                        borderRadius: 6,
                        boxShadow: `0 0 24px ${color}55, 0 0 0 4px ${color}22`,
                      }}
                    />
                  ) : (
                    <div
                      style={{
                        ...commonStyle,
                        border: `4px solid ${color}`,
                        borderRadius: "50%",
                        boxShadow: `0 0 24px ${color}55, 0 0 0 4px ${color}22`,
                      }}
                    />
                  )}
                  {/* 高亮文字标注 */}
                  {box.label && (
                    <div
                      style={{
                        position: "absolute",
                        left: leftPct,
                        top: `calc(${topPct} + ${heightPct} + 8px)`,
                        padding: "6px 12px",
                        backgroundColor: "rgba(255,255,255,0.96)",
                        color: "#1a1a1a",
                        border: `2px solid ${color}`,
                        borderRadius: 4,
                        fontFamily:
                          "'SF Pro Text', -apple-system, sans-serif",
                        fontSize: 16,
                        fontWeight: 600,
                        opacity: interpolate(appear, [0, 1], [0, 1]),
                        pointerEvents: "none",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {box.label}
                    </div>
                  )}
                </div>
              );
            })}

            {/* 左下说明卡 */}
            {label && (
              <div
                style={{
                  position: "absolute",
                  left: 28,
                  bottom: 24,
                  padding: "10px 16px",
                  backgroundColor: "rgba(255,255,255,0.96)",
                  borderRadius: 4,
                  borderLeft: `3px solid ${t.accent}`,
                  fontFamily: t.titleFont,
                  fontSize: 20,
                  fontWeight: 600,
                  color: "#1a1a1a",
                  boxShadow: "0 8px 18px rgba(30,24,18,0.18)",
                  letterSpacing: "-0.005em",
                  opacity: interpolate(enter, [0, 1], [0, 1]),
                }}
              >
                {label}
              </div>
            )}

            {/* 右上角徽标 */}
            {cornerNote && (
              <div
                style={{
                  position: "absolute",
                  top: 20,
                  right: 24,
                  padding: "6px 12px",
                  backgroundColor: "rgba(255,255,255,0.94)",
                  color: "#1a1a1a",
                  fontFamily: "'SF Pro Text', -apple-system, sans-serif",
                  fontSize: 12,
                  fontWeight: 600,
                  letterSpacing: "0.05em",
                  borderRadius: 4,
                  opacity: interpolate(enter, [0, 1], [0, 1]),
                }}
              >
                {cornerNote}
              </div>
            )}
          </div>
        </MacosWindow>
      </div>
    </AbsoluteFill>
  );
};

registry.register(
  {
    id: "slide.anthropic-screen-clip",
    schema: "slide",
    name: "Anthropic 屏幕录制片段",
    description:
      "从项目源视频裁剪一段屏幕录制，嵌进米白 macOS 窗框里，支持归一化 0-1 坐标的高亮区标注 (矩形/圆圈)。默认静音配合 TTS 中文旁白。用于技术解说片的演示片段。",
    isDefault: false,
    tags: ["anthropic", "screen-clip", "屏幕录制", "演示", "高亮", "macOS"],
  },
  AnthropicScreenClip,
);
export { AnthropicScreenClip };
