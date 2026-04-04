"""流水线级别的成本追踪器：记录每次 LLM/TTS 调用的 token 消耗。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict

import click


class BudgetExceeded(Exception):
    """总 token 用量超出 V2G_MAX_TOKENS 上限。"""


@dataclass
class LLMCallRecord:
    model: str
    input_tokens: int
    output_tokens: int
    stage: str = ""  # "script" | "agent" | "slides" | "quality_gate" ...


@dataclass
class CostTracker:
    """流水线级别的成本追踪器（进程内单例）。

    用法：
        from v2g.cost import get_tracker
        get_tracker().record_llm("claude-sonnet-...", 1000, 500, "script")
    """

    llm_calls: list[dict] = field(default_factory=list)
    tts_chars: int = 0
    tts_engine: str = ""
    degradations: list[dict] = field(default_factory=list)

    def record_llm(self, model: str, input_tokens: int, output_tokens: int,
                   stage: str = ""):
        """记录一次 LLM 调用的 token 消耗，超限时抛出 BudgetExceeded。"""
        self.llm_calls.append(asdict(LLMCallRecord(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            stage=stage,
        )))
        self._check_budget()

    def record_tts(self, chars: int, engine: str):
        """记录 TTS 生成的字符消耗。"""
        self.tts_chars += chars
        self.tts_engine = engine

    def record_degradation(self, stage: str, from_: str, to: str, reason: str):
        """记录一次降级事件（保存到 checkpoint.json 供事后追溯）。"""
        self.degradations.append({
            "stage": stage,
            "from": from_,
            "to": to,
            "reason": reason,
        })

    def total_tokens(self) -> int:
        """总 token 用量（input + output）。"""
        return sum(c["input_tokens"] + c["output_tokens"] for c in self.llm_calls)

    def _check_budget(self):
        """检查是否超出 V2G_MAX_TOKENS 上限。"""
        max_tokens = int(os.environ.get("V2G_MAX_TOKENS", "0"))
        if max_tokens <= 0:
            return
        total = self.total_tokens()
        if total > max_tokens:
            raise BudgetExceeded(
                f"总 token 用量 {total:,} 超出上限 {max_tokens:,} (V2G_MAX_TOKENS)。"
                f"已完成 {len(self.llm_calls)} 次 LLM 调用。"
            )

    def summary(self) -> dict:
        """返回汇总统计。"""
        by_model: dict[str, dict] = {}
        for c in self.llm_calls:
            m = c["model"]
            if m not in by_model:
                by_model[m] = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
            by_model[m]["input_tokens"] += c["input_tokens"]
            by_model[m]["output_tokens"] += c["output_tokens"]
            by_model[m]["calls"] += 1

        total_input = sum(v["input_tokens"] for v in by_model.values())
        total_output = sum(v["output_tokens"] for v in by_model.values())

        return {
            "llm_by_model": by_model,
            "llm_total_calls": len(self.llm_calls),
            "llm_total_input_tokens": total_input,
            "llm_total_output_tokens": total_output,
            "tts_chars": self.tts_chars,
            "tts_engine": self.tts_engine,
            "degradations": self.degradations,
        }

    def print_summary(self):
        """终端打印成本摘要。"""
        s = self.summary()
        if s["llm_total_calls"] == 0 and s["tts_chars"] == 0:
            return

        click.echo("\n" + "=" * 50)
        click.echo("💰 成本摘要")
        click.echo("=" * 50)

        if s["llm_total_calls"] > 0:
            click.echo(f"   LLM 调用: {s['llm_total_calls']} 次")
            click.echo(f"   总 token: {s['llm_total_input_tokens']:,} 输入 / "
                        f"{s['llm_total_output_tokens']:,} 输出")
            for model, stats in s["llm_by_model"].items():
                click.echo(f"      {model}: {stats['calls']} 次, "
                            f"{stats['input_tokens']:,} in / "
                            f"{stats['output_tokens']:,} out")

        if s["tts_chars"] > 0:
            click.echo(f"   TTS ({s['tts_engine']}): {s['tts_chars']:,} 字符")

        if s["degradations"]:
            click.echo(f"\n   ⚠️ 降级事件 ({len(s['degradations'])}):")
            for d in s["degradations"]:
                click.echo(f"      [{d['stage']}] {d['from']} → {d['to']}: {d['reason']}")

        click.echo()


# ── 模块级单例 ─────────────────────────────────────────────

_tracker = CostTracker()


def get_tracker() -> CostTracker:
    """获取全局 CostTracker 实例。"""
    return _tracker


def reset_tracker():
    """重置全局 CostTracker（流水线开始时调用）。"""
    global _tracker
    _tracker = CostTracker()
