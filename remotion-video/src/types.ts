/**
 * video2gen 脚本数据类型定义
 * 对应 Python 端 scriptwriter.py 输出的 script.json 结构
 */

export interface SlideContent {
  title: string;
  bullet_points: string[];
  chart_hint?: string;
  /** 场景专属结构化数据，各 anthropic-* slide style 自己定义 shape */
  scene_data?: Record<string, unknown>;
}

/** 段间转场类型 */
export type TransitionType =
  | "fade"
  | "slide"
  | "slide-left"
  | "zoom-in"
  | "wipe"
  | "glitch"
  | "none";

export interface ScriptSegment {
  id: number;
  type: "intro" | "body" | "outro";
  material: "A" | "B" | "C";
  narration_zh: string;
  notes?: string;
  /** 节奏标注：fast=快节奏段(hook/转折/数据冲击)，normal=标准讲解，slow=慢节奏段(总结/观点锤) */
  rhythm?: "fast" | "normal" | "slow";
  /** 指定视觉组件，格式 "{schema}.{style}"，如 "slide.tech-dark"。缺失时按 material 走默认。 */
  component?: string;
  /** 进入本段的转场类型。缺失时按 segment.type 自动选择。 */
  transition?: TransitionType;
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
    annotations?: Record<string, string>;
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
    nodes: Array<{
      id: string;
      label: string;
      type?: string;
      subtitle?: string;
      items?: Array<{ text: string; tag?: string }>;
      status?: string;
      icon?: string;
      keywords?: string[];
    }>;
    edges: Array<{ from: string; to: string; label?: string }>;
    direction?: "LR" | "TB";
  };
  // hero-stat 组件
  hero_stat?: {
    stats: Array<{ value: string; label: string; oldValue?: string; trend?: "up" | "down" | "neutral" }>;
    footnote?: string;
  };
  // image-overlay 组件
  image_content?: {
    image_path: string;
    overlay_text?: string;
    overlay_position?: "top" | "center" | "bottom";
    ken_burns?: "zoom-in" | "zoom-out" | "pan-left" | "pan-right";
  };
  // web-video 组件
  web_video?: {
    search_query: string;
    source_url?: string;
    clip_start?: number;
    clip_end?: number;
    overlay_text?: string;
    overlay_position?: "top" | "bottom";
    filter?: "none" | "desaturate" | "tint";
    fallback_component?: string;
  };
  // flash-meme 叠加（在段内某一时刻闪现梗图）
  flash_meme?: {
    image: string;           // public/ 下的图片文件名
    frame_offset?: number;   // 从段开头偏移多少帧后闪现（默认 0 = 段首）
    duration?: number;       // 持续帧数（默认 15 = 0.5s @ 30fps）
    display_mode?: "cover" | "contain" | "raw";
    contrast?: number;       // 对比度倍数，默认 2.5
    brightness?: number;     // 亮度倍数，默认 1.2
  };
  // browser 组件
  browser_content?: {
    url: string;
    tabTitle: string;
    pageTitle?: string;
    contentLines: string[];
    theme?: "light" | "dark";
    repoInfo?: {
      owner: string;
      repo: string;
      branch?: string;
      path?: string[];
      commitAuthor?: string;
      commitMessage?: string;
      commitHash?: string;
      files?: Array<{ name: string; type: "file" | "dir"; commitMessage?: string; highlight?: boolean }>;
      stars?: string;
      issues?: string;
      pullRequests?: string;
    };
  };
}

export interface ScriptData {
  title: string;
  description: string;
  tags: string[];
  source_channel?: string;
  total_duration_hint?: number;
  segments: ScriptSegment[];
  sources_used?: string[];
}

export interface SegmentTiming {
  file: string;
  duration: number;
  text_length: number;
  gap_after?: number;  // seconds of silence after this segment
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
  /** 视频主题 ID（tech-blue / warm-purple / emerald-dark），默认 tech-blue */
  theme?: string;
  /** BGM 文件名（public/ 下），可选 */
  bgmFile?: string;
  /** BGM 音量 0-1，默认 0.15 */
  bgmVolume?: number;
  /** 启用 LightLeak 光晕叠加（默认 true） */
  lightLeaks?: boolean;
  /** 启用底部进度条（默认 true） */
  progressBar?: boolean;
  /** 启用全局运镜（默认 true） */
  cameraRig?: boolean;
  /** 启用后期质感层：噪点 + 暗角 + 色差（默认 true） */
  filmGrain?: boolean;
  /** 启用烧入字幕（默认 true） */
  subtitles?: boolean;
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
