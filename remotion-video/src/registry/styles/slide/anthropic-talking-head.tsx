/**
 * slide.anthropic-talking-head — Anthropic 品牌片里的真人头像插入
 *
 * 把用户源视频的一个时间段裁剪出来，嵌进一个圆角白框里，
 * 配 Anthropic 米白波纹背景 + 底部衬线 lower-third 名片。
 * 专门用来在品牌短片里穿插"作者本人讲解"片段，保留真实感。
 *
 * 视频默认 **静音** —— 因为 anthropic_brand 档位是统一的中文 TTS 旁白，
 * 原视频的英文/中文人声会和 TTS 打架。若确实需要保留原音，把 scene_data
 * 里的 muted 设成 false。
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

/**
 * scene_data shape:
 * {
 *   // 以下字段可选；缺失时会从 segment 顶层的 source_video_index/start/end 走。
 *   videoFile?: string;      // public/ 下的文件名。缺失时自动用 sourceVideoFiles[source_video_index]。
 *   clipStart?: number;      // 起始秒数。缺失时用 segment.source_start。
 *   clipEnd?: number;        // 结束秒数。缺失时用 segment.source_end。
 *   muted?: boolean;         // 默认 true。false 时保留原音。
 *
 *   // 画面元素：
 *   caption?: string;        // lower-third 主文字（人名，如 "Lewis Menelaws"）
 *   subtitle?: string;       // lower-third 副文字（角色/标签，如 "Education"）
 *   cornerNote?: string;     // 右上角角标（如 "GUEST" / "02:15"）
 *   framePadding?: number;   // 窗口外边距，默认 120
 *   accent?: string;         // 可选主题色覆盖（默认用 theme.accent 珊瑚红）
 * }
 */

interface TalkingHeadSceneData {
  videoFile?: string;
  clipStart?: number;
  clipEnd?: number;
  muted?: boolean;
  caption?: string;
  subtitle?: string;
  cornerNote?: string;
  framePadding?: number;
  accent?: string;
  __source?: {
    videoFile?: string;
    videoFiles?: string[];
    videoFileMap?: Record<string, string>;
    start?: number;
    end?: number;
    channel?: string;
  };
}

/** 用 scene_data.__source.videoFileMap 把用户写的相对路径解析到实际落地路径 */
function resolveVideoPath(
  userPath: string,
  map?: Record<string, string>,
): string {
  if (!map || !userPath) return userPath;
  if (map[userPath]) return map[userPath];
  const mp4 = userPath.replace(/\.(mov|webm|mkv|avi)$/i, ".mp4");
  if (map[mp4]) return map[mp4];
  return userPath;
}

const AnthropicTalkingHead: React.FC<StyleComponentProps<"slide">> = ({
  data,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  const sd = (data.scene_data || {}) as TalkingHeadSceneData;
  const src = sd.__source || {};

  // 决议视频文件 / 时间范围
  // 优先级：scene_data.videoFile (显式) > __source.videoFile (dispatcher 注入的 source_0)
  // 用 videoFileMap 把相对路径 (如 "talking/lecture.mp4") 解析到实际落地路径
  const rawVideoFile = sd.videoFile || src.videoFile || "";
  const videoFile = resolveVideoPath(rawVideoFile, src.videoFileMap);
  const clipStart = sd.clipStart ?? src.start ?? 0;
  const clipEnd = sd.clipEnd ?? src.end ?? clipStart + 8;
  const muted = sd.muted !== false;
  const accent = sd.accent || t.accent;
  const framePadding = sd.framePadding ?? 120;

  // 入场动画：整体从 0.96 缓慢到 1.0 + 淡入，不做 scale 避免字幕抖动
  const enter = spring({
    frame,
    fps,
    config: { damping: 18, stiffness: 75 },
    durationInFrames: 24,
  });

  // lower-third 单独淡入，晚 10 帧
  const lower = spring({
    frame: Math.max(0, frame - 12),
    fps,
    config: { damping: 20, stiffness: 85 },
    durationInFrames: 22,
  });

  const caption = sd.caption || data.title || "";
  const subtitle = sd.subtitle || (data.bullet_points && data.bullet_points[0]) || "";
  const cornerNote = sd.cornerNote || "";

  // 没有视频文件时的降级显示
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
            letterSpacing: "-0.01em",
          }}
        >
          （缺少源视频）
        </div>
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill>
      <WavyPaperBg />

      {/* 视频窗口：居中圆角白框 + 柔和阴影 */}
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
        <div
          style={{
            width: "100%",
            height: "100%",
            borderRadius: 18,
            overflow: "hidden",
            position: "relative",
            boxShadow:
              "0 40px 80px rgba(30,24,18,0.18), 0 16px 30px rgba(30,24,18,0.08), 0 0 0 1px rgba(0,0,0,0.06)",
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

          {/* 顶部到底部的淡淡暗角 */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              background:
                "linear-gradient(to bottom, rgba(0,0,0,0.05) 0%, transparent 20%, transparent 60%, rgba(0,0,0,0.35) 100%)",
              pointerEvents: "none",
            }}
          />

          {/* 右上角 cornerNote */}
          {cornerNote && (
            <div
              style={{
                position: "absolute",
                top: 20,
                right: 24,
                padding: "6px 12px",
                borderRadius: 4,
                backgroundColor: "rgba(255,255,255,0.94)",
                color: "#1a1a1a",
                fontFamily: "'SF Pro Text', -apple-system, sans-serif",
                fontSize: 12,
                fontWeight: 600,
                letterSpacing: "0.05em",
                opacity: interpolate(enter, [0, 1], [0, 1]),
              }}
            >
              {cornerNote}
            </div>
          )}

          {/* 底部 lower-third 卡片 */}
          {(caption || subtitle) && (
            <div
              style={{
                position: "absolute",
                left: 36,
                bottom: 32,
                padding: "14px 22px",
                backgroundColor: "rgba(255,255,255,0.96)",
                borderRadius: 4,
                borderLeft: `3px solid ${accent}`,
                boxShadow: "0 10px 24px rgba(30,24,18,0.15)",
                opacity: interpolate(lower, [0, 1], [0, 1]),
                transform: `translateX(${interpolate(lower, [0, 1], [-18, 0])}px)`,
              }}
            >
              {caption && (
                <div
                  style={{
                    fontFamily: t.titleFont,
                    fontSize: 26,
                    fontWeight: 600,
                    color: "#1a1a1a",
                    lineHeight: 1.1,
                    letterSpacing: "-0.01em",
                  }}
                >
                  {caption}
                </div>
              )}
              {subtitle && (
                <div
                  style={{
                    marginTop: 4,
                    fontFamily: "'SF Pro Text', -apple-system, sans-serif",
                    fontSize: 13,
                    color: "#666",
                  }}
                >
                  {subtitle}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};

registry.register(
  {
    id: "slide.anthropic-talking-head",
    schema: "slide",
    name: "Anthropic 真人头像插入",
    description:
      "从源视频裁剪一段真人出镜片段，嵌进 Anthropic 米白风格的圆角白框 + 底部衬线 lower-third 名片。用于品牌短片中穿插『作者本人讲解』片段。默认静音以避免和 TTS 冲突，可通过 scene_data.muted=false 保留原音。",
    isDefault: false,
    tags: ["anthropic", "talking-head", "真人", "源视频", "插入片段"],
  },
  AnthropicTalkingHead,
);
export { AnthropicTalkingHead };
