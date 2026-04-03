"""TTS 音频词级时间戳对齐：用 mlx-whisper (Apple Silicon GPU) 提取词级时间。

生成 voiceover/word_timing.json，供 render.mjs 生成精确 SRT 字幕。
mlx-whisper 是可选依赖——不可用时 graceful fallback，不阻断流水线。
"""

from __future__ import annotations

import json
from pathlib import Path

import click

# mlx-whisper 模型名映射 (与 lecture2note 一致)
_MLX_MODELS = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "base": "mlx-community/whisper-base-mlx-q4",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large": "mlx-community/whisper-large-v3-mlx",
}


def align_voiceover(voiceover_dir: Path, model_name: str = "base") -> Path | None:
    """用 mlx-whisper 对 TTS 音频做词级对齐。

    Args:
        voiceover_dir: voiceover/ 目录，包含 segments/ 和 timing.json
        model_name: whisper 模型 (tiny/base/small/medium/large)
                    TTS 音频质量高，base 即够用，速度快

    Returns:
        word_timing.json 路径，失败返回 None

    输出格式:
        {
            "1": [{"word": "这是", "start": 0.12, "end": 0.45}, ...],
            "2": [...]
        }
    """
    try:
        import mlx_whisper
    except ImportError:
        click.echo("   ⚠️ mlx-whisper 未安装，跳过词级对齐 (pip install mlx-whisper)")
        return None

    # 读 timing.json 获取 segment ID 列表
    timing_path = voiceover_dir / "timing.json"
    if not timing_path.exists():
        click.echo("   ⚠️ timing.json 不存在，跳过词级对齐")
        return None

    timing = json.loads(timing_path.read_text(encoding="utf-8"))
    segments_dir = voiceover_dir / "segments"
    if not segments_dir.exists():
        click.echo("   ⚠️ segments/ 目录不存在，跳过词级对齐")
        return None

    model_path = _MLX_MODELS.get(model_name, model_name)
    click.echo(f"   🎯 词级对齐 [mlx-whisper {model_name}]...")

    # 临时清除代理（HuggingFace Hub 模型下载可能被 SOCKS 代理阻断）
    import os
    proxy_vars = {}
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                "http_proxy", "https_proxy", "all_proxy"):
        if key in os.environ:
            proxy_vars[key] = os.environ.pop(key)

    word_timing: dict[str, list[dict]] = {}

    try:
        for seg_id in sorted(timing.keys(), key=lambda x: int(x)):
            audio_file = segments_dir / f"seg_{seg_id}.mp3"
            if not audio_file.exists():
                continue

            result = mlx_whisper.transcribe(
                str(audio_file),
                path_or_hf_repo=model_path,
                language="zh",
                verbose=False,
                condition_on_previous_text=False,
                word_timestamps=True,
            )

            # 提取词级时间戳
            words = []
            for seg in result.get("segments", []):
                for w in seg.get("words", []):
                    word_text = w.get("word", "").strip()
                    if word_text:
                        words.append({
                            "word": word_text,
                            "start": round(w["start"], 3),
                            "end": round(w["end"], 3),
                        })

            if words:
                word_timing[seg_id] = words

            click.echo(f"      seg_{seg_id}: {len(words)} 词")
    finally:
        os.environ.update(proxy_vars)

    if not word_timing:
        click.echo("   ⚠️ 未提取到词级时间戳")
        return None

    # 写入 word_timing.json
    output_path = voiceover_dir / "word_timing.json"
    output_path.write_text(
        json.dumps(word_timing, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    total_words = sum(len(ws) for ws in word_timing.values())
    click.echo(f"   ✅ 词级对齐完成: {len(word_timing)} 段, {total_words} 词 → {output_path.name}")
    return output_path
