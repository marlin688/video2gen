/**
 * slide.live-counter — 数字滚动动画
 *
 * 大数字从起始值滚到目标值，适合展示效率提升、成本降低。
 * bullet_points 格式: "200行 → 0行" 或 "2小时 → 10秒"。
 * title = 场景描述。
 */

import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import React from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";

interface CounterItem { from: number; to: number; unit: string; label: string }

function parseCounter(line: string): CounterItem {
  // "200行 → 0行" or "2小时 → 10秒" or "手动写200行代码 → Claude 10秒搞定"
  const arrow = line.match(/(.+?)\s*[→>]\s*(.+)/);
  if (!arrow) return { from: 0, to: 0, unit: "", label: line };

  const left = arrow[1].trim();
  const right = arrow[2].trim();

  const numL = left.match(/([\d.]+)\s*(\S*)/);
  const numR = right.match(/([\d.]+)\s*(\S*)/);

  return {
    from: numL ? parseFloat(numL[1]) : 0,
    to: numR ? parseFloat(numR[1]) : 0,
    unit: numR?.[2] || numL?.[2] || "",
    label: left.replace(/[\d.]+\s*\S*/, "").trim() || right.replace(/[\d.]+\s*\S*/, "").trim() || line,
  };
}

const SlideLiveCounter: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  const counters = data.bullet_points.map(parseCounter);

  return (
    <AbsoluteFill style={{ background: t.bg, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "60px 100px" }}>
      {/* 标题 */}
      <div style={{
        fontSize: 32, fontWeight: 700, color: t.text, fontFamily: t.titleFont,
        marginBottom: 50, textAlign: "center" as const,
        opacity: interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp", extrapolateLeft: "clamp" }),
      }}>
        {data.title}
      </div>

      <div style={{ display: "flex", gap: 60, justifyContent: "center", flexWrap: "wrap" as const }}>
        {counters.map((item, i) => {
          const delay = 10 + i * 12;
          const countP = spring({ frame: Math.max(0, frame - delay), fps, config: { damping: 22, stiffness: 50 }, durationInFrames: 40 });
          const enterP = spring({ frame: Math.max(0, frame - delay), fps, config: { damping: 14, stiffness: 100 }, durationInFrames: 15 });

          const current = interpolate(countP, [0, 1], [item.from, item.to]);
          const isDecrease = item.to < item.from;
          const color = isDecrease ? t.success : t.accent;

          return (
            <div key={i} style={{
              display: "flex", flexDirection: "column", alignItems: "center", gap: 12,
              opacity: interpolate(enterP, [0, 1], [0, 1]),
              transform: `scale(${interpolate(enterP, [0, 1], [0.8, 1])})`,
            }}>
              {/* 起始值（小字删除线） */}
              <div style={{ fontSize: 28, color: t.textMuted, textDecoration: "line-through" as const, fontFamily: t.monoFont }}>
                {item.from}{item.unit}
              </div>
              {/* 箭头 */}
              <div style={{ fontSize: 24, color: t.textMuted }}>↓</div>
              {/* 当前滚动值 */}
              <div style={{
                fontSize: 80, fontWeight: 900, color,
                fontFamily: t.titleFont, lineHeight: 1,
                letterSpacing: "-0.03em",
              }}>
                {Math.round(current)}{item.unit}
              </div>
              {/* 标签 */}
              <div style={{ fontSize: 20, color: t.textDim, fontFamily: t.bodyFont, textAlign: "center" as const }}>
                {item.label || `${item.from}${item.unit} → ${item.to}${item.unit}`}
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

registry.register({ id: "slide.live-counter", schema: "slide", name: "数字滚动", description: "大数字从起始值滚到目标值。bullet_points 格式: '200行 → 0行'。适合展示效率提升(2h→10s)、成本降低($200→$0)。", isDefault: false, tags: ["数字", "动画", "滚动", "效率", "降低"] }, SlideLiveCounter);
export { SlideLiveCounter };
