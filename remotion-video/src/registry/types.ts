/**
 * 组件库类型定义
 *
 * 两层模型：Schema（数据契约）× Style（视觉实现）
 * style id 格式: "{schema}.{style-name}"，如 "slide.tech-dark"
 */

import type React from "react";

// ---------------------------------------------------------------------------
// Schema 数据接口
// ---------------------------------------------------------------------------

export interface SlideData {
  schema: "slide";
  title: string;
  bullet_points: string[];
  chart_hint?: string;
}

export interface TerminalData {
  schema: "terminal";
  instruction: string;
  narrationText?: string;
}

export interface RecordingData {
  schema: "recording";
  recordingFile: string;
}

export interface SourceClipData {
  schema: "source-clip";
  sourceVideoFile: string;
  sourceStart: number;
  sourceEnd: number;
  sourceChannel: string;
  ttsDuration: number;
}

/** 所有 schema 数据的 discriminated union */
export type SegmentData = SlideData | TerminalData | RecordingData | SourceClipData;

export type SchemaName = SegmentData["schema"];

// ---------------------------------------------------------------------------
// Schema → Data 类型映射（泛型约束用）
// ---------------------------------------------------------------------------

export type SchemaDataMap = {
  slide: SlideData;
  terminal: TerminalData;
  recording: RecordingData;
  "source-clip": SourceClipData;
};

// ---------------------------------------------------------------------------
// Style 组件 Props
// ---------------------------------------------------------------------------

/** 所有 style 组件接收的公共 props */
export interface StyleComponentProps<S extends SchemaName = SchemaName> {
  data: SchemaDataMap[S];
  segmentId: number;
  fps: number;
}

// ---------------------------------------------------------------------------
// Style 注册元信息
// ---------------------------------------------------------------------------

export interface StyleMeta {
  /** 唯一标识，格式 "{schema}.{style-name}"，如 "slide.tech-dark" */
  id: string;
  /** 归属的 schema */
  schema: SchemaName;
  /** 人类可读名称 */
  name: string;
  /** LLM 友好的自然语言描述（直接拼进 prompt） */
  description: string;
  /** 是否为该 schema 的默认 style */
  isDefault: boolean;
  /** 是否已废弃（LLM 不再选配，旧脚本仍可渲染） */
  deprecated?: boolean;
  /** 适用场景标签 */
  tags?: string[];
}

/** 注册表条目 = 元信息 + 组件 */
export interface RegistryEntry<S extends SchemaName = SchemaName> {
  meta: StyleMeta;
  component: React.ComponentType<StyleComponentProps<S>>;
}
