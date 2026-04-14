"""script.json 结构验证：Pydantic v2 模型，镜像 remotion-video/src/types.ts。

在 eval_script() 之前运行，确保字段类型、必填项、枚举值合法。
错误前置到脚本生成阶段，不让渲染层做 schema 校验。
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ── 子结构 ─────────────────────────────────────────────────


class SlideContent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    bullet_points: list[str]
    chart_hint: str | None = None
    # 场景专属结构化数据：各 anthropic-* style 自己定义 shape（Dict 透传）
    scene_data: dict | None = None


class TerminalStep(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["input", "output", "status", "tool", "blank"]
    text: str | None = None
    lines: list[str] | None = None
    name: str | None = None
    target: str | None = None
    result: str | None = None
    color: str | None = None


class CodeContent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fileName: str
    language: str
    code: list[str]
    highlightLines: list[int] | None = None
    annotations: dict[str, str] | None = None  # JSON key 总是 str


class SocialCard(BaseModel):
    model_config = ConfigDict(extra="ignore")

    platform: Literal["twitter", "github", "hackernews"]
    author: str
    text: str
    avatarColor: str | None = None
    stats: dict[str, int | str] | None = None
    subtitle: str | None = None
    language: str | None = None


class DiagramNodeItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str
    tag: str | None = None


class DiagramNode(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    label: str
    type: str | None = None
    subtitle: str | None = None
    items: list[DiagramNodeItem] | None = None
    status: str | None = None
    icon: str | None = None
    keywords: list[str] | None = None


class DiagramEdge(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    label: str | None = None


class Diagram(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    nodes: list[DiagramNode]
    edges: list[DiagramEdge]
    direction: Literal["LR", "TB"] | None = None


class HeroStatItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    value: str
    label: str
    oldValue: str | None = None
    trend: Literal["up", "down", "neutral"] | None = None


class HeroStat(BaseModel):
    model_config = ConfigDict(extra="ignore")

    stats: list[HeroStatItem]
    footnote: str | None = None


class RepoFileEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    type: Literal["file", "dir"]
    commitMessage: str | None = None


class RepoInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    owner: str
    repo: str
    branch: str | None = None
    path: list[str] | None = None
    commitAuthor: str | None = None
    commitMessage: str | None = None
    commitHash: str | None = None
    files: list[RepoFileEntry] | None = None
    stars: str | None = None
    issues: str | None = None
    pullRequests: str | None = None


class ImageContent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    image_path: str = ""  # 可为空，render 前由 image_prepare 填充
    source_method: Literal["screenshot", "search", "generate"] | None = None
    source_query: str | None = None  # URL / 关键词 / prompt
    overlay_text: str | None = None
    overlay_position: Literal["top", "center", "bottom"] | None = None
    ken_burns: Literal["zoom-in", "zoom-out", "pan-left", "pan-right"] | None = None


class WebVideo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    search_query: str
    source_url: str | None = None
    clip_start: float | None = None
    clip_end: float | None = None
    overlay_text: str | None = None
    overlay_position: Literal["top", "bottom"] | None = None
    filter: Literal["none", "desaturate", "tint"] | None = None
    fallback_component: str | None = None


class FlashMeme(BaseModel):
    """闪现梗图叠加参数，在段内某一时刻全屏闪现一张 Meme 图。"""
    model_config = ConfigDict(extra="ignore")

    image: str                    # public/ 下的图片文件名
    frame_offset: int | None = None  # 从段开头偏移多少帧后闪现（默认 0）
    duration: int | None = None      # 持续帧数（默认 15 = 0.5s @ 30fps）
    display_mode: Literal["cover", "contain", "raw"] | None = None
    contrast: float | None = None    # 对比度倍数，默认 2.5
    brightness: float | None = None  # 亮度倍数，默认 1.2


class BrowserContent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str
    tabTitle: str
    pageTitle: str | None = None
    contentLines: list[str]
    theme: Literal["light", "dark"] | None = None
    repoInfo: RepoInfo | None = None


# ── Segment ────────────────────────────────────────────────

# 合法的 component schema 前缀
_VALID_SCHEMAS = frozenset([
    "slide", "terminal", "recording", "source-clip",
    "code-block", "social-card", "diagram", "hero-stat", "browser",
    "image-overlay", "web-video",
])

_COMPONENT_RE = re.compile(r"^([a-z][a-z0-9-]*)\.\w[\w-]*$")


class ScriptSegment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    type: Literal["intro", "body", "outro"]
    material: Literal["A", "B", "C"]
    narration_zh: str
    rhythm: Literal["fast", "normal", "slow"] | None = None
    notes: str | None = None
    component: str | None = None
    transition: Literal[
        "fade", "slide", "slide-left", "zoom-in", "wipe", "glitch", "none",
    ] | None = None
    # 可选电影语言标签（有则覆盖自动推断）
    shot_type: Literal[
        "establishing", "medium", "close-up", "detail",
        "screen", "diagram", "data", "social", "cta", "quote",
    ] | None = None
    camera_move: Literal[
        "static", "push-in", "subtle-zoom", "drift-left", "drift-right",
    ] | None = None
    lighting_tag: Literal[
        "neutral", "bright", "dramatic", "cool", "warm", "accent",
    ] | None = None
    camera_intensity: float | None = None

    # 素材 A
    slide_content: SlideContent | None = None
    # 素材 B
    recording_instruction: str | None = None
    terminal_session: list[TerminalStep] | None = None
    # 素材 C
    source_video_index: int | None = None
    source_start: float | None = None
    source_end: float | None = None

    # 图片叠加组件
    image_content: ImageContent | None = None
    # 网络视频组件
    web_video: WebVideo | None = None

    # 闪现梗图叠加
    flash_meme: FlashMeme | None = None

    # 高级组件
    code_content: CodeContent | None = None
    social_card: SocialCard | None = None
    diagram: Diagram | None = None
    hero_stat: HeroStat | None = None
    browser_content: BrowserContent | None = None

    @field_validator("component")
    @classmethod
    def validate_component(cls, v: str | None) -> str | None:
        if v is None:
            return v
        m = _COMPONENT_RE.match(v)
        if not m:
            raise ValueError(
                f"component 格式错误: '{v}'，应为 '{{schema}}.{{style}}'，"
                f"如 'slide.tech-dark'"
            )
        schema = m.group(1)
        if schema not in _VALID_SCHEMAS:
            raise ValueError(
                f"未知 schema: '{schema}'，合法值: {sorted(_VALID_SCHEMAS)}"
            )
        return v

    @model_validator(mode="after")
    def validate_material_data(self) -> "ScriptSegment":
        """校验 material 类型对应的数据字段。"""
        errors = []

        if self.material == "A" and not self.component:
            if not self.slide_content:
                errors.append("material=A 且无 component 时必须有 slide_content")

        if self.component and self.component.startswith("image-overlay"):
            if not self.image_content:
                errors.append("使用 image-overlay 组件时必须有 image_content")

        if self.component and self.component.startswith("web-video"):
            if not self.web_video:
                errors.append("使用 web-video 组件时必须有 web_video")

        if self.component and self.component.startswith("social-card"):
            if not self.social_card:
                errors.append("使用 social-card 组件时必须有 social_card")

        if self.component and self.component.startswith("code-block"):
            if not self.code_content:
                errors.append("使用 code-block 组件时必须有 code_content")

        if self.component and self.component.startswith("diagram"):
            if not self.diagram:
                errors.append("使用 diagram 组件时必须有 diagram")

        if self.component and self.component.startswith("hero-stat"):
            if not self.hero_stat:
                errors.append("使用 hero-stat 组件时必须有 hero_stat")

        if self.component and self.component.startswith("browser"):
            if not self.browser_content:
                errors.append("使用 browser 组件时必须有 browser_content")

        if self.material == "B" and not self.component:
            if not self.terminal_session and not self.recording_instruction:
                errors.append(
                    "material=B 且无 component 时必须有 terminal_session 或 recording_instruction"
                )

        if self.material == "C":
            if self.source_start is not None and self.source_end is not None:
                if self.source_start >= self.source_end:
                    errors.append(
                        f"material=C 的 source_start ({self.source_start}) "
                        f"必须 < source_end ({self.source_end})"
                    )

        if self.camera_intensity is not None:
            if not (0.0 <= self.camera_intensity <= 1.2):
                errors.append(
                    f"camera_intensity ({self.camera_intensity}) 必须在 0.0-1.2 之间"
                )
            if self.camera_move == "static" and self.camera_intensity > 0:
                errors.append("camera_move=static 时 camera_intensity 必须为 0")

        if errors:
            raise ValueError("; ".join(errors))
        return self


# ── ScriptData (顶层) ─────────────────────────────────────


class ScriptData(BaseModel):
    """script.json 的顶层结构。"""
    model_config = ConfigDict(extra="ignore")

    title: str
    description: str
    tags: list[str]
    segments: list[ScriptSegment]
    source_channel: str | None = None
    total_duration_hint: float | None = None
    # 多源模式额外字段
    sources_used: list[str] | None = None


# ── 验证入口 ───────────────────────────────────────────────


def validate_script(script: dict) -> tuple[ScriptData | None, list[str]]:
    """验证 script.json 结构。

    Returns:
        (解析后的 ScriptData, 错误消息列表)
        如果验证通过，errors 为空列表。
        如果失败，ScriptData 为 None，errors 包含所有错误描述。
    """
    errors: list[str] = []
    try:
        data = ScriptData.model_validate(script)
        return data, errors
    except Exception as e:
        # Pydantic ValidationError 可能包含多个错误
        err_str = str(e)
        # 提取人类可读的错误信息
        if hasattr(e, "errors"):
            for err in e.errors():  # type: ignore[union-attr]
                loc = " → ".join(str(x) for x in err.get("loc", []))
                msg = err.get("msg", str(err))
                errors.append(f"[{loc}] {msg}")
        else:
            errors.append(err_str)
        return None, errors


def collect_script_blockers(script: dict, require_narration: bool = True) -> list[str]:
    """收集会阻塞下游阶段的脚本问题。

    包括:
    1) schema 结构错误（字段缺失、component 非法、类型错误等）
    2) （可选）空 narration_zh 段落
    """
    _, errors = validate_script(script)
    blockers = list(errors)

    if require_narration:
        for idx, seg in enumerate(script.get("segments", []), start=1):
            if not isinstance(seg, dict):
                blockers.append(f"[segments → {idx}] 结构错误: 段落不是对象")
                continue
            narration = (seg.get("narration_zh") or "").strip()
            if narration:
                continue
            seg_id = seg.get("id", idx)
            blockers.append(f"[segment {seg_id}] narration_zh 不能为空")

    return blockers
