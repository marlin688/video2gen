"""断点续传状态管理。"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class SourceVideo:
    """单个源视频的信息。"""
    video_id: str = ""
    video_url: str = ""
    channel_name: str = ""
    title: str = ""
    source_video_path: str = ""
    en_srt_path: str = ""
    zh_srt_path: str = ""
    prepared: bool = False


@dataclass
class PipelineState:
    """流水线状态，持久化为 checkpoint.json。

    支持两种模式:
    - 单视频模式: video_id + source_video (向后兼容)
    - 多源模式: project_id + sources[] (多视频综合)
    """

    # 项目标识 (多源模式用 project_id，单视频模式用 video_id)
    video_id: str = ""
    video_url: str = ""
    source_channel: str = ""
    created_at: str = ""

    # 多源模式
    project_id: str = ""
    topic: str = ""
    sources: list = field(default_factory=list)  # list[SourceVideo] as dicts

    # 阶段完成标记
    selected: bool = False
    downloaded: bool = False
    subtitled: bool = False
    scripted: bool = False
    script_reviewed: bool = False
    tts_done: bool = False
    slides_done: bool = False
    assembled: bool = False
    final_reviewed: bool = False

    # Agent 模式
    agent_sources: list = field(default_factory=list)  # 输入素材清单
    agent_outline_done: bool = False     # 大纲已生成
    outline_reviewed: bool = False       # 大纲已确认

    # 文件路径 (单视频模式)
    source_video: str = ""
    en_srt: str = ""
    zh_srt: str = ""
    script_json: str = ""
    recording_guide: str = ""
    voiceover: str = ""          # voiceover/full.mp3
    voiceover_timing: str = ""   # voiceover/timing.json
    slides_dir: str = ""
    recordings_dir: str = ""
    clips_dir: str = ""
    final_video: str = ""        # final/video.mp4

    last_error: str = ""

    # B站发布信息
    bvid: str = ""               # B站 BV 号（发布后填入）
    published_at: str = ""       # 发布时间 (ISO date)

    # 视觉主题 ID（remotion-video/src/registry/theme.ts 里注册的 key，
    # 如 "tech-blue" / "anthropic-cream"）。render.mjs / preview.mjs 会读这个字段。
    # 由 quality profile 自动设置，也可以手动编辑。
    theme: str = ""

    # 是否启用全局 CameraRig 运镜。技术解说片档位默认关闭（硬切不要额外运镜）。
    # 品牌片档位默认 true。None = 走 VideoComposition 的默认值。
    camera_rig: bool | None = None

    # 默认段间转场：空字符串 = VideoComposition 自动轮换；"none" = 硬切
    # (不加 fade/zoom/slide，适合技术解说片 talking-head ↔ screen-clip)。
    default_transition: str = ""

    # 成本追踪
    cost_summary: dict = field(default_factory=dict)

    @property
    def is_multi(self) -> bool:
        return bool(self.sources)

    @property
    def effective_id(self) -> str:
        return self.project_id or self.video_id

    def get_sources(self) -> list[SourceVideo]:
        """返回 SourceVideo 对象列表。"""
        result = []
        for s in self.sources:
            if isinstance(s, dict):
                result.append(SourceVideo(**{k: v for k, v in s.items() if k in SourceVideo.__dataclass_fields__}))
            elif isinstance(s, SourceVideo):
                result.append(s)
        return result

    def save(self, output_dir: Path):
        """保存到 checkpoint.json。"""
        eid = self.effective_id
        if not eid:
            return
        path = output_dir / eid / "checkpoint.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, output_dir: Path, project_or_video_id: str) -> "PipelineState":
        """从 checkpoint.json 加载，不存在则新建。"""
        path = output_dir / project_or_video_id / "checkpoint.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            valid = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
            return cls(**valid)
        return cls(
            video_id=project_or_video_id,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    @property
    def current_stage(self) -> str:
        stages = [
            ("selected", "select"),
            ("downloaded", "download"),
            ("subtitled", "subtitle"),
            ("scripted", "script"),
            ("script_reviewed", "review"),
            ("tts_done", "tts"),
            ("slides_done", "slides"),
            ("assembled", "assemble"),
            ("final_reviewed", "final_review"),
        ]
        for attr, name in stages:
            if not getattr(self, attr):
                return name
        return "done"

    def needs_human_review(self) -> str | None:
        if self.scripted and not self.script_reviewed:
            return "script_review"
        if self.assembled and not self.final_reviewed:
            return "final_review"
        return None
