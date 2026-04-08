"""Stage 3: AI 生成二创解说脚本 (含三素材分配)。"""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

import click

from v2g.config import Config
from v2g.checkpoint import PipelineState
from v2g.llm import call_llm

PROMPTS_DIR = Path(__file__).parent / "prompts"


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


def _save_script_meta(output_dir: Path, model: str, system_prompt: str,
                      user_message: str, response: str):
    """保存脚本生成元数据，用于 prompt 版本追踪和质量回溯。"""
    prompt_hash = hashlib.md5(system_prompt.encode()).hexdigest()[:8]
    meta = {
        "model": model,
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


def run_script(cfg: Config, video_id: str, model: str) -> PipelineState:
    """执行 Stage 3: AI 脚本生成。"""
    state = PipelineState.load(cfg.output_dir, video_id)
    if not state.subtitled:
        raise click.ClickException("字幕尚未生成，请先运行 v2g prepare")

    if state.scripted:
        click.echo("⏭️  脚本已存在，跳过")
        return state

    output_dir = cfg.output_dir / video_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # 读取字幕
    zh_srt_path = Path(state.zh_srt)
    en_srt_path = Path(state.en_srt)

    if not zh_srt_path.exists():
        raise click.ClickException(f"中文字幕不存在: {zh_srt_path}")

    zh_text = _parse_srt_to_text(zh_srt_path.read_text(encoding="utf-8"))
    en_text = ""
    if en_srt_path.exists():
        en_text = _parse_srt_to_text(en_srt_path.read_text(encoding="utf-8"))

    # 构建 user message
    user_parts = [
        f"## 视频信息\n",
        f"- Video ID: {video_id}",
        f"- URL: {state.video_url}",
        f"\n## 中文字幕\n",
        zh_text,
    ]
    if en_text:
        user_parts.append(f"\n## 英文字幕 (参考)\n")
        user_parts.append(en_text)

    # 读取 summary（如果存在）
    summary_path = cfg.l2n_output_dir / video_id / "summary.md"
    if summary_path.exists():
        user_parts.append(f"\n## 视频摘要\n")
        user_parts.append(summary_path.read_text(encoding="utf-8"))

    user_message = "\n".join(user_parts)
    system_prompt = _read_prompt("script_system.md")

    click.echo(f"🤖 生成二创脚本 (模型: {model})...")
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
        raise click.ClickException(state.last_error)

    # 保存输出
    script_json_path = output_dir / "script.json"
    script_json_path.write_text(
        json.dumps(script_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    state.script_json = str(script_json_path)

    script_md_path = output_dir / "script.md"
    _generate_script_md(script_data, script_md_path)

    recording_guide_path = output_dir / "recording_guide.md"
    _generate_recording_guide(script_data, recording_guide_path)
    state.recording_guide = str(recording_guide_path)

    # 保存生成元数据（用于 prompt 版本追踪）
    _save_script_meta(output_dir, model, system_prompt, user_message, response)

    # 创建素材目录（按需创建，不预创建空目录）
    (output_dir / "slides").mkdir(exist_ok=True)
    (output_dir / "recordings").mkdir(exist_ok=True)
    state.slides_dir = str(output_dir / "slides")
    state.recordings_dir = str(output_dir / "recordings")

    state.scripted = True
    state.last_error = ""
    state.save(cfg.output_dir)

    # 统计素材分配
    segments = script_data.get("segments", [])
    a_count = sum(1 for s in segments if s.get("material") == "A")
    b_count = sum(1 for s in segments if s.get("material") == "B")
    c_count = sum(1 for s in segments if s.get("material") == "C")
    total = len(segments)
    click.echo(f"   📊 素材分配: A(PPT)={a_count}/{total} B(录屏)={b_count}/{total} C(原视频)={c_count}/{total}")

    return state


def run_multi_script(cfg, project_id: str, model: str) -> "PipelineState":
    """多源综合脚本生成: 跨 N 个视频提炼精华。"""
    from v2g.checkpoint import PipelineState

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

    user_message = "\n".join(user_parts)
    system_prompt = _read_prompt("script_multi_system.md")

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

    script_md_path = output_dir / "script.md"
    _generate_script_md(script_data, script_md_path)

    recording_guide_path = output_dir / "recording_guide.md"
    _generate_recording_guide(script_data, recording_guide_path)
    state.recording_guide = str(recording_guide_path)

    # 保存生成元数据
    _save_script_meta(output_dir, model, system_prompt, user_message, response)

    (output_dir / "slides").mkdir(exist_ok=True)
    (output_dir / "recordings").mkdir(exist_ok=True)
    state.slides_dir = str(output_dir / "slides")
    state.recordings_dir = str(output_dir / "recordings")

    state.scripted = True
    state.last_error = ""
    state.save(cfg.output_dir)

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
