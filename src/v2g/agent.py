"""Agent 驱动的视频脚本编排：多源素材 → 大纲 → script.json。

支持两种 agent loop 后端：
- Anthropic SDK (Claude 系列模型)
- OpenAI 兼容 SDK (MiniMax / DeepSeek / GPT / Qwen 等)
"""

import json
import os
import re
from pathlib import Path

import click

from v2g.config import Config
from v2g.checkpoint import PipelineState

PROMPTS_DIR = Path(__file__).parent / "prompts"

# ---------------------------------------------------------------------------
# Tool definitions (Anthropic tool use schema)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "fetch_url",
        "description": "抓取网页/公众号文章内容，返回 markdown 格式正文。适用于 http/https 链接。",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要抓取的网页 URL",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "read_source_file",
        "description": "读取本地素材文件。支持 .md, .srt, .txt 等文本文件。",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "本地文件的绝对路径",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "save_outline",
        "description": "保存视频大纲到 outline.json。在阅读分析完所有素材后调用此工具。",
        "input_schema": {
            "type": "object",
            "properties": {
                "outline_json": {
                    "type": "string",
                    "description": "大纲的 JSON 字符串",
                },
            },
            "required": ["outline_json"],
        },
    },
    {
        "name": "save_script",
        "description": "保存最终脚本到 script.json。在大纲确认后，将大纲展开为完整脚本时调用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "script_json": {
                    "type": "string",
                    "description": "完整脚本的 JSON 字符串（与 video2gen 管线兼容的格式）",
                },
            },
            "required": ["script_json"],
        },
    },
]

# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

# Runtime context — set by run_agent() before agent loop starts
_ctx: dict = {}


def _exec_tool(name: str, input_data: dict) -> str:
    """Execute a tool call and return the result as a string."""
    if name == "fetch_url":
        return _tool_fetch_url(input_data["url"])
    if name == "read_source_file":
        return _tool_read_source_file(input_data["path"])
    if name == "save_outline":
        return _tool_save_outline(input_data["outline_json"])
    if name == "save_script":
        return _tool_save_script(input_data["script_json"])
    return f"未知工具: {name}"


def _tool_fetch_url(url: str) -> str:
    from v2g.fetcher import fetch_article

    try:
        result = fetch_article(url)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return f"抓取失败: {e}"


def _tool_read_source_file(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return f"文件不存在: {path}"
    try:
        content = p.read_text(encoding="utf-8")
        suffix = p.suffix.lower()
        # SRT 格式预处理：转为带时间戳的纯文本
        if suffix == ".srt":
            content = _parse_srt_to_text(content)
            return f"[文件类型: SRT 字幕]\n{content}"
        return f"[文件类型: {suffix}]\n{content}"
    except Exception as e:
        return f"读取失败: {e}"


def _tool_save_outline(outline_json_str: str) -> str:
    output_dir: Path = _ctx["output_dir"]
    try:
        outline = _safe_parse_json(outline_json_str)
    except (json.JSONDecodeError, ValueError) as e:
        return f"JSON 解析失败: {e}。请检查格式后重试。"

    # 基本结构校验
    if "outline" not in outline or "title" not in outline:
        return "大纲缺少必要字段 (title, outline)，请补充后重试。"

    path = output_dir / "outline.json"
    path.write_text(json.dumps(outline, ensure_ascii=False, indent=2), encoding="utf-8")
    click.echo(f"   ✅ 大纲已保存: {path}")

    # 同时保存可读版本
    _generate_outline_md(outline, output_dir / "outline.md")

    _ctx["outline_saved"] = True
    return "大纲已保存到 outline.json，等待用户确认。"


def _tool_save_script(script_json_str: str) -> str:
    output_dir: Path = _ctx["output_dir"]
    try:
        script_data = _safe_parse_json(script_json_str)
    except (json.JSONDecodeError, ValueError) as e:
        return f"JSON 解析失败: {e}。请检查格式后重试。"

    if "segments" not in script_data:
        return "脚本缺少 segments 字段，请补充后重试。"

    # 保存 script.json
    script_json_path = output_dir / "script.json"
    script_json_path.write_text(
        json.dumps(script_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 复用 scriptwriter 的辅助生成
    from v2g.scriptwriter import _generate_script_md, _generate_recording_guide

    _generate_script_md(script_data, output_dir / "script.md")
    _generate_recording_guide(script_data, output_dir / "recording_guide.md")

    click.echo(f"   ✅ 脚本已保存: {script_json_path}")

    _ctx["script_saved"] = True
    return "脚本已保存到 script.json、script.md、recording_guide.md。"


# ---------------------------------------------------------------------------
# OpenAI-compatible tool definitions (for MiniMax / DeepSeek / GPT / Qwen)
# ---------------------------------------------------------------------------

TOOLS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        },
    }
    for t in TOOLS
]


