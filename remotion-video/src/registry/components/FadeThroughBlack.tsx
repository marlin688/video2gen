/**
 * FadeThroughBlack — 自定义 TransitionPresentation
 *
 * 复制原有 SegmentTransition 的视觉效果（fade through black + 0.97→1.0 scale），
 * 打包为 @remotion/transitions 的 Presentation 接口。
 */

import { useMemo } from "react";
import { interpolate, Easing } from "remotion";
import type {
  TransitionPresentation,
  TransitionPresentationComponentProps,
} from "@remotion/transitions";

type FadeThroughBlackProps = Record<string, unknown>;

const FadeThroughBlackComponent: React.FC<
  TransitionPresentationComponentProps<FadeThroughBlackProps>
> = ({ children, presentationDirection, presentationProgress }) => {
  const isEntering = presentationDirection === "entering";

  // 进入：从黑渐显 + scale 0.97→1.0
  // 退出：渐隐到黑
  const opacity = isEntering
    ? interpolate(presentationProgress, [0, 1], [0, 1], {
        extrapolateRight: "clamp",
      })
    : interpolate(presentationProgress, [0, 1], [1, 0], {
        extrapolateLeft: "clamp",
      });

  const scale = isEntering
    ? interpolate(presentationProgress, [0, 1], [0.97, 1], {
        easing: Easing.out(Easing.cubic),
        extrapolateRight: "clamp",
      })
    : 1;

  const containerStyle = useMemo(
    () => ({
      width: "100%" as const,
      height: "100%" as const,
      position: "absolute" as const,
    }),
    [],
  );

  const contentStyle = useMemo(
    () => ({
      width: "100%" as const,
      height: "100%" as const,
      transform: `scale(${scale})`,
    }),
    [scale],
  );

  const overlayStyle = useMemo(
    () => ({
      position: "absolute" as const,
      top: 0,
      left: 0,
      width: "100%" as const,
      height: "100%" as const,
      backgroundColor: "#000",
      opacity: 1 - opacity,
      pointerEvents: "none" as const,
    }),
    [opacity],
  );

  return (
    <div style={containerStyle}>
      <div style={contentStyle}>{children}</div>
      <div style={overlayStyle} />
    </div>
  );
};

export const fadeThroughBlack = (): TransitionPresentation<FadeThroughBlackProps> => {
  return {
    component: FadeThroughBlackComponent,
    props: {},
  };
};
