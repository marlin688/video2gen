/**
 * useHumanTypist -- 模拟真人打字的 hook
 *
 * 与 useAnimatedText 的匀速线性不同，本 hook 模拟真人打字节奏：
 * - 每个字符之间有随机延迟（1-3 帧）
 * - 遇到空格/标点时强制停顿
 * - 支持打错字 → 停顿 → 退格 → 重打
 * - 使用 alea PRNG 保证确定性渲染
 *
 * 核心设计：useMemo 预计算帧→文本映射表，每帧 O(1) 二分查找。
 */

import { useMemo } from "react";
import { useCurrentFrame } from "remotion";
import alea from "alea";

/* ═══════════════ Types ═══════════════ */

export interface TypoSpec {
  /** 在第几个正确字符处触发 typo（0-based） */
  charIndex: number;
  /** 打出的错误字符（省略则随机选一个临近键） */
  wrongChar?: string;
  /** 打错后停顿帧数再退格，默认 8 */
  pauseBeforeFix?: number;
}

export interface HumanTypistOptions {
  /** 要打的完整文本 */
  text: string;
  /** 开始打字的帧（相对于 Sequence 内部），默认 0 */
  startFrame?: number;
  /** 基础每字符帧数，默认 2 */
  baseSpeed?: number;
  /** 速度随机抖动 ±帧数，默认 1（即每字符 1-3 帧） */
  speedVariation?: number;
  /** 遇到标点/空格的额外停顿帧数，默认 7 */
  punctuationPause?: number;
  /** typo 列表 */
  typos?: TypoSpec[];
  /** alea 随机种子，默认 "human-typist" */
  seed?: string;
}

export interface HumanTypistResult {
  /** 当前帧应显示的文本（含可能的 typo 状态） */
  displayText: string;
  /** 光标是否可见（打字中常亮，完成后闪烁） */
  cursorVisible: boolean;
  /** 是否还在打字 */
  isTyping: boolean;
  /** 完成进度 0-1 */
  progress: number;
  /** 打字结束的总帧数 */
  totalFrames: number;
}

/* ═══════════════ Constants ═══════════════ */

/** 标点和空格字符集 */
const PUNCTUATION = new Set([
  " ", "，", "。", "！", "？", "；", "：", "、",
  ",", ".", "!", "?", ";", ":", "\n",
  "\uff08", "\uff09", "(", ")", "\u300c", "\u300d", "\u201c", "\u201d",
]);

/** 临近键映射（QWERTY 键盘），用于生成随机 typo */
const NEARBY_KEYS: Record<string, string> = {
  a: "sq", b: "vn", c: "xv", d: "sf", e: "wr", f: "dg", g: "fh",
  h: "gj", i: "uo", j: "hk", k: "jl", l: "k;", m: "n,", n: "bm",
  o: "ip", p: "o[", q: "wa", r: "et", s: "ad", t: "ry", u: "yi",
  v: "cb", w: "qe", x: "zc", y: "tu", z: "xa",
};

/* ═══════════════ Schedule Builder ═══════════════ */

interface ScheduleEntry {
  /** 该条目生效的起始帧 */
  frame: number;
  /** 此时应显示的文本 */
  text: string;
}

function buildSchedule(opts: Required<Omit<HumanTypistOptions, "startFrame">>): ScheduleEntry[] {
  const { text, baseSpeed, speedVariation, punctuationPause, typos, seed } = opts;
  const rng = alea(seed);
  const schedule: ScheduleEntry[] = [];

  // 建立 typo 查找表：charIndex → TypoSpec
  const typoMap = new Map<number, TypoSpec>();
  for (const t of typos) {
    typoMap.set(t.charIndex, t);
  }

  let currentFrame = 0;
  let displayedSoFar = "";

  // 初始状态：空文本
  schedule.push({ frame: 0, text: "" });

  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    const typo = typoMap.get(i);

    // 计算本字符的打字延迟
    const variation = speedVariation > 0
      ? Math.round((rng() - 0.5) * 2 * speedVariation)
      : 0;
    const charDelay = Math.max(1, baseSpeed + variation);

    // 标点/空格额外停顿
    const isPunct = PUNCTUATION.has(char);
    const extraPause = isPunct ? punctuationPause : 0;

    if (typo) {
      // ── Typo 序列 ──
      // 1. 打出错误字符
      const wrongChar = typo.wrongChar || pickNearbyKey(char, rng);
      currentFrame += charDelay;
      schedule.push({ frame: currentFrame, text: displayedSoFar + wrongChar });

      // 2. 停顿（意识到打错了）
      const pause = typo.pauseBeforeFix ?? 8;
      currentFrame += pause;

      // 3. 退格（删除错字）
      currentFrame += 2; // 退格很快，2 帧
      schedule.push({ frame: currentFrame, text: displayedSoFar });

      // 4. 短暂停顿后打出正确字符
      currentFrame += 3;
      displayedSoFar += char;
      currentFrame += charDelay;
      schedule.push({ frame: currentFrame, text: displayedSoFar });
    } else {
      // ── 正常打字 ──
      currentFrame += charDelay + extraPause;
      displayedSoFar += char;
      schedule.push({ frame: currentFrame, text: displayedSoFar });
    }
  }

  return schedule;
}

/** 从临近键中随机选一个 */
function pickNearbyKey(char: string, rng: () => number): string {
  const lower = char.toLowerCase();
  const nearby = NEARBY_KEYS[lower];
  if (nearby) {
    return nearby[Math.floor(rng() * nearby.length)];
  }
  // 非字母字符：随机一个字母
  const alphabet = "abcdefghijklmnopqrstuvwxyz";
  return alphabet[Math.floor(rng() * alphabet.length)];
}

/** 二分查找：给定 frame，找到 schedule 中最后一个 entry.frame <= frame */
function lookupFrame(schedule: ScheduleEntry[], frame: number): ScheduleEntry {
  let lo = 0;
  let hi = schedule.length - 1;

  while (lo < hi) {
    const mid = (lo + hi + 1) >>> 1;
    if (schedule[mid].frame <= frame) {
      lo = mid;
    } else {
      hi = mid - 1;
    }
  }

  return schedule[lo];
}

/* ═══════════════ Hook ═══════════════ */

export function useHumanTypist(options: HumanTypistOptions): HumanTypistResult {
  const frame = useCurrentFrame();

  const {
    text,
    startFrame = 0,
    baseSpeed = 2,
    speedVariation = 1,
    punctuationPause = 7,
    typos = [],
    seed = "human-typist",
  } = options;

  // 预计算打字时间表（只在参数变化时重建）
  const schedule = useMemo(
    () => buildSchedule({ text, baseSpeed, speedVariation, punctuationPause, typos, seed }),
    [text, baseSpeed, speedVariation, punctuationPause, typos, seed],
  );

  const totalFrames = schedule.length > 0 ? schedule[schedule.length - 1].frame : 0;
  const elapsed = Math.max(0, frame - startFrame);
  const entry = lookupFrame(schedule, elapsed);
  const isTyping = elapsed < totalFrames;

  // 光标：打字中常亮，完成后闪烁（18帧周期，11帧亮 7帧灭）
  const cursorVisible = isTyping ? true : (frame % 18) < 11;

  return {
    displayText: entry.text,
    cursorVisible,
    isTyping,
    progress: text.length > 0 ? entry.text.length / text.length : 1,
    totalFrames,
  };
}
