/**
 * slide.fireship-title — Fireship 风格大字标题卡
 *
 * 纯黑背景 + 超大粗体白字，零装饰，瞬间出现。
 * 用于快节奏硬切视频中的信息锚点。
 *
 * 数据约定（复用 SlideData）：
 *   title       — 主文字（支持 <hl>高亮</hl> 标记变红色）
 *   bullet_points[0] — 可选副标题（小字）
 */

import React from "react";
import { AbsoluteFill } from "remotion";
import { registry } from "../../registry";
import type { StyleComponentProps } from "../../types";

const BG = "#1a1a1a";
const TEXT_COLOR = "#f0e6d3";
const HIGHLIGHT_COLOR = "#ff3333";

/** 解析 <hl>...</hl> 标记 */
function renderTitle(text: string) {
  const parts = text.split(/(<hl>.*?<\/hl>)/g);
  return parts.map((part, i) => {
    const match = part.match(/^<hl>(.*)<\/hl>$/);
    if (match) {
      return (
        <span key={i} style={{ color: HIGHLIGHT_COLOR }}>
          {match[1]}
        </span>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

const FireshipTitle: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const { title, bullet_points } = data;
  const subtitle = bullet_points?.[0];

  // 根据文字长度自适应字号
  const len = title.length;
  const fontSize = len <= 8 ? 120 : len <= 15 ? 96 : len <= 25 ? 72 : 56;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: BG,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        padding: "40px 80px",
      }}
    >
      {/* 主标题 — 瞬间出现，不带任何动画 */}
      <div
        style={{
          fontSize,
          fontWeight: 900,
          fontFamily: "'Impact', 'Arial Black', 'Noto Sans SC', sans-serif",
          color: TEXT_COLOR,
          textAlign: "center",
          lineHeight: 1.15,
          letterSpacing: "0.02em",
          textTransform: "uppercase",
          maxWidth: "90%",
        }}
      >
        {renderTitle(title)}
      </div>

      {/* 可选副标题 */}
      {subtitle && (
        <div
          style={{
            marginTop: 24,
            fontSize: 28,
            fontWeight: 400,
            fontFamily: "'SF Pro Display', 'Noto Sans SC', system-ui, sans-serif",
            color: "rgba(240, 230, 211, 0.6)",
            textAlign: "center",
            letterSpacing: "0.05em",
          }}
        >
          {subtitle}
        </div>
      )}
    </AbsoluteFill>
  );
};

registry.register(
  {
    id: "slide.fireship-title",
    schema: "slide",
    name: "Fireship 大字标题",
    description: "纯黑背景 + 超大粗体白字，零装饰，硬切节奏",
    isDefault: false,
    tags: ["标题", "快节奏", "硬切"],
  },
  FireshipTitle,
);
