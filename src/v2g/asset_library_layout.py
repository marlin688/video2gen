"""全局素材库的目录组织与命名规则。"""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

from v2g.asset_store import AssetMeta, AssetStore, VISUAL_TYPES
from v2g.config import Config


_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}
_HASHY_STEM_PREFIXES = ("img_", "wv_", "seg_")
_GENERIC_STEM_RE = re.compile(
    r"^(?:image_overlay|product_ui|terminal|diagram|chart|browser|web_video|screenshot|person|code_editor|text_slide)_[0-9]+$"
)
_CANONICAL_STEM_RE = re.compile(r"^(?P<base>.+)__[0-9a-f]{8,40}$")
_NON_SEMANTIC_SLUGS = frozenset({
    "image_overlay",
    "product_ui",
    "terminal",
    "diagram",
    "chart",
    "browser",
    "web_video",
    "screenshot",
    "person",
    "code_editor",
    "text_slide",
    "background",
    "visual",
    "photo",
    "ui",
    "wechat",
    "mmbiz_qpic_cn",
    "other",
})


def build_library_asset_path(
    cfg: Config,
    asset: AssetMeta,
    *,
    current_path: Path | None = None,
) -> Path:
    """根据素材元数据生成规范化的库内路径。"""
    current = current_path or (Path(asset.file_path) if asset.file_path else Path())
    suffix = current.suffix.lower()
    if not suffix:
        suffix = ".mp4" if asset.visual_type == "web_video" else ".png"
    if asset.visual_type == "web_video" and suffix not in _VIDEO_EXTS:
        suffix = ".mp4"
    if asset.visual_type != "web_video" and suffix not in _IMAGE_EXTS:
        suffix = ".png"

    digest = (asset.asset_hash or _stable_digest(asset, current))[:10]
    semantic_dir = _semantic_dir_slug(asset, current=current)
    filename_slug = _filename_slug(asset, current=current, semantic_dir=semantic_dir)

    root = cfg.output_dir / "asset_library"
    if asset.visual_type == "web_video":
        category_dir = _category_dir_slug(asset, current=current)
        return root / "web_videos" / category_dir / semantic_dir / f"{filename_slug}__{digest}{suffix}"
    visual_dir = _safe_slug(asset.visual_type, fallback="image_overlay")
    return root / "images" / visual_dir / semantic_dir / f"{filename_slug}__{digest}{suffix}"


def reorganize_asset_library(
    cfg: Config,
    *,
    dry_run: bool = False,
    include_seed_dirs: bool = False,
) -> dict:
    """把全局素材库迁移到规范目录，并同步更新 assets.db。"""
    db_path = cfg.output_dir / "assets.db"
    library_root = cfg.output_dir / "asset_library"
    report = {
        "dry_run": dry_run,
        "include_seed_dirs": include_seed_dirs,
        "scanned": 0,
        "moved": 0,
        "updated_only": 0,
        "already_canonical": 0,
        "skipped_missing": 0,
        "skipped_outside_library": 0,
        "skipped_seed_dirs": 0,
        "skipped_no_path": 0,
        "errors": [],
        "changes": [],
    }
    processed_path_redirects: dict[str, str] = {}

    with AssetStore(db_path) as store:
        assets = store.list_assets(reusable_only=False, limit=None)
        for asset in assets:
            report["scanned"] += 1
            if not asset.file_path:
                report["skipped_no_path"] += 1
                continue

            current = _resolve_asset_path(cfg, asset.file_path)

            redirected = processed_path_redirects.get(str(current))
            if redirected:
                if not dry_run:
                    store.update_asset(asset.clip_id, file_path=redirected)
                report["updated_only"] += 1
                report["changes"].append(
                    {
                        "asset_id": asset.clip_id,
                        "action": "update_path",
                        "from": str(current),
                        "to": redirected,
                    }
                )
                continue

            if not current.exists():
                report["skipped_missing"] += 1
                continue
            if not current.is_relative_to(library_root.resolve()):
                report["skipped_outside_library"] += 1
                continue
            if current.name.startswith("."):
                report["skipped_outside_library"] += 1
                continue
            if not include_seed_dirs and _is_curated_seed_path(library_root, current, asset.visual_type):
                report["skipped_seed_dirs"] += 1
                continue

            target = build_library_asset_path(cfg, asset, current_path=current).resolve()
            if current == target:
                report["already_canonical"] += 1
                continue

            target = _dedupe_target(target, asset.clip_id)
            change = {
                "asset_id": asset.clip_id,
                "from": str(current),
                "to": str(target),
            }

            if dry_run:
                report["changes"].append({"action": "move", **change})
                continue

            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    if _same_content(current, target, asset.asset_hash):
                        processed_path_redirects[str(current)] = str(target)
                        store.update_asset(asset.clip_id, file_path=str(target))
                        report["updated_only"] += 1
                        report["changes"].append({"action": "update_path", **change})
                        continue
                    target = _dedupe_target(target, asset.clip_id, force_clip_suffix=True)
                    target.parent.mkdir(parents=True, exist_ok=True)

                shutil.move(str(current), str(target))
                processed_path_redirects[str(current)] = str(target)
                store.update_asset(asset.clip_id, file_path=str(target))
                report["moved"] += 1
                report["changes"].append({"action": "move", **change})
            except Exception as exc:  # pragma: no cover - defensive
                report["errors"].append(
                    {
                        "asset_id": asset.clip_id,
                        "from": str(current),
                        "to": str(target),
                        "error": str(exc),
                    }
                )

    return report


