import { Composition } from "remotion";
import type { CalculateMetadataFunction } from "remotion";
import { VideoComposition } from "./VideoComposition";
import type { VideoCompositionProps, TimingMap } from "./types";

const FPS = 30;

/**
 * 动态计算视频总时长（基于 TTS 时长之和）
 */
const calculateMetadata: CalculateMetadataFunction<VideoCompositionProps> = async ({
  props,
}) => {
  const { timing } = props;
  const totalSeconds = Object.values(timing).reduce((sum, t) => sum + t.duration, 0);
  const totalFrames = Math.ceil(totalSeconds * FPS);

  return {
    durationInFrames: Math.max(totalFrames, 1),
    fps: FPS,
    width: 1920,
    height: 1080,
  };
};

/**
 * 默认 props（空数据，实际渲染时通过 --props 传入）
 */
const defaultProps: VideoCompositionProps = {
  script: {
    title: "",
    description: "",
    tags: [],
    source_channel: "",
    total_duration_hint: 60,
    segments: [],
  },
  timing: {} as TimingMap,
  fps: FPS,
  slidesDir: "slides",
  recordingsDir: "recordings",
  sourceVideoFiles: [],
  sourceChannels: [],
  voiceoverFile: "voiceover.mp3",
  availableRecordings: [],
};

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="V2GVideo"
      component={VideoComposition}
      durationInFrames={FPS * 60}
      fps={FPS}
      width={1920}
      height={1080}
      defaultProps={defaultProps}
      calculateMetadata={calculateMetadata}
    />
  );
};
