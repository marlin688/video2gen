/**
 * slide.web-scroll — 网页滚动浏览 + 关键句高亮
 *
 * 模拟浏览器查看网页的体验：
 * - 顶部 Chrome 风格地址栏（显示 URL）
 * - 内容区：长图从 scrollFrom 滚动到 scrollTo
 * - 高亮：在指定时间范围内，对指定 Y 区域显示黄色半透明背景
 * - 底部：overlay 文字（可选）
 *
 * scene_data shape:
 * {
 *   fullPageImage: string,        // 长图路径（相对 public/）
 *   url?: string,                 // 地址栏显示的 URL
 *   scrollFrom?: number,          // 滚动起始位置（0-1，默认 0）
 *   scrollTo?: number,            // 滚动结束位置（0-1，默认 0.5）
 *   scrollDuration?: number,      // 滚动动画占段落时长比例（0-1，默认 0.3 即前30%滚完后停住）
 *   overlayText?: string,         // 底部叠加文字
 *   highlights?: Array<{
 *     y: number,                  // 高亮区域在长图中的 Y 位置（0-1）
 *     height: number,             // 高亮区域高度（0-1）
 *     startPct: number,           // 开始显示时间（0-1 相对段落时长）
 *     endPct: number,             // 结束显示时间（0-1）
 *     label?: string,             // 高亮标注文字（可选）
 *     selectedText?: string,      // 模拟鼠标选中的文字（蓝色背景从左到右展开）
 *   }>,
 * }
 */

import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";

/* ═══════════════ 类型 ═══════════════ */

interface Highlight {
  y: number;
  height: number;
  startPct: number;
  endPct: number;
  label?: string;
  selectedText?: string;
}

interface WebScrollSceneData {
  fullPageImage?: string;
  url?: string;
  scrollFrom?: number;
  scrollTo?: number;
  scrollDuration?: number;
  overlayText?: string;
  highlights?: Highlight[];
}

/* ═══════════════ 浏览器框 ═══════════════ */

const TOOLBAR_HEIGHT = 56;
const CONTENT_HEIGHT = 1080 - TOOLBAR_HEIGHT;

const BrowserToolbar: React.FC<{ url: string }> = ({ url }) => {
  return (
    <div
      style={{
        height: TOOLBAR_HEIGHT,
        background: "#f1f3f4",
        borderBottom: "1px solid #ddd",
        display: "flex",
        alignItems: "center",
        padding: "0 16px",
        gap: 12,
      }}
    >
      {/* 红绿黄三点 */}
      <div style={{ display: "flex", gap: 8 }}>
        {["#ff5f57", "#febc2e", "#28c840"].map((c) => (
          <div
            key={c}
            style={{
              width: 12,
              height: 12,
              borderRadius: "50%",
              background: c,
            }}
          />
        ))}
      </div>
      {/* 地址栏 */}
      <div
        style={{
          flex: 1,
          background: "#fff",
          borderRadius: 20,
          padding: "6px 16px",
          fontSize: 14,
          fontFamily: "'SF Pro Text', -apple-system, sans-serif",
          color: "#555",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          border: "1px solid #e0e0e0",
        }}
      >
        <span style={{ color: "#28a745", marginRight: 6 }}>🔒</span>
        {url}
      </div>
    </div>
  );
};

/* ═══════════════ 主组件 ═══════════════ */

