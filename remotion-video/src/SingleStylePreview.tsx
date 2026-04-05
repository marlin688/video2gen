/**
 * 单组件预览容器
 *
 * 在 Remotion Studio 中为每个 style 提供独立的 Composition 预览。
 * 直接从 registry 解析组件并渲染，不走 VideoComposition 的完整管线。
 */

import { AbsoluteFill } from "remotion";
import React from "react";
import { registry } from "./registry/registry";
import "./registry/init";
import { ThemeProvider, getTheme } from "./registry/theme";
import type { SegmentData, SchemaName } from "./registry/types";

export interface SingleStyleProps {
  styleId: string;
  data: SegmentData;
  theme?: string;
}

export const SingleStylePreview: React.FC<SingleStyleProps> = ({
  styleId,
  data,
  theme = "tech-blue",
}) => {
  const entry = registry.resolve(styleId);

  if (!entry) {
    return (
      <AbsoluteFill style={{
        background: "#1a1a2e",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: "#ef4444",
        fontSize: 36,
        fontFamily: "monospace",
      }}>
        Style not found: {styleId}
      </AbsoluteFill>
    );
  }

  const Component = entry.component as React.ComponentType<{
    data: SegmentData;
    segmentId: number;
    fps: number;
  }>;

  return (
    <ThemeProvider value={getTheme(theme)}>
      <AbsoluteFill>
        <Component data={data} segmentId={1} fps={30} />
      </AbsoluteFill>
    </ThemeProvider>
  );
};
