"""多 provider LLM 客户端 (复用 lecture2note 的路由模式)。

代理管理：per-request httpx.Client，不修改全局 os.environ。
成本追踪：每次调用自动记录 token usage 到 CostTracker。
"""

from __future__ import annotations

import os

import click
import httpx

# 一次性启动清理：修复系统中可能携带非法字符的 proxy 环境变量
# 例如 all_proxy=socks5://127.0.0.1:7890~
for _k in list(os.environ):
    if "proxy" in _k.lower():
        _v = os.environ[_k]
        if _v and _v.rstrip("/").endswith("~"):
            os.environ[_k] = _v.rstrip("~")


# ── 代理管理（per-request，不改 env var）─────────────────────


# 各 provider 的官方域名（用于判断是否需要系统代理）
_OFFICIAL_DOMAINS = {
    "anthropic": "api.anthropic.com",
    "openai": "api.openai.com",
}

# 国内 API：始终不走系统代理
_NO_PROXY_PROVIDERS = frozenset(["zhipu", "minimax", "gemini"])


def _read_proxy_url() -> str | None:
    """只读取系统代理环境变量，不修改。"""
    url = os.environ.get("https_proxy") or os.environ.get("http_proxy") or None
    # 跳过畸形值
    if url and url.rstrip("/").endswith("~"):
        return None
    return url


def _make_http_client(provider: str, base_url: str = "",
                      timeout: float = 600.0) -> httpx.Client:
    """为指定 provider 创建带正确代理配置的 httpx.Client。

    - 国内 API (zhipu/minimax/gemini): trust_env=False, proxy=None
    - 自定义 base_url (非官方): trust_env=False, proxy=None
    - 官方 API: trust_env=False, proxy=系统代理
    """
    # 决定是否需要代理
    if provider in _NO_PROXY_PROVIDERS:
        proxy_url = None
    elif base_url:
        official = _OFFICIAL_DOMAINS.get(provider, "")
        if official and official in base_url:
            proxy_url = _read_proxy_url()
        else:
            # 自定义网关，本身就是代理，不需要系统代理
            proxy_url = None
    else:
        proxy_url = _read_proxy_url()

    return httpx.Client(
        timeout=httpx.Timeout(timeout, connect=60.0),
        proxy=proxy_url,
        trust_env=False,  # 不自动读取 env var 中的代理
    )


# ── 模型类型判断 ─────────────────────────────────────────


def is_gemini_model(model: str) -> bool:
    return model.startswith("gemini")


def is_gpt_model(model: str) -> bool:
    return model.startswith("gpt") or model.startswith("o1") or model.startswith("o3") or model.startswith("o4")


def is_zhipu_model(model: str) -> bool:
    """智谱 GLM 系列模型（走官方 API）。"""
    return model.lower().startswith("glm")


def is_openai_compat_model(model: str) -> bool:
    """走 OpenAI 兼容 API 的模型（DeepSeek / Qwen 等，通过 GPT 代理）。"""
    prefixes = ("deepseek", "qwen", "abab")
    return model.lower().startswith(prefixes)


def is_minimax_model(model: str) -> bool:
    return model.lower().startswith("minimax")


# ── 统一调用入口 ──────────────────────────────────────────


def call_llm(system_prompt: str, user_message: str, model: str,
             temperature: float = 0.3, max_tokens: int = 16000,
             fallback_model: str | None = None) -> str:
    """统一 LLM 调用接口，根据模型名称自动路由。

    MiniMax 模型优先走官方 API (TTS_MINMAX_KEY)，失败时 fallback 到 GPT 代理。
    fallback_model: 主模型失败时自动切换到此模型重试（一次）。
      - 显式传入优先；未传入时自动读取 SCOUT_FALLBACK_MODEL 环境变量。
    """
    fb = fallback_model or os.environ.get("SCOUT_FALLBACK_MODEL") or None
    try:
        return _call_llm_single(system_prompt, user_message, model, temperature, max_tokens)
    except Exception as e:
        if fb and fb != model:
            click.echo(f"   ⚠️ {model} 失败: {e}")
            click.echo(f"   🔄 Fallback → {fb}")
            return _call_llm_single(system_prompt, user_message, fb, temperature, max_tokens)
        raise