def prune_missing_asset_records(
    cfg: Config,
    *,
    dry_run: bool = False,
) -> dict:
    """清理 assets.db 中已失效的文件记录。"""
    db_path = cfg.output_dir / "assets.db"
    report = {
        "dry_run": dry_run,
        "scanned": 0,
        "missing": 0,
        "deleted": 0,
        "skipped_no_path": 0,
        "errors": [],
        "changes": [],
    }

    with AssetStore(db_path) as store:
        assets = store.list_assets(reusable_only=False, limit=None)
        for asset in assets:
            report["scanned"] += 1
            if not asset.file_path:
                report["skipped_no_path"] += 1
                continue

            resolved = _resolve_asset_path(cfg, asset.file_path)
            if resolved.exists():
                continue

            report["missing"] += 1
            change = {
                "asset_id": asset.clip_id,
                "file_path": asset.file_path,
                "resolved_path": str(resolved),
            }
            if dry_run:
                report["changes"].append({"action": "delete_record", **change})
                continue

            try:
                deleted = store.delete(asset.clip_id)
            except Exception as exc:  # pragma: no cover - defensive
                report["errors"].append(
                    {
                        "asset_id": asset.clip_id,
                        "file_path": asset.file_path,
                        "error": str(exc),
                    }
                )
                continue

            if deleted:
                report["deleted"] += 1
                report["changes"].append({"action": "delete_record", **change})
            else:
                report["errors"].append(
                    {
                        "asset_id": asset.clip_id,
                        "file_path": asset.file_path,
                        "error": "delete_returned_false",
                    }
                )

    return report


def _category_dir_slug(asset: AssetMeta, *, current: Path) -> str:
    explicit = _safe_slug(asset.library_category, fallback="")
    if explicit:
        return explicit
    if current.parent.name and current.parent.parent.name and current.parent.parent.name not in {"web_videos", "asset_library"}:
        existing = _safe_slug(current.parent.parent.name, fallback="")
        if existing:
            return existing
    candidates = [*asset.scene_tags[:2], *asset.tags[:2]]
    for candidate in candidates:
        slug = _safe_slug(candidate, fallback="")
        if _is_meaningful_slug(slug):
            return slug
    return "general"


def _semantic_dir_slug(asset: AssetMeta, *, current: Path) -> str:
    candidates = [
        asset.semantic_type,
        *asset.entities,
        *asset.scene_tags,
        *asset.tags,
        _fallback_stem(current),
    ]
    for candidate in candidates:
        slug = _safe_slug(candidate, fallback="")
        if _is_meaningful_slug(slug):
            return slug
    return "generic"