# ---------------------------------------------------------------------------
# Agent loop router
# ---------------------------------------------------------------------------

def _is_openai_compatible_model(model: str) -> bool:
    """判断是否应使用 OpenAI 兼容 API 的 agent loop。"""
    from v2g.llm import is_gpt_model
    prefixes = ("gpt", "o1", "o3", "o4", "minimax", "deepseek", "qwen", "glm", "abab")
    return model.lower().startswith(prefixes) or is_gpt_model(model)


def _is_minimax_model(model: str) -> bool:
    return model.lower().startswith("minimax")


def _is_zhipu_model(model: str) -> bool:
    return model.lower().startswith("glm")


def _dispatch_agent_loop(
    system_prompt: str,
    user_message: str,
    model: str,
    max_turns: int = 20,
) -> str:
    """根据 model 名称自动选择 Anthropic 或 OpenAI 兼容的 agent loop。"""
    if _is_openai_compatible_model(model):
        return _run_agent_loop_openai(system_prompt, user_message, model, max_turns)
    return _run_agent_loop(system_prompt, user_message, model, max_turns)


# ---------------------------------------------------------------------------
# Agent loop — Anthropic
# ---------------------------------------------------------------------------

def _run_agent_loop(
    system_prompt: str,
    user_message: str,
    model: str,
    max_turns: int = 20,
) -> str:
    """Run the tool-use agent loop until the model stops calling tools.

    Uses streaming API to be compatible with proxy platforms that only
    support SSE responses.
    """
    import anthropic
    import httpx

    base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise click.ClickException("未设置 ANTHROPIC_API_KEY")

    # 清理代理环境变量中的非法字符（与 llm.py 一致）
    _cleaned_proxy = {}
    for _pk in ("all_proxy", "ALL_PROXY"):
        _pv = os.environ.get(_pk, "")
        if _pv and not _pv.rstrip("/").replace("://", "").replace(".", "").replace(":", "").isalnum():
            _cleaned_proxy[_pk] = os.environ.pop(_pk)

    # 如果使用了自定义 base_url (代理网关)，不走本地系统代理
    if base_url and "api.anthropic.com" not in base_url:
        proxy_url = None
    else:
        proxy_url = os.environ.get("https_proxy") or os.environ.get("http_proxy") or None
    client = anthropic.Anthropic(
        api_key=api_key,
        base_url=base_url,
        http_client=httpx.Client(
            timeout=httpx.Timeout(600.0, connect=60.0),
            proxy=proxy_url,
        ),
    )
    os.environ.update(_cleaned_proxy)

    messages = [{"role": "user", "content": user_message}]
    final_text = ""

    for turn in range(max_turns):
        # 使用 streaming API（兼容代理平台）
        response = _stream_message_with_tools(
            client, model, system_prompt, messages, TOOLS,
        )

        # Collect assistant content blocks
        assistant_content = []
        tool_calls = []
        stop_reason = response.get("stop_reason", "end_turn")

        for block in response.get("content", []):
            btype = block.get("type")
            if btype == "text":
                final_text = block["text"]
                assistant_content.append({"type": "text", "text": block["text"]})
            elif btype == "tool_use":
                tool_calls.append(block)
                assistant_content.append({
                    "type": "tool_use",
                    "id": block["id"],
                    "name": block["name"],
                    "input": block["input"],
                })

        messages.append({"role": "assistant", "content": assistant_content})

        # If no tool calls, we're done
        if not tool_calls or stop_reason == "end_turn":
            break

        # Execute tools and feed results back
        tool_results = []
        for tc in tool_calls:
            click.echo(f"   🔧 {tc['name']}({_summarize_input(tc['input'])})")
            result_str = _exec_tool(tc["name"], tc["input"])
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc["id"],
                "content": result_str,
            })

        messages.append({"role": "user", "content": tool_results})

    return final_text