def _call_llm_single(system_prompt: str, user_message: str, model: str,
                     temperature: float, max_tokens: int) -> str:
    """单次 LLM 调用，根据模型名称路由到具体 provider。"""
    if is_gemini_model(model):
        return _call_gemini(system_prompt, user_message, model, temperature, max_tokens)
    if is_zhipu_model(model):
        return _call_zhipu(system_prompt, user_message, model, temperature, max_tokens)
    if is_minimax_model(model):
        try:
            return _call_minimax(system_prompt, user_message, model, temperature, max_tokens)
        except Exception as e:
            if "overload" in str(e).lower() or "529" in str(e) or "2061" in str(e):
                click.echo(f"   ⚠️ MiniMax 官方 API 过载，尝试 GPT 代理...")
                return _call_gpt(system_prompt, user_message, model, temperature, max_tokens)
            raise
    if is_gpt_model(model) or is_openai_compat_model(model):
        return _call_gpt(system_prompt, user_message, model, temperature, max_tokens)
    return _call_claude(system_prompt, user_message, model, temperature, max_tokens)


# ── Provider 实现 ─────────────────────────────────────────


def _call_claude(system_prompt: str, user_message: str, model: str,
                 temperature: float, max_tokens: int) -> str:
    import anthropic
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

    # 使用流式调用（兼容中转平台）
    text_parts_delta = []
    text_parts_event = []
    has_thinking = False
    usage_input = 0
    usage_output = 0

    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        for event in stream:
            etype = getattr(event, "type", None)
            if etype == "content_block_delta":
                delta = event.delta
                delta_type = getattr(delta, "type", None)
                if delta_type == "text_delta":
                    text_parts_delta.append(getattr(delta, "text", ""))
                elif delta_type == "thinking_delta":
                    has_thinking = True
            elif etype == "text":
                text_parts_event.append(getattr(event, "text", ""))
        # 提取 usage（流结束后从 final message 获取）
        try:
            final_msg = stream.get_final_message()
            if final_msg and hasattr(final_msg, "usage"):
                usage_input = getattr(final_msg.usage, "input_tokens", 0)
                usage_output = getattr(final_msg.usage, "output_tokens", 0)
        except Exception:
            pass

    result = "".join(text_parts_delta) or "".join(text_parts_event)

    if not result:
        if has_thinking:
            click.echo("   ⚠️ thinking 模式耗尽 token，增大 budget 重试...")
            text_parts_delta = []
            with client.messages.stream(
                model=model,
                max_tokens=max_tokens * 4,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            ) as stream:
                for event in stream:
                    etype = getattr(event, "type", None)
                    if etype == "content_block_delta":
                        delta = event.delta
                        if getattr(delta, "type", None) == "text_delta":
                            text_parts_delta.append(getattr(delta, "text", ""))
                try:
                    final_msg = stream.get_final_message()
                    if final_msg and hasattr(final_msg, "usage"):
                        usage_input += getattr(final_msg.usage, "input_tokens", 0)
                        usage_output += getattr(final_msg.usage, "output_tokens", 0)
                except Exception:
                    pass
            result = "".join(text_parts_delta)

    if not result:
        raise RuntimeError("Claude 返回空响应")

    get_tracker().record_llm(model, usage_input, usage_output)
    return result


def _call_gemini(system_prompt: str, user_message: str, model: str,
                 temperature: float, max_tokens: int) -> str:
    from google import genai
    from v2g.cost import get_tracker

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise click.ClickException("未设置 GEMINI_API_KEY")

    base_url = os.environ.get("GEMINI_BASE_URL")
    http_client = _make_http_client("gemini")
    http_opts: dict = {"httpxClient": http_client}
    if base_url:
        http_opts["base_url"] = base_url

    client = genai.Client(api_key=api_key, http_options=http_opts)
    response = client.models.generate_content(
        model=model,
        contents=user_message,
        config=genai.types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_tokens,
        ),
    )

    # 提取 usage
    usage_input = 0
    usage_output = 0
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        usage_input = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
        usage_output = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
    get_tracker().record_llm(model, usage_input, usage_output)

    return response.text


