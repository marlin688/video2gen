"""Agent 驱动的视频脚本编排：多源素材 → 大纲 → script.json。

支持两种 agent loop 后端：
- Anthropic SDK (Claude 系列模型)
- OpenAI 兼容 SDK (MiniMax / DeepSeek / GPT / Qwen 等)
"""

import json
import os
import re
from contextvars import ContextVar
from pathlib import Path

import click

from v2g.config import Config
from v2g.checkpoint import PipelineState
from v2g.quality_profile import resolve_quality_profile, load_profile_prompt
from v2g.asset_context import build_asset_context
from v2g.services.input_adapters import SourceInput, resolve_source_input

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
    {
        "name": "search_github",
        "description": "搜索 GitHub 仓库，返回按 stars 排序的仓库列表（名称、描述、stars、语言、URL）。"
                       "用于获取项目热度、最新 star 数等真实数据来支撑脚本内容。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，如 'claude code editor'",
                },
                "min_stars": {
                    "type": "integer",
                    "description": "最低 star 数 (默认 100)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_hn",
        "description": "搜索 Hacker News 帖子，返回按 points 排序的帖子列表（标题、URL、作者、points、评论数）。"
                       "用于了解社区讨论热度、争议点和用户反馈。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，如 'Claude Code'",
                },
                "hours": {
                    "type": "integer",
                    "description": "最近多少小时内 (默认 168 即一周)",
                },
            },
            "required": ["query"],
        },
    },
]

# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

# Runtime context — per-agent-run context (避免模块级共享状态串扰)
_CTX_VAR: ContextVar[dict | None] = ContextVar("v2g_agent_ctx", default=None)


def _get_ctx() -> dict:
    ctx = _CTX_VAR.get()
    if ctx is None:
        raise RuntimeError("Agent 上下文未初始化")
    return ctx


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
    if name == "search_github":
        return _tool_search_github(input_data["query"], input_data.get("min_stars", 100))
    if name == "search_hn":
        return _tool_search_hn(input_data["query"], input_data.get("hours", 168))
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
    ctx = _get_ctx()
    output_dir: Path = ctx["output_dir"]
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

    ctx["outline_saved"] = True
    return "大纲已保存到 outline.json，等待用户确认。"


def _tool_save_script(script_json_str: str) -> str:
    ctx = _get_ctx()
    output_dir: Path = ctx["output_dir"]
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
    from v2g.scriptwriter import (
        sync_script_sidecars,
        validate_script_sidecars,
    )

    sync_script_sidecars(script_data, output_dir)
    sidecar_issues = validate_script_sidecars(script_data, output_dir)
    if sidecar_issues:
        return "脚本已保存，但 sidecar 校验失败: " + "; ".join(sidecar_issues[:5])

    click.echo(f"   ✅ 脚本已保存: {script_json_path}")

    ctx["script_saved"] = True
    return "脚本已保存到 script.json、script.md、recording_guide.md、script_beats.md、shot_plan.json、render_plan.json。"


