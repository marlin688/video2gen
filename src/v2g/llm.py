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


def call_llm(system_prompt: str, user_message: str, model: str,
             temperature: float = 0.3, max_tokens: int = 16000) -> str:
    """统一 LLM 调用接口，根据模型名称自动路由。"""
    if is_gemini_model(model):
        return _call_gemini(system_prompt, user_message, model, temperature, max_tokens)
    if is_gpt_model(model):
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
    text_parts = []
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        for text in stream.text_stream:
            text_parts.append(text)
    result = "".join(text_parts)
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
    return response.choices[0].message.content
