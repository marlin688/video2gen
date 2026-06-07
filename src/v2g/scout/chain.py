"""产业链轮动型推文生成器：输入主题 → 4 波结构 + 信息图 JSON。

风格定位是中文 X 上的"AI 产业链拆解派"：
- 第一波/第二波/第三波/现在 四段产业链节奏 + 下一波方向猜测
- 美股大盘 ticker
- 配套信息图结构 + 评论引导 + 风险提示

只走单次 LLM 调用，输出 JSON，再渲染成可读 Markdown。
"""

import json
import re
from datetime import date as date_cls
from pathlib import Path

import click

KNOWN_US_TICKERS: set[str] = {
    # Big tech
    "MSFT", "GOOG", "GOOGL", "META", "AMZN", "AAPL", "NVDA", "TSLA", "NFLX",
    # AI 算力 / 半导体
    "AMD", "AVGO", "ARM", "INTC", "QCOM", "MU", "TSM", "MRVL",
    # 半导体设备
    "LRCX", "AMAT", "KLAC", "ASML",
    # 存储 / 服务器
    "STX", "WDC", "NTAP", "PSTG", "SMCI", "DELL", "HPE", "IBM",
    # 网络
    "CSCO", "JNPR", "ANET", "FFIV",
    # 云 & 数据
    "ORCL", "SNOW", "DDOG", "NET", "MDB", "ESTC", "CRWD", "ZS", "PANW", "FTNT",
    # SaaS & Agent 应用
    "CRM", "NOW", "ADBE", "GTLB", "PATH", "PLTR", "TEAM", "WDAY", "INTU",
    # ETF/指数（少数情况下会用到）
    "SPY", "QQQ", "SMH", "SOXX", "WCLD",
}

# 形如 ticker 的字符串：1-5 个大写字母（允许 .A/.B 等股权类型后缀）
_TICKER_SHAPE = re.compile(r"^[A-Z]{1,5}(?:\.[A-Z])?$")

REQUIRED_DISCLAIMER = "不喊单，只拆逻辑。"

FORBIDDEN_INVESTMENT_PATTERNS: tuple[str, ...] = (
    "建议买入",
    "建议卖出",
    "无脑买",
    "闭眼买",
    "稳赚",
    "必涨",
    "目标价",
    "满仓",
    "梭哈",
)


def _topic_slug(topic: str) -> str:
    slug = re.sub(r"[^\w一-鿿]+", "-", topic)[:30].strip("-")
    return slug.lower() or "chain"


def _resolve_vault(cfg) -> Path:
    p = cfg.obsidian_vault_path
    if p and str(p) not in ("", "."):
        return Path(p)
    return Path("output")


def generate_chain(cfg, topic: str) -> dict | None:
    """调 LLM 生成产业链推文 JSON。失败返回 None。"""
    from v2g.llm import call_llm
    from v2g.scout import _load_prompt
    from v2g.scriptwriter import _extract_json

    system_prompt = _load_prompt("scout_chain.md")
    user_message = f"主题：{topic}\n\n请按系统提示词中的 JSON 格式输出。"

    click.echo("   🤖 LLM 生成产业链推文...")
    raw = call_llm(
        system_prompt,
        user_message,
        cfg.scout_model,
        temperature=0.7,
        max_tokens=4500,
    )

    try:
        data = _extract_json(raw)
    except Exception as e:
        click.echo(f"   ⚠️ JSON 解析失败: {e}")
        return None

    if not _validate_chain(data):
        return None

    data = _enforce_invariants(data, topic)
    blockers = _chain_blockers(data)
    if blockers:
        click.echo("   ⚠️ 产业链推文未通过硬校验:")
        for b in blockers[:8]:
            click.echo(f"      - {b}")
        if len(blockers) > 8:
            click.echo(f"      ... 其余 {len(blockers) - 8} 项省略")
        return None
    return data