def _filename_slug(asset: AssetMeta, *, current: Path, semantic_dir: str) -> str:
    pieces = [
        *asset.entities[:3],
        *asset.scene_tags,
        *asset.product[:1],
        *asset.tags,
        _fallback_stem(current),
    ]
    seen: set[str] = set()
    used_tokens = set(_slug_tokens(semantic_dir))
    slugs: list[str] = []
    for piece in pieces:
        slug = _safe_slug(piece, fallback="")
        if not _is_meaningful_slug(slug) or slug in seen:
            continue
        compact = "_".join(
            token
            for token in _slug_tokens(slug)
            if token not in used_tokens and token not in _NON_SEMANTIC_SLUGS
        )
        compact = compact.strip("_")
        if not _is_meaningful_slug(compact) or compact in seen:
            continue
        seen.add(slug)
        seen.add(compact)
        slugs.append(compact)
        used_tokens.update(_slug_tokens(compact))
        if len(slugs) >= 3 or len("_".join(slugs)) >= 40:
            break
    if not slugs:
        if _is_meaningful_slug(semantic_dir):
            return semantic_dir
        return _safe_slug(asset.visual_type or "asset", fallback="asset")
    return "_".join(slugs)[:48].strip("_") or semantic_dir or "asset"


def _fallback_stem(path: Path) -> str:
    stem = path.stem.strip().lower()
    if not stem:
        return ""
    canonical = _CANONICAL_STEM_RE.match(stem)
    if canonical:
        return ""
    if stem.startswith(_HASHY_STEM_PREFIXES):
        return ""
    if _GENERIC_STEM_RE.match(stem):
        return ""
    if len(stem) >= 16 and all(ch in "0123456789abcdef_-" for ch in stem):
        return ""
    return stem


def _is_meaningful_slug(slug: str) -> bool:
    if not slug:
        return False
    if slug in _NON_SEMANTIC_SLUGS:
        return False
    if not any(ch.isalpha() for ch in slug):
        return False
    if slug.isdigit():
        return False
    if len(slug) <= 2 and not any(ch.isalpha() for ch in slug):
        return False
    return True


def _slug_tokens(slug: str) -> list[str]:
    return [part for part in slug.split("_") if part]


def _stable_digest(asset: AssetMeta, path: Path) -> str:
    seed = "|".join(
        [
            asset.clip_id,
            str(path),
            asset.source_url,
            asset.semantic_type,
        ]
    )
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()


def _safe_slug(value: str | None, *, fallback: str = "generic") -> str:
    text = str(value or "").strip().lower()
    if not text:
        return fallback
    chars: list[str] = []
    prev_sep = False
    for ch in text:
        if ch.isascii() and ch.isalnum():
            chars.append(ch)
            prev_sep = False
        else:
            if not prev_sep:
                chars.append("_")
                prev_sep = True
    slug = "".join(chars).strip("_")
    slug = "_".join(part for part in slug.split("_") if part)
    return slug[:48] or fallback


def _is_curated_seed_path(library_root: Path, current: Path, visual_type: str) -> bool:
    try:
        rel = current.relative_to(library_root.resolve())
    except ValueError:
        return False
    parts = rel.parts
    if len(parts) < 3:
        return False
    top, child = parts[0], parts[1]
    if top == "images" and child not in VISUAL_TYPES:
        return True
    if top == "web_videos" and child.startswith("seed_"):
        return True
    return False


def _resolve_asset_path(cfg: Config, raw_file_path: str) -> Path:
    raw = Path(raw_file_path)
    if raw.is_absolute():
        return raw.resolve()
    if raw.exists():
        return raw.resolve()
    candidate = (cfg.output_dir / raw).resolve()
    if candidate.exists():
        return candidate
    return raw.resolve()


def _dedupe_target(target: Path, clip_id: str, *, force_clip_suffix: bool = False) -> Path:
    if force_clip_suffix or target.exists():
        suffix = target.suffix
        stem = target.stem
        return target.with_name(f"{stem}__{_safe_slug(clip_id, fallback='asset')}{suffix}")
    return target


def _same_content(current: Path, target: Path, expected_hash: str = "") -> bool:
    if not current.exists() or not target.exists():
        return False
    current_hash = expected_hash or _file_hash(current)
    target_hash = _file_hash(target)
    return bool(current_hash and target_hash and current_hash == target_hash)


def _file_hash(path: Path) -> str:
    hasher = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
