/**
 * 字幕叠加层
 * 逐句显示，底部居中，白字黑描边
 * 素材 A 段不显示字幕（卡片已有文字）
 */

import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import type { ScriptSegment, TimingMap } from "../types";

interface SubtitleEntry {
  text: string;
  startFrame: number;
  endFrame: number;
}

/** 将 narration 按标点切分为多条字幕 */
function splitNarration(text: string, durationFrames: number, startFrame: number): SubtitleEntry[] {
  // 按句号/问号/感叹号/分号切分
  const parts = text.split(/(?<=[。！？；])/).filter((p) => p.trim());
  if (parts.length === 0) return [{ text, startFrame, endFrame: startFrame + durationFrames }];

  // 合并太短的（< 6 字）
  const merged: string[] = [];
  for (const p of parts) {
    if (merged.length > 0 && merged[merged.length - 1].length < 6) {
      merged[merged.length - 1] += p;
    } else {
      merged.push(p.trim());
    }
  }

  // 超 36 字的按逗号再拆
  const final: string[] = [];
  for (const m of merged) {
    if (m.length <= 36) {
      final.push(m);
    } else {
      const subs = m.split(/(?<=[，,])/).filter((s) => s.trim());
      let buf = "";
      for (const s of subs) {
        if (buf.length + s.length <= 36) {
          buf += s;
        } else {
          if (buf) final.push(buf);
          buf = s;
        }
      }
      if (buf) final.push(buf);
    }
  }

  // 按字数比例分配帧
  const totalChars = final.reduce((a, f) => a + f.length, 0) || 1;
  const entries: SubtitleEntry[] = [];
  let f = startFrame;
  for (const t of final) {
    const dur = Math.round((durationFrames * t.length) / totalChars);
    // 每行最多 18 字，超出换行（避免拆断英文单词）
    let display = t;
    if (display.length > 18) {
      // 在 18 字附近找合适的断行点：空格、中文字符后
      let breakAt = 18;
      // 如果 pos 18 落在 ASCII 连续段内，向前找到该段起始位置
      if (/[A-Za-z0-9+\-_.]/.test(display[breakAt] ?? "")) {
        const before = display.slice(0, breakAt + 1);
        const match = before.match(/[A-Za-z0-9+\-_.]+$/);
        if (match && match.index != null && match.index > 0) {
          breakAt = match.index;
        }
      }
      display = display.slice(0, breakAt).trimEnd() + "\n" + display.slice(breakAt).trimStart();
    }
    entries.push({ text: display, startFrame: f, endFrame: f + dur });
    f += dur;
  }

  return entries;
}

interface SubtitleOverlayProps {
  segments: ScriptSegment[];
  timing: TimingMap;
}

export const SubtitleOverlay: React.FC<SubtitleOverlayProps> = ({ segments, timing }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // 构建所有字幕条目的时间线
  const allEntries: SubtitleEntry[] = [];
  let currentFrame = 0;

  for (const seg of segments) {
    const t = timing[String(seg.id)];
    if (!t) continue;
    const durationFrames = Math.round(t.duration * fps);

    // 素材 A 不显示字幕
    if (seg.material !== "A" && seg.narration_zh) {
      const entries = splitNarration(seg.narration_zh, durationFrames, currentFrame);
      allEntries.push(...entries);
    }

    currentFrame += durationFrames;
  }

  // 找到当前帧应显示的字幕
  const current = allEntries.find((e) => frame >= e.startFrame && frame < e.endFrame);
  if (!current) return null;

  const lines = current.text.split("\n");

  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          bottom: 50,
          left: 0,
          right: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}
      >
        {lines.map((line, i) => (
          <div
            key={i}
            style={{
              fontSize: 48,
              fontWeight: 700,
              fontFamily: "'PingFang SC', 'Hiragino Sans GB', sans-serif",
              color: "#ffffff",
              textShadow:
                "-2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000, 2px 2px 0 #000," +
                "0 -2px 0 #000, 0 2px 0 #000, -2px 0 0 #000, 2px 0 0 #000",
              lineHeight: 1.4,
              textAlign: "center",
            }}
          >
            {line}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