def _tool_search_github(query: str, min_stars: int = 100) -> str:
    """搜索 GitHub 仓库，返回精简摘要。"""
    import httpx

    try:
        resp = httpx.get(
            "https://api.github.com/search/repositories",
            params={
                "q": f"{query} stars:>{min_stars}",
                "sort": "stars",
                "order": "desc",
                "per_page": 10,
            },
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "video2gen-agent",
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        results = [{
            "name": r["full_name"],
            "description": (r.get("description") or "")[:200],
            "stars": r["stargazers_count"],
            "language": r.get("language"),
            "url": r["html_url"],
            "created": r["created_at"][:10],
        } for r in items[:10]]
        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        return f"GitHub 搜索失败: {e}"


def _tool_search_hn(query: str, hours: int = 168) -> str:
    """搜索 Hacker News，返回精简摘要。"""
    import time
    import httpx

    try:
        cutoff = int(time.time()) - hours * 3600
        resp = httpx.get(
            "https://hn.algolia.com/api/v1/search",
            params={
                "query": query,
                "tags": "story",
                "numericFilters": f"created_at_i>{cutoff},points>5",
                "hitsPerPage": 10,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
        results = [{
            "title": h.get("title"),
            "url": h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}",
            "points": h.get("points"),
            "comments": h.get("num_comments"),
            "author": h.get("author"),
        } for h in hits[:10]]
        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        return f"HN 搜索失败: {e}"


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
    from v2g.llm import _make_http_client
    from v2g.cost import get_tracker

    base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise click.ClickException("未设置 ANTHROPIC_API_KEY")

    client = anthropic.Anthropic(
        api_key=api_key,
        base_url=base_url,
        http_client=_make_http_client("anthropic", base_url),
    )

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
    from v2g.llm import _make_http_client
    from v2g.cost import get_tracker

    # 各厂商官方 API 路由
    if _is_zhipu_model(model):
        base_url = "https://open.bigmodel.cn/api/paas/v4"
        api_key = os.environ.get("ZHIPU_API_KEY", "")
        provider = "zhipu"
        if not api_key:
            raise click.ClickException("未设置 ZHIPU_API_KEY")
    elif _is_minimax_model(model):
        minimax_key = os.environ.get("TTS_MINMAX_KEY", "")
        gpt_key = os.environ.get("GPT_API_KEY", "")
        if minimax_key:
            base_url = "https://api.minimax.chat"
            api_key = minimax_key
            provider = "minimax"
        elif gpt_key:
            base_url = os.environ.get("GPT_BASE_URL", "")
            api_key = gpt_key
            provider = "openai"
        else:
            raise click.ClickException("未设置 TTS_MINMAX_KEY 或 GPT_API_KEY")
    else:
        base_url = os.environ.get("GPT_BASE_URL", "")
        api_key = os.environ.get("GPT_API_KEY", "")
        provider = "openai"
        if not api_key:
            base_url = os.environ.get("ANTHROPIC_BASE_URL", base_url)
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise click.ClickException("未设置 GPT_API_KEY")

    # 只对需要 /v1 后缀的平台补充（智谱等已有正确路径的跳过）
    if base_url and not any(base_url.rstrip("/").endswith(s) for s in ("/v1", "/v4")):
        base_url = base_url.rstrip("/") + "/v1"

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        http_client=_make_http_client(provider, base_url),
    )

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

        # 记录 token usage
        if response.usage:
            get_tracker().record_llm(
                model,
                response.usage.prompt_tokens or 0,
                response.usage.completion_tokens or 0,
                stage="agent",
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
# Phase 2: 分段脚本生成 (骨架 → 逐批填充)
# ---------------------------------------------------------------------------

def _generate_script_phased(
    outline: dict, system_prompt: str, model: str, output_dir: Path,
) -> dict:
    """分段生成脚本：骨架 → 逐批填充，解决代理网关截断大 JSON。

    Step 1: 生成精简骨架 (narration_zh 只写前 10 字)
    Step 2: 每批 3 段，单独填充完整内容
    Fallback: 如果分段失败，回退到单次完整调用
    """
    from v2g.llm import call_llm
    from v2g.scriptwriter import _extract_json

    outline_str = json.dumps(outline, ensure_ascii=False, indent=2)

    # ── Step 1: 骨架 ──
    click.echo("   📋 Step 1/2: 生成骨架...")
    skeleton_prompt = (
        f"请根据以下大纲生成视频脚本的骨架结构。\n\n"
        f"## 已确认的大纲\n\n{outline_str}\n\n"
        f"---\n\n"
        f"要求：\n"
        f"1. 输出完整的 script.json 结构 (title, description, tags, segments)\n"
        f"2. 每个 segment 包含: id, type, material, component (可选)\n"
        f"3. narration_zh 只写前 10 个字 + \"...\" (占位，后续填充)\n"
        f"4. slide_content/terminal_session/code_content 等数据字段留空或写最简形式\n"
        f"5. 严格输出 JSON，不要代码块标记，不要其他文字。"
    )

    try:
        skeleton_resp = call_llm(system_prompt, skeleton_prompt, model, max_tokens=8000)
        skeleton_resp = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', skeleton_resp)
        skeleton = _extract_json(skeleton_resp)
    except Exception as e:
        click.echo(f"   ⚠️ 骨架生成失败，回退到单次完整调用: {e}")
        from v2g.cost import get_tracker
        get_tracker().record_degradation("agent_script", "phased", "oneshot", str(e))
        return _generate_script_oneshot(outline_str, system_prompt, model, output_dir)

    segments = skeleton.get("segments", [])
    if not segments:
        click.echo("   ⚠️ 骨架无 segments，回退到单次完整调用")
        from v2g.cost import get_tracker
        get_tracker().record_degradation("agent_script", "phased", "oneshot", "skeleton has no segments")
        return _generate_script_oneshot(outline_str, system_prompt, model, output_dir)

    click.echo(f"   ✅ 骨架: {len(segments)} 段")

    # ── Step 2: 逐批填充 ──
    click.echo("   📝 Step 2/2: 逐批填充内容...")
    skeleton_summary = json.dumps(
        [{"id": s["id"], "type": s.get("type"), "material": s.get("material"),
          "component": s.get("component")}
         for s in segments],
        ensure_ascii=False,
    )

    batch_size = 3
    for batch_start in range(0, len(segments), batch_size):
        batch = segments[batch_start:batch_start + batch_size]
        batch_ids = [s["id"] for s in batch]
        click.echo(f"      填充 seg {batch_ids}...")

        # 收集已填充段的 narration 作为上下文，帮助后续批次承接和避免重复
        filled_context = ""
        for s in segments[:batch_start]:
            nar = s.get("narration_zh", "")
            if nar and not nar.endswith("..."):
                filled_context += f"[seg {s['id']} ({s.get('type', 'body')})]: {nar}\n"

        fill_prompt = (
            f"你正在为一个视频脚本逐段填充内容。\n\n"
            f"## 脚本骨架 (全部段)\n{skeleton_summary}\n\n"
            f"## 大纲\n{outline_str}\n\n"
            + (f"## 已生成的段落（请承接上文，避免重复）\n{filled_context}\n" if filled_context else "")
            + f"---\n\n"
            f"请填充 segment {batch_ids} 的完整内容。\n"
            f"输出格式: {{\"segments\": [{{完整的 segment 1}}, {{完整的 segment 2}}, ...]}}\n"
            f"每个 segment 必须包含完整的 narration_zh、slide_content/terminal_session 等所有数据字段。\n"
            f"严格输出 JSON，不要代码块标记，不要其他文字。"
        )

        try:
            fill_resp = call_llm(system_prompt, fill_prompt, model, max_tokens=8000)
            fill_resp = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', fill_resp)
            filled = _extract_json(fill_resp)
            filled_segs = filled.get("segments", [])

            # 合并回骨架
            id_map = {s["id"]: s for s in filled_segs}
            for i, s in enumerate(segments):
                if s["id"] in id_map:
                    segments[i] = id_map[s["id"]]

        except Exception as e:
            click.echo(f"      ⚠️ 批次 {batch_ids} 填充失败: {e}")
            click.echo("      🔄 回退到单次完整调用，避免占位脚本进入下游阶段")
            from v2g.cost import get_tracker
            get_tracker().record_degradation(
                "agent_script", "phased-batch", "oneshot", f"batch {batch_ids} failed: {e}"
            )
            return _generate_script_oneshot(outline_str, system_prompt, model, output_dir)

    # 占位文本未被替换说明分批填充不完整，直接回退确保脚本可用性
    placeholder_segments = [
        s.get("id") for s in segments
        if isinstance(s.get("narration_zh"), str) and s.get("narration_zh", "").strip().endswith("...")
    ]
    if placeholder_segments:
        click.echo(f"      ⚠️ 检测到占位段落: {placeholder_segments}")
        click.echo("      🔄 回退到单次完整调用，避免不完整脚本进入下游阶段")
        from v2g.cost import get_tracker
        get_tracker().record_degradation(
            "agent_script", "phased-placeholder", "oneshot",
            f"placeholder segments: {placeholder_segments}",
        )
        return _generate_script_oneshot(outline_str, system_prompt, model, output_dir)

    skeleton["segments"] = segments

    # 保存原始响应供调试
    (output_dir / "script_raw.txt").write_text(
        json.dumps(skeleton, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return skeleton


def _generate_script_oneshot(
    outline_str: str, system_prompt: str, model: str, output_dir: Path,
) -> dict:
    """回退方案：单次完整调用 + 截断续写。"""
    from v2g.llm import call_llm
    from v2g.scriptwriter import _extract_json

    user_message = (
        f"请根据以下大纲生成完整的视频脚本。\n\n"
        f"## 已确认的大纲\n\n{outline_str}\n\n"
        f"---\n\n"
        f"严格输出 JSON，不要代码块标记，不要任何其他文字。"
    )

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

    response = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', response)
    (output_dir / "script_raw.txt").write_text(response, encoding="utf-8")
    return _extract_json(response)


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
    auto_confirm: bool = False,
    auto_confirm_threshold: int = 85,
    quality_profile: str = "default",
):
    """Agent 驱动的脚本编排：素材 → 大纲 → script.json。

    auto_confirm: True 时根据评分自动确认大纲，不需人工交互。
    auto_confirm_threshold: 自动确认的最低分数（0-100）。
    """
    from v2g.workflow_contract import sync_workflow_contract

    model = model or cfg.script_model
    try:
        profile = resolve_quality_profile(quality_profile)
    except ValueError as e:
        raise click.ClickException(str(e))
    profile_prompt = load_profile_prompt(profile["name"])
    resolved_sources = [resolve_source_input(source) for source in sources]
    unreadable_videos = [
        source.path
        for source in resolved_sources
        if source.kind == "local_video" and source.readable_path is None
    ]
    if unreadable_videos:
        files = ", ".join(str(path) for path in unreadable_videos if path)
        raise click.ClickException(
            "以下本地视频缺少可读 companion 文件（需要同目录 .srt/.md/.txt）: "
            + files
        )

    output_dir = cfg.output_dir / project_id
    output_dir.mkdir(parents=True, exist_ok=True)
    sync_workflow_contract(
        output_dir, project_id,
        stage="agent", status="start",
        message="Agent 任务启动",
        extra={"topic": topic, "source_count": len(sources)},
    )

    # Load or create state
    state = PipelineState.load(cfg.output_dir, project_id)
    if not state.project_id:
        state.project_id = project_id
    state.topic = topic

    # 档位自动设置视觉主题（如 anthropic_brand → anthropic-cream）
    profile_theme = profile.get("theme") or ""
    if profile_theme and state.theme != profile_theme:
        click.echo(f"   🎨 档位覆盖主题: {state.theme or '(未设)'} → {profile_theme}")
        state.theme = profile_theme
        state.save(cfg.output_dir)

    # 档位自动设置 camera_rig 开关（tech_explainer → False 硬切风格）
    profile_camera_rig = profile.get("camera_rig")
    if profile_camera_rig is not None and state.camera_rig != profile_camera_rig:
        click.echo(f"   🎥 档位覆盖运镜: camera_rig → {profile_camera_rig}")
        state.camera_rig = profile_camera_rig
        state.save(cfg.output_dir)

    # 档位自动设置默认段间转场（tech_explainer → "none" 硬切）
    profile_default_transition = profile.get("default_transition") or ""
    if profile_default_transition and state.default_transition != profile_default_transition:
        click.echo(f"   ✂️  档位覆盖默认转场: → {profile_default_transition}")
        state.default_transition = profile_default_transition
        state.save(cfg.output_dir)

    # Initialize context
    _CTX_VAR.set({
        "output_dir": output_dir,
        "cfg": cfg,
        "outline_saved": False,
        "script_saved": False,
    })

    # ── Phase 1: 素材分析 + 大纲生成 ──────────────────────────
    outline_path = output_dir / "outline.json"
    if state.agent_outline_done and outline_path.exists():
        click.echo("⏭️  大纲已存在")
    else:
        click.echo(f"\n🤖 Agent 启动 (模型: {model})")
        click.echo(f"   主题: {topic}")
        click.echo(f"   目标时长: {duration}s")
        click.echo(f"   质量档位: {profile['name']}")
        click.echo(f"   素材: {len(sources)} 个\n")

        # Classify sources and build description
        source_desc = _describe_sources(resolved_sources)

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

        if not _get_ctx().get("outline_saved"):
            sync_workflow_contract(
                output_dir, project_id,
                stage="agent", status="error",
                message="Agent 未生成大纲",
            )
            raise click.ClickException("Agent 未生成大纲。请检查素材内容后重试。")

        state.agent_outline_done = True
        state.agent_sources = _build_source_records(resolved_sources)
        state.save(cfg.output_dir)

    # ── 大纲预览 + 自动/人工确认 ─────────────────────────────
    if not state.outline_reviewed:
        outline = json.loads(outline_path.read_text(encoding="utf-8"))
        _print_outline_preview(outline)

        # 自动评分：检查大纲结构质量
        score = _score_outline(outline, duration)
        click.echo(f"\n📊 大纲评分: {score}/100")

        if auto_confirm:
            if score >= auto_confirm_threshold:
                click.echo(f"   ✅ 自动确认（≥{auto_confirm_threshold}分）")
            else:
                click.echo(f"   ❌ 评分不足（<{auto_confirm_threshold}分），中止")
                click.echo("💡 请手动编辑 outline.json 后重新运行")
                return
        else:
            if not click.confirm("\n✅ 确认大纲？", default=True):
                click.echo("💡 请手动编辑 outline.json 后重新运行 v2g agent")
                return

        state.outline_reviewed = True
        state.save(cfg.output_dir)

    # ── Phase 2: 大纲 → script.json (分段生成，避免截断) ──────
    script_path = output_dir / "script.json"
    if state.scripted and script_path.exists():
        click.echo("⏭️  脚本已存在")
    else:
        click.echo("\n🔄 展开脚本中...")

        outline = json.loads(outline_path.read_text(encoding="utf-8"))
        from v2g.style_catalog import inject_catalog
        style_id_prefix = profile.get("style_id_prefix") or None
        if style_id_prefix:
            click.echo(f"   🎯 档位限定组件前缀: {style_id_prefix}")
        system_prompt = (
            _read_prompt("agent_system.md")
            + "\n\n"
            + inject_catalog(
                _read_prompt("agent_script.md"),
                id_prefix=style_id_prefix,
            )
        )
        topic_template = _topic_script_template(topic, sources)
        if topic_template:
            click.echo("   🧩 应用专题骨架: Claude Code + Obsidian")
            system_prompt += "\n\n" + topic_template
        if profile_prompt:
            click.echo(f"   🧪 应用质量档位: {profile['name']}")
            system_prompt += "\n\n## 质量档位约束\n" + profile_prompt

        # 注入素材库历史反馈（留存表现 + 可复用素材）
        asset_ctx = build_asset_context(cfg)
        if asset_ctx:
            system_prompt += "\n\n" + asset_ctx

        from v2g.llm import call_llm
        from v2g.scriptwriter import (
            _extract_json,
            sync_script_sidecars,
            validate_script_sidecars,
        )

        try:
            script_data = _generate_script_phased(
                outline, system_prompt, model, output_dir
            )
        except Exception as e:
            state.last_error = f"脚本生成失败: {e}"
            state.save(cfg.output_dir)
            sync_workflow_contract(
                output_dir, project_id,
                stage="agent", status="error",
                message=state.last_error,
            )
            raise click.ClickException(state.last_error)

        # 保存脚本及辅助文件
        script_path.write_text(
            json.dumps(script_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # Update checkpoint
        state.script_json = str(script_path)
        state.recording_guide = str(output_dir / "recording_guide.md")
        state.slides_dir = str(output_dir / "slides")
        state.recordings_dir = str(output_dir / "recordings")
        (output_dir / "slides").mkdir(exist_ok=True)
        (output_dir / "recordings").mkdir(exist_ok=True)

        # ── Phase 2.1: scene_data 字段名校验 + 自动修复 ─────
        from v2g.scene_data_validator import validate_and_fix_scene_data
        script_data, sd_warnings = validate_and_fix_scene_data(script_data, auto_fix=True)
        if sd_warnings:
            click.echo(f"\n🔧 scene_data 字段名修复: {len(sd_warnings)} 处")
            for w in sd_warnings:
                click.echo(f"   {w}")
            # 重新保存修复后的 script
            script_path.write_text(
                json.dumps(script_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        # ── Phase 2.2: 脚本结构自动修复 ──────────────────────
        from v2g.script_fixer import fix_script
        script_data, fix_logs = fix_script(script_data, output_dir)
        if fix_logs:
            click.echo(f"\n🔧 脚本结构修复: {len(fix_logs)} 处")
            for log in fix_logs:
                click.echo(f"   {log}")
            script_path.write_text(
                json.dumps(script_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        # 统一以最终修复后的 script 生成辅助文件，避免产物不一致
        sync_script_sidecars(script_data, output_dir)
        sidecar_issues = validate_script_sidecars(script_data, output_dir)
        if sidecar_issues:
            sync_workflow_contract(
                output_dir, project_id,
                stage="agent", status="error",
                message="脚本 sidecar 一致性校验失败",
                extra={"issues": sidecar_issues[:8]},
            )
            raise click.ClickException(
                "脚本 sidecar 一致性校验失败: " + "; ".join(sidecar_issues[:8])
            )

        state.scripted = True
    state.last_error = ""
    state.save(cfg.output_dir)
    sync_workflow_contract(
        output_dir, project_id,
        stage="agent", status="ok",
        message="Agent 阶段完成",
        extra={"scripted": state.scripted, "tts_done": state.tts_done, "slides_done": state.slides_done},
    )

    # ── Phase 2.5: 质量门控（agent 模式不自动重试，仅报告）─────
    from v2g.pipeline import _run_quality_gate
    _run_quality_gate(
        cfg,
        project_id,
        model,
        max_retries=0,
        threshold=85,
        quality_profile=profile["name"],
    )

    # agent 模式质量门控后强制阻断 critical 与关键 warning，避免平庸脚本进入下游
    from v2g.eval import eval_script, get_blocking_warnings
    report = eval_script(
        json.loads(script_path.read_text(encoding="utf-8")),
        project_id,
        quality_profile=profile["name"],
        assets_db_path=cfg.output_dir / "assets.db",
    )
    blocking_warnings = get_blocking_warnings(report)
    if report.get("has_critical") or blocking_warnings:
        failed = [c["name"] for c in report.get("critical_failed", [])] + [
            w["name"] for w in blocking_warnings
        ]
        raise click.ClickException(
            "脚本质量门控未通过（critical / blocking warning）: "
            + ", ".join(failed)
            + "。请修复 outline/script 后重试。"
        )

    # ── Phase 3: B 类素材自动采集 ─────────────────────────
    script_data = json.loads(script_path.read_text(encoding="utf-8"))
    segments = script_data.get("segments", [])
    b_count = sum(1 for s in segments if s.get("material") == "B")

    if b_count > 0:
        # 预检：ffmpeg 是否可用（autocap → recorder 需要 ffmpeg 合成视频）
        import shutil as _shutil
        _ffmpeg_available = _shutil.which("ffmpeg") is not None
        if not _ffmpeg_available:
            try:
                import imageio_ffmpeg
                imageio_ffmpeg.get_ffmpeg_exe()
                _ffmpeg_available = True
            except (ImportError, RuntimeError):
                pass

        if _ffmpeg_available:
            click.echo(f"\n🖥️ 自动采集 B 类素材 ({b_count} 段)...")
            from v2g.autocap import run_capture
            run_capture(cfg, project_id)
        else:
            click.echo(f"\n⚠️ ffmpeg 未安装，跳过 B 类素材自动采集（{b_count} 段将在渲染时使用终端模拟动画）")

    # ── 完成 ─────────────────────────────────────────────
    a = sum(1 for s in segments if s.get("material") == "A")
    b = b_count
    c = sum(1 for s in segments if s.get("material") == "C")

    click.echo(f"\n✅ 脚本生成完成:")
    click.echo(f"   📊 {len(segments)} 段 (A={a} B={b} C={c})")
    click.echo(f"   📄 脚本: output/{project_id}/script.md")
    click.echo(f"   🖥️  录屏指南: output/{project_id}/recording_guide.md")

    # 成本摘要
    from v2g.cost import get_tracker
    tracker = get_tracker()
    tracker.print_summary()
    state.cost_summary = tracker.summary()
    state.save(cfg.output_dir)

    click.echo(f"\n💡 下一步:")
    click.echo(f"   v2g tts {project_id}")
    click.echo(f"   v2g slides {project_id}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def _topic_script_template(topic: str, sources: tuple[str, ...]) -> str:
    """按主题自动注入专项脚本骨架模板。"""
    t = (topic or "").lower()
    source_text = " ".join(sources).lower()

    has_claude = "claude" in t or "claude" in source_text
    has_obsidian = "obsidian" in t or "obsidian" in source_text

    if has_claude and has_obsidian:
        return _read_prompt("tutorial_cc_obsidian_skeleton.md")
    return ""


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


def _describe_sources(sources: list[SourceInput]) -> str:
    """生成素材列表描述，区分 URL、本地文本和本地视频 sidecar。"""
    lines = []
    for i, source in enumerate(sources):
        if source.kind in {"url", "youtube"} and source.url:
            label = "YouTube 视频页" if source.kind == "youtube" else "网页文章"
            lines.append(f"[{i}] 🌐 {label}: {source.url}")
            lines.append("    → 请用 `fetch_url` 抓取")
            continue

        readable = source.readable_path
        if readable:
            suffix = readable.suffix.lower()
            type_map = {".srt": "字幕文件", ".md": "Markdown 笔记", ".txt": "文本文件"}
            ftype = type_map.get(suffix, f"{suffix} 文件")
            prefix = "🎬 本地视频" if source.kind == "local_video" else "📄"
            lines.append(f"[{i}] {prefix} {source.display_name}")
            lines.append(f"    → 请用 `read_source_file` 读取 {ftype}: {readable}")
            continue

        if source.path:
            lines.append(f"[{i}] 📄 本地文件: {source.path.name}")
            lines.append(f"    → 路径无法识别，请人工检查: {source.path}")
        else:
            lines.append(f"[{i}] ❓ 未知素材: {source.raw}")
    return "\n".join(lines)


def _build_source_records(sources: list[SourceInput]) -> list[dict]:
    """构建素材记录列表，存入 checkpoint。"""
    records = []
    for i, source in enumerate(sources):
        if source.url:
            records.append({"id": i, "type": source.kind, "path": source.url})
        elif source.path:
            records.append({"id": i, "type": source.kind, "path": str(source.path)})
        else:
            records.append({"id": i, "type": source.kind, "path": source.raw})
    return records


def _load_cached_sources(output_dir: Path, sources: list[SourceInput]) -> str:
    """加载素材内容摘要，供阶段二参考。"""
    parts = []
    for i, source in enumerate(sources):
        if source.url:
            parts.append(f"### 素材 [{i}]: 网页文章 ({source.url})")
            parts.append("（已在阶段一分析，请参考大纲中的 source_summary）\n")
        else:
            readable = source.readable_path or source.path
            if readable and readable.exists():
                content = readable.read_text(encoding="utf-8")
                if readable.suffix.lower() == ".srt":
                    content = _parse_srt_to_text(content)
                # 截断过长内容
                if len(content) > 6000:
                    content = content[:6000] + "\n...(已截断)"
                parts.append(f"### 素材 [{i}]: {readable.name}")
                parts.append(content + "\n")
            else:
                parts.append(f"### 素材 [{i}]: {source.display_name} (文件不存在)")
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
        materials = " + ".join(
            material_map.get(m, str(m)) if isinstance(m, str) else str(m)
            for m in item.get("suggested_materials", [])
        )
        refs = item.get("source_refs", [])
        est = item.get("est_duration", "?")

        lines.append(f"### {i}. [{section}] {item.get('theme', '')}\n")
        lines.append(f"素材: {materials} | 来源: {refs} | 时长: ~{est}s\n\n")
        for kp in item.get("key_points", []):
            lines.append(f"- {kp}\n")
        lines.append("\n")

    output_path.write_text("".join(lines), encoding="utf-8")


def _score_outline(outline: dict, target_duration: int = 240) -> int:
    """对大纲进行结构质量评分（0-100）。

    评分维度（各 20 分，共 100）：
    1. 段落数量：8-20 段满分，<4 或 >25 不及格
    2. 结构完整性：有 intro + body + outro
    3. 素材多样性：A/B/C 三种都有
    4. 时长匹配：总预估时长与目标时长偏差 <30%
    5. 内容充实度：每段都有 theme 和 key_points
    """
    items = outline.get("outline", [])
    score = 0

    # 1. 段落数量 (20 分)
    n = len(items)
    if 8 <= n <= 20:
        score += 20
    elif 6 <= n <= 24:
        score += 12
    elif n >= 3:
        score += 5

    # 2. 结构完整性 (20 分)
    sections = {item.get("section", "") for item in items}
    if "intro" in sections:
        score += 7
    if "body" in sections:
        score += 7
    if "outro" in sections:
        score += 6

    # 3. 素材多样性 (20 分)
    all_materials = set()
    for item in items:
        for m in item.get("suggested_materials", []):
            all_materials.add(m)
    score += min(len(all_materials) * 7, 20)

    # 4. 时长匹配 (20 分)
    total_est = sum(item.get("est_duration", 0) for item in items)
    if total_est > 0 and target_duration > 0:
        ratio = total_est / target_duration
        if 0.7 <= ratio <= 1.3:
            score += 20
        elif 0.5 <= ratio <= 1.5:
            score += 12
        else:
            score += 5

    # 5. 内容充实度 (20 分)
    if items:
        filled = sum(1 for item in items if item.get("theme") and item.get("key_points"))
        fill_rate = filled / len(items)
        score += int(fill_rate * 20)

    return min(score, 100)


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