# ---------------------------------------------------------------------------
# Agent loop — OpenAI compatible (MiniMax / DeepSeek / GPT / Qwen / GLM)
# ---------------------------------------------------------------------------

def _run_agent_loop_openai(
    system_prompt: str,
    user_message: str,
    model: str,
    max_turns: int = 20,
) -> str:
    """OpenAI-compatible agent loop with function calling."""
    from openai import OpenAI
    import httpx

    # 各厂商官方 API 路由
    if _is_zhipu_model(model):
        base_url = "https://open.bigmodel.cn/api/paas/v4"
        api_key = os.environ.get("ZHIPU_API_KEY", "")
        if not api_key:
            raise click.ClickException("未设置 ZHIPU_API_KEY")
    elif _is_minimax_model(model):
        minimax_key = os.environ.get("TTS_MINMAX_KEY", "")
        gpt_key = os.environ.get("GPT_API_KEY", "")
        if minimax_key:
            base_url = "https://api.minimax.chat"
            api_key = minimax_key
        elif gpt_key:
            base_url = os.environ.get("GPT_BASE_URL", "")
            api_key = gpt_key
        else:
            raise click.ClickException("未设置 TTS_MINMAX_KEY 或 GPT_API_KEY")
    else:
        base_url = os.environ.get("GPT_BASE_URL", "")
        api_key = os.environ.get("GPT_API_KEY", "")
        if not api_key:
            base_url = os.environ.get("ANTHROPIC_BASE_URL", base_url)
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise click.ClickException("未设置 GPT_API_KEY")

    # 只对需要 /v1 后缀的平台补充（智谱等已有正确路径的跳过）
    if base_url and not any(base_url.rstrip("/").endswith(s) for s in ("/v1", "/v4")):
        base_url = base_url.rstrip("/") + "/v1"

    # 清理代理变量（MiniMax/智谱等国内 API 不走本地代理）
    _cleaned = {}
    if _is_minimax_model(model) or _is_zhipu_model(model):
        for k in list(os.environ):
            if "proxy" in k.lower() and os.environ[k]:
                _cleaned[k] = os.environ.pop(k)
    else:
        for k in list(os.environ):
            if "proxy" in k.lower():
                v = os.environ[k]
                if v and v.rstrip("/").endswith("~"):
                    _cleaned[k] = os.environ.pop(k)

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        http_client=httpx.Client(timeout=httpx.Timeout(600.0, connect=60.0)),
    )
    os.environ.update(_cleaned)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    final_text = ""

    for turn in range(max_turns):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS_OPENAI,
            temperature=0.3,
            max_tokens=16000,
        )

        choice = response.choices[0]
        msg = choice.message
        final_text = msg.content or ""

        # 清理 thinking 标签（MiniMax/DeepSeek 可能返回 <think>...</think>）
        if final_text:
            final_text = re.sub(r"<think>.*?</think>", "", final_text, flags=re.DOTALL).strip()

        # Append assistant message
        messages.append(msg)

        # Check for tool calls
        if not msg.tool_calls or choice.finish_reason == "stop":
            break

        # Execute tools
        for tc in msg.tool_calls:
            fn = tc.function
            try:
                args = json.loads(fn.arguments)
            except json.JSONDecodeError:
                args = {"raw": fn.arguments}

            click.echo(f"   🔧 {fn.name}({_summarize_input(args)})")
            result_str = _exec_tool(fn.name, args)

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_str,
            })

    return final_text


