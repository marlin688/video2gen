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


_REGISTER_RE = re.compile(r"registry\.register\s*\(")


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
            results.append({
                "id": id_val,
                "schema": schema_val,
                "name": name_val,
                "description": desc_val,
                "is_default": is_default,
                "tags": tags_val,
                "file": str(tsx.relative_to(_REPO_ROOT)) if tsx.is_relative_to(_REPO_ROOT) else str(tsx),
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
            lines.append(
                f"| `{e['id']}`{default_mark} | {e['name']} | {desc} | {tags} |"
            )
    return "\n".join(lines).lstrip("\n")


def inject_catalog(prompt_text: str, placeholder: str = "{{STYLE_CATALOG}}") -> str:
    """Replace ``placeholder`` in ``prompt_text`` with the generated catalog.

    No-op when the placeholder is absent or when the registry cannot be
    parsed — the prompt still works, just without the dynamic table.
    """
    if placeholder not in prompt_text:
        return prompt_text
    try:
        styles = load_styles()
        if not styles:
            return prompt_text.replace(placeholder, "_（组件注册表为空）_")
        table = to_markdown_table(styles)
    except Exception as exc:  # pragma: no cover — defensive
        return prompt_text.replace(
            placeholder, f"_（组件表加载失败: {exc}）_"
        )
    return prompt_text.replace(placeholder, table)
