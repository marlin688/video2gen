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
  // 素材 A
  slide_content?: SlideContent;
  // 素材 B
  recording_instruction?: string;
  // 素材 C
  source_video_index?: number; // 多源模式: 从哪个源视频截取 (0-based)
  source_start?: number;
  source_end?: number;
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
