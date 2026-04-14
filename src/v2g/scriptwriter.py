"""Stage 3: AI 生成二创解说脚本 (含三素材分配)。"""

import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import click

from v2g.config import Config
from v2g.checkpoint import PipelineState
from v2g.llm import call_llm
from v2g.quality_profile import resolve_quality_profile, load_profile_prompt
from v2g.asset_context import build_asset_context

PROMPTS_DIR = Path(__file__).parent / "prompts"

SHOT_TYPES = frozenset({
    "establishing",
    "medium",
    "close-up",
    "detail",
    "screen",
    "diagram",
    "data",
    "social",
    "cta",
    "quote",
})
CAMERA_MOVES = frozenset({
    "static",
    "push-in",
    "subtle-zoom",
    "drift-left",
    "drift-right",
})
LIGHTING_TAGS = frozenset({
    "neutral",
    "bright",
    "dramatic",
    "cool",
    "warm",
    "accent",
})


def _read_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def _parse_srt_to_text(srt_content: str) -> str:
    """将 SRT 内容转为带时间戳的纯文本。"""
    lines = []
    entries = srt_content.strip().split("\n\n")
    for entry in entries:
        parts = entry.strip().split("\n")
        if len(parts) >= 3:
            timestamp = parts[1]
            text = " ".join(parts[2:])
            # 提取起始时间
            m = re.match(r"(\d{2}):(\d{2}):(\d{2})", timestamp)
            if m:
                h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
                total_s = h * 3600 + mi * 60 + s
                lines.append(f"[{total_s}s] {text}")
            else:
                lines.append(text)
    return "\n".join(lines)


def _extract_json(text: str) -> dict:
    """从 LLM 输出中提取 JSON，自动修复常见问题。"""
    text = text.strip()
    # 去掉代码块标记
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    # 找到 JSON 区域
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]

    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 修复常见问题: 尾逗号、中文引号、未转义换行、控制字符
    fixed = text
    # 修复字符串值内的裸换行 (在引号内的 \n 替换为 \\n)
    fixed = re.sub(r'(?<=": ")(.*?)(?=")', lambda m: m.group(0).replace('\n', '\\n').replace('\r', ''), fixed, flags=re.DOTALL)
    fixed = re.sub(r",\s*([}\]])", r"\1", fixed)  # 去尾逗号
    fixed = fixed.replace("\u201c", '"').replace("\u201d", '"')  # 中文引号
    fixed = fixed.replace("\u2018", "'").replace("\u2019", "'")
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # 最后尝试: 用 LLM 返回的原始文本逐行去掉注释
    lines = []
    for line in fixed.split("\n"):
        stripped = line.rstrip()
        # 去掉行尾 // 注释
        comment_match = re.search(r'(?<=["\d\]\}])\s*//.*$', stripped)
        if comment_match:
            stripped = stripped[:comment_match.start()]
        lines.append(stripped)
    fixed = "\n".join(lines)
    fixed = re.sub(r",\s*([}\]])", r"\1", fixed)
    return json.loads(fixed)