def _validate_chain(data: dict) -> bool:
    """4 波结构 + 必要字段校验。"""
    if not isinstance(data, dict):
        click.echo("   ⚠️ 输出不是 JSON 对象")
        return False
    if not data.get("short_tweet") or not data.get("long_tweet"):
        click.echo("   ⚠️ 缺少 short_tweet / long_tweet")
        return False
    info = data.get("infographic")
    if not isinstance(info, dict):
        click.echo("   ⚠️ infographic 字段缺失")
        return False
    waves = info.get("waves")
    if not isinstance(waves, list) or len(waves) != 4:
        click.echo(f"   ⚠️ waves 必须恰好 4 段，当前 {len(waves) if isinstance(waves, list) else 0}")
        return False
    for i, w in enumerate(waves):
        if not isinstance(w, dict):
            click.echo(f"   ⚠️ wave[{i}] 不是 object")
            return False
        if not w.get("label") or not w.get("logic"):
            click.echo(f"   ⚠️ wave[{i}] 缺 label/logic")
            return False
        tickers = w.get("tickers")
        if not isinstance(tickers, list) or not tickers:
            click.echo(f"   ⚠️ wave[{i}] tickers 为空")
            return False
        if not (3 <= len(tickers) <= 5):
            click.echo(f"   ⚠️ wave[{i}] tickers 必须 3-5 个，当前 {len(tickers)}")
            return False
    nexts = info.get("next_candidates")
    if not isinstance(nexts, list) or not (3 <= len(nexts) <= 5):
        click.echo("   ⚠️ next_candidates 必须 3-5 项")
        return False
    return True


def _enforce_invariants(data: dict, topic: str) -> dict:
    """强制 disclaimer + ticker 三档分级 + 跨波重复检测。

    Ticker 三档：
      1) 白名单内 → 通过（`$NVDA`）
      2) 形如 ticker 但不在白名单 → 软警告（`$LRCX ⚠️`），不污染 logic
      3) 完全不像 ticker（含数字/中文/特殊后缀） → 替换为 `$XXX (待核实, 原: ...)`
         并在该 wave 的 logic 末尾加 `（部分代码待核实）`
    """
    data["topic"] = data.get("topic") or topic
    data["disclaimer"] = REQUIRED_DISCLAIMER

    waves = data["infographic"]["waves"]
    broken_any = False
    soft_warn_any = False
    seen_tickers: dict[str, list[int]] = {}  # base ticker → wave indices

    for idx, w in enumerate(waves):
        new_tickers: list[str] = []
        has_broken = False
        for t in w.get("tickers", []):
            sym = t.lstrip("$").strip()
            base = sym.split(".")[0].upper()
            if not sym:
                continue
            sym_upper = sym.upper()
            if base in KNOWN_US_TICKERS:
                new_tickers.append(f"${sym_upper}")
                seen_tickers.setdefault(base, []).append(idx)
            elif _TICKER_SHAPE.match(sym_upper):
                new_tickers.append(f"${sym_upper} ⚠️")
                soft_warn_any = True
                seen_tickers.setdefault(base, []).append(idx)
            else:
                new_tickers.append(f"$XXX (待核实, 原: {t})")
                has_broken = True
        w["tickers"] = new_tickers
        if has_broken:
            broken_any = True
            w["logic"] = (w.get("logic", "") + "（部分代码待核实）").strip()

    # 跨波重复检测（只警告，不修复——重选 ticker 不是代码该做的事）
    dups = [(tk, idxs) for tk, idxs in seen_tickers.items() if len(idxs) >= 2]
    if dups:
        click.echo(
            "   ⚠️ 跨波重复 ticker: "
            + ", ".join(f"${tk} (波 {','.join(str(i+1) for i in idxs)})" for tk, idxs in dups)
        )

    # 长推必须包含 disclaimer
    long_t = data.get("long_tweet", "").rstrip()
    if REQUIRED_DISCLAIMER not in long_t:
        data["long_tweet"] = long_t + "\n\n" + REQUIRED_DISCLAIMER

    if broken_any:
        click.echo("   ⚠️ 部分 ticker 形态异常，已替换为待核实占位")
    if soft_warn_any:
        click.echo("   ℹ️ 部分 ticker 非白名单内（形态正常，已加 ⚠️ 让你复核）")
    return data


def _normalize_ticker_token(raw: str) -> str:
    token = str(raw or "").lstrip("$").replace("⚠️", "").strip().upper()
    token = token.split()[0] if token else ""
    return token.split(".")[0]


