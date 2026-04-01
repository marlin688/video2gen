"""多 provider LLM 客户端 (复用 lecture2note 的路由模式)。"""

import os

import click

# 清理系统中可能携带非法字符的 proxy 环境变量（如 all_proxy=socks5://127.0.0.1:7890~）
for _k in list(os.environ):
    if "proxy" in _k.lower():
        _v = os.environ[_k]
        if _v and _v.rstrip("/").endswith("~"):
            os.environ[_k] = _v.rstrip("~")


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


def call_llm(system_prompt: str, user_message: str, model: str,
             temperature: float = 0.3, max_tokens: int = 16000) -> str:
    """统一 LLM 调用接口，根据模型名称自动路由。

    MiniMax 模型优先走官方 API (TTS_MINMAX_KEY)，失败时 fallback 到 GPT 代理。
    """
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


def _call_claude(system_prompt: str, user_message: str, model: str,
                 temperature: float, max_tokens: int) -> str:
    import anthropic
    import httpx

    base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise click.ClickException("未设置 ANTHROPIC_API_KEY")

    # 清理可能带非法字符的 proxy env（如 all_proxy=socks5://...~）
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
    os.environ.update(_cleaned_proxy)  # restore

    # 使用流式调用（兼容中转平台）
    # 代理平台可能同时发送 content_block_delta 和简化的 text 事件
    # 优先用 content_block_delta，fallback 到 text 事件
    text_parts_delta = []
    text_parts_event = []
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
                if getattr(delta, "type", None) == "text_delta":
                    text_parts_delta.append(getattr(delta, "text", ""))
            elif etype == "text":
                text_parts_event.append(getattr(event, "text", ""))
    # 优先使用 delta 模式；如果为空则 fallback 到 event 模式
    result = "".join(text_parts_delta) or "".join(text_parts_event)
    if not result:
        raise RuntimeError("Claude 返回空响应")
    return result


def _call_gemini(system_prompt: str, user_message: str, model: str,
                 temperature: float, max_tokens: int) -> str:
    from google import genai
    import httpx

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise click.ClickException("未设置 GEMINI_API_KEY")

    base_url = os.environ.get("GEMINI_BASE_URL")
    http_opts = {"httpxClient": httpx.Client()}
    if base_url:
        http_opts["base_url"] = base_url

    # 临时清除代理（Gemini SDK 不走系统代理）
    proxy_vars = {}
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        if key in os.environ:
            proxy_vars[key] = os.environ.pop(key)
    try:
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
    finally:
        os.environ.update(proxy_vars)
    return response.text


def _call_gpt(system_prompt: str, user_message: str, model: str,
              temperature: float, max_tokens: int) -> str:
    from openai import OpenAI
    import httpx

    base_url = os.environ.get("GPT_BASE_URL")
    api_key = os.environ.get("GPT_API_KEY", "")

    if not api_key:
        # fallback: 尝试 Anthropic 中转作为 GPT 兼容
        base_url = os.environ.get("ANTHROPIC_BASE_URL") or base_url
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise click.ClickException("未设置 GPT_API_KEY")

    client_kwargs = {}
    if base_url:
        if not base_url.rstrip("/").endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"
        client_kwargs["base_url"] = base_url
        client_kwargs["http_client"] = httpx.Client()

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
    result = response.choices[0].message.content or ""
    # 清理 thinking 标签 (DeepSeek/MiniMax 可能返回 <think>...</think>)
    import re as _re
    result = _re.sub(r"<think>.*?</think>", "", result, flags=_re.DOTALL).strip()
    return result


def _call_minimax(system_prompt: str, user_message: str, model: str,
                  temperature: float, max_tokens: int) -> str:
    """MiniMax 官方 API (OpenAI 兼容格式，用 TTS_MINMAX_KEY)。"""
    from openai import OpenAI
    import httpx

    api_key = os.environ.get("TTS_MINMAX_KEY", "")
    if not api_key:
        raise click.ClickException("未设置 TTS_MINMAX_KEY (MiniMax API Key)")

    # 临时清除有问题的代理变量
    proxy_vars = {}
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        if key in os.environ:
            val = os.environ[key]
            if val and val.rstrip("/").endswith("~"):
                proxy_vars[key] = os.environ.pop(key)
    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.minimax.chat/v1",
            http_client=httpx.Client(timeout=httpx.Timeout(600.0, connect=60.0)),
        )
        # M2.7 是 reasoning 模型，reasoning_content 也算在 max_tokens 里
        # 需要给更大的 budget 确保 content 不被截断
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
    finally:
        os.environ.update(proxy_vars)

    if not response.choices:
        # MiniMax 可能返回错误在 base_resp 而非 HTTP status
        raise RuntimeError(f"MiniMax 返回空 choices")

    result = response.choices[0].message.content or ""
    import re as _re
    result = _re.sub(r"<think>.*?</think>", "", result, flags=_re.DOTALL).strip()
    return result


def _call_zhipu(system_prompt: str, user_message: str, model: str,
                temperature: float, max_tokens: int) -> str:
    """智谱 GLM 官方 API (OpenAI 兼容格式)。"""
    from openai import OpenAI
    import httpx

    api_key = os.environ.get("ZHIPU_API_KEY", "")
    if not api_key:
        raise click.ClickException("未设置 ZHIPU_API_KEY")

    # 临时清除所有代理变量（智谱 API 不走本地代理）
    proxy_vars = {}
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        if key in os.environ:
            proxy_vars[key] = os.environ.pop(key)
    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://open.bigmodel.cn/api/paas/v4",
            http_client=httpx.Client(timeout=httpx.Timeout(600.0, connect=60.0)),
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
    finally:
        os.environ.update(proxy_vars)

    result = response.choices[0].message.content or ""
    return result