def _save_script_meta(
    output_dir: Path,
    model: str,
    system_prompt: str,
    user_message: str,
    response: str,
    quality_profile: str = "default",
):
    """保存脚本生成元数据，用于 prompt 版本追踪和质量回溯。"""
    prompt_hash = hashlib.md5(system_prompt.encode()).hexdigest()[:8]
    meta = {
        "model": model,
        "quality_profile": quality_profile,
        "prompt_hash": prompt_hash,
        "timestamp": datetime.now().isoformat(),
        "input_chars": len(user_message),
        "output_chars": len(response),
    }
    meta_path = output_dir / "script_meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _generate_recording_guide(script_data: dict, output_path: Path):
    """从脚本中提取素材 B 的录屏指南。"""
    lines = [
        "# 录屏操作指南\n",
        f"视频: {script_data.get('title', '未知')}\n",
        "---\n",
        "请按以下顺序录制操作视频，完成后将文件放入 `recordings/` 目录。\n",
        "文件命名格式: `seg_{id}.mp4` (例如 seg_3.mp4)\n\n",
    ]

    b_segments = [s for s in script_data.get("segments", []) if s.get("material") == "B"]

    if not b_segments:
        lines.append("*本脚本无需录屏素材*\n")
    else:
        for seg in b_segments:
            seg_id = seg.get("id", "?")
            instruction = seg.get("recording_instruction", "无具体说明")
            narration = seg.get("narration_zh", "")
            # 估算时长: 中文约 4 字/秒
            est_duration = max(10, len(narration) // 4)

            lines.append(f"## Segment {seg_id}\n")
            lines.append(f"**参考时长**: ~{est_duration} 秒\n")
            lines.append(f"**操作说明**: {instruction}\n")
            lines.append(f"**对应解说词**: {narration[:80]}...\n" if len(narration) > 80 else f"**对应解说词**: {narration}\n")
            lines.append(f"**输出文件**: `recordings/seg_{seg_id}.mp4`\n\n")

    output_path.write_text("".join(lines), encoding="utf-8")


def _generate_script_md(script_data: dict, output_path: Path):
    """生成人工可读的脚本 Markdown。"""
    lines = [
        f"# {script_data.get('title', '未命名')}\n",
        f"> {script_data.get('description', '')}\n",
        f"> 标签: {', '.join(script_data.get('tags', []))}\n",
        f"> 来源: {script_data.get('source_channel', '')}\n\n",
        "---\n\n",
    ]

    material_labels = {"A": "📊 PPT 图文", "B": "🖥️ 操作录屏", "C": "🎬 原视频片段"}
    type_labels = {"intro": "开头", "body": "主体", "outro": "结尾"}

    for seg in script_data.get("segments", []):
        seg_id = seg.get("id", "?")
        seg_type = type_labels.get(seg.get("type", "body"), "主体")
        material = seg.get("material", "?")
        mat_label = material_labels.get(material, material)
        component = seg.get("component", "")

        lines.append(f"## [{seg_id}] {seg_type} | {mat_label}\n\n")
        lines.append(f"{seg.get('narration_zh', '')}\n\n")
        if component:
            lines.append(f"*组件: `{component}`*\n")

        if component.startswith("social-card") and seg.get("social_card"):
            card = seg["social_card"]
            lines.append("*社交卡片:*\n")
            lines.append(f"- 平台: {card.get('platform', '')}\n")
            lines.append(f"- 作者: {card.get('author', '')}\n")
            text = (card.get("text", "") or "").strip().replace("\n", " ")
            if text:
                lines.append(f"- 文案: {text[:140]}{'...' if len(text) > 140 else ''}\n")
            stats = card.get("stats") or {}
            if stats:
                stat_parts = [f"{k}={v}" for k, v in stats.items()]
                lines.append(f"- 互动: {', '.join(stat_parts)}\n")
            lines.append("\n")

        elif component.startswith("browser") and seg.get("browser_content"):
            bc = seg["browser_content"]
            lines.append("*浏览器内容:*\n")
            if bc.get("url"):
                lines.append(f"- URL: {bc['url']}\n")
            if bc.get("pageTitle"):
                lines.append(f"- 页面标题: {bc['pageTitle']}\n")
            for ln in (bc.get("contentLines") or [])[:5]:
                lines.append(f"- {ln}\n")
            lines.append("\n")

        elif component.startswith("diagram") and seg.get("diagram"):
            dg = seg["diagram"]
            nodes = dg.get("nodes") or []
            edges = dg.get("edges") or []
            lines.append("*流程图:*\n")
            lines.append(f"- 节点数: {len(nodes)}\n")
            lines.append(f"- 连线数: {len(edges)}\n")
            for node in nodes[:4]:
                label = node.get("label", "")
                if label:
                    lines.append(f"- 节点: {label}\n")
            lines.append("\n")

        elif component.startswith("hero-stat") and seg.get("hero_stat"):
            hs = seg["hero_stat"]
            lines.append("*关键指标:*\n")
            for item in hs.get("stats", []):
                value = item.get("value", "")
                label = item.get("label", "")
                trend = item.get("trend", "")
                t = f" ({trend})" if trend else ""
                lines.append(f"- {label}: {value}{t}\n")
            if hs.get("footnote"):
                lines.append(f"- 说明: {hs['footnote']}\n")
            lines.append("\n")

        if material == "A" and "slide_content" in seg:
            sc = seg["slide_content"]
            lines.append(f"*卡片: {sc.get('title', '')}*\n")
            for bp in sc.get("bullet_points", []):
                lines.append(f"- {bp}\n")
            if sc.get("chart_hint"):
                lines.append(f"- 📈 {sc['chart_hint']}\n")
            lines.append("\n")
        elif material == "B" and "recording_instruction" in seg:
            lines.append(f"*录屏: {seg['recording_instruction']}*\n\n")
        elif material == "C":
            start = seg.get("source_start", 0)
            end = seg.get("source_end", 0)
            lines.append(f"*原视频 {start:.1f}s - {end:.1f}s*\n\n")

        if seg.get("notes"):
            lines.append(f"> {seg['notes']}\n\n")

        lines.append("---\n\n")

    output_path.write_text("".join(lines), encoding="utf-8")


def _split_narration_to_beats(narration: str) -> list[str]:
    """将段落旁白拆成逐句 beat（口语短句优先）。"""
    text = (narration or "").strip()
    if not text:
        return []

    token_map: dict[str, str] = {}

    def _protect_token(match: re.Match) -> str:
        key = f"__TK{len(token_map)}__"
        token_map[key] = match.group(0)
        return key

    # 保护不可切分 token（命令、URL、路径、反引号代码）
    protected = re.sub(
        r"`[^`]+`|https?://[^\s，。！？；;]+|(?:[A-Za-z]:\\\\|/)?(?:[\w.\-]+/){1,}[\w.\-]+|\b(?:v2g|node|npm|python3?|pip|git|ffmpeg|claude)\s+[^\n，。！？；;]+",
        _protect_token,
        text,
    )

    # 先按强停顿断句
    sentences = [s.strip() for s in re.split(r"(?<=[。！？!?；;])\s*", protected) if s.strip()]
    if not sentences:
        sentences = [protected]

    beats: list[str] = []
    for sent in sentences:
        # 长句再按逗号做轻拆分，保持口语节奏
        if len(sent) > 42 and ("，" in sent or "," in sent) and "__TK" not in sent:
            parts = [p.strip() for p in re.split(r"(?<=[，,])\s*", sent) if p.strip()]
            beats.extend(parts or [sent])
        else:
            beats.append(sent)

    # 恢复 token
    restored = []
    for beat in beats:
        val = beat
        for k, v in token_map.items():
            val = val.replace(k, v)
        restored.append(val.strip())

    # 最小句长保护：过短句与前句合并，避免“嗯。对。好。”式碎片
    merged: list[str] = []
    min_chars = 3
    for beat in restored:
        raw_len = len(re.sub(r"[\s，,。！？!?；;：:、\"'“”‘’]", "", beat))
        if merged and raw_len < min_chars:
            merged[-1] = f"{merged[-1]} {beat}".strip()
        else:
            merged.append(beat)

    # 首句过短时与次句合并
    if len(merged) >= 2:
        first_len = len(re.sub(r"[\s，,。！？!?；;：:、\"'“”‘’]", "", merged[0]))
        if first_len < min_chars:
            merged = [f"{merged[0]} {merged[1]}".strip()] + merged[2:]

    return [m for m in merged if m]


def _segment_visual_type(seg: dict) -> str:
    comp = (seg.get("component") or "").strip()
    if comp:
        return comp.split(".")[0]
    mat = seg.get("material", "A")
    return {"A": "slide", "B": "terminal", "C": "source-clip"}.get(mat, "slide")


def _segment_asset_candidates(seg: dict) -> list[str]:
    """推断该段潜在素材路径，供分镜与合成规划参考。"""
    seg_id = seg.get("id", "")
    material = seg.get("material", "A")
    comp = (seg.get("component") or "").strip()
    assets: list[str] = []

    if material == "A":
        assets.append(f"slides/slide_{seg_id}.png")
    if material == "B":
        assets.append(f"recordings/seg_{seg_id}.mp4")
    if material == "C":
        source_idx = seg.get("source_video_index", 0)
        assets.append(f"source_{source_idx}.mp4")

    image_content = seg.get("image_content") or {}
    if isinstance(image_content, dict) and image_content.get("image_path"):
        assets.append(str(image_content["image_path"]))

    web_video = seg.get("web_video") or {}
    if isinstance(web_video, dict):
        if web_video.get("source_url"):
            assets.append(str(web_video["source_url"]))
        if web_video.get("search_query"):
            assets.append(f"web_videos/seg_{seg_id}.mp4")

    if comp.startswith("social-card"):
        assets.append("images/tweet_*.png")

    # 去重且保持顺序
    dedup: list[str] = []
    seen = set()
    for a in assets:
        if a and a not in seen:
            seen.add(a)
            dedup.append(a)
    return dedup


def _pick_primary_asset(seg: dict, assets: list[str]) -> str:
    """按画面类型选择最能代表该镜头的主素材路径。"""
    if not assets:
        return ""

    visual_type = _segment_visual_type(seg)

    def _first(prefixes: tuple[str, ...]) -> str:
        for item in assets:
            for p in prefixes:
                if item.startswith(p):
                    return item
        return ""

    if visual_type == "image-overlay":
        image_content = seg.get("image_content") or {}
        image_path = str(image_content.get("image_path") or "").strip()
        if image_path and image_path in assets:
            return image_path
        picked = _first(("images/",))
        if picked:
            return picked

    if visual_type == "web-video":
        picked = _first(("web_videos/",))
        if picked:
            return picked
        web_video = seg.get("web_video") or {}
        source_url = str(web_video.get("source_url") or "").strip()
        if source_url and source_url in assets:
            return source_url

    if visual_type in {"terminal", "recording"}:
        picked = _first(("recordings/",))
        if picked:
            return picked

    if visual_type == "source-clip":
        picked = _first(("source_",))
        if picked:
            return picked

    if visual_type == "social-card":
        picked = _first(("images/",))
        if picked:
            return picked

    picked = _first(("slides/",))
    if picked:
        return picked

    return assets[0]


def _segment_scene_hint(seg: dict, asset_path: str) -> str:
    """生成镜头的一行画面说明，便于人工快速校稿。"""
    visual_type = _segment_visual_type(seg)

    if visual_type == "slide":
        slide = seg.get("slide_content") or {}
        title = str(slide.get("title") or "").strip()
        bullets = slide.get("bullet_points") or []
        first_bullet = str(bullets[0]).strip() if bullets else ""
        if title and first_bullet:
            return f"{title} / {first_bullet}"
        return title or first_bullet or "图文卡片"

    if visual_type in {"terminal", "recording"}:
        steps = seg.get("terminal_session") or []
        if isinstance(steps, list):
            for step in steps:
                if not isinstance(step, dict):
                    continue
                if step.get("type") == "input" and step.get("text"):
                    return f"终端命令: {step['text']}"
        ins = str(seg.get("recording_instruction") or "").strip()
        return ins or "录屏演示"

    if visual_type == "source-clip":
        ss = seg.get("source_start")
        se = seg.get("source_end")
        if ss is not None and se is not None:
            return f"源视频片段 {ss:.1f}s-{se:.1f}s"
        return "源视频片段"

    if visual_type == "image-overlay":
        image = seg.get("image_content") or {}
        text = str(image.get("overlay_text") or "").strip()
        path = str(image.get("image_path") or "").strip()
        if text:
            return text
        if path:
            return f"图片叠字: {Path(path).name}"
        return f"图片叠字: {Path(asset_path).name}" if asset_path else "图片叠字"

    if visual_type == "web-video":
        web_video = seg.get("web_video") or {}
        query = str(web_video.get("search_query") or "").strip()
        if query:
            return f"网络视频搜索: {query}"
        source = str(web_video.get("source_url") or "").strip()
        if source:
            host = urlparse(source).netloc or source
            return f"网络视频引用: {host}"
        return "网络视频片段"

    if visual_type == "diagram":
        return "流程图/关系图"
    if visual_type == "hero-stat":
        return "关键数据强调"
    if visual_type == "social-card":
        return "社媒卡片引用"
    if visual_type == "code-block":
        return "代码片段高亮"
    if visual_type == "browser":
        return "浏览器页面演示"

    return "基础镜头"


def _first_sentence(text: str) -> str:
    val = (text or "").strip()
    if not val:
        return ""
    parts = [s.strip() for s in re.split(r"[。！？!?；;]", val) if s.strip()]
    return parts[0] if parts else val


def _short_label(text: str, limit: int = 20) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if not value:
        return ""
    if len(value) <= limit:
        return value
    trimmed = value[:limit].rstrip("，,。.!?；;：:、 ")
    return (trimmed or value[:limit]) + "…"


def _beat_scene_hint(seg: dict, beat_text: str, asset_path: str) -> str:
    """生成逐句短标签，避免整段复用导致信息过长。"""
    visual_type = _segment_visual_type(seg)
    beat_label = _short_label(beat_text, limit=16)
    base = _segment_scene_hint(seg, asset_path)
    base_label = _short_label(base, limit=22)

    if visual_type == "slide":
        return beat_label or base_label or "图文卡片"

    if visual_type in {"terminal", "recording"}:
        steps = seg.get("terminal_session") or []
        cmd = ""
        if isinstance(steps, list):
            for step in steps:
                if not isinstance(step, dict):
                    continue
                if step.get("type") == "input" and step.get("text"):
                    cmd = _short_label(step["text"], limit=14)
                    break
        if cmd and beat_label:
            return f"{cmd} / {beat_label}"
        return cmd or beat_label or "录屏演示"

    if visual_type == "image-overlay":
        image = seg.get("image_content") or {}
        overlay = _short_label(image.get("overlay_text", ""), limit=16)
        if overlay and beat_label:
            return f"{overlay} / {beat_label}"
        return overlay or beat_label or "图片叠字"

    if visual_type == "web-video":
        web_video = seg.get("web_video") or {}
        query = _short_label(web_video.get("search_query", ""), limit=16)
        if query and beat_label:
            return f"{query} / {beat_label}"
        return query or beat_label or base_label or "网络视频片段"

    if visual_type == "source-clip":
        if beat_label:
            return f"源片段 / {beat_label}"
        return "源视频片段"

    if beat_label and base_label:
        return f"{base_label} / {beat_label}"
    return beat_label or base_label or "基础镜头"


def _infer_cinematography_tags(seg: dict, beat_text: str, beat_id: int) -> dict:
    """根据逐句文案 + 段落信息推断分镜标签。"""
    visual_type = _segment_visual_type(seg)
    beat = (beat_text or "").strip()
    lower = beat.lower()
    seg_type = seg.get("type", "body")
    rhythm = seg.get("rhythm", "normal")

    explicit_shot = seg.get("shot_type")
    explicit_move = seg.get("camera_move")
    explicit_light = seg.get("lighting_tag")
    explicit_intensity = seg.get("camera_intensity")
    used_explicit = False

    if explicit_shot in SHOT_TYPES:
        shot_type = explicit_shot
        used_explicit = True
    elif visual_type in {"terminal", "recording", "source-clip", "web-video", "browser", "code-block"}:
        shot_type = "screen"
    elif visual_type == "diagram":
        shot_type = "diagram"
    elif visual_type == "hero-stat":
        shot_type = "data"
    elif visual_type == "social-card":
        shot_type = "social"
    elif seg_type == "intro":
        shot_type = "establishing"
    elif seg_type == "outro":
        shot_type = "cta"
    elif re.search(r"\d+|%|万|亿|增长|提升|下降|留存", beat):
        shot_type = "data"
    elif re.search(r"[“\"].+[”\"]|观点|结论|一句话", beat):
        shot_type = "quote"
    elif len(beat) <= 8:
        shot_type = "detail"
    else:
        shot_type = "medium"

    if explicit_move in CAMERA_MOVES:
        camera_move = explicit_move
        used_explicit = True
    elif shot_type in {"screen", "diagram"}:
        camera_move = "static"
    elif rhythm == "fast":
        camera_move = "drift-right" if beat_id % 2 else "drift-left"
    elif shot_type in {"data", "social", "establishing"}:
        camera_move = "push-in"
    else:
        camera_move = "subtle-zoom"

    warn_tokens = ("风险", "危险", "失败", "踩坑", "错误", "崩", "告警", "bug", "dmca")
    cta_tokens = ("总结", "最后", "今晚", "现在就", "马上", "执行", "关注", "订阅", "cta")
    if explicit_light in LIGHTING_TAGS:
        lighting_tag = explicit_light
        used_explicit = True
    elif any(t in lower for t in warn_tokens):
        lighting_tag = "dramatic"
    elif any(t in lower for t in cta_tokens) or seg_type == "outro":
        lighting_tag = "warm"
    elif visual_type in {"terminal", "recording", "code-block", "browser"}:
        lighting_tag = "cool"
    elif shot_type in {"data", "social"}:
        lighting_tag = "accent"
    elif seg_type == "intro":
        lighting_tag = "dramatic"
    else:
        lighting_tag = "neutral"

    if isinstance(explicit_intensity, (int, float)) and not isinstance(explicit_intensity, bool):
        camera_intensity = max(0.0, min(float(explicit_intensity), 1.2))
        used_explicit = True
    else:
        camera_intensity = {"fast": 1.0, "slow": 0.55}.get(rhythm, 0.75)
    if camera_move == "static":
        camera_intensity = 0.0

    return {
        "shot_type": shot_type,
        "camera_move": camera_move,
        "lighting_tag": lighting_tag,
        "camera_intensity": round(float(camera_intensity), 3),
        "tag_source": "script" if used_explicit else "auto",
    }


def _infer_segment_cinematography(
    seg: dict,
    seg_index: int,
    seg_beats: list[dict] | None = None,
    beat_timeline: dict[int, dict] | None = None,
) -> dict:
    """按段聚合运镜/光线标签，供渲染层直接消费。"""
    seg_beats = seg_beats or []
    beat_timeline = beat_timeline or {}
    if not seg_beats:
        seed_text = _first_sentence(seg.get("narration_zh", "")) or "过渡镜头"
        return _infer_cinematography_tags(seg, seed_text, beat_id=max(1, seg_index + 1))

    scored: list[tuple[dict, float]] = []
    for beat in seg_beats:
        beat_id = int(beat.get("beat_id", 0) or 0)
        tags = _infer_cinematography_tags(seg, beat.get("text", ""), beat_id=max(1, beat_id))
        bt = beat_timeline.get(beat_id) or {}
        duration = _as_float(bt.get("duration_sec"), 0.0)
        if duration <= 0:
            duration = max(0.8, _estimate_beat_weight(beat.get("text", "")) / 6.0)
        scored.append((tags, duration))

    def _weighted_pick(field: str, default: str) -> str:
        acc: dict[str, float] = defaultdict(float)
        order: list[str] = []
        for tags, w in scored:
            val = str(tags.get(field, default) or default)
            if val not in acc:
                order.append(val)
            acc[val] += max(0.01, w)
        if not acc:
            return default
        best = max(acc.items(), key=lambda kv: (kv[1], -order.index(kv[0])))
        return best[0]

    shot_type = _weighted_pick("shot_type", "medium")
    camera_move = _weighted_pick("camera_move", "subtle-zoom")
    lighting_tag = _weighted_pick("lighting_tag", "neutral")

    total_w = sum(max(0.01, w) for _, w in scored) or 1.0
    camera_intensity = sum(tags.get("camera_intensity", 0.75) * max(0.01, w) for tags, w in scored) / total_w
    if camera_move == "static":
        camera_intensity = 0.0

    tag_source = "script" if any(tags.get("tag_source") == "script" for tags, _ in scored) else "auto"
    return {
        "shot_type": shot_type,
        "camera_move": camera_move,
        "lighting_tag": lighting_tag,
        "camera_intensity": round(float(max(0.0, min(camera_intensity, 1.2))), 3),
        "tag_source": tag_source,
    }


def _segment_visual_change(seg: dict) -> str:
    """给镜头一个简化的视觉变化说明，便于人工校审。"""
    parts: list[str] = []
    rhythm = seg.get("rhythm")
    if rhythm == "fast":
        parts.append("快切")
    elif rhythm == "slow":
        parts.append("慢切")
    else:
        parts.append("常速")

    transition = seg.get("transition")
    if transition and transition != "none":
        parts.append(f"转场:{transition}")

    schema = _segment_visual_type(seg)
    schema_effect = {
        "slide": "标题弹入",
        "terminal": "打字光标",
        "recording": "镜头轻推",
        "source-clip": "片段切入",
        "code-block": "代码高亮",
        "social-card": "卡片弹入",
        "diagram": "节点渐显",
        "hero-stat": "数字跳动",
        "browser": "页面滚动",
        "image-overlay": "Ken Burns",
        "web-video": "画面叠字",
    }
    parts.append(schema_effect.get(schema, "基础切换"))
    return " + ".join(parts)


def _build_script_beats(script_data: dict) -> list[dict]:
    beats: list[dict] = []
    beat_id = 1
    for seg in script_data.get("segments", []):
        seg_id = seg.get("id", beat_id)
        narration = seg.get("narration_zh", "")
        items = _split_narration_to_beats(narration)
        if not items and narration:
            items = [narration]
        for line in items:
            beats.append({
                "beat_id": beat_id,
                "segment_id": seg_id,
                "text": line,
                "est_sec": round(max(1.0, len(line) / 4.0), 1),
            })
            beat_id += 1
    return beats


def _load_timing_map(output_dir: Path) -> dict[str, dict]:
    """读取 TTS timing.json（不存在则返回空）。"""
    timing_path = output_dir / "voiceover" / "timing.json"
    if not timing_path.exists():
        return {}
    try:
        data = json.loads(timing_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _as_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _estimate_beat_weight(text: str) -> float:
    """估算语音节奏权重（兼容中英混合、命令、路径、URL）。"""
    val = str(text or "")
    if not val.strip():
        return 1.0
    cjk = len(re.findall(r"[\u4e00-\u9fff]", val))
    latin_chunks = re.findall(r"[A-Za-z0-9_./:-]+", val)
    latin_weight = sum(min(len(tok), 12) for tok in latin_chunks) * 0.32
    punct_weight = len(re.findall(r"[，,。！？!?；;：:、]", val)) * 0.35
    has_structured = bool(
        re.search(
            r"https?://|(?:[A-Za-z]:\\\\|/)?(?:[\w.\-]+/){1,}[\w.\-]+|\b(?:v2g|node|npm|python3?|pip|git|ffmpeg|claude)\b",
            val,
        )
    )
    structured_bonus = 2.6 if has_structured else 0.0
    return max(1.0, cjk + latin_weight + punct_weight + structured_bonus)


def _build_segment_timeline(script_data: dict, timing_map: dict[str, dict]) -> tuple[dict[int, dict], bool]:
    """将 segment 时长映射为绝对时间轴。"""
    seg_timeline: dict[int, dict] = {}
    cursor = 0.0
    has_timing = False

    for seg in script_data.get("segments", []):
        seg_id = seg.get("id")
        if seg_id is None:
            continue
        t = timing_map.get(str(seg_id), {})
        duration = max(0.0, _as_float(t.get("duration"), 0.0))
        gap_after = max(0.0, _as_float(t.get("gap_after"), 0.0))
        if duration > 0:
            start = cursor
            end = start + duration
            cursor = end + gap_after
            has_timing = True
        else:
            start = None
            end = None

        seg_timeline[int(seg_id)] = {
            "start_sec": round(start, 3) if start is not None else None,
            "end_sec": round(end, 3) if end is not None else None,
            "duration_sec": round(duration, 3),
            "gap_after_sec": round(gap_after, 3),
        }

    return seg_timeline, has_timing


def _build_beat_timeline(beats: list[dict], seg_timeline: dict[int, dict]) -> dict[int, dict]:
    """把 segment 时间轴细分到 beat（按字数近似分配）。"""
    beat_timeline: dict[int, dict] = {}
    by_seg: dict[int, list[dict]] = {}
    for beat in beats:
        seg_id = beat.get("segment_id")
        if seg_id is None:
            continue
        by_seg.setdefault(int(seg_id), []).append(beat)

    for seg_id, seg_beats in by_seg.items():
        timeline = seg_timeline.get(seg_id) or {}
        seg_start = timeline.get("start_sec")
        seg_duration = _as_float(timeline.get("duration_sec"), 0.0)
        if seg_start is None or seg_duration <= 0:
            continue

        weights = [max(1.0, _estimate_beat_weight(str(b.get("text", "")))) for b in seg_beats]
        total_weight = sum(weights) or 1
        cursor = float(seg_start)
        seg_end = float(seg_start) + seg_duration

        for idx, beat in enumerate(seg_beats):
            if idx == len(seg_beats) - 1:
                end = seg_end
            else:
                portion = seg_duration * (weights[idx] / total_weight)
                end = cursor + portion
            beat_timeline[int(beat["beat_id"])] = {
                "start_sec": round(cursor, 3),
                "end_sec": round(end, 3),
                "duration_sec": round(max(0.0, end - cursor), 3),
            }
            cursor = end

    return beat_timeline


def _build_shot_plan(script_data: dict, beats: list[dict], timing_map: dict[str, dict]) -> dict:
    seg_map = {seg.get("id"): seg for seg in script_data.get("segments", [])}
    seg_timeline, has_timing = _build_segment_timeline(script_data, timing_map)
    beat_timeline = _build_beat_timeline(beats, seg_timeline)
    shots = []
    for beat in beats:
        seg = seg_map.get(beat["segment_id"], {})
        assets = _segment_asset_candidates(seg)
        primary_asset = _pick_primary_asset(seg, assets)
        cine = _infer_cinematography_tags(seg, beat.get("text", ""), int(beat["beat_id"]))
        bt = beat_timeline.get(int(beat["beat_id"]), {})
        st = seg_timeline.get(int(beat["segment_id"]), {})
        shot = {
            "shot_id": beat["beat_id"],
            "beat_id": beat["beat_id"],
            "segment_id": beat["segment_id"],
            "text": beat["text"],
            "visual_type": _segment_visual_type(seg),
            "component": seg.get("component", ""),
            "asset_path": primary_asset,
            "asset_candidates": assets,
            "scene_hint": _beat_scene_hint(seg, beat["text"], primary_asset),
            "visual_change": _segment_visual_change(seg),
            "shot_type": cine["shot_type"],
            "camera_move": cine["camera_move"],
            "lighting_tag": cine["lighting_tag"],
            "camera_intensity": cine["camera_intensity"],
            "tag_source": cine["tag_source"],
            "start_sec": bt.get("start_sec"),
            "end_sec": bt.get("end_sec"),
            "duration_sec": bt.get("duration_sec"),
            "segment_start_sec": st.get("start_sec"),
            "segment_end_sec": st.get("end_sec"),
        }
        if seg.get("material") == "C":
            shot["source_start"] = seg.get("source_start")
            shot["source_end"] = seg.get("source_end")
        shots.append(shot)

    return {
        "version": "v1",
        "title": script_data.get("title", ""),
        "timing_source": "voiceover/timing.json" if has_timing else "",
        "has_timing": has_timing,
        "shots": shots,
    }


def _build_render_plan(script_data: dict, timing_map: dict[str, dict], beats: list[dict] | None = None) -> dict:
    seg_timeline, has_timing = _build_segment_timeline(script_data, timing_map)
    beats = beats or _build_script_beats(script_data)
    beat_timeline = _build_beat_timeline(beats, seg_timeline)
    beats_by_seg: dict[int, list[dict]] = defaultdict(list)
    for beat in beats:
        seg_id = beat.get("segment_id")
        if seg_id is None:
            continue
        beats_by_seg[int(seg_id)].append(beat)

    segments = []
    for idx, seg in enumerate(script_data.get("segments", [])):
        assets = _segment_asset_candidates(seg)
        primary_asset = _pick_primary_asset(seg, assets)
        seg_id = seg.get("id")
        seg_beats = beats_by_seg.get(int(seg_id), []) if seg_id is not None else []
        cine = _infer_segment_cinematography(seg, idx, seg_beats=seg_beats, beat_timeline=beat_timeline)
        seg_id = seg.get("id")
        st = seg_timeline.get(int(seg_id), {}) if seg_id is not None else {}
        segments.append({
            "segment_id": seg_id,
            "type": seg.get("type", "body"),
            "material": seg.get("material", "A"),
            "component": seg.get("component", ""),
            "visual_type": _segment_visual_type(seg),
            "narration_chars": len((seg.get("narration_zh") or "").strip()),
            "asset_path": primary_asset,
            "expected_assets": assets,
            "scene_hint": _segment_scene_hint(seg, primary_asset),
            "cinematography": {
                "shot_type": cine["shot_type"],
                "camera_move": cine["camera_move"],
                "lighting_tag": cine["lighting_tag"],
                "camera_intensity": cine["camera_intensity"],
                "tag_source": cine["tag_source"],
            },
            "subtitle_source": "voiceover/word_timing.json -> fallback timing.json",
            "start_sec": st.get("start_sec"),
            "end_sec": st.get("end_sec"),
            "duration_sec": st.get("duration_sec"),
            "gap_after_sec": st.get("gap_after_sec"),
        })

    return {
        "version": "v1",
        "title": script_data.get("title", ""),
        "render_backend": "remotion",
        "toolchain": ["voxcpm/edge-tts/minimax", "remotion", "ffmpeg"],
        "timing_source": "voiceover/timing.json" if has_timing else "",
        "has_timing": has_timing,
        "segments": segments,
    }


def _generate_script_beats_md(beats: list[dict], shot_plan: dict, output_path: Path):
    """输出人工可读中间层：逐句文案 + 逐句画面编排。"""
    shot_map = {s["beat_id"]: s for s in shot_plan.get("shots", [])}
    lines = [
        "# 逐句文案（口语化）\n\n",
    ]
    for beat in beats:
        lines.append(f"{beat['beat_id']}. {beat['text']}\n")
    lines.append(f"\n共 {len(beats)} 句。\n\n")

    lines.append("## 逐句画面编排（Step 6b 逐句匹配）\n\n")
    lines.append("| # | 文案 | 分镜 | 运镜 | 光线 | 画面类型 | 素材路径 | 画面说明 | 时间窗 |\n")
    lines.append("|---:|---|---|---|---|---|---|---|---|\n")
    for beat in beats:
        shot = shot_map.get(beat["beat_id"], {})
        text = beat["text"].replace("\n", " ")
        asset = shot.get("asset_path") or "-"
        start_sec = shot.get("start_sec")
        end_sec = shot.get("end_sec")
        if start_sec is None or end_sec is None:
            window = "-"
        else:
            window = f"{float(start_sec):.2f}-{float(end_sec):.2f}s"
        scene_hint = (shot.get("scene_hint") or "-").replace("\n", " ")
        lines.append(
            f"| {beat['beat_id']} | {text} | {shot.get('shot_type', '-')} | "
            f"{shot.get('camera_move', '-')} | {shot.get('lighting_tag', '-')} | "
            f"{shot.get('visual_type', '-')} | `{asset}` | {scene_hint} | {window} |\n"
        )

    output_path.write_text("".join(lines), encoding="utf-8")


def _generate_script_artifacts(script_data: dict, output_dir: Path):
    """生成脚本中间层产物：文案层、分镜层、合成层。"""
    beats = _build_script_beats(script_data)
    timing_map = _load_timing_map(output_dir)
    shot_plan = _build_shot_plan(script_data, beats, timing_map)
    render_plan = _build_render_plan(script_data, timing_map, beats=beats)

    (output_dir / "shot_plan.json").write_text(
        json.dumps(shot_plan, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "render_plan.json").write_text(
        json.dumps(render_plan, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _generate_script_beats_md(beats, shot_plan, output_dir / "script_beats.md")
    _generate_script_beats_md(beats, shot_plan, output_dir / "storyboard.md")


def sync_script_sidecars(script_data: dict, output_dir: Path) -> None:
    """以 script.json 为唯一真源，重建所有派生产物。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    _generate_script_md(script_data, output_dir / "script.md")
    _generate_recording_guide(script_data, output_dir / "recording_guide.md")
    _generate_script_artifacts(script_data, output_dir)


def validate_script_sidecars(script_data: dict, output_dir: Path) -> list[str]:
    """校验 script.json 与 sidecar 产物的一致性。"""
    issues: list[str] = []
    segments = script_data.get("segments", [])
    seg_map = {seg.get("id"): seg for seg in segments}
    seg_ids = [seg.get("id") for seg in segments]
    beats = _build_script_beats(script_data)
    beat_map = {b["beat_id"]: b for b in beats}

    shot_path = output_dir / "shot_plan.json"
    render_path = output_dir / "render_plan.json"

    if not shot_path.exists():
        issues.append("缺少 sidecar: shot_plan.json")
    else:
        try:
            shot_plan = json.loads(shot_path.read_text(encoding="utf-8"))
            shots = shot_plan.get("shots", [])
            has_timing = bool(shot_plan.get("has_timing"))
            if len(shots) != len(beats):
                issues.append(
                    f"shot_plan 条目数不一致: shots={len(shots)} vs beats={len(beats)}"
                )
            prev_end: float | None = None
            for shot in shots:
                beat_id = shot.get("beat_id")
                seg_id = shot.get("segment_id")
                if beat_id not in beat_map:
                    issues.append(f"shot_plan 包含未知 beat_id={beat_id}")
                    continue
                if beat_map[beat_id].get("segment_id") != seg_id:
                    issues.append(
                        f"shot_plan beat->segment 映射不一致: beat_id={beat_id}, "
                        f"plan={seg_id}, expected={beat_map[beat_id].get('segment_id')}"
                    )
                seg = seg_map.get(seg_id)
                if not seg:
                    issues.append(f"shot_plan 引用了不存在的 segment_id={seg_id}")
                    continue
                expected_visual = _segment_visual_type(seg)
                if shot.get("visual_type") != expected_visual:
                    issues.append(
                        f"shot_plan visual_type 不一致: segment_id={seg_id}, "
                        f"plan={shot.get('visual_type')}, expected={expected_visual}"
                    )
                shot_type = shot.get("shot_type")
                if shot_type not in SHOT_TYPES:
                    issues.append(
                        f"shot_plan shot_type 非法: beat_id={beat_id}, value={shot_type}"
                    )
                camera_move = shot.get("camera_move")
                if camera_move not in CAMERA_MOVES:
                    issues.append(
                        f"shot_plan camera_move 非法: beat_id={beat_id}, value={camera_move}"
                    )
                lighting_tag = shot.get("lighting_tag")
                if lighting_tag not in LIGHTING_TAGS:
                    issues.append(
                        f"shot_plan lighting_tag 非法: beat_id={beat_id}, value={lighting_tag}"
                    )
                cam_intensity = _as_float(shot.get("camera_intensity"), -1.0)
                if cam_intensity < 0 or cam_intensity > 1.2:
                    issues.append(
                        f"shot_plan camera_intensity 越界: beat_id={beat_id}, value={shot.get('camera_intensity')}"
                    )
                if has_timing:
                    start_sec = shot.get("start_sec")
                    end_sec = shot.get("end_sec")
                    if start_sec is None or end_sec is None:
                        issues.append(f"shot_plan 缺失时间窗: beat_id={beat_id}")
                    else:
                        s = _as_float(start_sec, -1)
                        e = _as_float(end_sec, -1)
                        if s < 0 or e < 0 or e <= s:
                            issues.append(
                                f"shot_plan 时间窗非法: beat_id={beat_id}, start={start_sec}, end={end_sec}"
                            )
                        if prev_end is not None and s + 0.02 < prev_end:
                            issues.append(
                                f"shot_plan 时间线倒退: beat_id={beat_id}, start={s:.3f}, prev_end={prev_end:.3f}"
                            )
                        prev_end = e
        except Exception as e:
            issues.append(f"shot_plan.json 解析失败: {e}")

    if not render_path.exists():
        issues.append("缺少 sidecar: render_plan.json")
    else:
        try:
            render_plan = json.loads(render_path.read_text(encoding="utf-8"))
            rsegs = render_plan.get("segments", [])
            has_timing = bool(render_plan.get("has_timing"))
            if len(rsegs) != len(segments):
                issues.append(
                    f"render_plan 条目数不一致: segments={len(rsegs)} vs script={len(segments)}"
                )
            rmap = {s.get("segment_id"): s for s in rsegs}
            for seg_id in seg_ids:
                seg = seg_map.get(seg_id) or {}
                rseg = rmap.get(seg_id)
                if not rseg:
                    issues.append(f"render_plan 缺失 segment_id={seg_id}")
                    continue
                expected_material = seg.get("material", "A")
                if rseg.get("material") != expected_material:
                    issues.append(
                        f"render_plan material 不一致: segment_id={seg_id}, "
                        f"plan={rseg.get('material')}, expected={expected_material}"
                    )
                expected_visual = _segment_visual_type(seg)
                if rseg.get("visual_type") != expected_visual:
                    issues.append(
                        f"render_plan visual_type 不一致: segment_id={seg_id}, "
                        f"plan={rseg.get('visual_type')}, expected={expected_visual}"
                    )
                cine = rseg.get("cinematography") or {}
                if not isinstance(cine, dict):
                    issues.append(f"render_plan cinematography 非对象: segment_id={seg_id}")
                else:
                    shot_type = cine.get("shot_type")
                    camera_move = cine.get("camera_move")
                    lighting_tag = cine.get("lighting_tag")
                    if shot_type not in SHOT_TYPES:
                        issues.append(
                            f"render_plan shot_type 非法: segment_id={seg_id}, value={shot_type}"
                        )
                    if camera_move not in CAMERA_MOVES:
                        issues.append(
                            f"render_plan camera_move 非法: segment_id={seg_id}, value={camera_move}"
                        )
                    if lighting_tag not in LIGHTING_TAGS:
                        issues.append(
                            f"render_plan lighting_tag 非法: segment_id={seg_id}, value={lighting_tag}"
                        )
                    cam_intensity = _as_float(cine.get("camera_intensity"), -1.0)
                    if cam_intensity < 0 or cam_intensity > 1.2:
                        issues.append(
                            f"render_plan camera_intensity 越界: segment_id={seg_id}, value={cine.get('camera_intensity')}"
                        )
                if has_timing:
                    s = rseg.get("start_sec")
                    e = rseg.get("end_sec")
                    d = _as_float(rseg.get("duration_sec"), -1)
                    if s is None or e is None:
                        issues.append(f"render_plan 缺失时间窗: segment_id={seg_id}")
                    else:
                        sv = _as_float(s, -1)
                        ev = _as_float(e, -1)
                        if sv < 0 or ev < 0 or ev <= sv:
                            issues.append(
                                f"render_plan 时间窗非法: segment_id={seg_id}, start={s}, end={e}"
                            )
                        if d > 0 and abs((ev - sv) - d) > 0.12:
                            issues.append(
                                f"render_plan 时长不一致: segment_id={seg_id}, "
                                f"window={ev - sv:.3f}, duration_sec={d:.3f}"
                            )
        except Exception as e:
            issues.append(f"render_plan.json 解析失败: {e}")

    return issues


def _load_subtitles_for_script(state: PipelineState) -> tuple[str, str]:
    """加载脚本生成所需字幕，优先中文，缺失时回退英文。

    Returns:
        (zh_text, en_text)
    """
    zh_text = ""
    en_text = ""

    zh_srt_path = Path(state.zh_srt) if state.zh_srt else None
    en_srt_path = Path(state.en_srt) if state.en_srt else None

    if zh_srt_path and zh_srt_path.exists():
        zh_text = _parse_srt_to_text(zh_srt_path.read_text(encoding="utf-8"))

    if en_srt_path and en_srt_path.exists():
        en_text = _parse_srt_to_text(en_srt_path.read_text(encoding="utf-8"))

    if not zh_text and not en_text:
        raise click.ClickException(
            "未找到可用字幕：需要 subtitle_zh.srt 或 subtitle_en.srt。"
        )

    return zh_text, en_text


def run_script(
    cfg: Config,
    video_id: str,
    model: str,
    quality_profile: str = "default",
) -> PipelineState:
    """执行 Stage 3: AI 脚本生成。"""
    from v2g.workflow_contract import sync_workflow_contract

    state = PipelineState.load(cfg.output_dir, video_id)
    if not state.subtitled:
        raise click.ClickException("字幕尚未生成，请先运行 v2g prepare")

    if state.scripted:
        click.echo("⏭️  脚本已存在，跳过")
        return state

    output_dir = cfg.output_dir / video_id
    output_dir.mkdir(parents=True, exist_ok=True)
    sync_workflow_contract(
        output_dir, video_id,
        stage="script", status="start",
        message="开始脚本生成",
        extra={"model": model, "quality_profile": quality_profile},
    )

    # 读取字幕（优先中文，缺失时回退英文）
    zh_text, en_text = _load_subtitles_for_script(state)

    # 构建 user message
    user_parts = [
        f"## 视频信息\n",
        f"- Video ID: {video_id}",
        f"- URL: {state.video_url}",
    ]
    if zh_text:
        user_parts.append(f"\n## 中文字幕\n")
        user_parts.append(zh_text)
    if en_text and not zh_text:
        user_parts.append(f"\n## 英文字幕（仅有英文字幕，请据此生成中文解说）\n")
        user_parts.append(en_text)
    elif en_text:
        user_parts.append(f"\n## 英文字幕 (参考)\n")
        user_parts.append(en_text)

    # 读取 summary（如果存在）
    summary_path = cfg.l2n_output_dir / video_id / "summary.md"
    if summary_path.exists():
        user_parts.append(f"\n## 视频摘要\n")
        user_parts.append(summary_path.read_text(encoding="utf-8"))

    # 注入素材库历史反馈（留存表现 + 可复用素材）
    asset_ctx = build_asset_context(cfg)
    if asset_ctx:
        user_parts.append(f"\n{asset_ctx}")

    user_message = "\n".join(user_parts)
    try:
        profile = resolve_quality_profile(quality_profile)
    except ValueError as e:
        raise click.ClickException(str(e))
    profile_prompt = load_profile_prompt(profile["name"])

    from v2g.style_catalog import inject_catalog
    style_id_prefix = profile.get("style_id_prefix") or None
    system_prompt = inject_catalog(
        _read_prompt("script_system.md"),
        id_prefix=style_id_prefix,
    )
    if profile_prompt:
        system_prompt = (
            system_prompt
            + "\n\n## 质量档位约束\n"
            + profile_prompt
        )

    click.echo(f"🤖 生成二创脚本 (模型: {model}, 档位: {profile['name']})...")
    try:
        response = call_llm(system_prompt, user_message, model, max_tokens=16000)

        # 如果 JSON 被截断（没有结尾的 ]})，尝试 continue
        stripped = response.rstrip()
        if stripped and not (stripped.endswith("}") and stripped.count("{") == stripped.count("}")):
            click.echo("   🔄 输出被截断，自动续写...")
            cont = call_llm(
                "你之前输出了一段 JSON 但被截断了。请直接从截断处续写剩余的 JSON 内容，"
                "不要重复已有内容，不要加任何解释文字，只输出 JSON 的剩余部分。"
                "\n\n截断处的最后 300 字：",
                response[-300:],
                model, max_tokens=4000,
            )
            # 去掉续写中可能的重复部分
            cont = cont.strip()
            if cont.startswith("```"):
                cont = re.sub(r"^```(?:json)?\s*", "", cont)
                cont = re.sub(r"\s*```$", "", cont)
            response = response + "\n" + cont

        # 保存原始响应用于调试
        raw_path = output_dir / "script_raw.txt"
        raw_path.write_text(response, encoding="utf-8")
        script_data = _extract_json(response)
    except Exception as e:
        state.last_error = f"脚本生成失败: {e}"
        state.save(cfg.output_dir)
        sync_workflow_contract(
            output_dir, video_id,
            stage="script", status="error",
            message=state.last_error,
        )
        raise click.ClickException(state.last_error)

    # 保存输出
    script_json_path = output_dir / "script.json"
    script_json_path.write_text(
        json.dumps(script_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    state.script_json = str(script_json_path)

    sync_script_sidecars(script_data, output_dir)
    sidecar_issues = validate_script_sidecars(script_data, output_dir)
    if sidecar_issues:
        sync_workflow_contract(
            output_dir, video_id,
            stage="script", status="error",
            message="脚本 sidecar 一致性校验失败",
            extra={"issues": sidecar_issues[:8]},
        )
        raise click.ClickException(
            "脚本 sidecar 一致性校验失败:\n- " + "\n- ".join(sidecar_issues[:8])
        )
    state.recording_guide = str(output_dir / "recording_guide.md")

    # 保存生成元数据（用于 prompt 版本追踪）
    _save_script_meta(
        output_dir,
        model,
        system_prompt,
        user_message,
        response,
        quality_profile=profile["name"],
    )

    # 创建素材目录（按需创建，不预创建空目录）
    (output_dir / "slides").mkdir(exist_ok=True)
    (output_dir / "recordings").mkdir(exist_ok=True)
    state.slides_dir = str(output_dir / "slides")
    state.recordings_dir = str(output_dir / "recordings")

    state.scripted = True
    state.last_error = ""
    state.save(cfg.output_dir)
    sync_workflow_contract(
        output_dir, video_id,
        stage="script", status="ok",
        message="脚本生成完成",
        extra={"segments": len(script_data.get("segments", []))},
    )

    # 统计素材分配
    segments = script_data.get("segments", [])
    a_count = sum(1 for s in segments if s.get("material") == "A")
    b_count = sum(1 for s in segments if s.get("material") == "B")
    c_count = sum(1 for s in segments if s.get("material") == "C")
    total = len(segments)
    click.echo(f"   📊 素材分配: A(PPT)={a_count}/{total} B(录屏)={b_count}/{total} C(原视频)={c_count}/{total}")

    return state


def run_multi_script(
    cfg,
    project_id: str,
    model: str,
    quality_profile: str = "default",
) -> "PipelineState":
    """多源综合脚本生成: 跨 N 个视频提炼精华。"""
    from v2g.checkpoint import PipelineState
    from v2g.workflow_contract import sync_workflow_contract

    state = PipelineState.load(cfg.output_dir, project_id)
    if not state.is_multi:
        raise click.ClickException("非多源项目，请使用 v2g script")
    if not state.subtitled:
        raise click.ClickException("字幕尚未生成，请先运行 v2g multi-prepare")
    if state.scripted:
        click.echo("⏭️  脚本已存在，跳过")
        return state

    output_dir = cfg.output_dir / project_id
    output_dir.mkdir(parents=True, exist_ok=True)
    sync_workflow_contract(
        output_dir, project_id,
        stage="script", status="start",
        message="开始多源脚本生成",
        extra={"model": model, "quality_profile": quality_profile},
    )

    sources = state.get_sources()
    click.echo(f"🤖 多源综合脚本 (模型: {model}, {len(sources)} 个源视频)")

    # 构建包含所有源视频摘要 + 字幕的 user message
    user_parts = [f"## 主题: {state.topic}\n", f"共 {len(sources)} 个源视频\n"]

    for i, src in enumerate(sources):
        user_parts.append(f"\n{'='*40}")
        user_parts.append(f"### [{i}] {src.channel_name or '未知频道'} - \"{src.title or src.video_id}\"")
        user_parts.append(f"URL: {src.video_url}\n")

        # 优先使用摘要（信息密度更高）
        srt_dir = Path(src.zh_srt_path).parent if src.zh_srt_path else None
        summary_path = srt_dir / "summary.md" if srt_dir else None
        if summary_path and summary_path.exists():
            summary_text = summary_path.read_text(encoding="utf-8")
            user_parts.append(f"视频摘要:\n{summary_text}\n")

        # 中文字幕（带时间戳，用于 source_start/source_end 定位）
        zh_path = Path(src.zh_srt_path) if src.zh_srt_path else None
        if zh_path and zh_path.exists():
            zh_text = _parse_srt_to_text(zh_path.read_text(encoding="utf-8"))
            if len(zh_text) > 8000:
                zh_text = zh_text[:8000] + "\n...(字幕截断)"
            user_parts.append(f"中文字幕:\n{zh_text}")
        else:
            user_parts.append("中文字幕: 不可用")

    # 注入素材库历史反馈（留存表现 + 可复用素材）
    asset_ctx = build_asset_context(cfg)
    if asset_ctx:
        user_parts.append(f"\n{asset_ctx}")

    user_message = "\n".join(user_parts)
    try:
        profile = resolve_quality_profile(quality_profile)
    except ValueError as e:
        raise click.ClickException(str(e))
    profile_prompt = load_profile_prompt(profile["name"])

    from v2g.style_catalog import inject_catalog as _inject_catalog
    style_id_prefix_m = profile.get("style_id_prefix") or None
    system_prompt = _inject_catalog(
        _read_prompt("script_multi_system.md"),
        id_prefix=style_id_prefix_m,
    )
    if profile_prompt:
        system_prompt = (
            system_prompt
            + "\n\n## 质量档位约束\n"
            + profile_prompt
        )

    click.echo(f"   总输入长度: {len(user_message)} 字符")

    try:
        response = call_llm(system_prompt, user_message, model, max_tokens=16000)

        # 截断续写
        stripped = response.rstrip()
        if stripped and not (stripped.endswith("}") and stripped.count("{") == stripped.count("}")):
            click.echo("   🔄 输出被截断，自动续写...")
            cont = call_llm(
                "你之前输出了一段 JSON 但被截断了。请直接从截断处续写剩余的 JSON 内容，"
                "不要重复已有内容，不要加任何解释文字，只输出 JSON 的剩余部分。"
                "\n\n截断处的最后 300 字：",
                response[-300:],
                model, max_tokens=4000,
            )
            cont = cont.strip()
            if cont.startswith("```"):
                cont = re.sub(r"^```(?:json)?\s*", "", cont)
                cont = re.sub(r"\s*```$", "", cont)
            response = response + "\n" + cont

        raw_path = output_dir / "script_raw.txt"
        raw_path.write_text(response, encoding="utf-8")
        script_data = _extract_json(response)
    except Exception as e:
        state.last_error = f"脚本生成失败: {e}"
        state.save(cfg.output_dir)
        sync_workflow_contract(
            output_dir, project_id,
            stage="script", status="error",
            message=state.last_error,
        )
        raise click.ClickException(state.last_error)

    # 补充 source_channel 信息（多源用 sources_used）
    if "source_channel" not in script_data:
        channels = [s.channel_name for s in sources if s.channel_name]
        script_data["source_channel"] = " / ".join(channels[:3]) if channels else ""

    # 保存
    script_json_path = output_dir / "script.json"
    script_json_path.write_text(
        json.dumps(script_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    state.script_json = str(script_json_path)

    sync_script_sidecars(script_data, output_dir)
    sidecar_issues = validate_script_sidecars(script_data, output_dir)
    if sidecar_issues:
        sync_workflow_contract(
            output_dir, project_id,
            stage="script", status="error",
            message="脚本 sidecar 一致性校验失败",
            extra={"issues": sidecar_issues[:8]},
        )
        raise click.ClickException(
            "脚本 sidecar 一致性校验失败:\n- " + "\n- ".join(sidecar_issues[:8])
        )
    state.recording_guide = str(output_dir / "recording_guide.md")

    # 保存生成元数据
    _save_script_meta(
        output_dir,
        model,
        system_prompt,
        user_message,
        response,
        quality_profile=profile["name"],
    )

    (output_dir / "slides").mkdir(exist_ok=True)
    (output_dir / "recordings").mkdir(exist_ok=True)
    state.slides_dir = str(output_dir / "slides")
    state.recordings_dir = str(output_dir / "recordings")

    state.scripted = True
    state.last_error = ""
    state.save(cfg.output_dir)
    sync_workflow_contract(
        output_dir, project_id,
        stage="script", status="ok",
        message="多源脚本生成完成",
        extra={"segments": len(script_data.get("segments", []))},
    )

    segments = script_data.get("segments", [])
    a_count = sum(1 for s in segments if s.get("material") == "A")
    b_count = sum(1 for s in segments if s.get("material") == "B")
    c_count = sum(1 for s in segments if s.get("material") == "C")
    click.echo(f"   📊 素材分配: A={a_count} B={b_count} C={c_count}")

    # 统计引用了哪些源视频
    used_sources = set()
    for s in segments:
        if s.get("material") == "C" and "source_video_index" in s:
            used_sources.add(s["source_video_index"])
    click.echo(f"   🎬 引用源视频: {sorted(used_sources)}")

    return state
