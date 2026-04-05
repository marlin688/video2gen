/**
 * slide.compare-table — 左右对比表格
 *
 * 将 bullet_points 解析为对比行：格式 "A: xxx → B: yyy" 或 "feature: A值 vs B值"。
 * 标题自动拆为两列表头（含 "vs" 时拆分）。
 * 适合工具评测、方案对比、Before/After。
 */

import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import React from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";

function parseHeaders(title: string): [string, string] {
  const vs = title.match(/(.+?)\s+vs\.?\s+(.+)/i);
  if (vs) return [vs[1].trim(), vs[2].trim()];
  return ["Before", "After"];
}

function parseRow(line: string): { label: string; left: string; right: string } {
  // "feature: leftVal → rightVal"
  const arrow = line.match(/^(.+?):\s*(.+?)\s*[→→>]\s*(.+)$/);
  if (arrow) return { label: arrow[1].trim(), left: arrow[2].trim(), right: arrow[3].trim() };
  // "feature: leftVal vs rightVal"
  const vs = line.match(/^(.+?):\s*(.+?)\s+vs\.?\s+(.+)$/i);
  if (vs) return { label: vs[1].trim(), left: vs[2].trim(), right: vs[3].trim() };
  // fallback: split by |
  const pipe = line.split("|");
  if (pipe.length >= 3) return { label: pipe[0].trim(), left: pipe[1].trim(), right: pipe[2].trim() };
  return { label: line, left: "", right: "" };
}

const SlideCompareTable: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();
  const [headerL, headerR] = parseHeaders(data.title);
  const rows = data.bullet_points.map(parseRow);

  return (
    <AbsoluteFill style={{ background: t.bg, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "60px 120px", fontFamily: t.bodyFont }}>
      {/* 表格 */}
      <div style={{ width: "100%", maxWidth: 1400, borderRadius: 16, overflow: "hidden", border: `1px solid ${t.surfaceBorder}` }}>
        {/* 表头 */}
        <div style={{ display: "flex", background: t.surface, borderBottom: `1px solid ${t.surfaceBorder}`, opacity: interpolate(spring({ frame, fps, config: { damping: 16, stiffness: 100 }, durationInFrames: 15 }), [0, 1], [0, 1]) }}>
          <div style={{ flex: 1, padding: "18px 28px", fontSize: 16, color: t.textMuted, fontWeight: 600 }} />
          <div style={{ flex: 1, padding: "18px 28px", fontSize: 22, color: t.danger, fontWeight: 700, textAlign: "center" as const }}>{headerL}</div>
          <div style={{ flex: 1, padding: "18px 28px", fontSize: 22, color: t.success, fontWeight: 700, textAlign: "center" as const }}>{headerR}</div>
        </div>
        {/* 数据行 */}
        {rows.map((row, i) => {
          const p = spring({ frame: Math.max(0, frame - 8 - i * 6), fps, config: { damping: 16, stiffness: 100 }, durationInFrames: 15 });
          return (
            <div key={i} style={{
              display: "flex", borderBottom: i < rows.length - 1 ? `1px solid ${t.surfaceBorder}` : "none",
              opacity: interpolate(p, [0, 1], [0, 1]), transform: `translateY(${interpolate(p, [0, 1], [20, 0])}px)`,
            }}>
              <div style={{ flex: 1, padding: "16px 28px", fontSize: 19, color: t.text, fontWeight: 600, fontFamily: t.monoFont }}>{row.label}</div>
              <div style={{ flex: 1, padding: "16px 28px", fontSize: 18, color: t.textDim, textAlign: "center" as const }}>{row.left}</div>
              <div style={{ flex: 1, padding: "16px 28px", fontSize: 18, color: t.text, textAlign: "center" as const, fontWeight: 600 }}>{row.right}</div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

registry.register({ id: "slide.compare-table", schema: "slide", name: "对比表格", description: "左右对比表格，bullet_points 格式: 'feature: 旧值 → 新值' 或 'feature: A vs B'。标题含 'vs' 时自动拆为两列表头。适合工具评测、方案对比。", isDefault: false, tags: ["对比", "表格", "评测", "vs"] }, SlideCompareTable);
export { SlideCompareTable };