def _chain_blockers(data: dict) -> list[str]:
    """自动发布前的硬校验，返回阻断原因。"""
    blockers: list[str] = []
    info = data.get("infographic") or {}
    waves = info.get("waves") or []
    seen: dict[str, int] = {}

    for idx, wave in enumerate(waves, start=1):
        tickers = wave.get("tickers") or []
        if not (3 <= len(tickers) <= 5):
            blockers.append(f"第 {idx} 波 ticker 数量必须 3-5 个，当前 {len(tickers)}")
        for raw in tickers:
            raw_text = str(raw or "")
            sym = _normalize_ticker_token(raw_text)
            if not sym:
                blockers.append(f"第 {idx} 波存在空 ticker")
                continue
            if "XXX" in sym or "待核实" in raw_text or "⚠️" in raw_text:
                blockers.append(f"第 {idx} 波 ticker 需要人工复核: {raw_text}")
            if sym in seen:
                blockers.append(f"ticker ${sym} 同时出现在第 {seen[sym]} 波和第 {idx} 波")
            seen[sym] = idx

    text_parts = [
        str(data.get("short_tweet") or ""),
        str(data.get("long_tweet") or ""),
        str(info.get("bottom_line") or ""),
    ]
    for wave in waves:
        text_parts.append(str(wave.get("logic") or ""))
    joined = "\n".join(text_parts)
    for pat in FORBIDDEN_INVESTMENT_PATTERNS:
        if pat in joined:
            blockers.append(f"含投资建议/喊单风险表达: {pat}")

    short_tweet = str(data.get("short_tweet") or "")
    long_tweet = str(data.get("long_tweet") or "")
    if len(short_tweet) > 180:
        blockers.append(f"short_tweet 过长: {len(short_tweet)} 字符")
    if len(long_tweet) > 1200:
        blockers.append(f"long_tweet 过长: {len(long_tweet)} 字符")

    if REQUIRED_DISCLAIMER not in str(data.get("long_tweet") or ""):
        blockers.append(f"long_tweet 缺少免责声明: {REQUIRED_DISCLAIMER}")

    nexts = info.get("next_candidates") or []
    if not (3 <= len(nexts) <= 5):
        blockers.append(f"next_candidates 必须 3-5 项，当前 {len(nexts)}")

    return blockers


def render_chain_md(today: date_cls, data: dict) -> str:
    """JSON → 人类可读 Markdown。"""
    topic = data.get("topic", "")
    info = data.get("infographic", {})

    lines = [
        "---",
        f"date: {today}",
        f"topic: {topic}",
        "type: chain-narrative",
        "tags: [twitter, chain, industry]",
        "---",
        "",
        f"# 产业链推文 — {topic}",
        "",
        "## 一、短推版",
        "",
        "```",
        (data.get("short_tweet") or "").strip(),
        "```",
        "",
        "## 二、长推版（X Premium）",
        "",
        (data.get("long_tweet") or "").strip(),
        "",
        "## 三、信息图结构",
        "",
        f"**主标题**: {info.get('title', '')}",
        f"**副标题**: {info.get('subtitle', '')}",
        "",
    ]
    for w in info.get("waves", []):
        tickers = "  ".join(w.get("tickers", []))
        lines.append(f"### {w.get('label', '')}")
        lines.append(f"`{tickers}`")
        lines.append(f"逻辑: {w.get('logic', '')}")
        lines.append("")

    lines.append("### 下一波，可能轮到")
    for i, n in enumerate(info.get("next_candidates", []), 1):
        lines.append(f"{i}. {n}")
    lines.append("")

    if info.get("bottom_line"):
        lines.append(f"**底部金句**: {info['bottom_line']}")
        lines.append("")

    lines += [
        "## 四、评论区引导",
        "",
        f"> {data.get('comment_starter', '')}",
        "",
        "## 五、风险提示 / 签名",
        "",
        f"_{data.get('disclaimer', REQUIRED_DISCLAIMER)}_",
        "",
    ]
    return "\n".join(lines)


def _write_outputs(vault: Path, today: date_cls, topic: str, data: dict) -> tuple[Path, Path]:
    slug = _topic_slug(topic)
    base = vault / "scout" / "chain"
    base.mkdir(parents=True, exist_ok=True)

    md_path = base / f"{today}-{slug}-chain.md"
    json_path = base / f"{today}-{slug}-chain.json"

    md_path.write_text(render_chain_md(today, data), encoding="utf-8")
    json_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return md_path, json_path


def run_chain(cfg, topic: str, today: date_cls | None = None) -> Path | None:
    """产业链推文主流程。"""
    today = today or date_cls.today()
    if not topic or not topic.strip():
        click.echo("   ⚠️ 主题不能为空")
        return None

    click.echo(f"📊 产业链推文 — {topic}")

    data = generate_chain(cfg, topic.strip())
    if data is None:
        return None

    vault = _resolve_vault(cfg)
    md_path, json_path = _write_outputs(vault, today, topic.strip(), data)
    click.echo(f"   📝 Markdown: {md_path}")
    click.echo(f"   📦 JSON:     {json_path}")
    return md_path
