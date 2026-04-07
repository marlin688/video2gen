/**
 * 全局 Easing 规范
 *
 * 所有位移、缩放、透明度的连续动画统一使用 GLOBAL_EASE。
 * Spring 动画使用标准预设，确保全片节奏一致。
 */

import { Easing } from "remotion";

/* ── 连续动画曲线（interpolate 的 easing 参数） ── */

/** 标准全局缓动：inOut cubic，适用于运镜、入场、退场 */
export const GLOBAL_EASE = Easing.inOut(Easing.cubic);

/** 仅出场缓动：快进慢出 */
export const EASE_OUT = Easing.out(Easing.cubic);

/** 仅入场缓动：慢进快出 */
export const EASE_IN = Easing.in(Easing.cubic);

/* ── Spring 预设（spring() 的 config 参数） ── */

/** 快速弹性入场（~15 帧），适用于标题、卡片弹入 */
export const SPRING_SNAPPY = { damping: 14, stiffness: 120 } as const;

/** 中速平滑入场（~20 帧），适用于内容块、列表项 */
export const SPRING_MEDIUM = { damping: 16, stiffness: 100 } as const;

/** 慢速柔和入场（~30 帧），适用于背景元素、计数动画 */
export const SPRING_GENTLE = { damping: 20, stiffness: 60 } as const;
