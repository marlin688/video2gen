/**
 * ZoomIn — 放大推进式入场转场
 *
 * 实现 @remotion/transitions TransitionPresentation 接口。
 * 进入：scale 0.82 → 1.0 + fade 0 → 1（弹性缓出），给人"被推到眼前"的感觉。
 * 退出：scale 1.0 → 1.08 + fade 1 → 0（继续往前推，类似 dolly-in 收尾）。
 *
 * 与 fadeThroughBlack 的微推 (0.97→1) 形成明显差异，用于轮换入场时强化"换镜头"感。
 */

import React, { useMemo } from "react";
import { interpolate, Easing } from "remotion";
import type {
  TransitionPresentation,
  TransitionPresentationComponentProps,
} from "@remotion/transitions";

type ZoomInProps = Record<string, unknown>;

const ZoomInComponent: React.FC<
  TransitionPresentationComponentProps<ZoomInProps>
> = ({ children, presentationDirection, presentationProgress }) => {
  const isEntering = presentationDirection === "entering";

  const opacity = isEntering
    ? interpolate(presentationProgress, [0, 0.6, 1], [0, 0.9, 1], {
        extrapolateRight: "clamp",
      })
    : interpolate(presentationProgress, [0, 0.4, 1], [1, 0.9, 0], {
        extrapolateLeft: "clamp",
      });

  const scale = isEntering
    ? interpolate(presentationProgress, [0, 1], [0.82, 1.0], {
        easing: Easing.out(Easing.cubic),
        extrapolateRight: "clamp",
      })
    : interpolate(presentationProgress, [0, 1], [1.0, 1.08], {
        easing: Easing.in(Easing.cubic),
        extrapolateLeft: "clamp",
      });

  const containerStyle = useMemo(
    () => ({
      width: "100%" as const,
      height: "100%" as const,
      position: "absolute" as const,
      opacity,
      transform: `scale(${scale})`,
      transformOrigin: "center center" as const,
    }),
    [opacity, scale],
  );

  return <div style={containerStyle}>{children}</div>;
};

export const zoomIn = (): TransitionPresentation<ZoomInProps> => {
  return {
    component: ZoomInComponent,
    props: {},
  };
};
