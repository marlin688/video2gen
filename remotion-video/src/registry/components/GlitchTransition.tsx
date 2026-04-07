/**
 * GlitchTransition -- RGB 通道错位故障转场
 *
 * 实现 @remotion/transitions TransitionPresentation 接口。
 * 红/蓝通道水平偏移 + 扫描线 + scale 脉冲。
 */

import React, { useMemo } from "react";
import { interpolate } from "remotion";
import type {
  TransitionPresentation,
  TransitionPresentationComponentProps,
} from "@remotion/transitions";

type GlitchProps = {
  intensity: number;
};

const GlitchComponent: React.FC<
  TransitionPresentationComponentProps<GlitchProps>
> = ({ children, presentationDirection, presentationProgress, passedProps }) => {
  const { intensity } = passedProps;

  const isEntering = presentationDirection === "entering";

  const effectAmount = isEntering
    ? interpolate(presentationProgress, [0, 0.6, 1], [1, 0.3, 0])
    : interpolate(presentationProgress, [0, 0.4, 1], [0, 0.3, 1]);

  const offset = effectAmount * intensity;
  const scaleVal = isEntering
    ? interpolate(presentationProgress, [0, 1], [1.02, 1])
    : interpolate(presentationProgress, [0, 1], [1, 1.02]);

  const containerOpacity = isEntering
    ? interpolate(presentationProgress, [0, 0.3], [0, 1], {
        extrapolateRight: "clamp",
      })
    : interpolate(presentationProgress, [0.7, 1], [1, 0], {
        extrapolateLeft: "clamp",
      });

  const scanlineOpacity = effectAmount * 0.15;

  const containerStyle = useMemo(
    () => ({
      width: "100%",
      height: "100%",
      position: "absolute" as const,
      transform: `scale(${scaleVal})`,
      opacity: containerOpacity,
    }),
    [scaleVal, containerOpacity],
  );

  const redStyle = useMemo(
    () => ({
      position: "absolute" as const,
      width: "100%",
      height: "100%",
      mixBlendMode: "screen" as const,
      transform: `translateX(${offset}px)`,
      opacity: effectAmount > 0.01 ? 0.8 : 1,
      filter:
        effectAmount > 0.01
          ? "saturate(2) hue-rotate(-30deg)"
          : undefined,
    }),
    [offset, effectAmount],
  );

  const blueStyle = useMemo(
    () => ({
      position: "absolute" as const,
      width: "100%",
      height: "100%",
      mixBlendMode: "screen" as const,
      transform: `translateX(${-offset}px)`,
      opacity: effectAmount > 0.01 ? 0.8 : 1,
      filter:
        effectAmount > 0.01
          ? "saturate(2) hue-rotate(30deg)"
          : undefined,
    }),
    [offset, effectAmount],
  );

  const scanlineStyle = useMemo(
    () => ({
      position: "absolute" as const,
      width: "100%",
      height: "100%",
      backgroundImage:
        "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.3) 2px, rgba(0,0,0,0.3) 4px)",
      opacity: scanlineOpacity,
      pointerEvents: "none" as const,
    }),
    [scanlineOpacity],
  );

  if (effectAmount < 0.01) {
    return <div style={containerStyle}>{children}</div>;
  }

  return (
    <div style={containerStyle}>
      <div style={redStyle}>{children}</div>
      <div style={blueStyle}>{children}</div>
      <div style={scanlineStyle} />
    </div>
  );
};

export const glitch = (props?: Partial<GlitchProps>): TransitionPresentation<GlitchProps> => {
  return {
    component: GlitchComponent,
    props: {
      intensity: props?.intensity ?? 8,
    },
  };
};
