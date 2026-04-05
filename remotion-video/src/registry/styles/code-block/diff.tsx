/**
 * code-block.diff — Git diff 视图
 *
 * 代码行以 +/- 开头时显示为绿/红色背景（新增/删除）。
 * 适合展示代码变更、PR diff、Before/After 对比。
 */

import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import React from "react";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";

const DIFF = {
  addBg: "rgba(46,160,67,0.15)", addBorder: "rgba(46,160,67,0.4)", addText: "#7ee787",
  delBg: "rgba(248,81,73,0.15)", delBorder: "rgba(248,81,73,0.4)", delText: "#ffa198",
  hunkBg: "rgba(56,139,253,0.1)", hunkText: "#79c0ff",
  lineBg: "transparent", lineText: "#e6edf3",
  gutter: "#484f58", mono: "'SF Mono', 'Fira Code', 'JetBrains Mono', monospace",
};

const CodeBlockDiff: React.FC<StyleComponentProps<"code-block">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  let addNum = 0, delNum = 0;

  return (
    <AbsoluteFill style={{ background: "#0d1117", display: "flex", flexDirection: "column", padding: "40px 60px", fontFamily: DIFF.mono }}>
      {/* 文件名标题栏 */}
      <div style={{
        padding: "12px 20px", background: "#161b22", borderRadius: "10px 10px 0 0",
        border: "1px solid #30363d", borderBottom: "none",
        fontSize: 16, color: "#e6edf3", fontWeight: 600,
        display: "flex", alignItems: "center", gap: 8,
        opacity: interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp", extrapolateLeft: "clamp" }),
      }}>
        <span style={{ color: "#8b949e" }}>📄</span>
        {data.fileName}
      </div>

      {/* Diff 内容 */}
      <div style={{
        flex: 1, border: "1px solid #30363d", borderRadius: "0 0 10px 10px",
        overflow: "hidden",
      }}>
        {data.code.map((line, i) => {
          const delay = 5 + i * 2;
          const p = spring({ frame: Math.max(0, frame - delay), fps, config: { damping: 20, stiffness: 120 }, durationInFrames: 10 });

          const isAdd = line.startsWith("+") && !line.startsWith("+++");
          const isDel = line.startsWith("-") && !line.startsWith("---");
          const isHunk = line.startsWith("@@");
          const isHeader = line.startsWith("---") || line.startsWith("+++");

          if (isAdd) addNum++;
          if (isDel) delNum++;
          const lineNum = isAdd ? addNum : isDel ? delNum : Math.max(addNum, delNum) + 1;
          if (!isAdd && !isDel && !isHunk && !isHeader) { addNum++; delNum++; }

          const bg = isAdd ? DIFF.addBg : isDel ? DIFF.delBg : isHunk ? DIFF.hunkBg : DIFF.lineBg;
          const textColor = isAdd ? DIFF.addText : isDel ? DIFF.delText : isHunk ? DIFF.hunkText : DIFF.lineText;
          const borderLeft = isAdd ? `3px solid ${DIFF.addBorder}` : isDel ? `3px solid ${DIFF.delBorder}` : "3px solid transparent";

          return (
            <div key={i} style={{
              display: "flex", background: bg, borderLeft,
              opacity: interpolate(p, [0, 1], [0, 1]),
              minHeight: 28,
            }}>
              {/* 行号 */}
              {!isHunk && !isHeader && (
                <span style={{ width: 50, padding: "4px 8px", textAlign: "right" as const, fontSize: 14, color: DIFF.gutter, userSelect: "none" as const }}>
                  {lineNum}
                </span>
              )}
              {/* 符号 */}
              <span style={{ width: 24, padding: "4px 4px", fontSize: 15, color: textColor, textAlign: "center" as const, fontWeight: 700 }}>
                {isAdd ? "+" : isDel ? "−" : isHunk ? "" : ""}
              </span>
              {/* 代码 */}
              <span style={{
                flex: 1, padding: "4px 8px", fontSize: 17, color: textColor,
                whiteSpace: "pre" as const,
              }}>
                {isAdd || isDel ? line.slice(1) : line}
              </span>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

registry.register({ id: "code-block.diff", schema: "code-block", name: "Git Diff", description: "Git diff 视图，以 +/- 开头的代码行显示为绿/红色背景。支持 @@ hunk 头。适合展示代码变更、PR diff。", isDefault: false, tags: ["diff", "git", "变更", "PR"] }, CodeBlockDiff);
export { CodeBlockDiff };
