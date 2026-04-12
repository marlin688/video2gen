"""Style catalog — scan Remotion registry and build LLM-facing component table.

Walks ``remotion-video/src/registry/styles/**/*.tsx`` and parses each
``registry.register({...}, Component)`` call to extract style metadata
(id, schema, name, description, isDefault, tags). The resulting table is
injected into script-generation prompts so the LLM always sees the full
current component library — no more hand-maintained prompt tables drifting
out of sync with the actual registry.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import TypedDict

_REPO_ROOT = Path(__file__).resolve().parents[2]
STYLES_DIR = _REPO_ROOT / "remotion-video" / "src" / "registry" / "styles"

# Schema ordering for prompt output: high-signal / frequently-used first.
_SCHEMA_ORDER = [
    "slide",
    "code-block",
    "diagram",
    "hero-stat",
    "browser",
    "social-card",
    "terminal",
    "image-overlay",
    "web-video",
    "recording",
    "source-clip",
]


class StyleEntry(TypedDict):
    id: str
    schema: str
    name: str
    description: str
    is_default: bool
    tags: list[str]
    file: str
    scene_data_fields: dict[str, str] | None


_REGISTER_RE = re.compile(r"registry\.register\s*\(")


def _extract_scene_data_shape(tsx_text: str) -> dict[str, str] | None:
    """从 .tsx 源码中提取 scene_data 的字段定义。

    支持两种写法：
    1) 内联类型:  ``(data.scene_data || {}) as { field?: type; ... }``
    2) 命名类型:  ``(data.scene_data || {}) as SomeName``
       → 回溯找同文件中 ``interface SomeName { ... }``

    Returns: {"fieldName": "type"} 或 None（没有 scene_data）。
    """
    # Pattern 1: inline cast — ``as {``
    inline_re = re.compile(
        r"""(?:data\.)?scene_data\s*(?:\|\|\s*\{\})\s*\)\s*as\s*\{""",
        re.DOTALL,
    )
    m = inline_re.search(tsx_text)
    if m:
        brace_start = m.end() - 1  # position of '{'
        return _parse_ts_fields_from_brace(tsx_text, brace_start)

    # Pattern 2: named type — ``as TypeName``
    named_re = re.compile(
        r"""(?:data\.)?scene_data\s*(?:\|\|\s*\{\})\s*\)\s*as\s+([A-Z]\w+)""",
    )
    m = named_re.search(tsx_text)
    if m:
        type_name = m.group(1)
        iface_re = re.compile(
            rf"(?:interface|type)\s+{re.escape(type_name)}\s*\{{",
        )
        im = iface_re.search(tsx_text)
        if im:
            brace_start = im.end() - 1
            return _parse_ts_fields_from_brace(tsx_text, brace_start)

    return None


def _parse_ts_fields_from_brace(text: str, brace_start: int) -> dict[str, str]:
    """从 ``{`` 位置开始解析 TypeScript 字段定义到匹配的 ``}``。

    只解析顶层字段（depth=0），跳过嵌套 ``{...}`` 内部的分号。
    """
    end = _skip_string_aware(
        text, brace_start + 1, {"}"},
        track_brace=True, track_bracket=False, track_paren=False,
    )
    body = text[brace_start + 1 : end]

    fields: dict[str, str] = {}
    # 逐字符扫描顶层字段：``name?: type;``
    i = 0
    n = len(body)
    while i < n:
        # 跳过空白和注释
        while i < n and body[i] in " \t\n\r":
            i += 1
        if i >= n:
            break
        # 跳过行注释
        if body[i:i+2] == "//":
            nl = body.find("\n", i)
            i = nl + 1 if nl >= 0 else n
            continue

        # 尝试匹配字段名
        m = re.match(r"(\w+)\??\s*:\s*", body[i:])
        if not m:
            i += 1
            continue

        fname = m.group(1)
        type_start = i + m.end()

        # 从 type_start 开始，找到顶层 ';' 或 '\n' (depth=0 且不在字符串内)
        j = type_start
        depth_b = depth_k = depth_p = 0
        in_str: str | None = None
        escape = False
        while j < n:
            c = body[j]
            if escape:
                escape = False
            elif in_str:
                if c == "\\":
                    escape = True
                elif c == in_str:
                    in_str = None
            elif c in ("'", '"', "`"):
                in_str = c
            elif c == "{":
                depth_b += 1
            elif c == "}":
                if depth_b == 0:
                    break
                depth_b -= 1
            elif c == "[":
                depth_k += 1
            elif c == "]":
                if depth_k == 0:
                    break
                depth_k -= 1
            elif c == "(":
                depth_p += 1
            elif c == ")":
                if depth_p == 0:
                    break
                depth_p -= 1
            elif c == ";" and depth_b == 0 and depth_k == 0 and depth_p == 0:
                break
            j += 1

        ftype = body[type_start:j].strip().rstrip(",;")
        i = j + 1

        # 跳过双下划线开头的内部属性
        if fname.startswith("__"):
            continue
        if ftype:
            fields[fname] = ftype

    return fields if fields else None


def _skip_string_aware(text: str, i: int, stop_chars: set[str],
                       track_brace: bool = True,
                       track_bracket: bool = True,
                       track_paren: bool = True) -> int:
    """Advance ``i`` over ``text`` until a character in ``stop_chars`` is hit
    at zero nesting depth. String literals are treated as opaque."""
    n = len(text)
    depth_b = depth_k = depth_p = 0
    in_str: str | None = None
    escape = False
    while i < n:
        c = text[i]
        if escape:
            escape = False
        elif in_str:
            if c == "\\":
                escape = True
            elif c == in_str:
                in_str = None
        elif c in ("'", '"', "`"):
            in_str = c
        elif track_brace and c == "{":
            depth_b += 1
        elif track_brace and c == "}":
            if depth_b == 0 and "}" in stop_chars:
                return i
            depth_b -= 1
        elif track_bracket and c == "[":
            depth_k += 1
        elif track_bracket and c == "]":
            if depth_k == 0 and "]" in stop_chars:
                return i
            depth_k -= 1
        elif track_paren and c == "(":
            depth_p += 1
        elif track_paren and c == ")":
            if depth_p == 0 and ")" in stop_chars:
                return i
            depth_p -= 1
        elif (c in stop_chars
              and depth_b == 0 and depth_k == 0 and depth_p == 0):
            return i
        i += 1
    return i


def _extract_meta_block(call_body: str) -> str:
    """Given the text inside ``register(...)``, return the first argument —
    the meta object literal ``{...}`` — as a string. Returns "" on failure."""
    i = 0
    n = len(call_body)
    while i < n and call_body[i].isspace():
        i += 1
    if i >= n or call_body[i] != "{":
        return ""
    start = i
    end = _skip_string_aware(call_body, i + 1, {"}"}, track_brace=True,
                             track_bracket=False, track_paren=False)
    if end >= n:
        return ""
    return call_body[start:end + 1]


def _parse_key_value(meta_text: str, key: str) -> str | None:
    """Extract raw value expression for ``key`` from a JS object literal.

    Returns the value text (stripped), or None if the key is not present.
    Commas inside nested strings / arrays / objects are respected.
    """
    # Key must follow either the opening '{' or a ',' at depth 0.
    pattern = re.compile(rf"[{{,]\s*{re.escape(key)}\s*:\s*")
    m = pattern.search(meta_text)
    if not m:
        return None
    start = m.end()
    end = _skip_string_aware(meta_text, start, {",", "}"},
                             track_brace=True, track_bracket=True,
                             track_paren=True)
    return meta_text[start:end].strip()


_STR_LITERAL_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _parse_string_concat(expr: str | None) -> str:
    """Parse one or more ``"..."`` string literals joined with ``+``.

    Chinese descriptions in the registry are stored as literal UTF-8 — we
    do NOT run them through ``unicode_escape`` because that would mangle
    multibyte characters. We do handle the small set of backslash escapes
    that are actually used (``\\"``, ``\\\\``, ``\\n``).
    """
    if not expr:
        return ""
    parts = _STR_LITERAL_RE.findall(expr)
    joined = "".join(parts)
    return (
        joined.replace("\\\\", "\x00")
              .replace('\\"', '"')
              .replace("\\n", "\n")
              .replace("\x00", "\\")
    )


def _parse_tags(expr: str | None) -> list[str]:
    if not expr:
        return []
    m = re.match(r"\[(.*)\]", expr, re.DOTALL)
    inner = m.group(1) if m else expr
    return _STR_LITERAL_RE.findall(inner)


def load_styles(styles_dir: Path = STYLES_DIR) -> list[StyleEntry]:
    """Scan the registry directory and return a sorted list of style entries."""
    results: list[StyleEntry] = []
    if not styles_dir.exists():
        return results

    for tsx in sorted(styles_dir.rglob("*.tsx")):
        try:
            text = tsx.read_text(encoding="utf-8")
        except OSError:
            continue
        for call_match in _REGISTER_RE.finditer(text):
            call_start = call_match.end()
            # Find matching closing ')' of the register(...) call.
            close_idx = _skip_string_aware(text, call_start, {")"},
                                           track_brace=True,
                                           track_bracket=True,
                                           track_paren=True)
            call_body = text[call_start:close_idx]
            meta = _extract_meta_block(call_body)
            if not meta:
                continue
            id_val = _parse_string_concat(_parse_key_value(meta, "id"))
            schema_val = _parse_string_concat(_parse_key_value(meta, "schema"))
            if not id_val or not schema_val:
                continue
            name_val = _parse_string_concat(_parse_key_value(meta, "name"))
            desc_val = _parse_string_concat(_parse_key_value(meta, "description"))
            is_default = (_parse_key_value(meta, "isDefault") or "false").strip() == "true"
            tags_val = _parse_tags(_parse_key_value(meta, "tags"))
            sd_fields = _extract_scene_data_shape(text)

            results.append({
                "id": id_val,
                "schema": schema_val,
                "name": name_val,
                "description": desc_val,
                "is_default": is_default,
                "tags": tags_val,
                "file": str(tsx.relative_to(_REPO_ROOT)) if tsx.is_relative_to(_REPO_ROOT) else str(tsx),
                "scene_data_fields": sd_fields,
            })
    return results


def to_markdown_table(styles: list[StyleEntry], max_desc: int = 140) -> str:
    """Render styles as grouped-by-schema Markdown tables for LLM prompts."""
    by_schema: dict[str, list[StyleEntry]] = defaultdict(list)
    for s in styles:
        by_schema[s["schema"]].append(s)

    ordered_schemas = (
        [s for s in _SCHEMA_ORDER if s in by_schema]
        + sorted(s for s in by_schema if s not in _SCHEMA_ORDER)
    )

    lines: list[str] = []
    for schema in ordered_schemas:
        entries = sorted(
            by_schema[schema],
            key=lambda e: (not e["is_default"], e["id"]),
        )
        lines.append("")
        lines.append(f"**`{schema}` schema** ({len(entries)} 种):")
        lines.append("")
        lines.append("| 组件 ID | 名称 | 适用场景 | 标签 |")
        lines.append("|---------|------|---------|------|")
        for e in entries:
            default_mark = " ⭐" if e["is_default"] else ""
            desc = " ".join(e["description"].split())
            if len(desc) > max_desc:
                desc = desc[:max_desc - 1] + "…"
            tags = ", ".join(e["tags"])
            # 在描述末尾追加 scene_data 字段概要
            sd = e.get("scene_data_fields")
            if sd:
                compact = ", ".join(f"{k}: {v}" for k, v in sd.items())
                desc += f" 【scene_data: {{{compact}}}】"
            lines.append(
                f"| `{e['id']}`{default_mark} | {e['name']} | {desc} | {tags} |"
            )
    return "\n".join(lines).lstrip("\n")


def inject_catalog(
    prompt_text: str,
    placeholder: str = "{{STYLE_CATALOG}}",
    id_prefix: str | None = None,
) -> str:
    """Replace ``placeholder`` in ``prompt_text`` with the generated catalog.

    Args:
        prompt_text: prompt 文本，需要包含 placeholder 才会替换
        placeholder: 占位符，默认 ``{{STYLE_CATALOG}}``
        id_prefix: 可选白名单前缀，只注入 id 以此开头的 style。用于 quality
            profile 限制 LLM 可选组件范围（例如 ``"slide.anthropic-"`` 让
            LLM 只能选品牌片专用场景）。

    No-op when the placeholder is absent or when the registry cannot be
    parsed — the prompt still works, just without the dynamic table.
    """
    if placeholder not in prompt_text:
        return prompt_text
    try:
        styles = load_styles()
        if id_prefix:
            styles = [s for s in styles if s["id"].startswith(id_prefix)]
        if not styles:
            return prompt_text.replace(placeholder, "_（组件注册表为空）_")
        table = to_markdown_table(styles)
    except Exception as exc:  # pragma: no cover — defensive
        return prompt_text.replace(
            placeholder, f"_（组件表加载失败: {exc}）_"
        )
    return prompt_text.replace(placeholder, table)
