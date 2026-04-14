import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";

type LightingTag = "neutral" | "bright" | "dramatic" | "cool" | "warm" | "accent";

interface SegmentFrameInfo {
  segmentId: number;
  start: number;
  duration: number;
  gap: number;
}

interface SegmentLightingPlan {
  lighting_tag?: LightingTag;
}

interface BeatLightingPlan {
  beatId?: number;
  segmentId: number;
  startFrame: number;
  endFrame: number;
  lighting_tag?: LightingTag;
}

interface LightingRigProps {
  segmentFrameInfo: SegmentFrameInfo[];
  segmentLightingPlans?: Record<number, SegmentLightingPlan>;
  beatLightingPlans?: BeatLightingPlan[];
  enabled?: boolean;
}

interface LightingProfile {
  opacity: number;
  blendMode: React.CSSProperties["mixBlendMode"];
  background: string;
  vignetteOpacity: number;
}

const PROFILES: Record<LightingTag, LightingProfile> = {
  neutral: {
    opacity: 0,
    blendMode: "normal",
    background: "transparent",
    vignetteOpacity: 0,
  },
  bright: {
    opacity: 0.2,
    blendMode: "screen",
    background:
      "radial-gradient(circle at 50% 35%, rgba(255,255,255,0.55), rgba(255,255,255,0.08) 45%, rgba(255,255,255,0) 70%)",
    vignetteOpacity: 0.02,
  },
  dramatic: {
    opacity: 0.24,
    blendMode: "multiply",
    background:
      "radial-gradient(circle at 50% 45%, rgba(20,20,28,0.05), rgba(8,8,12,0.32) 70%, rgba(0,0,0,0.55) 100%)",
    vignetteOpacity: 0.18,
  },
  cool: {
    opacity: 0.16,
    blendMode: "soft-light",
    background:
      "linear-gradient(140deg, rgba(80,150,255,0.45) 0%, rgba(90,120,220,0.2) 40%, rgba(20,30,55,0.12) 100%)",
    vignetteOpacity: 0.08,
  },
  warm: {
    opacity: 0.16,
    blendMode: "soft-light",
    background:
      "linear-gradient(140deg, rgba(255,184,120,0.45) 0%, rgba(255,130,90,0.22) 50%, rgba(70,35,15,0.14) 100%)",
    vignetteOpacity: 0.09,
  },
  accent: {
    opacity: 0.2,
    blendMode: "screen",
    background:
      "linear-gradient(120deg, rgba(255,0,140,0.18) 0%, rgba(20,200,255,0.18) 48%, rgba(140,120,255,0.2) 100%)",
    vignetteOpacity: 0.06,
  },
};

export const LightingRig: React.FC<LightingRigProps> = ({
  segmentFrameInfo,
  segmentLightingPlans,
  beatLightingPlans,
  enabled = true,
}) => {
  const frame = useCurrentFrame();

  const { info, profile, windowStart, windowDuration } = React.useMemo(() => {
    if (!enabled || segmentFrameInfo.length === 0) {
      return { info: null, profile: PROFILES.neutral, windowStart: 0, windowDuration: 1 };
    }

    let current = segmentFrameInfo[0];
    for (let i = 0; i < segmentFrameInfo.length; i++) {
      const seg = segmentFrameInfo[i];
      if (frame >= seg.start && frame < seg.start + seg.duration + seg.gap) {
        current = seg;
        break;
      }
      if (i === segmentFrameInfo.length - 1) current = seg;
    }

    const activeBeat = beatLightingPlans?.find(
      (b) => frame >= b.startFrame && frame < b.endFrame,
    );
    const tag = activeBeat?.lighting_tag || segmentLightingPlans?.[current.segmentId]?.lighting_tag || "neutral";
    const start = activeBeat ? activeBeat.startFrame : current.start;
    const duration = activeBeat
      ? Math.max(1, activeBeat.endFrame - activeBeat.startFrame)
      : Math.max(1, current.duration + current.gap);
    return {
      info: current,
      profile: PROFILES[tag] || PROFILES.neutral,
      windowStart: start,
      windowDuration: duration,
    };
  }, [enabled, frame, segmentFrameInfo, segmentLightingPlans, beatLightingPlans]);

  if (!enabled || !info || profile.opacity <= 0) return null;

  const segmentProgress = interpolate(
    frame,
    [windowStart, windowStart + windowDuration],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const envelope = interpolate(
    segmentProgress,
    [0, 0.08, 0.92, 1],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const pulse = 0.92 + 0.08 * Math.sin(frame * 0.03);
  const opacity = profile.opacity * envelope * pulse;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <AbsoluteFill
        style={{
          opacity,
          mixBlendMode: profile.blendMode,
          background: profile.background,
        }}
      />
      {profile.vignetteOpacity > 0 && (
        <AbsoluteFill
          style={{
            opacity: profile.vignetteOpacity * envelope,
            background:
              "radial-gradient(circle at center, rgba(0,0,0,0) 48%, rgba(0,0,0,0.38) 100%)",
          }}
        />
      )}
    </AbsoluteFill>
  );
};
