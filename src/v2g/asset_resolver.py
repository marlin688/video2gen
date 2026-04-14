"""素材解析阶段：本地素材库优先，未命中时再在线拉取。"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import click

from v2g.asset_store import AssetMeta, AssetStore
from v2g.config import Config
from v2g.image_source import source_image
from v2g.workflow_contract import sync_workflow_contract

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}
_IMAGE_VISUAL_TYPES = {"image_overlay", "screenshot", "product_ui"}


def resolve_project_assets(
    cfg: Config,
    project_id: str,
    *,
    require_cleared_rights: bool = False,
) -> dict:
    """解析 script.json 中的 image/web_video 依赖，返回阶段报告。"""
    project_dir = cfg.output_dir / project_id
    script_path = project_dir / "script.json"
    if not script_path.exists():
        raise FileNotFoundError(f"script.json 不存在: {script_path}")

    sync_workflow_contract(
        project_dir,
        project_id,
        stage="assets_resolve",
        status="start",
        message="开始素材解析（本地优先）",
        extra={"require_cleared_rights": require_cleared_rights},
    )

    script = json.loads(script_path.read_text(encoding="utf-8"))
    segments = script.get("segments", [])
    report = {
        "version": "v3",
        "project_id": project_id,
        "require_cleared_rights": require_cleared_rights,
        "checked_segments": 0,
        "checked_image_segments": 0,
        "checked_web_video_segments": 0,
        "kept_existing": 0,
        "resolved_local": 0,
        "resolved_remote": 0,
        "resolved_local_image": 0,
        "resolved_remote_image": 0,
        "resolved_local_web_video": 0,
        "resolved_remote_web_video": 0,
        "unresolved": 0,
        "unknown_rights_local_hits": 0,
        "records": [],
        "warnings": [],
    }
    unresolved_ids: list[int] = []
    modified = False

    db_path = cfg.output_dir / "assets.db"
    with AssetStore(db_path) as store:
        for seg in segments:
            seg_id = int(seg.get("id") or 0)

            image_content = seg.get("image_content")
            if isinstance(image_content, dict):
                changed = _resolve_image_segment(
                    cfg=cfg,
                    project_dir=project_dir,
                    project_id=project_id,
                    seg=seg,
                    seg_id=seg_id,
                    image_content=image_content,
                    store=store,
                    report=report,
                    unresolved_ids=unresolved_ids,
                    require_cleared_rights=require_cleared_rights,
                )
                modified = modified or changed

            web_video = seg.get("web_video")
            if isinstance(web_video, dict):
                changed = _resolve_web_video_segment(
                    cfg=cfg,
                    project_dir=project_dir,
                    project_id=project_id,
                    seg=seg,
                    seg_id=seg_id,
                    web_video=web_video,
                    store=store,
                    report=report,
                    unresolved_ids=unresolved_ids,
                    require_cleared_rights=require_cleared_rights,
                )
                modified = modified or changed

    if modified:
        script_path.write_text(
            json.dumps(script, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    report["unresolved_segment_ids"] = sorted(set(unresolved_ids))
    if report["unresolved"] > 0:
        report["warnings"].append(
            f"{report['unresolved']} segments unresolved: {report['unresolved_segment_ids']}"
        )
    if report["unknown_rights_local_hits"] > 0:
        report["warnings"].append(
            f"{report['unknown_rights_local_hits']} local hits have rights_status=unknown"
        )

    report_path = project_dir / "asset_resolve_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    sync_workflow_contract(
        project_dir,
        project_id,
        stage="assets_resolve",
        status="ok",
        message="素材解析完成",
        extra={
            "checked": report["checked_segments"],
            "local": report["resolved_local"],
            "remote": report["resolved_remote"],
            "unresolved": report["unresolved"],
            "report": str(report_path.relative_to(project_dir)),
        },
    )
    return report


def _resolve_image_segment(
    *,
    cfg: Config,
    project_dir: Path,
    project_id: str,
    seg: dict,
    seg_id: int,
    image_content: dict,
    store: AssetStore,
    report: dict,
    unresolved_ids: list[int],
    require_cleared_rights: bool,
) -> bool:
    report["checked_segments"] += 1
    report["checked_image_segments"] += 1

    current_path = str(image_content.get("image_path") or "").strip()
    if current_path:
        current_abs = project_dir / current_path
        if current_abs.exists() and _is_image_file(current_abs):
            report["kept_existing"] += 1
            report["records"].append(
                {
                    "segment_id": seg_id,
                    "asset_kind": "image",
                    "decision": "keep_existing",
                    "image_path": current_path,
                }
            )
            return False

        # 旧 path 不可用时清空，避免下游继续读脏路径。
        image_content["image_path"] = ""

    query = _resolve_query(seg, image_content)
    local = _pick_local_asset(
        store,
        query=query,
        require_cleared_rights=require_cleared_rights,
        asset_kind="image",
    )
    if local is not None:
        rel_path = _materialize_to_project(
            asset_path=Path(local.file_path),
            project_dir=project_dir,
            seg_id=seg_id,
            subdir="images",
            prefix="img",
            suffixes=_IMAGE_SUFFIXES,
        )
        image_content["image_path"] = rel_path
        report["resolved_local"] += 1
        report["resolved_local_image"] += 1
        if local.rights_status == "unknown":
            report["unknown_rights_local_hits"] += 1
        report["records"].append(
            {
                "segment_id": seg_id,
                "asset_kind": "image",
                "decision": "resolved_local",
                "asset_id": local.clip_id,
                "asset_file": local.file_path,
                "rights_status": local.rights_status,
                "assigned_path": rel_path,
                "query": query,
            }
        )
        _record_usage(
            store,
            asset_id=local.clip_id,
            project_id=project_id,
            segment_id=seg_id,
            asset_role="image-overlay",
            note="local hit",
        )
        return True

    method = str(image_content.get("source_method") or "").strip()
    if method not in {"screenshot", "search", "generate"}:
        report["unresolved"] += 1
        unresolved_ids.append(seg_id)
        report["records"].append(
            {
                "segment_id": seg_id,
                "asset_kind": "image",
                "decision": "unresolved",
                "reason": "missing_or_invalid_source_method",
                "query": query,
            }
        )
        return bool(current_path)

    source_query = str(image_content.get("source_query") or "").strip() or query
    if not source_query:
        report["unresolved"] += 1
        unresolved_ids.append(seg_id)
        report["records"].append(
            {
                "segment_id": seg_id,
                "asset_kind": "image",
                "decision": "unresolved",
                "reason": "missing_source_query",
            }
        )
        return bool(current_path)

    kwargs = {}
    api_key = _get_image_api_key(method)
    if api_key:
        kwargs["api_key"] = api_key

    click.echo(f"   [{seg_id}] 图片库未命中，在线补图: {method} | {source_query[:60]}")
    remote_path = source_image(
        query=source_query,
        method=method,
        output_dir=project_dir / "images",
        **kwargs,
    )
    if remote_path is None:
        report["unresolved"] += 1
        unresolved_ids.append(seg_id)
        report["records"].append(
            {
                "segment_id": seg_id,
                "asset_kind": "image",
                "decision": "unresolved",
                "reason": "remote_source_failed",
                "method": method,
                "query": source_query,
            }
        )
        return bool(current_path)

    rel_path = str(remote_path.relative_to(project_dir))
    image_content["image_path"] = rel_path
    report["resolved_remote"] += 1
    report["resolved_remote_image"] += 1
    report["records"].append(
        {
            "segment_id": seg_id,
            "asset_kind": "image",
            "decision": "resolved_remote",
            "method": method,
            "query": source_query,
            "assigned_path": rel_path,
        }
    )

    meta = _ingest_remote_image(
        store=store,
        cfg=cfg,
        project_id=project_id,
        seg=seg,
        method=method,
        source_query=source_query,
        local_image_path=remote_path,
    )
    if meta:
        _record_usage(
            store,
            asset_id=meta.clip_id,
            project_id=project_id,
            segment_id=seg_id,
            asset_role="image-overlay",
            note="remote ingest",
        )

    return True


def _resolve_web_video_segment(
    *,
    cfg: Config,
    project_dir: Path,
    project_id: str,
    seg: dict,
    seg_id: int,
    web_video: dict,
    store: AssetStore,
    report: dict,
    unresolved_ids: list[int],
    require_cleared_rights: bool,
) -> bool:
    report["checked_segments"] += 1
    report["checked_web_video_segments"] += 1

    source_url = str(web_video.get("source_url") or "").strip()
    existing = _resolve_existing_web_video_path(project_dir, source_url)
    if existing is not None:
        rel_path = _materialize_to_project(
            asset_path=existing,
            project_dir=project_dir,
            seg_id=seg_id,
            subdir="web_videos",
            prefix="wv",
            suffixes=_VIDEO_SUFFIXES,
        )
        canonical_name = Path(rel_path).name
        changed = web_video.get("source_url") != canonical_name
        web_video["source_url"] = canonical_name

        report["kept_existing"] += 1
        report["records"].append(
            {
                "segment_id": seg_id,
                "asset_kind": "web_video",
                "decision": "keep_existing",
                "source_url": source_url,
                "assigned_path": rel_path,
            }
        )
        return changed

    query = str(web_video.get("search_query") or "").strip() or _resolve_query(seg, web_video)
    local = _pick_local_asset(
        store,
        query=query,
        require_cleared_rights=require_cleared_rights,
        asset_kind="web_video",
    )
    if local is not None:
        rel_path = _materialize_to_project(
            asset_path=Path(local.file_path),
            project_dir=project_dir,
            seg_id=seg_id,
            subdir="web_videos",
            prefix="wv",
            suffixes=_VIDEO_SUFFIXES,
        )
        canonical_name = Path(rel_path).name
        web_video["source_url"] = canonical_name
        report["resolved_local"] += 1
        report["resolved_local_web_video"] += 1
        if local.rights_status == "unknown":
            report["unknown_rights_local_hits"] += 1
        report["records"].append(
            {
                "segment_id": seg_id,
                "asset_kind": "web_video",
                "decision": "resolved_local",
                "asset_id": local.clip_id,
                "asset_file": local.file_path,
                "rights_status": local.rights_status,
                "assigned_path": rel_path,
                "query": query,
            }
        )
        _record_usage(
            store,
            asset_id=local.clip_id,
            project_id=project_id,
            segment_id=seg_id,
            asset_role="web-video",
            note="local hit",
        )
        return True

    remote_path, remote_reason = _download_web_video(
        project_dir=project_dir,
        seg_id=seg_id,
        source_url=source_url,
        search_query=query,
    )
    if remote_path is None:
        report["unresolved"] += 1
        unresolved_ids.append(seg_id)
        report["records"].append(
            {
                "segment_id": seg_id,
                "asset_kind": "web_video",
                "decision": "unresolved",
                "reason": remote_reason,
                "source_url": source_url,
                "query": query,
            }
        )
        return False

    web_video["source_url"] = remote_path.name
    report["resolved_remote"] += 1
    report["resolved_remote_web_video"] += 1
    report["records"].append(
        {
            "segment_id": seg_id,
            "asset_kind": "web_video",
            "decision": "resolved_remote",
            "assigned_path": str(remote_path.relative_to(project_dir)),
            "source_url": source_url,
            "query": query,
            "reason": remote_reason,
        }
    )

    meta = _ingest_remote_web_video(
        store=store,
        cfg=cfg,
        project_id=project_id,
        seg=seg,
        source_url=source_url,
        query=query,
        local_video_path=remote_path,
    )
    if meta:
        _record_usage(
            store,
            asset_id=meta.clip_id,
            project_id=project_id,
            segment_id=seg_id,
            asset_role="web-video",
            note="remote ingest",
        )

    return True


def _resolve_query(seg: dict, payload: dict) -> str:
    parts = [
        str(payload.get("source_query") or "").strip(),
        str(payload.get("search_query") or "").strip(),
        str(payload.get("overlay_text") or "").strip(),
        str(seg.get("narration_zh") or "").strip(),
        str(seg.get("notes") or "").strip(),
    ]
    for p in parts:
        if p:
            return p
    return ""


def _pick_local_asset(
    store: AssetStore,
    *,
    query: str,
    require_cleared_rights: bool,
    asset_kind: str,
) -> AssetMeta | None:
    visual_type = "web_video" if asset_kind == "web_video" else None
    candidates = store.search_local_first(
        query,
        visual_type=visual_type,
        require_cleared_rights=require_cleared_rights,
        allow_possibly_outdated=False,
        limit=12,
    )
    for asset in candidates:
        path = Path(asset.file_path)
        if not path.exists():
            continue
        if asset_kind == "web_video":
            if asset.visual_type != "web_video" and not _is_video_file(path):
                continue
            return asset
        if asset.visual_type not in _IMAGE_VISUAL_TYPES and not _is_image_file(path):
            continue
        return asset
    return None


def _materialize_to_project(
    *,
    asset_path: Path,
    project_dir: Path,
    seg_id: int,
    subdir: str,
    prefix: str,
    suffixes: set[str],
) -> str:
    """将素材落到 output/{project}/{subdir}，返回相对路径。"""
    if asset_path.exists() and asset_path.is_relative_to(project_dir):
        rel = str(asset_path.relative_to(project_dir))
        parts = Path(rel).parts
        if parts and parts[0] == subdir:
            return rel

    target_dir = project_dir / subdir
    target_dir.mkdir(parents=True, exist_ok=True)

    suffix = asset_path.suffix.lower() if asset_path.suffix else ""
    if suffix not in suffixes:
        suffix = ".png" if subdir == "images" else ".mp4"
    digest = hashlib.sha1(str(asset_path).encode("utf-8")).hexdigest()[:10]
    dst = target_dir / f"seg_{seg_id}_{prefix}_{digest}{suffix}"
    if not dst.exists():
        shutil.copy2(asset_path, dst)
    return str(dst.relative_to(project_dir))


def _resolve_existing_web_video_path(project_dir: Path, source_url: str) -> Path | None:
    if not source_url:
        return None

    if _is_http_url(source_url):
        return None

    # 绝对路径
    p = Path(source_url)
    if p.is_absolute() and p.exists() and _is_video_file(p):
        return p

    # 相对 project 路径
    rel = project_dir / source_url
    if rel.exists() and _is_video_file(rel):
        return rel

    # filename 风格（source_url 只存文件名）
    in_web = project_dir / "web_videos" / source_url
    if in_web.exists() and _is_video_file(in_web):
        return in_web

    return None


def _download_web_video(
    *,
    project_dir: Path,
    seg_id: int,
    source_url: str,
    search_query: str,
) -> tuple[Path | None, str]:
    web_dir = project_dir / "web_videos"
    web_dir.mkdir(parents=True, exist_ok=True)

    ytdlp = shutil.which("yt-dlp")
    if not ytdlp:
        return None, "yt_dlp_missing"

    if _is_http_url(source_url):
        target = source_url
        mode = "source_url"
    elif search_query:
        target = f"ytsearch1:{search_query}"
        mode = "search_query"
    else:
        return None, "missing_source_url_and_search_query"

    temp_tpl = web_dir / f"seg_{seg_id}_tmp.%(ext)s"
    cmd = [
        ytdlp,
        target,
        "--no-playlist",
        "--no-progress",
        "--quiet",
        "-f",
        "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format",
        "mp4",
        "-o",
        str(temp_tpl),
    ]

    proc = _run_command(cmd, timeout=480)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip().splitlines()
        short = err[-1][:140] if err else "unknown"
        return None, f"yt_dlp_failed:{short}"

    candidates = sorted(web_dir.glob(f"seg_{seg_id}_tmp*"))
    file_path = next((p for p in candidates if p.suffix.lower() in _VIDEO_SUFFIXES), None)
    if file_path is None:
        return None, "download_missing_output"

    final_path = web_dir / f"seg_{seg_id}.mp4"
    if final_path.exists():
        final_path.unlink()
    if file_path.suffix.lower() != ".mp4":
        shutil.move(str(file_path), str(final_path))
    else:
        file_path.rename(final_path)

    # 清理残留临时文件
    for stale in web_dir.glob(f"seg_{seg_id}_tmp*"):
        if stale.exists():
            stale.unlink(missing_ok=True)

    return final_path, mode


def _run_command(cmd: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _ingest_remote_image(
    *,
    store: AssetStore,
    cfg: Config,
    project_id: str,
    seg: dict,
    method: str,
    source_query: str,
    local_image_path: Path,
) -> AssetMeta | None:
    """把在线补图回灌到全局素材库，供后续项目复用。"""
    library_dir = _asset_library_root(cfg) / "images"
    library_dir.mkdir(parents=True, exist_ok=True)

    file_hash = _compute_file_hash(local_image_path)
    existing = store.get_by_hash(file_hash) if file_hash else None
    if existing is not None:
        return existing

    suffix = local_image_path.suffix.lower() if local_image_path.suffix else ".png"
    if suffix not in _IMAGE_SUFFIXES:
        suffix = ".png"
    digest = file_hash[:16] if file_hash else hashlib.sha1(str(local_image_path).encode("utf-8")).hexdigest()[:16]
    library_name = f"img_{digest}{suffix}"

    library_path = library_dir / library_name
    if not library_path.exists():
        shutil.copy2(local_image_path, library_path)

    clip_id = f"img-{digest[:12]}"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    mood = _infer_mood(seg)
    products = _infer_products(source_query)
    tags = _tokenize_tags(source_query)

    meta = AssetMeta(
        clip_id=clip_id,
        source_video=project_id,
        time_range_start=0.0,
        time_range_end=0.0,
        duration=0.0,
        captured_date=today,
        visual_type="screenshot" if method == "screenshot" else "image_overlay",
        tags=tags,
        product=products,
        mood=mood,
        reusable=True,
        freshness="current",
        file_path=str(library_path),
        notes=f"auto-ingest image from {project_id} segment {seg.get('id', '?')}: {source_query[:120]}",
        source_kind=_method_to_source_kind(method),
        source_url=source_query if method == "screenshot" else "",
        asset_hash=file_hash,
        rights_status="unknown",
        license_type=method,
        license_scope="",
        expires_at="",
    )
    store.insert(meta)
    return meta


def _ingest_remote_web_video(
    *,
    store: AssetStore,
    cfg: Config,
    project_id: str,
    seg: dict,
    source_url: str,
    query: str,
    local_video_path: Path,
) -> AssetMeta | None:
    """把远程下载的视频回灌到全局素材库。"""
    library_dir = _asset_library_root(cfg) / "web_videos"
    library_dir.mkdir(parents=True, exist_ok=True)

    file_hash = _compute_file_hash(local_video_path)
    existing = store.get_by_hash(file_hash) if file_hash else None
    if existing is not None:
        return existing

    digest = file_hash[:16] if file_hash else hashlib.sha1(str(local_video_path).encode("utf-8")).hexdigest()[:16]
    library_name = f"wv_{digest}.mp4"
    library_path = library_dir / library_name
    if not library_path.exists():
        shutil.copy2(local_video_path, library_path)

    clip_id = f"web-{digest[:12]}"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tags = _tokenize_tags(query or source_url)
    products = _infer_products(query or source_url)

    meta = AssetMeta(
        clip_id=clip_id,
        source_video=project_id,
        time_range_start=0.0,
        time_range_end=0.0,
        duration=0.0,
        captured_date=today,
        visual_type="web_video",
        tags=tags,
        product=products,
        mood=_infer_mood(seg),
        reusable=True,
        freshness="current",
        file_path=str(library_path),
        notes=f"auto-ingest web_video from {project_id} segment {seg.get('id', '?')}: {(query or source_url)[:120]}",
        source_kind="search_download" if query else "external",
        source_url=source_url,
        asset_hash=file_hash,
        rights_status="unknown",
        license_type="downloaded_video",
        license_scope="",
        expires_at="",
    )
    store.insert(meta)
    return meta


def _asset_library_root(cfg: Config) -> Path:
    return cfg.output_dir / "asset_library"


def _record_usage(
    store: AssetStore,
    *,
    asset_id: str,
    project_id: str,
    segment_id: int,
    asset_role: str,
    note: str,
) -> None:
    if not asset_id:
        return
    try:
        store.record_usage(
            asset_id=asset_id,
            project_id=project_id,
            video_id=project_id,
            segment_id=segment_id,
            asset_role=asset_role,
            render_version="v2g-resolver-v3",
            resolver_stage="assets_resolve",
            note=note,
        )
    except Exception:
        pass


def _is_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except Exception:
        return False
    return parsed.scheme in {"http", "https"}


def _is_image_file(path: Path) -> bool:
    return path.suffix.lower() in _IMAGE_SUFFIXES


def _is_video_file(path: Path) -> bool:
    return path.suffix.lower() in _VIDEO_SUFFIXES


def _method_to_source_kind(method: str) -> str:
    if method == "screenshot":
        return "screenshot"
    if method == "search":
        return "search_download"
    if method == "generate":
        return "ai_generated"
    return "external"


def _infer_mood(seg: dict) -> str:
    seg_type = str(seg.get("type") or "").strip()
    if seg_type == "intro":
        return "hook"
    if seg_type == "outro":
        return "cta"
    narration = str(seg.get("narration_zh") or "")
    if any(k in narration for k in ("风险", "警告", "注意", "坑")):
        return "warning"
    if any(k in narration for k in ("对比", "比较", "vs")):
        return "compare"
    if any(k in narration for k in ("演示", "实测", "Demo", "demo")):
        return "demo"
    return "explain"


def _infer_products(text: str) -> list[str]:
    from v2g.asset_store import PRODUCTS

    low = text.lower()
    found = [p for p in PRODUCTS if p != "other" and p in low]
    if not found:
        return ["other"]
    return found[:3]


def _tokenize_tags(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    tokens = re.findall(r"[a-zA-Z0-9_\-\.]+", text.lower())
    zh = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    merged = tokens + zh
    seen: set[str] = set()
    result: list[str] = []
    for token in merged:
        if token in seen:
            continue
        seen.add(token)
        result.append(token)
        if len(result) >= 10:
            break
    return result


def _compute_file_hash(path: Path) -> str:
    try:
        hasher = hashlib.sha1()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return ""


def _get_image_api_key(method: str) -> str:
    import os

    if method == "search":
        return os.environ.get("BING_IMAGE_API_KEY", "")
    if method == "generate":
        return os.environ.get("GPT_API_KEY", "")
    return ""
