/**
 * video2gen 脚本数据类型定义
 * 对应 Python 端 scriptwriter.py 输出的 script.json 结构
 */

export interface SlideContent {
  title: string;
  bullet_points: string[];
  chart_hint?: string;
}

export interface ScriptSegment {
  id: number;
  type: "intro" | "body" | "outro";
  material: "A" | "B" | "C";
  narration_zh: string;
  notes?: string;
  /** 指定视觉组件，格式 "{schema}.{style}"，如 "slide.tech-dark"。缺失时按 material 走默认。 */
  component?: string;
  // 素材 A
  slide_content?: SlideContent;
  // 素材 B
  recording_instruction?: string;
  /** LLM 生成的结构化终端会话（B 类素材无录屏时驱动终端动画） */
  terminal_session?: Array<{
    type: "input" | "output" | "status" | "tool" | "blank";
    text?: string;
    lines?: string[];
    name?: string;
    target?: string;
    result?: string;
    color?: string;
  }>;
  // 素材 C
  source_video_index?: number; // 多源模式: 从哪个源视频截取 (0-based)
  source_start?: number;
  source_end?: number;
  // code-block 组件
  code_content?: {
    fileName: string;
    language: string;
    code: string[];
    highlightLines?: number[];
    annotations?: Record<number, string>;
  };
  // social-card 组件
  social_card?: {
    platform: "twitter" | "github" | "hackernews";
    author: string;
    avatarColor?: string;
    text: string;
    stats?: Record<string, number | string>;
    subtitle?: string;
    language?: string;
  };
  // diagram 组件
  diagram?: {
    title?: string;
    nodes: Array<{ id: string; label: string; type?: string }>;
    edges: Array<{ from: string; to: string; label?: string }>;
    direction?: "LR" | "TB";
  };
  // hero-stat 组件
  hero_stat?: {
    stats: Array<{ value: string; label: string; oldValue?: string; trend?: "up" | "down" | "neutral" }>;
    footnote?: string;
  };
  // browser 组件
  browser_content?: {
    url: string;
    tabTitle: string;
    pageTitle?: string;
    contentLines: string[];
    theme?: "light" | "dark";
  };
}

export interface ScriptData {
  title: string;
  description: string;
  tags: string[];
  source_channel: string;
  total_duration_hint: number;
  segments: ScriptSegment[];
}

export interface SegmentTiming {
  file: string;
  duration: number;
  text_length: number;
}

export type TimingMap = Record<string, SegmentTiming>;

/** 传给主 Composition 的 props */
export interface VideoCompositionProps {
  script: ScriptData;
  timing: TimingMap;
  fps: number;
  slidesDir: string;
  recordingsDir: string;
  sourceVideoFiles: string[];   // 多源视频文件名列表 (public/ 下)
  sourceChannels: string[];     // 每个源的频道名
  voiceoverFile: string;
  availableRecordings: number[];
}

/** 计算每个 segment 在时间线上的帧范围 */
export interface SegmentLayout {
  segment: ScriptSegment;
  startFrame: number;
  durationFrames: number;
}

export function computeLayout(
  segments: ScriptSegment[],
  timing: TimingMap,
  fps: number,
): SegmentLayout[] {
  const layouts: SegmentLayout[] = [];
  let currentFrame = 0;

  for (const seg of segments) {
    const t = timing[String(seg.id)];
    if (!t) continue;
    const durationFrames = Math.round(t.duration * fps);
    layouts.push({ segment: seg, startFrame: currentFrame, durationFrames });
    currentFrame += durationFrames;
  }

  return layouts;
}

export function totalFrames(layouts: SegmentLayout[]): number {
  if (layouts.length === 0) return 1;
  const last = layouts[layouts.length - 1];
  return last.startFrame + last.durationFrames;
}
