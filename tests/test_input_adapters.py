from pathlib import Path

from v2g.services.input_adapters import (
    build_youtube_url,
    resolve_source_input,
)


def test_resolve_local_video_prefers_sidecar_subtitle(tmp_path: Path):
    video_path = tmp_path / "demo.mp4"
    subtitle_path = tmp_path / "demo.zh.srt"
    video_path.write_bytes(b"video")
    subtitle_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello", encoding="utf-8")

    source = resolve_source_input(str(video_path))

    assert source.kind == "local_video"
    assert source.readable_path == subtitle_path.resolve()
    assert source.stable_id.startswith("demo-")


def test_bare_srt_is_not_auto_classified_as_known_language(tmp_path: Path):
    video_path = tmp_path / "demo.mp4"
    subtitle_path = tmp_path / "demo.srt"
    video_path.write_bytes(b"video")
    subtitle_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello", encoding="utf-8")

    source = resolve_source_input(str(video_path))

    assert source.kind == "local_video"
    assert source.readable_path is None


def test_resolve_youtube_input_normalizes_url():
    source = resolve_source_input("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert source.kind == "youtube"
    assert source.video_id == "dQw4w9WgXcQ"
    assert source.url == build_youtube_url("dQw4w9WgXcQ")


def test_resolve_local_text_file(tmp_path: Path):
    note_path = tmp_path / "notes.md"
    note_path.write_text("# hi", encoding="utf-8")

    source = resolve_source_input(str(note_path))

    assert source.kind == "local_text"
    assert source.readable_path == note_path.resolve()
