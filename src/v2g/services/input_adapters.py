"""Normalize external inputs into a small set of reusable source types."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi"}
TEXT_EXTS = {".srt", ".md", ".txt"}


@dataclass(frozen=True)
class SourceInput:
    raw: str
    kind: str
    path: Path | None = None
    url: str | None = None
    video_id: str = ""

    @property
    def is_local(self) -> bool:
        return self.path is not None

    @property
    def display_name(self) -> str:
        if self.path:
            return self.path.name
        return self.url or self.raw

    @property
    def stable_id(self) -> str:
        if self.kind == "youtube":
            return self.video_id
        if self.kind == "local_video" and self.path:
            stem = re.sub(r"[^a-z0-9]+", "-", self.path.stem.lower()).strip("-")
            digest = hashlib.sha1(str(self.path.resolve()).encode("utf-8")).hexdigest()[:8]
            return f"{stem or 'video'}-{digest}"
        if self.path:
            stem = re.sub(r"[^a-z0-9]+", "-", self.path.stem.lower()).strip("-")
            return stem or "source"
        digest = hashlib.sha1(self.raw.encode("utf-8")).hexdigest()[:8]
        return f"source-{digest}"

    @property
    def readable_path(self) -> Path | None:
        if self.kind == "local_text":
            return self.path
        if self.kind == "local_video" and self.path:
            return find_local_video_companion(self.path)
        return None


def resolve_source_input(raw: str) -> SourceInput:
    value = raw.strip()
    path = Path(value)
    if path.exists():
        resolved = path.resolve()
        suffix = resolved.suffix.lower()
        if suffix in VIDEO_EXTS:
            return SourceInput(raw=raw, kind="local_video", path=resolved)
        if suffix in TEXT_EXTS:
            return SourceInput(raw=raw, kind="local_text", path=resolved)

    youtube_id = extract_youtube_id(value)
    if youtube_id:
        return SourceInput(
            raw=raw,
            kind="youtube",
            url=build_youtube_url(youtube_id),
            video_id=youtube_id,
        )

    if value.startswith(("http://", "https://")):
        return SourceInput(raw=raw, kind="url", url=value)

    return SourceInput(raw=raw, kind="unknown")


def find_local_video_companion(video_path: Path) -> Path | None:
    """Locate a readable sidecar file for a local video."""
    zh_srt, en_srt = find_local_video_subtitles(video_path)
    if zh_srt:
        return zh_srt
    if en_srt:
        return en_srt

    candidates = [
        video_path.with_suffix(".md"),
        video_path.with_suffix(".txt"),
        video_path.with_name("notes.md"),
        video_path.with_name("transcript.txt"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def find_local_video_subtitles(video_path: Path) -> tuple[Path | None, Path | None]:
    zh_candidates = [
        video_path.with_name("subtitle_zh.srt"),
        video_path.with_name(f"{video_path.stem}.zh.srt"),
        video_path.with_name(f"{video_path.stem}.cn.srt"),
    ]
    en_candidates = [
        video_path.with_name("subtitle_en.srt"),
        video_path.with_name(f"{video_path.stem}.en.srt"),
    ]

    zh_path = next((candidate.resolve() for candidate in zh_candidates if candidate.exists()), None)
    en_path = next((candidate.resolve() for candidate in en_candidates if candidate.exists()), None)

    if zh_path and en_path and zh_path == en_path:
        en_path = None
    return zh_path, en_path


def extract_youtube_id(value: str) -> str:
    if re.match(r"^[\w-]{11}$", value):
        return value
    patterns = [
        r"(?:v=|youtu\.be/|embed/)([^&?/]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, value)
        if match:
            return match.group(1)
    return ""


def build_youtube_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"
