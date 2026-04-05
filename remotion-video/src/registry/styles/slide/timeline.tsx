/**
 * slide.timeline — 垂直时间线
 *
 * bullet_points 格式: "2024.03: Claude 3 发布" → 时间节点 + 描述。
 * 适合版本发布、技术演进、事件回顾。
 */

import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import React from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";

const DOT_COLORS = ["#4a9eff", "#a882ff", "#22c55e", "#eab308", "#f472b6", "#38bdf8"];

function parseEvent(line: string): { time: string; desc: string } {
  const m = line.match(/^(.+?)[:：]\s*(.+)$/);
  if (m) return { time: m[1].trim(), desc: m[2].trim() };
  return { time: "", desc: line };
}

const SlideTimeline: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();
  const events = data.bullet_points.map(parseEvent);

  return (
    <AbsoluteFill style={{ background: t.bg, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "50px 100px", fontFamily: t.bodyFont }}>
      {/* 标题 */}
      <div style={{ fontSize: 32, fontWeight: 700, color: t.text, marginBottom: 48, fontFamily: t.titleFont, opacity: interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp", extrapolateLeft: "clamp" }) }}>
        {data.title}
      </div>
      {/* 时间线 */}
      <div style={{ position: "relative", paddingLeft: 80 }}>
        {/* 竖线 */}
        <div style={{ position: "absolute", left: 39, top: 0, bottom: 0, width: 2, background: t.surfaceBorder }} />
        {events.map((ev, i) => {
          const delay = 8 + i * 10;
          const p = spring({ frame: Math.max(0, frame - delay), fps, config: { damping: 14, stiffness: 100 }, durationInFrames: 18 });
          const dotColor = DOT_COLORS[i % DOT_COLORS.length];
          return (
            <div key={i} style={{
              display: "flex", alignItems: "flex-start", gap: 24, marginBottom: 36,
              opacity: interpolate(p, [0, 1], [0, 1]), transform: `translateX(${interpolate(p, [0, 1], [-30, 0])}px)`,
            }}>
              {/* 圆点 */}
              <div style={{ position: "absolute", left: 30, width: 20, height: 20, borderRadius: "50%", background: dotColor, border: `3px solid ${t.bg}`, boxShadow: `0 0 12px ${dotColor}66`, marginTop: 4 }} />
              {/* 内容 */}
              <div>
                {ev.time && <div style={{ fontSize: 16, color: dotColor, fontWeight: 700, fontFamily: t.monoFont, marginBottom: 4 }}>{ev.time}</div>}
                <div style={{ fontSize: 22, color: t.text, fontWeight: 500, maxWidth: 900 }}>{ev.desc}</div>
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

registry.register({ id: "slide.timeline", schema: "slide", name: "时间线", description: "垂直时间线，bullet_points 格式: '2024.03: Claude 3 发布'。每个时间节点逐个出现，带彩色圆点和光晕。适合版本发布、技术演进。", isDefault: false, tags: ["时间线", "历史", "版本", "changelog"] }, SlideTimeline);
export { SlideTimeline };