def _stream_message_with_tools(client, model, system_prompt, messages, tools):
    """Stream a message and collect content blocks including tool_use.

    Returns a dict mimicking the Message structure:
    {"content": [...], "stop_reason": str}
    """
    import anthropic

    content_blocks = []
    stop_reason = "end_turn"

    # 当前正在构建的块
    current_block = None
    current_index = -1
    text_parts = []
    json_parts = []

    try:
        with client.messages.stream(
            model=model,
            max_tokens=16000,
            temperature=0.3,
            system=system_prompt,
            messages=messages,
            tools=tools,
        ) as stream:
            for event in stream:
                etype = getattr(event, "type", None)

                if etype == "content_block_start":
                    # 保存前一个块
                    _flush_block(current_block, text_parts, json_parts, content_blocks)
                    text_parts = []
                    json_parts = []
                    current_index = getattr(event, "index", -1)
                    cb = event.content_block
                    cb_type = getattr(cb, "type", None)
                    if cb_type == "text":
                        current_block = {"type": "text", "text": ""}
                    elif cb_type == "tool_use":
                        current_block = {
                            "type": "tool_use",
                            "id": getattr(cb, "id", ""),
                            "name": getattr(cb, "name", ""),
                            "input": {},
                        }
                    elif cb_type == "thinking":
                        current_block = {"type": "thinking"}
                    else:
                        current_block = None

                elif etype == "content_block_delta":
                    delta = event.delta
                    dtype = getattr(delta, "type", None)
                    if dtype == "text_delta":
                        text_parts.append(getattr(delta, "text", ""))
                    elif dtype == "input_json_delta":
                        json_parts.append(getattr(delta, "partial_json", ""))
                    # thinking_delta — ignore

                elif etype == "content_block_stop":
                    _flush_block(current_block, text_parts, json_parts, content_blocks)
                    text_parts = []
                    json_parts = []
                    current_block = None

                elif etype == "message_delta":
                    delta = event.delta
                    sr = getattr(delta, "stop_reason", None)
                    if sr:
                        stop_reason = sr

    except anthropic.APIError as e:
        raise click.ClickException(f"API 调用失败: {e}")

    # Flush anything remaining
    _flush_block(current_block, text_parts, json_parts, content_blocks)

    return {"content": content_blocks, "stop_reason": stop_reason}


def _flush_block(block, text_parts, json_parts, content_blocks):
    """Finalize a content block and append to list."""
    if block is None:
        return
    if block["type"] == "text":
        block["text"] = "".join(text_parts)
        if block["text"]:  # skip empty text blocks
            content_blocks.append(block)
    elif block["type"] == "tool_use":
        raw = "".join(json_parts)
        if raw:
            try:
                block["input"] = json.loads(raw)
            except json.JSONDecodeError:
                block["input"] = {"raw": raw}
        content_blocks.append(block)
    # thinking blocks are ignored


