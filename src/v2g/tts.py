"""Stage 4: TTS 中文语音合成 (支持 edge-tts / MiniMax Speech / GPT-SoVITS)。"""

import asyncio
import json
import os
import subprocess
from pathlib import Path

import click
import requests

from v2g.config import Config
from v2g.checkpoint import PipelineState


def _get_ffprobe() -> str:
    """获取 ffprobe 路径。"""
    try:
        import imageio_ffmpeg
        probe = Path(imageio_ffmpeg.get_ffmpeg_exe()).parent / "ffprobe"
        if probe.exists():
            return str(probe)
    except ImportError:
        pass
    return "ffprobe"


def _get_ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def _get_duration(audio_path: Path) -> float:
    """用 ffprobe 获取音频时长（秒）。"""
    result = subprocess.run(
        [_get_ffprobe(), "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True, timeout=10,
    )
    return float(result.stdout.strip())


# ─── edge-tts 引擎 ───

async def _generate_segment_edge(text: str, output_path: Path, voice: str, rate: str):
    """edge-tts: 免费 Microsoft TTS。"""
    import edge_tts

    proxy = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY") or os.environ.get("http_proxy") or os.environ.get("HTTP_PROXY")
    communicate = edge_tts.Communicate(text, voice, rate=rate, proxy=proxy)
    await communicate.save(str(output_path))


# ─── MiniMax Speech 引擎 ───

MINIMAX_TTS_URL = "https://api.minimaxi.com/v1/t2a_v2"

# 默认中文男声 (可在 .env 中用 TTS_MINIMAX_VOICE_ID 覆盖)
MINIMAX_DEFAULT_VOICE = "male-qn-qingse"


def _generate_segment_minimax(text: str, output_path: Path, voice_id: str, speed: float = 1.0):
    """MiniMax Speech: 高质量中文 TTS。"""
    api_key = os.environ.get("TTS_MINMAX_KEY", "")
    if not api_key:
        raise RuntimeError("未设置 TTS_MINMAX_KEY")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "speech-2.8-hd",
        "text": text,
        "stream": False,
        "voice_setting": {
            "voice_id": voice_id,
            "speed": speed,
            "vol": 1,
            "pitch": 0,
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
            "channel": 1,
        },
    }

    resp = requests.post(MINIMAX_TTS_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    result = resp.json()

    # 检查 API 错误
    if result.get("base_resp", {}).get("status_code", 0) != 0:
        err_msg = result.get("base_resp", {}).get("status_msg", "未知错误")
        raise RuntimeError(f"MiniMax TTS 错误: {err_msg}")

    # 音频数据为 hex 编码
    audio_hex = result.get("data", {}).get("audio", "")
    if not audio_hex:
        raise RuntimeError("MiniMax TTS 返回空音频")

    audio_bytes = bytes.fromhex(audio_hex)
    output_path.write_bytes(audio_bytes)


# ─── GPT-SoVITS 引擎 ───

SOVITS_DEFAULT_URL = "http://127.0.0.1:9880"


def _generate_segment_sovits(
    text: str,
    output_path: Path,
    server_url: str = "",
    ref_audio: str = "",
    ref_text: str = "",
    text_lang: str = "zh",
    speed: float = 1.0,
):
    """GPT-SoVITS: 开源声音克隆 TTS，本地推理。

    需要先启动 GPT-SoVITS API 服务器:
        python api_v2.py
    """
    url = (server_url or os.environ.get("TTS_SOVITS_URL", SOVITS_DEFAULT_URL)).rstrip("/")
    ref_audio = ref_audio or os.environ.get("TTS_SOVITS_REF_AUDIO", "")
    ref_text = ref_text or os.environ.get("TTS_SOVITS_REF_TEXT", "")

    if not ref_audio:
        raise RuntimeError(
            "GPT-SoVITS 需要参考音频，请设置 TTS_SOVITS_REF_AUDIO=/path/to/ref.wav"
        )

    payload = {
        "text": text,
        "text_lang": text_lang,
        "ref_audio_path": ref_audio,
        "prompt_text": ref_text,
        "prompt_lang": text_lang,
        "text_split_method": "cut5",
        "speed_factor": speed,
        "streaming_mode": False,
        "media_type": "wav",
    }

    resp = requests.post(f"{url}/tts", json=payload, timeout=120)

    # API 返回错误时是 JSON，正常时是音频二进制
    content_type = resp.headers.get("Content-Type", "")
    if resp.status_code != 200 or "json" in content_type:
        try:
            err = resp.json()
            raise RuntimeError(f"GPT-SoVITS 错误: {err.get('message', err)}")
        except ValueError:
            raise RuntimeError(f"GPT-SoVITS HTTP {resp.status_code}: {resp.text[:200]}")

    # GPT-SoVITS 输出 WAV，转为 MP3（与管线其他部分一致）
    wav_tmp = output_path.with_suffix(".wav")
    wav_tmp.write_bytes(resp.content)
    subprocess.run(
        [_get_ffmpeg_exe(), "-y", "-i", str(wav_tmp),
         "-c:a", "libmp3lame", "-q:a", "2", str(output_path)],
        capture_output=True, text=True, timeout=30,
    )
    wav_tmp.unlink(missing_ok=True)


def _generate_silence(output_path: Path, duration_sec: float):
    """生成指定时长的静音 MP3 文件。"""
    subprocess.run(
        [_get_ffmpeg_exe(), "-y", "-f", "lavfi",
         "-i", f"anullsrc=r=44100:cl=mono",
         "-t", str(duration_sec),
         "-q:a", "9", "-acodec", "libmp3lame",
         str(output_path)],
        capture_output=True, text=True, timeout=30,
    )


def _concat_segments(segment_files: list[Path], output_path: Path, gap_sec: float = 0.0):
    """用 FFmpeg concat 合并所有 segment 音频，段间可插入静音。"""
    silence_file = None
    if gap_sec > 0:
        silence_file = output_path.parent / "silence.mp3"
        _generate_silence(silence_file, gap_sec)

    list_file = output_path.parent / "concat_list.txt"
    with open(list_file, "w") as f:
        for i, seg_file in enumerate(segment_files):
            f.write(f"file '{seg_file.resolve()}'\n")
            if silence_file and i < len(segment_files) - 1:
                f.write(f"file '{silence_file.resolve()}'\n")

    subprocess.run(
        [_get_ffmpeg_exe(), "-y", "-f", "concat", "-safe", "0",
         "-i", str(list_file), "-c:a", "libmp3lame", "-q:a", "2",
         str(output_path)],
        capture_output=True, text=True, timeout=300,
    )
    list_file.unlink(missing_ok=True)
    if silence_file:
        silence_file.unlink(missing_ok=True)


def _detect_tts_engine() -> str:
    """检测使用哪个 TTS 引擎: edge / minimax / sovits。

    默认 edge（免费），设置 TTS_ENGINE=minimax 或 sovits 切换。
    """
    engine = os.environ.get("TTS_ENGINE", "").lower()
    if engine in ("minimax", "edge", "sovits"):
        return engine
    return "edge"


def _parse_rate_to_speed(rate: str) -> float:
    """将 edge-tts 格式的 rate (如 '+5%') 转换为 MiniMax speed (0.5-2.0)。"""
    try:
        pct = int(rate.replace("%", "").replace("+", ""))
        return max(0.5, min(2.0, 1.0 + pct / 100))
    except (ValueError, AttributeError):
        return 1.0


def run_tts(cfg: Config, video_id: str, voice: str, rate: str, force: bool = False) -> PipelineState:
    """执行 Stage 4: TTS 配音。"""
    state = PipelineState.load(cfg.output_dir, video_id)
    if not state.script_reviewed:
        raise click.ClickException("脚本尚未审核，请先运行 v2g review")

    output_dir = cfg.output_dir / video_id
    voiceover_dir = output_dir / "voiceover"

    if state.tts_done:
        click.echo("⏭️  TTS 已完成，跳过")
        # 自愈：即使 TTS 已完成，若缺少 word_timing.json 仍尝试补齐词级对齐
        if not (voiceover_dir / "word_timing.json").exists():
            click.echo("   🔁 缺少 word_timing.json，自动补齐词级对齐")
            try:
                from v2g.subtitle import align_voiceover
                align_voiceover(voiceover_dir)
            except Exception as e:
                click.echo(f"   ⚠️ 词级对齐失败 (非致命): {e}")
                from v2g.cost import get_tracker
                get_tracker().record_degradation("subtitle", "mlx-whisper", "char-split", str(e))
        return state

    segments_dir = voiceover_dir / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)

    # 读取脚本
    script_path = Path(state.script_json)
    if not script_path.exists():
        raise click.ClickException(f"脚本不存在: {script_path}")
    script_data = json.loads(script_path.read_text(encoding="utf-8"))

    # 硬门禁：结构错误 / 空 narration_zh 不允许继续 TTS
    from v2g.schema import collect_script_blockers
    blockers = collect_script_blockers(script_data, require_narration=True)
    if blockers:
        click.echo("❌ 脚本结构校验失败（已阻断 TTS）:")
        for i, err in enumerate(blockers[:10], start=1):
            click.echo(f"   {i}. {err}")
        if len(blockers) > 10:
            click.echo(f"   ... 其余 {len(blockers) - 10} 项省略")

        if not force:
            raise click.ClickException(
                "请先修复 script.json 后再运行 tts；如需跳过可加 --force"
            )
        click.echo("⚠️  已使用 --force，继续执行 TTS")

    segments = script_data.get("segments", [])
    timing = {}
    segment_files = []

    # 段间静音时长（秒），通过环境变量配置
    gap_sec = float(os.environ.get("TTS_SEGMENT_GAP", "0.5"))

    engine = _detect_tts_engine()

    if engine == "sovits":
        sovits_url = os.environ.get("TTS_SOVITS_URL", SOVITS_DEFAULT_URL)
        sovits_ref = os.environ.get("TTS_SOVITS_REF_AUDIO", "")
        sovits_ref_text = os.environ.get("TTS_SOVITS_REF_TEXT", "")
        sovits_speed = _parse_rate_to_speed(rate)
        ref_name = Path(sovits_ref).name if sovits_ref else "未设置"
        click.echo(f"🎙️ TTS 配音 [GPT-SoVITS] (参考: {ref_name}, 语速: {sovits_speed})")
    elif engine == "minimax":
        minimax_voice = os.environ.get("TTS_MINIMAX_VOICE_ID", MINIMAX_DEFAULT_VOICE)
        minimax_speed = _parse_rate_to_speed(rate)
        click.echo(f"🎙️ TTS 配音 [MiniMax Speech] (音色: {minimax_voice}, 语速: {minimax_speed})")
    else:
        click.echo(f"🎙️ TTS 配音 [edge-tts] (声音: {voice}, 语速: {rate})")

    for seg in segments:
        seg_id = seg.get("id", 0)
        narration = seg.get("narration_zh", "").strip()
        if not narration:
            continue

        seg_file = segments_dir / f"seg_{seg_id}.mp3"
        click.echo(f"   Segment {seg_id}: {narration[:30]}...")

        try:
            if engine == "sovits":
                _generate_segment_sovits(
                    narration, seg_file,
                    server_url=sovits_url,
                    ref_audio=sovits_ref,
                    ref_text=sovits_ref_text,
                    speed=sovits_speed,
                )
            elif engine == "minimax":
                _generate_segment_minimax(narration, seg_file, minimax_voice, minimax_speed)
            else:
                asyncio.run(_generate_segment_edge(narration, seg_file, voice, rate))

            # 记录 TTS 字符消耗
            from v2g.cost import get_tracker
            get_tracker().record_tts(len(narration), engine)

            duration = _get_duration(seg_file)
            timing[str(seg_id)] = {
                "file": str(seg_file),
                "duration": duration,
                "text_length": len(narration),
                "gap_after": gap_sec,
            }
            segment_files.append(seg_file)
            click.echo(f"   ✅ {duration:.1f}s")
        except Exception as e:
            click.echo(f"   ❌ Segment {seg_id} 失败: {e}")
            state.last_error = f"TTS segment {seg_id} 失败: {e}"
            state.save(cfg.output_dir)
            raise click.ClickException(state.last_error)

    # 最后一段不加静音
    if timing:
        last_key = str(segments[-1].get("id", 0))
        if last_key in timing:
            timing[last_key]["gap_after"] = 0

    # 保存时长信息
    timing_path = voiceover_dir / "timing.json"
    timing_path.write_text(json.dumps(timing, ensure_ascii=False, indent=2), encoding="utf-8")
    state.voiceover_timing = str(timing_path)

    # 合并音频
    if segment_files:
        voiceover_path = voiceover_dir / "full.mp3"
        click.echo(f"   🔗 合并音频 (段间静音: {gap_sec}s)...")
        _concat_segments(segment_files, voiceover_path, gap_sec=gap_sec)
        total_duration = sum(t["duration"] for t in timing.values())
        click.echo(f"   ✅ 总时长: {total_duration:.1f}s")
        state.voiceover = str(voiceover_path)

    state.tts_done = True
    state.last_error = ""
    state.save(cfg.output_dir)

    # 词级时间戳对齐（可选，mlx-whisper 未安装时跳过）
    try:
        from v2g.subtitle import align_voiceover
        align_voiceover(voiceover_dir)
    except Exception as e:
        click.echo(f"   ⚠️ 词级对齐失败 (非致命): {e}")
        from v2g.cost import get_tracker
        get_tracker().record_degradation("subtitle", "mlx-whisper", "char-split", str(e))

    return state
