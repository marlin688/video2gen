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

/** 结构化终端会话步骤（LLM 在 script.json 中生成） */
export interface TerminalSessionStep {
  type: "input" | "output" | "status" | "tool" | "blank";
  /** input: 用户输入的命令; output: 命令输出文本; status: 状态提示; tool: 工具调用 */
  text?: string;
  /** output 类型可包含多行 */
  lines?: string[];
  /** tool 类型的工具名 (Read/Write/Edit/Bash/Grep 等) */
  name?: string;
  /** tool 类型的操作目标 */
  target?: string;
  /** tool 类型的执行结果 */
  result?: string;
  /** 显示颜色覆盖 */
  color?: string;
}

export interface TerminalData {
  schema: "terminal";
  instruction: string;
  narrationText?: string;
  /** LLM 生成的结构化终端会话，优先于 instruction 正则解析 */
  session?: TerminalSessionStep[];
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

export interface CodeBlockData {
  schema: "code-block";
  /** 文件名（显示在标题栏） */
  fileName: string;
  /** 编程语言（用于语法高亮） */
  language: string;
  /** 代码行 */
  code: string[];
  /** 高亮行号（1-based） */
  highlightLines?: number[];
  /** 可选注释（行号 → 注释文字） */
  annotations?: Record<number, string>;
}

export interface SocialCardData {
  schema: "social-card";
  /** 平台: twitter / github / hackernews */
  platform: "twitter" | "github" | "hackernews";
  /** 作者/仓库名 */
  author: string;
  /** 头像占位色（无真实头像时用） */
  avatarColor?: string;
  /** 正文内容 */
  text: string;
  /** 统计数据 */
  stats?: Record<string, number | string>;
  /** 可选: 仓库描述 (github)、子标题 */
  subtitle?: string;
  /** 可选: 语言标签 (github) */
  language?: string;
}

export interface DiagramData {
  schema: "diagram";
  /** 图表标题 */
  title?: string;
  /** 节点列表 */
  nodes: Array<{
    id: string;
    label: string;
    /** 节点类型影响样式 */
    type?: "default" | "primary" | "success" | "warning" | "danger";
  }>;
  /** 连线列表 */
  edges: Array<{
    from: string;
    to: string;
    label?: string;
  }>;
  /** 布局方向 */
  direction?: "LR" | "TB";
}

export interface HeroStatData {
  schema: "hero-stat";
  /** 1-3 个指标 */
  stats: Array<{
    value: string;
    label: string;
    /** 前值（显示为 oldValue → value） */
    oldValue?: string;
    /** 趋势色: up=绿, down=红, neutral=蓝 */
    trend?: "up" | "down" | "neutral";
  }>;
  /** 底部小字说明 */
  footnote?: string;
}

export interface BrowserData {
  schema: "browser";
  /** 地址栏 URL */
  url: string;
  /** 标签页标题 */
  tabTitle: string;
  /** 页面内容区: 标题 + 内容行 */
  pageTitle?: string;
  /** 页面内容行 */
  contentLines: string[];
  /** 页面风格: light / dark */
  theme?: "light" | "dark";
}

/** 所有 schema 数据的 discriminated union */
export type SegmentData =
  | SlideData
  | TerminalData
  | RecordingData
  | SourceClipData
  | CodeBlockData
  | SocialCardData
  | DiagramData
  | HeroStatData
  | BrowserData;

export type SchemaName = SegmentData["schema"];

// ---------------------------------------------------------------------------
// Schema → Data 类型映射（泛型约束用）
// ---------------------------------------------------------------------------

export type SchemaDataMap = {
  slide: SlideData;
  terminal: TerminalData;
  recording: RecordingData;
  "source-clip": SourceClipData;
  "code-block": CodeBlockData;
  "social-card": SocialCardData;
  diagram: DiagramData;
  "hero-stat": HeroStatData;
  browser: BrowserData;
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