def _summarize_input(input_data: dict) -> str:
    """Summarize tool input for logging."""
    parts = []
    for k, v in input_data.items():
        v_str = str(v)
        if len(v_str) > 60:
            v_str = v_str[:57] + "..."
        parts.append(f"{k}={v_str}")
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_agent(
    cfg: Config,
    project_id: str,
    sources: tuple[str, ...],
    topic: str,
    model: str | None,
    duration: int,
):
    """Agent 驱动的脚本编排：素材 → 大纲 → script.json。"""
    model = model or cfg.script_model
    output_dir = cfg.output_dir / project_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load or create state
    state = PipelineState.load(cfg.output_dir, project_id)
    if not state.project_id:
        state.project_id = project_id
    state.topic = topic

    # Initialize context
    _ctx.clear()
    _ctx["output_dir"] = output_dir
    _ctx["cfg"] = cfg
    _ctx["outline_saved"] = False
    _ctx["script_saved"] = False

    # ── Phase 1: 素材分析 + 大纲生成 ──────────────────────────
    outline_path = output_dir / "outline.json"
    if state.agent_outline_done and outline_path.exists():
        click.echo("⏭️  大纲已存在")
    else:
        click.echo(f"\n🤖 Agent 启动 (模型: {model})")
        click.echo(f"   主题: {topic}")
        click.echo(f"   目标时长: {duration}s")
        click.echo(f"   素材: {len(sources)} 个\n")

        # Classify sources and build description
        source_desc = _describe_sources(sources)

        system_prompt = _read_prompt("agent_system.md")
        outline_prompt = _read_prompt("agent_outline.md")

        user_message = (
            f"请分析以下素材并生成视频大纲。\n\n"
            f"**主题**: {topic}\n"
            f"**目标时长**: {duration} 秒\n\n"
            f"## 素材列表\n\n{source_desc}\n\n"
            f"---\n\n"
            f"请逐一读取/抓取每个素材，分析核心观点后，按以下要求生成大纲：\n\n"
            f"{outline_prompt}"
        )

        _dispatch_agent_loop(system_prompt, user_message, model)

        if not _ctx.get("outline_saved"):
            raise click.ClickException("Agent 未生成大纲。请检查素材内容后重试。")

        state.agent_outline_done = True
        state.agent_sources = _build_source_records(sources)
        state.save(cfg.output_dir)

    # ── 大纲预览 + 人工确认 ─────────────────────────────────
    if not state.outline_reviewed:
        outline = json.loads(outline_path.read_text(encoding="utf-8"))
        _print_outline_preview(outline)

        if not click.confirm("\n✅ 确认大纲？", default=True):
            click.echo("💡 请手动编辑 outline.json 后重新运行 v2g agent")
            return

        state.outline_reviewed = True
        state.save(cfg.output_dir)

    # ── Phase 2: 大纲 → script.json ─────────────────────────
    # 阶段二用直接 LLM 调用（不走 agent loop），避免大 JSON 被代理截断
    script_path = output_dir / "script.json"
    if state.scripted and script_path.exists():
        click.echo("⏭️  脚本已存在")
    else:
        click.echo("\n🔄 展开脚本中...")

        outline = json.loads(outline_path.read_text(encoding="utf-8"))

        system_prompt = _read_prompt("agent_system.md") + "\n\n" + _read_prompt("agent_script.md")

        # 仅传大纲（已包含素材摘要），不传完整素材内容以避免上下文过长
        outline_str = json.dumps(outline, ensure_ascii=False, indent=2)
        user_message = (
            f"请根据以下大纲生成完整的视频脚本。\n\n"
            f"## 已确认的大纲\n\n{outline_str}\n\n"
            f"---\n\n"
            f"严格输出 JSON，不要代码块标记，不要任何其他文字。"
        )

        from v2g.llm import call_llm
        from v2g.scriptwriter import _extract_json, _generate_script_md, _generate_recording_guide

        try:
            response = call_llm(system_prompt, user_message, model, max_tokens=16000)

            # 截断续写
            stripped = response.rstrip()
            if stripped and not (stripped.endswith("}") and stripped.count("{") == stripped.count("}")):
                click.echo("   🔄 输出被截断，自动续写...")
                cont = call_llm(
                    system_prompt,
                    f"你之前根据大纲生成视频脚本 JSON，但输出在中途被截断了。\n"
                    f"请从截断处直接续写，补全剩余的 JSON 内容。\n"
                    f"不要重复已有内容，不要加解释文字，只输出 JSON 的剩余部分。\n\n"
                    f"已有内容的最后 500 字符：\n{response[-500:]}",
                    model, max_tokens=8000,
                )
                cont = cont.strip()
                if cont.startswith("```"):
                    cont = re.sub(r"^```(?:json)?\s*", "", cont)
                    cont = re.sub(r"\s*```$", "", cont)
                response = response + cont

            # 清理控制字符并保存
            response = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', response)
            (output_dir / "script_raw.txt").write_text(response, encoding="utf-8")
            script_data = _extract_json(response)
        except Exception as e:
            state.last_error = f"脚本生成失败: {e}"
            state.save(cfg.output_dir)
            raise click.ClickException(state.last_error)

        # 保存脚本及辅助文件
        script_path.write_text(
            json.dumps(script_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        _generate_script_md(script_data, output_dir / "script.md")
        _generate_recording_guide(script_data, output_dir / "recording_guide.md")

        # Update checkpoint
        state.script_json = str(script_path)
        state.recording_guide = str(output_dir / "recording_guide.md")
        state.slides_dir = str(output_dir / "slides")
        state.recordings_dir = str(output_dir / "recordings")
        (output_dir / "slides").mkdir(exist_ok=True)
        (output_dir / "recordings").mkdir(exist_ok=True)

        state.scripted = True
        state.last_error = ""
        state.save(cfg.output_dir)

    # ── Phase 3: B 类素材自动采集 ─────────────────────────
    script_data = json.loads(script_path.read_text(encoding="utf-8"))
    segments = script_data.get("segments", [])
    b_count = sum(1 for s in segments if s.get("material") == "B")

    if b_count > 0:
        click.echo(f"\n🖥️ 自动采集 B 类素材 ({b_count} 段)...")
        from v2g.autocap import run_capture
        run_capture(cfg, project_id)

    # ── 完成 ─────────────────────────────────────────────
    a = sum(1 for s in segments if s.get("material") == "A")
    b = b_count
    c = sum(1 for s in segments if s.get("material") == "C")

    click.echo(f"\n✅ 脚本生成完成:")
    click.echo(f"   📊 {len(segments)} 段 (A={a} B={b} C={c})")
    click.echo(f"   📄 脚本: output/{project_id}/script.md")
    click.echo(f"   🖥️  录屏指南: output/{project_id}/recording_guide.md")
    click.echo(f"\n💡 下一步:")
    click.echo(f"   v2g tts {project_id}")
    click.echo(f"   v2g slides {project_id}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def _parse_srt_to_text(srt_content: str) -> str:
    """将 SRT 转为带时间戳的纯文本（复用 scriptwriter 的逻辑）。"""
    lines = []
    entries = srt_content.strip().split("\n\n")
    for entry in entries:
        parts = entry.strip().split("\n")
        if len(parts) >= 3:
            timestamp = parts[1]
            text = " ".join(parts[2:])
            m = re.match(r"(\d{2}):(\d{2}):(\d{2})", timestamp)
            if m:
                h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
                total_s = h * 3600 + mi * 60 + s
                lines.append(f"[{total_s}s] {text}")
            else:
                lines.append(text)
    return "\n".join(lines)


def _safe_parse_json(text: str) -> dict:
    """解析 JSON 字符串，自动修复常见问题。"""
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

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 修复尾逗号、中文引号
    fixed = re.sub(r",\s*([}\]])", r"\1", text)
    fixed = fixed.replace("\u201c", '"').replace("\u201d", '"')
    fixed = fixed.replace("\u2018", "'").replace("\u2019", "'")
    return json.loads(fixed)


def _describe_sources(sources: tuple[str, ...]) -> str:
    """生成素材列表描述，区分 URL 和本地文件。"""
    lines = []
    for i, src in enumerate(sources):
        src = src.strip()
        if src.startswith("http://") or src.startswith("https://"):
            lines.append(f"[{i}] 🌐 网页文章: {src}")
            lines.append(f"    → 请用 `fetch_url` 抓取")
        else:
            p = Path(src)
            suffix = p.suffix.lower()
            type_map = {".srt": "字幕文件", ".md": "Markdown 笔记", ".txt": "文本文件"}
            ftype = type_map.get(suffix, f"{suffix} 文件")
            abs_path = p.resolve()
            lines.append(f"[{i}] 📄 {ftype}: {p.name}")
            lines.append(f"    → 请用 `read_source_file` 读取，路径: {abs_path}")
    return "\n".join(lines)


def _build_source_records(sources: tuple[str, ...]) -> list[dict]:
    """构建素材记录列表，存入 checkpoint。"""
    records = []
    for i, src in enumerate(sources):
        src = src.strip()
        if src.startswith("http://") or src.startswith("https://"):
            records.append({"id": i, "type": "url", "path": src})
        else:
            records.append({"id": i, "type": Path(src).suffix.lstrip("."), "path": str(Path(src).resolve())})
    return records


def _load_cached_sources(output_dir: Path, sources: tuple[str, ...]) -> str:
    """加载素材内容摘要，供阶段二参考。"""
    parts = []
    for i, src in enumerate(sources):
        src = src.strip()
        if src.startswith("http://") or src.startswith("https://"):
            parts.append(f"### 素材 [{i}]: 网页文章 ({src})")
            parts.append("（已在阶段一分析，请参考大纲中的 source_summary）\n")
        else:
            p = Path(src)
            if p.exists():
                content = p.read_text(encoding="utf-8")
                if p.suffix.lower() == ".srt":
                    content = _parse_srt_to_text(content)
                # 截断过长内容
                if len(content) > 6000:
                    content = content[:6000] + "\n...(已截断)"
                parts.append(f"### 素材 [{i}]: {p.name}")
                parts.append(content + "\n")
            else:
                parts.append(f"### 素材 [{i}]: {p.name} (文件不存在)")
    return "\n".join(parts)


def _generate_outline_md(outline: dict, output_path: Path):
    """生成可读的大纲 Markdown。"""
    lines = [
        f"# {outline.get('title', '未命名')}\n",
        f"> {outline.get('theme', '')}\n",
        f"> 目标时长: {outline.get('target_duration', '?')}s\n\n",
    ]

    # 素材摘要
    for src in outline.get("source_summary", []):
        lines.append(f"### 素材 [{src['id']}] {src.get('title', '')}\n")
        for kp in src.get("key_points", []):
            lines.append(f"- {kp}\n")
        lines.append("\n")

    lines.append("---\n\n")
    lines.append("## 大纲\n\n")

    material_map = {"A": "📊图文", "B": "🖥️录屏", "C": "🎬原片"}
    section_map = {"intro": "开头", "body": "主体", "outro": "结尾"}

    for i, item in enumerate(outline.get("outline", []), 1):
        section = section_map.get(item.get("section", "body"), "主体")
        materials = " + ".join(material_map.get(m, m) for m in item.get("suggested_materials", []))
        refs = item.get("source_refs", [])
        est = item.get("est_duration", "?")

        lines.append(f"### {i}. [{section}] {item.get('theme', '')}\n")
        lines.append(f"素材: {materials} | 来源: {refs} | 时长: ~{est}s\n\n")
        for kp in item.get("key_points", []):
            lines.append(f"- {kp}\n")
        lines.append("\n")

    output_path.write_text("".join(lines), encoding="utf-8")


def _print_outline_preview(outline: dict):
    """在终端打印大纲预览。"""
    click.echo(f"\n📋 大纲预览: {outline.get('title', '?')}")
    click.echo(f"   主线: {outline.get('theme', '?')}")
    click.echo()

    material_icons = {"A": "📊", "B": "🖥️", "C": "🎬"}

    for i, item in enumerate(outline.get("outline", []), 1):
        section = item.get("section", "body")
        materials = "+".join(item.get("suggested_materials", []))
        mat_icons = "".join(material_icons.get(m, m) for m in item.get("suggested_materials", []))
        est = item.get("est_duration", "?")
        refs = item.get("source_refs", [])

        click.echo(f"   {i}. [{section}] {item.get('theme', '')}")
        click.echo(f"      {mat_icons} ({materials}, ~{est}s) ← 来源 {refs}")
