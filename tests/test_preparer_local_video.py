from pathlib import Path

import click

from v2g.config import Config
from v2g.preparer import run_prepare


def test_local_video_prepare_requires_explicitly_named_subtitles(tmp_path: Path):
    video_path = tmp_path / "demo.mp4"
    bare_subtitle = tmp_path / "demo.srt"
    video_path.write_bytes(b"video")
    bare_subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello", encoding="utf-8")

    cfg = Config(sources_dir=tmp_path / "sources", output_dir=tmp_path / "output")

    try:
        run_prepare(cfg, str(video_path))
    except click.ClickException as exc:
        assert "subtitle_zh.srt" in str(exc)
        assert "subtitle_en.srt" in str(exc)
    else:
        raise AssertionError("Expected local prepare to fail without explicitly named subtitles")


def test_local_video_prepare_uses_staged_project_path(tmp_path: Path):
    video_path = tmp_path / "demo.mp4"
    zh_subtitle = tmp_path / "subtitle_zh.srt"
    video_path.write_bytes(b"video")
    zh_subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\n你好", encoding="utf-8")

    cfg = Config(sources_dir=tmp_path / "sources", output_dir=tmp_path / "output")
    state = run_prepare(cfg, str(video_path))

    assert state.subtitled is True
    assert state.downloaded is True
    assert Path(state.source_video).parent == (tmp_path / "sources" / state.video_id)