def _call_gpt(system_prompt: str, user_message: str, model: str,
              temperature: float, max_tokens: int) -> str:
    from openai import OpenAI
    from v2g.cost import get_tracker

    base_url = os.environ.get("GPT_BASE_URL")
    api_key = os.environ.get("GPT_API_KEY", "")

    if not api_key:
        base_url = os.environ.get("ANTHROPIC_BASE_URL") or base_url
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise click.ClickException("未设置 GPT_API_KEY")

    client_kwargs: dict = {}
    if base_url:
        if not base_url.rstrip("/").endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"
        client_kwargs["base_url"] = base_url
    client_kwargs["http_client"] = _make_http_client("openai", base_url or "")

    client = OpenAI(api_key=api_key, **client_kwargs)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # 提取 usage
    usage_input = 0
    usage_output = 0
    if response.usage:
        usage_input = response.usage.prompt_tokens or 0
        usage_output = response.usage.completion_tokens or 0
    get_tracker().record_llm(model, usage_input, usage_output)

    result = response.choices[0].message.content or ""
    import re as _re
    result = _re.sub(r"<think>.*?</think>", "", result, flags=_re.DOTALL).strip()
    return result


def _call_minimax(system_prompt: str, user_message: str, model: str,
                  temperature: float, max_tokens: int) -> str:
    """MiniMax 官方 API (OpenAI 兼容格式，用 TTS_MINMAX_KEY)。"""
    from openai import OpenAI
    from v2g.cost import get_tracker

    api_key = os.environ.get("TTS_MINMAX_KEY", "")
    if not api_key:
        raise click.ClickException("未设置 TTS_MINMAX_KEY (MiniMax API Key)")

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.minimax.chat/v1",
        http_client=_make_http_client("minimax"),
    )

    effective_max = max_tokens * 4 if "m2.7" in model.lower() else max_tokens

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=temperature,
        max_tokens=effective_max,
    )

    if not response.choices:
        raise RuntimeError(f"MiniMax 返回空 choices")

    # 提取 usage
    usage_input = 0
    usage_output = 0
    if response.usage:
        usage_input = response.usage.prompt_tokens or 0
        usage_output = response.usage.completion_tokens or 0
    get_tracker().record_llm(model, usage_input, usage_output)

    result = response.choices[0].message.content or ""
    import re as _re
    result = _re.sub(r"<think>.*?</think>", "", result, flags=_re.DOTALL).strip()
    return result


def _call_zhipu(system_prompt: str, user_message: str, model: str,
                temperature: float, max_tokens: int) -> str:
    """智谱 GLM 官方 API (OpenAI 兼容格式)。"""
    from openai import OpenAI
    from v2g.cost import get_tracker

    api_key = os.environ.get("ZHIPU_API_KEY", "")
    if not api_key:
        raise click.ClickException("未设置 ZHIPU_API_KEY")

    base_url = os.environ.get("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        http_client=_make_http_client("zhipu"),
    )

    # 推理模型 (glm-5 等) 需要更大的 max_tokens 给 reasoning
    effective_max = max_tokens * 4 if "glm-5" in model.lower() else max_tokens

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=temperature,
        max_tokens=effective_max,
    )

    # 提取 usage
    usage_input = 0
    usage_output = 0
    if response.usage:
        usage_input = response.usage.prompt_tokens or 0
        usage_output = response.usage.completion_tokens or 0
    get_tracker().record_llm(model, usage_input, usage_output)

    # 推理模型可能把内容放在 reasoning_content，content 为空
    msg = response.choices[0].message
    result = msg.content or ""
    if not result and hasattr(msg, "reasoning_content") and msg.reasoning_content:
        result = msg.reasoning_content
    return result