const WebScroll: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = useTheme();

  const sceneData = (data.scene_data || {}) as WebScrollSceneData;
  const imgSrc = sceneData.fullPageImage || "";
  const url = sceneData.url || "";
  const scrollFrom = sceneData.scrollFrom ?? 0;
  const scrollTo = sceneData.scrollTo ?? 0.5;
  const overlayText = sceneData.overlayText || data.title || "";
  const highlights = sceneData.highlights || [];

  // 滚动逻辑：前 30% 时间滚动到目标位置，后 70% 停住让观众看
  const scrollEndPct = sceneData.scrollDuration ?? 0.3;
  const scrollFrames = Math.round(durationInFrames * scrollEndPct);

  // 滚动阶段：0→1（仅在前 scrollEndPct 时间内）
  const rawScrollProgress = interpolate(
    frame,
    [0, scrollFrames],
    [0, 1],
    { extrapolateRight: "clamp" },
  );
  // ease-out 缓动（快速启动，平滑减速停住）
  const easedProgress = 1 - Math.pow(1 - rawScrollProgress, 3);

  const scrollPosition = interpolate(
    easedProgress,
    [0, 1],
    [scrollFrom, scrollTo],
  );

  // 图片高度设定（长图拉伸到视口宽度 1920，高度按比例；我们用 translateY 百分比控制滚动）
  // 假设长图高度 >> 视口高度，用百分比定位
  const translateY = -scrollPosition * 100;

  // 底部 overlay 文字入场
  const textSpring = spring({
    frame: Math.max(0, frame - 12),
    fps,
    config: { damping: 16, stiffness: 90 },
    durationInFrames: 20,
  });

  return (
    <AbsoluteFill style={{ background: "#f1f3f4", overflow: "hidden" }}>
      {/* 浏览器工具栏 */}
      <BrowserToolbar url={url} />

      {/* 内容区 */}
      <div
        style={{
          position: "absolute",
          top: TOOLBAR_HEIGHT,
          left: 0,
          right: 0,
          bottom: 0,
          overflow: "hidden",
        }}
      >
        {/* 长图 + 滚动 + 高亮：同一容器，高度由图片撑开 */}
        {imgSrc && (
          <div
            style={{
              position: "relative",
              width: "100%",
              transform: `translateY(${translateY}%)`,
            }}
          >
            {/* 图片：宽度 100%，高度自然比例 */}
            <Img
              src={staticFile(imgSrc)}
              style={{
                display: "block",
                width: "100%",
              }}
            />

            {/* 高亮层：absolute 覆盖图片，百分比相对于同一容器（= 图片高度） */}
            <div
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                height: "100%",
                pointerEvents: "none",
              }}
            >
              {highlights.map((h, i) => {
                const pct = frame / durationInFrames;

                // 淡入淡出
                const fadeIn = interpolate(
                  pct,
                  [h.startPct, h.startPct + 0.05],
                  [0, 1],
                  { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
                );
                const fadeOut = interpolate(
                  pct,
                  [h.endPct - 0.05, h.endPct],
                  [1, 0],
                  { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
                );
                const opacity = Math.min(fadeIn, fadeOut);

                if (opacity <= 0) return null;

                // 鼠标选中动画进度（在高亮可见期间从 0→1 展开）
                const selectProgress = h.selectedText
                  ? interpolate(
                      pct,
                      [h.startPct, h.startPct + (h.endPct - h.startPct) * 0.4],
                      [0, 1],
                      { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
                    )
                  : 0;

                return (
                  <div
                    key={i}
                    style={{
                      position: "absolute",
                      top: `${h.y * 100}%`,
                      left: "3%",
                      right: "3%",
                      height: `${h.height * 100}%`,
                      background: h.selectedText
                        ? "transparent"
                        : `rgba(255, 230, 0, ${0.35 * opacity})`,
                      borderRadius: h.selectedText ? 0 : 6,
                      border: h.selectedText
                        ? "none"
                        : `2px solid rgba(255, 200, 0, ${0.6 * opacity})`,
                      display: "flex",
                      alignItems: "center",
                      overflow: "hidden",
                    }}
                  >
                    {/* 模拟鼠标选中效果 */}
                    {h.selectedText && (() => {
                      // 单行（height < 0.008）从左到右展开；多行从上到下展开
                      const isMultiLine = h.height > 0.008;
                      return (
                        <>
                          <div
                            style={{
                              position: "absolute",
                              top: 0,
                              left: 0,
                              // 多行：宽度 100%，高度从上到下展开
                              // 单行：高度 100%，宽度从左到右展开
                              width: isMultiLine ? "100%" : `${selectProgress * 100}%`,
                              height: isMultiLine ? `${selectProgress * 100}%` : "100%",
                              background: `rgba(51, 144, 255, ${0.35 * opacity})`,
                              borderRadius: 2,
                            }}
                          />
                          {/* 模拟文本光标（仅单行） */}
                          {!isMultiLine && selectProgress < 1 && selectProgress > 0 && (
                            <div
                              style={{
                                position: "absolute",
                                left: `${selectProgress * 100}%`,
                                top: "5%",
                                bottom: "5%",
                                width: 2,
                                background: `rgba(0, 0, 0, ${opacity * (Math.floor(pct * 200) % 2 === 0 ? 1 : 0)})`,
                              }}
                            />
                          )}
                        </>
                      );
                    })()}
                    {/* 普通高亮标注（无 selectedText 时） */}
                    {!h.selectedText && h.label && (
                      <span
                        style={{
                          marginLeft: "auto",
                          background: `rgba(0, 0, 0, ${0.75 * opacity})`,
                          color: "#ffe600",
                          padding: "4px 14px",
                          borderRadius: 4,
                          fontSize: 18,
                          fontWeight: 600,
                          fontFamily:
                            "'SF Pro Text', -apple-system, sans-serif",
                          opacity,
                        }}
                      >
                        {h.label}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* 底部渐变遮罩 + 文字 */}
      {overlayText && (
        <>
          <div
            style={{
              position: "absolute",
              bottom: 0,
              left: 0,
              right: 0,
              height: 200,
              background:
                "linear-gradient(transparent, rgba(0,0,0,0.7), rgba(0,0,0,0.85))",
              pointerEvents: "none",
            }}
          />
          <div
            style={{
              position: "absolute",
              bottom: 40,
              left: 60,
              right: 60,
              opacity: textSpring,
              transform: `translateY(${interpolate(textSpring, [0, 1], [20, 0])}px)`,
            }}
          >
            {overlayText.split("\n").map((line, i) => (
              <div
                key={i}
                style={{
                  color: "#fff",
                  fontSize: i === 0 ? 32 : 28,
                  fontWeight: i === 0 ? 700 : 500,
                  fontFamily: "'SF Pro Display', -apple-system, sans-serif",
                  textShadow: "0 2px 8px rgba(0,0,0,0.5)",
                  marginBottom: 8,
                  lineHeight: 1.4,
                }}
              >
                {line}
              </div>
            ))}
          </div>
        </>
      )}
    </AbsoluteFill>
  );
};

/* ═══════════════ 注册 ═══════════════ */

registry.register(
  {
    id: "slide.web-scroll",
    schema: "slide",
    name: "网页滚动浏览",
    description:
      "浏览器框 + 长图滚动 + 黄色高亮标注关键句，适合展示网页条款、文档、新闻报道",
    isDefault: false,
    tags: ["web", "scroll", "highlight", "browser"],
  },
  WebScroll,
);

export default WebScroll;
