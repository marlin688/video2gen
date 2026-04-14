"""本地素材审核台（批量审批 / 封禁 / 打标签 / 删除）。"""

from __future__ import annotations

import json
import mimetypes
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

import click

from v2g.asset_store import MOODS, PRODUCTS, RIGHTS_STATUS_VALUES, VISUAL_TYPES, AssetMeta, AssetStore
from v2g.config import Config


_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
_VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".m4v", ".avi", ".mkv"}
_MAX_BODY = 2 * 1024 * 1024


@dataclass
class ReviewUIContext:
    """Runtime context for review UI server."""

    cfg: Config
    db_path: Path


def _split_csv_or_list(raw: object) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        vals = [str(v).strip() for v in raw]
    else:
        vals = [v.strip() for v in str(raw).split(",")]
    return [v for v in vals if v]


def _merge_unique(base: list[str], added: list[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for val in [*base, *added]:
        if val in seen:
            continue
        seen.add(val)
        out.append(val)
    return out


def _asset_note(existing: str, incoming: str, append: bool = True) -> str:
    incoming = incoming.strip()
    if not incoming:
        return existing
    if not append or not existing:
        return incoming
    return f"{existing} | {incoming}"


def _safe_iso_date(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    try:
        datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return ""
    return raw


def _asset_match_queue(asset: AssetMeta, queue: str) -> bool:
    queue = (queue or "all").strip().lower()
    if queue in {"", "all"}:
        return True
    if queue == "review_pending":
        return asset.rights_status == "unknown"
    if queue == "blocked":
        return asset.rights_status in {"restricted", "expired"}
    if queue == "missing_file":
        return not (asset.file_path and Path(asset.file_path).exists())
    if queue == "stale":
        return asset.freshness == "possibly_outdated"
    if queue == "expiring_30d":
        if not asset.expires_at:
            return False
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        horizon = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
        return today <= asset.expires_at <= horizon
    if queue == "reusable_off":
        return not asset.reusable
    return True


def _sort_assets(assets: list[AssetMeta], sort_by: str) -> list[AssetMeta]:
    sort_by = (sort_by or "newest").strip().lower()
    if sort_by == "oldest":
        return sorted(
            assets,
            key=lambda a: (a.captured_date or "9999-12-31", a.clip_id),
        )
    if sort_by == "rights":
        order = {"unknown": 0, "restricted": 1, "expired": 2, "cleared": 3}
        return sorted(
            assets,
            key=lambda a: (
                order.get(a.rights_status, 99),
                a.captured_date or "0000-00-00",
                a.clip_id,
            ),
        )
    # newest
    return sorted(
        assets,
        key=lambda a: (a.captured_date or "0000-00-00", a.clip_id),
        reverse=True,
    )


def query_assets_for_review(
    store: AssetStore,
    *,
    query: str = "",
    visual_type: str = "",
    rights_status: str = "",
    show_all: bool = False,
    project_id: str = "",
    date_from: str = "",
    date_to: str = "",
    queue: str = "all",
    sort_by: str = "newest",
    limit: int = 80,
) -> list[AssetMeta]:
    """Build filtered review list with queue/project/time dimensions."""
    query = (query or "").strip()
    visual_type = (visual_type or "").strip()
    rights_status = (rights_status or "").strip()
    project_id = (project_id or "").strip()
    date_from = _safe_iso_date(date_from)
    date_to = _safe_iso_date(date_to)
    limit = max(1, min(500, int(limit)))

    if query:
        assets = store.search_text(
            query,
            limit=max(limit * 6, 300),
            reusable_only=not show_all,
        )
    else:
        assets = store.list_assets(
            reusable_only=not show_all,
            visual_type=visual_type or None,
            rights_status=rights_status or None,
            limit=None,
        )

    filtered: list[AssetMeta] = []
    for asset in assets:
        if visual_type and asset.visual_type != visual_type:
            continue
        if rights_status and asset.rights_status != rights_status:
            continue
        if project_id and asset.source_video != project_id:
            continue
        if date_from and (not asset.captured_date or asset.captured_date < date_from):
            continue
        if date_to and (not asset.captured_date or asset.captured_date > date_to):
            continue
        if not _asset_match_queue(asset, queue):
            continue
        filtered.append(asset)

    return _sort_assets(filtered, sort_by)[:limit]


def apply_batch_action(
    store: AssetStore,
    *,
    asset_ids: list[str],
    action: str,
    payload: dict,
) -> dict:
    """Apply one batch moderation action and return a structured result."""
    selected = [aid.strip() for aid in asset_ids if aid and aid.strip()]
    selected = list(dict.fromkeys(selected))
    if not selected:
        return {
            "ok": False,
            "action": action,
            "message": "no asset_ids provided",
            "updated_count": 0,
            "failed_count": 0,
            "updated": [],
            "failed": [],
        }

    updated: list[str] = []
    failed: list[dict] = []
    warnings: list[dict] = []

    for asset_id in selected:
        asset = store.get(asset_id)
        if not asset:
            failed.append({"asset_id": asset_id, "error": "asset not found"})
            continue

        try:
            if action == "approve":
                scope = str(payload.get("license_scope", "commercial") or "commercial")
                license_type = str(payload.get("license_type", "manual_approved") or "manual_approved")
                res = store.update_asset(
                    asset_id,
                    rights_status="cleared",
                    license_scope=scope,
                    license_type=license_type,
                    reusable=True,
                )
            elif action == "block":
                reason = str(payload.get("reason", "rights blocked") or "rights blocked")
                res = store.update_asset(
                    asset_id,
                    rights_status="restricted",
                    reusable=False,
                    notes=_asset_note(asset.notes, reason, append=True),
                )
            elif action == "set_tags":
                incoming_tags = _split_csv_or_list(payload.get("tags"))
                incoming_products = _split_csv_or_list(payload.get("products"))
                tag_mode = str(payload.get("tag_mode", "merge") or "merge").lower()
                note_mode = str(payload.get("note_mode", "append") or "append").lower()
                mood = str(payload.get("mood", "") or "").strip()
                note = str(payload.get("note", "") or "")

                if tag_mode not in {"merge", "replace"}:
                    raise ValueError("invalid tag_mode, expected merge/replace")
                if mood and mood not in MOODS:
                    raise ValueError(f"invalid mood: {mood}")

                final_tags = incoming_tags if tag_mode == "replace" else _merge_unique(asset.tags, incoming_tags)
                final_products = (
                    incoming_products if tag_mode == "replace" else _merge_unique(asset.product, incoming_products)
                )
                next_note = _asset_note(asset.notes, note, append=(note_mode != "replace"))
                res = store.update_asset(
                    asset_id,
                    tags=final_tags,
                    product=final_products,
                    mood=mood or None,
                    notes=next_note if note else None,
                )
            elif action == "remove":
                delete_file = bool(payload.get("delete_file", False))
                deleted_path = ""
                if delete_file and asset.file_path:
                    p = Path(asset.file_path)
                    if p.exists():
                        p.unlink()
                        deleted_path = str(p)
                    else:
                        warnings.append({"asset_id": asset_id, "warning": "file missing, skipped file delete"})
                ok = store.delete(asset_id)
                if not ok:
                    raise ValueError("delete failed")
                res = asset
                if deleted_path:
                    warnings.append({"asset_id": asset_id, "warning": f"file deleted: {deleted_path}"})
            else:
                raise ValueError(f"unsupported action: {action}")
        except Exception as exc:  # pragma: no cover - defensive for API boundary
            failed.append({"asset_id": asset_id, "error": str(exc)})
            continue

        if res is None:
            failed.append({"asset_id": asset_id, "error": "update failed"})
            continue
        updated.append(asset_id)

    ok = len(failed) == 0
    return {
        "ok": ok,
        "action": action,
        "updated_count": len(updated),
        "failed_count": len(failed),
        "updated": updated,
        "failed": failed,
        "warnings": warnings,
    }


def run_asset_review_ui(
    cfg: Config,
    *,
    host: str = "127.0.0.1",
    port: int = 8877,
    open_browser: bool = False,
) -> None:
    """Run local asset review web UI server."""
    db_path = cfg.output_dir / "assets.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with AssetStore(db_path):
        # ensure DB initialized
        pass

    ctx = ReviewUIContext(cfg=cfg, db_path=db_path)
    server = _ReviewHTTPServer((host, port), _AssetReviewHandler, ctx)
    url = f"http://{host}:{port}"
    click.echo(f"🧰 素材审核台已启动: {url}")
    click.echo("   批量动作: approve / block / set tags / remove")
    click.echo("   退出: Ctrl+C")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            click.echo("   ⚠️ 自动打开浏览器失败，请手动访问上方地址")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        click.echo("\n👋 素材审核台已停止")
    finally:
        server.server_close()


class _ReviewHTTPServer(ThreadingHTTPServer):
    """HTTP server with injected runtime context."""

    daemon_threads = True

    def __init__(self, server_address, handler_class, ctx: ReviewUIContext):
        super().__init__(server_address, handler_class)
        self.ctx = ctx


class _AssetReviewHandler(BaseHTTPRequestHandler):
    server_version = "V2GAssetReview/0.1"

    def log_message(self, format, *args):  # noqa: A003
        # keep terminal output clean, errors still returned in responses
        return

    def _ctx(self) -> ReviewUIContext:
        return self.server.ctx  # type: ignore[attr-defined]

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, body: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = body.encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self._send_json({"ok": False, "message": "file not found"}, HTTPStatus.NOT_FOUND)
            return
        ctype, _ = mimetypes.guess_type(str(path))
        ctype = ctype or "application/octet-stream"
        size = path.stat().st_size
        self.send_response(int(HTTPStatus.OK))
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(size))
        self.end_headers()
        with path.open("rb") as f:
            while True:
                chunk = f.read(64 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def _read_json_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > _MAX_BODY:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _list_assets(self, query_params: dict) -> dict:
        query = (query_params.get("query", [""])[0] or "").strip()
        visual_type = (query_params.get("visual_type", [""])[0] or "").strip()
        rights_status = (query_params.get("rights_status", [""])[0] or "").strip()
        project_id = (query_params.get("project_id", [""])[0] or "").strip()
        date_from = (query_params.get("date_from", [""])[0] or "").strip()
        date_to = (query_params.get("date_to", [""])[0] or "").strip()
        queue = (query_params.get("queue", ["all"])[0] or "all").strip()
        sort_by = (query_params.get("sort", ["newest"])[0] or "newest").strip()
        show_all = (query_params.get("show_all", ["0"])[0] or "0").strip() in {"1", "true", "yes", "on"}
        try:
            limit = int(query_params.get("limit", ["80"])[0] or 80)
        except ValueError:
            limit = 80
        limit = max(1, min(500, limit))

        with AssetStore(self._ctx().db_path) as store:
            assets = query_assets_for_review(
                store,
                query=query,
                visual_type=visual_type,
                rights_status=rights_status,
                show_all=show_all,
                project_id=project_id,
                date_from=date_from,
                date_to=date_to,
                queue=queue,
                sort_by=sort_by,
                limit=limit,
            )

        return {"ok": True, "items": [_serialize_asset(a) for a in assets], "count": len(assets)}

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self._send_html(_INDEX_HTML)
            return
        if parsed.path == "/api/meta":
            with AssetStore(self._ctx().db_path) as store:
                projects = store.list_source_projects(limit=300)
            self._send_json(
                {
                    "ok": True,
                    "visual_types": sorted(VISUAL_TYPES),
                    "rights_statuses": sorted(RIGHTS_STATUS_VALUES),
                    "products": sorted(PRODUCTS),
                    "moods": sorted(MOODS),
                    "projects": projects,
                    "queue_options": [
                        {"value": "all", "label": "全部素材"},
                        {"value": "review_pending", "label": "待审核(unknown)"},
                        {"value": "blocked", "label": "已封禁/过期"},
                        {"value": "missing_file", "label": "文件缺失"},
                        {"value": "stale", "label": "过期候选(possibly_outdated)"},
                        {"value": "expiring_30d", "label": "30天内到期"},
                        {"value": "reusable_off", "label": "reusable=0"},
                    ],
                }
            )
            return
        if parsed.path == "/api/assets":
            self._send_json(self._list_assets(parse_qs(parsed.query)))
            return
        if parsed.path == "/api/preview":
            params = parse_qs(parsed.query)
            asset_id = (params.get("asset_id", [""])[0] or "").strip()
            if not asset_id:
                self._send_json({"ok": False, "message": "asset_id required"}, HTTPStatus.BAD_REQUEST)
                return
            with AssetStore(self._ctx().db_path) as store:
                asset = store.get(asset_id)
            if not asset:
                self._send_json({"ok": False, "message": "asset not found"}, HTTPStatus.NOT_FOUND)
                return
            self._send_file(Path(asset.file_path))
            return

        self._send_json({"ok": False, "message": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/assets/batch":
            self._send_json({"ok": False, "message": "not found"}, HTTPStatus.NOT_FOUND)
            return

        body = self._read_json_body()
        asset_ids = body.get("asset_ids", [])
        action = str(body.get("action", "") or "").strip().lower()
        if not isinstance(asset_ids, list) or not action:
            self._send_json(
                {"ok": False, "message": "asset_ids(list) and action are required"},
                HTTPStatus.BAD_REQUEST,
            )
            return

        payload = dict(body)
        payload.pop("asset_ids", None)
        payload.pop("action", None)

        with AssetStore(self._ctx().db_path) as store:
            result = apply_batch_action(
                store,
                asset_ids=asset_ids,
                action=action,
                payload=payload,
            )

        status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
        self._send_json(result, status)


def _serialize_asset(asset: AssetMeta) -> dict:
    p = Path(asset.file_path) if asset.file_path else Path("")
    suffix = p.suffix.lower()
    if suffix in _IMAGE_SUFFIXES:
        preview_kind = "image"
    elif suffix in _VIDEO_SUFFIXES:
        preview_kind = "video"
    else:
        preview_kind = "none"

    return {
        "clip_id": asset.clip_id,
        "project_id": asset.source_video,
        "visual_type": asset.visual_type,
        "mood": asset.mood,
        "rights_status": asset.rights_status,
        "license_type": asset.license_type,
        "license_scope": asset.license_scope,
        "reusable": bool(asset.reusable),
        "freshness": asset.freshness,
        "captured_date": asset.captured_date,
        "expires_at": asset.expires_at,
        "file_path": asset.file_path,
        "file_name": p.name,
        "file_exists": p.exists(),
        "source_kind": asset.source_kind,
        "source_url": asset.source_url,
        "tags": asset.tags,
        "product": asset.product,
        "notes": asset.notes,
        "preview_kind": preview_kind,
        "preview_url": f"/api/preview?asset_id={quote(asset.clip_id)}",
    }


_INDEX_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>v2g 素材审核台</title>
  <style>
    :root{
      --bg: #f4f2ec;
      --panel: #fffdf9;
      --ink: #2d2a24;
      --muted: #7e756a;
      --line: #e0d7ca;
      --brand: #cb6f4a;
      --brand-2: #256f73;
      --danger: #b13b2b;
      --ok: #1f7a4f;
      --warn: #9a6a10;
      --shadow: 0 10px 30px rgba(25, 20, 15, 0.08);
      --radius: 14px;
    }
    *{ box-sizing: border-box; }
    body{
      margin:0;
      font-family: "Avenir Next", "PingFang SC", "Noto Sans CJK SC", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 10% 10%, #fce9dd 0%, transparent 40%),
        radial-gradient(circle at 90% 0%, #dceff0 0%, transparent 36%),
        var(--bg);
    }
    .app{
      max-width: 1320px;
      margin: 20px auto 40px;
      padding: 0 14px;
    }
    .card{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 14px;
      margin-bottom: 14px;
    }
    h1{
      margin: 4px 0 8px;
      font-size: 26px;
      letter-spacing: 0.2px;
    }
    .sub{
      color: var(--muted);
      font-size: 14px;
    }
    .grid{
      display:grid;
      grid-template-columns: repeat(12, minmax(0,1fr));
      gap:10px;
      align-items:end;
    }
    .col-2{ grid-column: span 2; }
    .col-3{ grid-column: span 3; }
    .col-4{ grid-column: span 4; }
    .col-6{ grid-column: span 6; }
    .col-12{ grid-column: span 12; }
    label{
      display:block;
      font-size:12px;
      color: var(--muted);
      margin: 0 0 5px;
    }
    input, select, textarea, button{
      width:100%;
      border:1px solid var(--line);
      border-radius:10px;
      font-size:14px;
      padding: 9px 10px;
      background: #fff;
      color: var(--ink);
    }
    textarea{ min-height: 68px; resize: vertical; }
    .btn{
      cursor:pointer;
      border:0;
      background: linear-gradient(120deg, var(--brand), #de8d56);
      color:#fff;
      font-weight:600;
    }
    .btn.alt{ background: linear-gradient(120deg, var(--brand-2), #338f8f); }
    .btn.warn{ background: linear-gradient(120deg, #cc8d2a, var(--warn)); }
    .btn.danger{ background: linear-gradient(120deg, #ca4f42, var(--danger)); }
    .btn.ghost{
      background:#fff;
      color:var(--ink);
      border:1px solid var(--line);
      font-weight:500;
    }
    .toolbar{
      display:flex;
      gap:10px;
      flex-wrap:wrap;
      align-items:center;
      margin-top:6px;
    }
    .pill{
      border:1px solid var(--line);
      background:#fff;
      border-radius:999px;
      padding:4px 10px;
      font-size:12px;
      color:var(--muted);
    }
    .table-wrap{
      overflow:auto;
      border:1px solid var(--line);
      border-radius:12px;
      background:#fff;
    }
    table{
      width:100%;
      border-collapse: collapse;
      min-width: 1160px;
      font-size:13px;
    }
    th, td{
      border-bottom:1px solid #eee5d8;
      padding:8px 8px;
      text-align:left;
      vertical-align: top;
    }
    th{
      background:#f6f1e8;
      position: sticky;
      top: 0;
      z-index: 2;
      font-size:12px;
      color:#6e6458;
    }
    tr:hover td{ background:#fffcf6; }
    tr.missing td{ background:#fff3f3; }
    .preview{
      width: 132px;
      height: 74px;
      border:1px solid var(--line);
      border-radius:8px;
      overflow:hidden;
      background:#efebe3;
      display:flex;
      align-items:center;
      justify-content:center;
    }
    .preview img, .preview video{
      width:100%;
      height:100%;
      object-fit:cover;
      display:block;
    }
    .mono{ font-family: "SFMono-Regular", Menlo, Monaco, monospace; font-size:12px; }
    .muted{ color: var(--muted); }
    .status{
      display:inline-block;
      border-radius:999px;
      padding:2px 8px;
      font-size:11px;
      font-weight:600;
      border:1px solid currentColor;
    }
    .status.cleared{ color:var(--ok); }
    .status.unknown{ color:#666; }
    .status.restricted, .status.expired{ color:var(--danger); }
    @media (max-width: 980px){
      .col-2, .col-3, .col-4, .col-6{ grid-column: span 12; }
    }
  </style>
</head>
<body>
  <div class="app">
    <div class="card">
      <h1>素材审核台</h1>
      <div class="sub">支持批量审批 / 封禁 / 标签治理。勾选后统一执行，执行结果会写回 <span class="mono">output/assets.db</span></div>
      <div class="toolbar">
        <span class="pill" id="summaryCount">总计 0 条</span>
        <span class="pill" id="selectedCount">已选 0 条</span>
        <span class="pill" id="lastAction">待操作</span>
      </div>
    </div>

    <div class="card">
      <div class="grid">
        <div class="col-4">
          <label>关键词</label>
          <input id="query" placeholder="notes/tags/source 等关键词" />
        </div>
        <div class="col-2">
          <label>visual_type</label>
          <select id="visualType"><option value="">全部</option></select>
        </div>
        <div class="col-2">
          <label>rights_status</label>
          <select id="rightsStatus"><option value="">全部</option></select>
        </div>
        <div class="col-2">
          <label>项目</label>
          <select id="projectId"><option value="">全部项目</option></select>
        </div>
        <div class="col-2">
          <label>审核队列</label>
          <select id="queue">
            <option value="all">全部素材</option>
          </select>
        </div>
        <div class="col-2">
          <label>date_from</label>
          <input id="dateFrom" type="date" />
        </div>
        <div class="col-2">
          <label>date_to</label>
          <input id="dateTo" type="date" />
        </div>
        <div class="col-2">
          <label>sort</label>
          <select id="sortBy">
            <option value="newest">newest</option>
            <option value="oldest">oldest</option>
            <option value="rights">rights</option>
          </select>
        </div>
        <div class="col-2">
          <label>limit</label>
          <input id="limit" type="number" value="120" min="1" max="500" />
        </div>
        <div class="col-2">
          <label>include blocked</label>
          <select id="showAll">
            <option value="0">仅 reusable=1</option>
            <option value="1">包含全部</option>
          </select>
        </div>
        <div class="col-12">
          <div class="grid">
            <div class="col-3"><button class="btn ghost" id="btnReload">刷新列表</button></div>
            <div class="col-3"><button class="btn alt" id="btnSelectAll">全选当前页</button></div>
            <div class="col-3"><button class="btn ghost" id="btnClearSel">清空选择</button></div>
            <div class="col-3"><button class="btn ghost" id="btnResetFilters">重置筛选</button></div>
          </div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="grid">
        <div class="col-3">
          <label>审批 scope</label>
          <input id="approveScope" value="commercial" />
        </div>
        <div class="col-3">
          <label>审批 license_type</label>
          <input id="approveLicenseType" value="manual_approved" />
        </div>
        <div class="col-3">
          <label>封禁原因</label>
          <input id="blockReason" value="rights blocked" />
        </div>
        <div class="col-3">
          <label>标签模式</label>
          <select id="tagMode">
            <option value="merge">merge（追加）</option>
            <option value="replace">replace（覆盖）</option>
          </select>
        </div>

        <div class="col-4">
          <label>tags（逗号分隔）</label>
          <input id="tagsInput" placeholder="ai,agent,demo" />
        </div>
        <div class="col-4">
          <label>products（逗号分隔）</label>
          <input id="productsInput" placeholder="openai,github" />
        </div>
        <div class="col-2">
          <label>mood</label>
          <select id="moodSelect"><option value="">不改</option></select>
        </div>
        <div class="col-2">
          <label>note 模式</label>
          <select id="noteMode">
            <option value="append">append</option>
            <option value="replace">replace</option>
          </select>
        </div>
        <div class="col-12">
          <label>note</label>
          <textarea id="noteInput" placeholder="审核备注（可选）"></textarea>
        </div>
        <div class="col-3"><button class="btn" id="btnApprove">批量 Approve</button></div>
        <div class="col-3"><button class="btn danger" id="btnBlock">批量 Block</button></div>
        <div class="col-3"><button class="btn warn" id="btnSetTags">批量 Set Tags</button></div>
        <div class="col-3"><button class="btn ghost" id="btnRemove">批量删除记录</button></div>
        <div class="col-12"><button class="btn danger" id="btnRemoveWithFile">批量删除记录 + 文件（危险）</button></div>
      </div>
    </div>

    <div class="card table-wrap">
      <table>
        <thead>
          <tr>
            <th style="width:38px;"><input type="checkbox" id="headCheck"></th>
            <th style="width:150px;">预览</th>
            <th style="width:180px;">asset_id</th>
            <th style="width:120px;">项目/日期</th>
            <th style="width:120px;">type/mood</th>
            <th style="width:120px;">rights</th>
            <th style="width:220px;">tags/products</th>
            <th style="width:280px;">file</th>
            <th style="width:170px;">source</th>
          </tr>
        </thead>
        <tbody id="assetRows"></tbody>
      </table>
    </div>
  </div>

  <script>
    const state = {
      assets: [],
      selected: new Set(),
      meta: null,
    };

    const el = (id) => document.getElementById(id);
    const esc = (s) => (s || "").replace(/[&<>"]/g, (c) => ({'&': '&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;'}[c]));

    async function boot() {
      await loadMeta();
      bindEvents();
      await loadAssets();
    }

    function bindEvents() {
      el("btnReload").addEventListener("click", loadAssets);
      el("btnSelectAll").addEventListener("click", () => {
        state.assets.forEach((a) => state.selected.add(a.clip_id));
        renderRows();
      });
      el("btnClearSel").addEventListener("click", () => {
        state.selected.clear();
        renderRows();
      });
      el("btnResetFilters").addEventListener("click", () => {
        el("query").value = "";
        el("visualType").value = "";
        el("rightsStatus").value = "";
        el("projectId").value = "";
        el("queue").value = "all";
        el("dateFrom").value = "";
        el("dateTo").value = "";
        el("sortBy").value = "newest";
        el("showAll").value = "0";
        el("limit").value = "120";
        loadAssets();
      });
      el("btnApprove").addEventListener("click", async () => {
        await batchAction("approve", {
          license_scope: el("approveScope").value.trim(),
          license_type: el("approveLicenseType").value.trim(),
        });
      });
      el("btnBlock").addEventListener("click", async () => {
        await batchAction("block", {
          reason: el("blockReason").value.trim(),
        });
      });
      el("btnSetTags").addEventListener("click", async () => {
        await batchAction("set_tags", {
          tags: el("tagsInput").value.trim(),
          products: el("productsInput").value.trim(),
          mood: el("moodSelect").value,
          note: el("noteInput").value.trim(),
          note_mode: el("noteMode").value,
          tag_mode: el("tagMode").value,
        });
      });
      el("btnRemove").addEventListener("click", async () => {
        if (!confirm(`确定删除 ${state.selected.size} 条素材记录？文件会保留。`)) return;
        await batchAction("remove", {
          delete_file: false,
        });
      });
      el("btnRemoveWithFile").addEventListener("click", async () => {
        if (!confirm(`危险操作：删除 ${state.selected.size} 条记录并尝试删除文件，继续吗？`)) return;
        await batchAction("remove", {
          delete_file: true,
        });
      });
      el("headCheck").addEventListener("change", (e) => {
        if (e.target.checked) {
          state.assets.forEach((a) => state.selected.add(a.clip_id));
        } else {
          state.assets.forEach((a) => state.selected.delete(a.clip_id));
        }
        renderRows();
      });
      ["query","visualType","rightsStatus","projectId","queue","dateFrom","dateTo","sortBy","showAll","limit"].forEach((id) => {
        el(id).addEventListener("change", () => loadAssets());
      });
    }

    async function loadMeta() {
      const res = await fetch("/api/meta");
      const data = await res.json();
      state.meta = data;

      data.visual_types.forEach((t) => {
        const opt = document.createElement("option");
        opt.value = t;
        opt.textContent = t;
        el("visualType").appendChild(opt);
      });
      data.rights_statuses.forEach((s) => {
        const opt = document.createElement("option");
        opt.value = s;
        opt.textContent = s;
        el("rightsStatus").appendChild(opt);
      });
      el("projectId").innerHTML = "<option value=''>全部项目</option>";
      (data.projects || []).forEach((p) => {
        const opt = document.createElement("option");
        opt.value = p.project_id;
        opt.textContent = `${p.project_id} (${p.asset_count})`;
        el("projectId").appendChild(opt);
      });
      el("queue").innerHTML = "";
      (data.queue_options || []).forEach((q) => {
        const opt = document.createElement("option");
        opt.value = q.value;
        opt.textContent = q.label;
        el("queue").appendChild(opt);
      });
      data.moods.forEach((m) => {
        const opt = document.createElement("option");
        opt.value = m;
        opt.textContent = m;
        el("moodSelect").appendChild(opt);
      });
    }

    async function loadAssets() {
      const params = new URLSearchParams({
        query: el("query").value.trim(),
        visual_type: el("visualType").value,
        rights_status: el("rightsStatus").value,
        project_id: el("projectId").value,
        queue: el("queue").value,
        date_from: el("dateFrom").value,
        date_to: el("dateTo").value,
        sort: el("sortBy").value,
        show_all: el("showAll").value,
        limit: String(el("limit").value || 120),
      });
      const res = await fetch("/api/assets?" + params.toString());
      const data = await res.json();
      state.assets = data.items || [];

      const visibleIds = new Set(state.assets.map((a) => a.clip_id));
      [...state.selected].forEach((id) => {
        if (!visibleIds.has(id)) state.selected.delete(id);
      });
      renderRows();
    }

    function renderRows() {
      const tbody = el("assetRows");
      tbody.innerHTML = "";

      state.assets.forEach((a) => {
        const tr = document.createElement("tr");
        if (!a.file_exists) tr.classList.add("missing");
        const checked = state.selected.has(a.clip_id) ? "checked" : "";
        const tags = (a.tags || []).slice(0, 6).join(", ");
        const products = (a.product || []).slice(0, 6).join(", ");

        let preview = "<div class='preview muted'>无预览</div>";
        if (a.preview_kind === "image") {
          preview = "<div class='preview'><img src='" + a.preview_url + "' loading='lazy' /></div>";
        } else if (a.preview_kind === "video") {
          preview = "<div class='preview'><video src='" + a.preview_url + "' muted preload='metadata'></video></div>";
        }

        tr.innerHTML = `
          <td><input type="checkbox" data-id="${esc(a.clip_id)}" ${checked}></td>
          <td>${preview}</td>
          <td><span class="mono">${esc(a.clip_id)}</span></td>
          <td><div>${esc(a.project_id || "-")}</div>
              <div class="muted">${esc(a.captured_date || "-")}</div></td>
          <td>${esc(a.visual_type)}<br><span class="muted">${esc(a.mood)}</span></td>
          <td><span class="status ${esc(a.rights_status)}">${esc(a.rights_status)}</span>
              <br><span class="muted">reusable=${a.reusable ? 1 : 0}, exp=${esc(a.expires_at || "-")}</span></td>
          <td><div>${esc(tags || "-")}</div><div class="muted">${esc(products || "-")}</div></td>
          <td><div class="mono">${esc(a.file_name || "-")}</div>
              <div class="muted mono">${esc(a.file_path || "-")}</div></td>
          <td><div>${esc(a.source_kind || "-")}</div>
              <div class="muted mono">${esc(a.source_url || "")}</div></td>
        `;
        tbody.appendChild(tr);
      });

      tbody.querySelectorAll("input[type=checkbox][data-id]").forEach((cb) => {
        cb.addEventListener("change", (e) => {
          const id = e.target.getAttribute("data-id");
          if (!id) return;
          if (e.target.checked) {
            state.selected.add(id);
          } else {
            state.selected.delete(id);
          }
          updateSummary();
        });
      });

      el("headCheck").checked = state.assets.length > 0 && state.assets.every((a) => state.selected.has(a.clip_id));
      updateSummary();
    }

    async function batchAction(action, payload) {
      if (state.selected.size === 0) {
        alert("请先勾选素材");
        return;
      }
      const body = {
        action,
        asset_ids: [...state.selected],
        ...payload,
      };

      const res = await fetch("/api/assets/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        const msg = (data.failed || []).map((x) => `${x.asset_id}: ${x.error}`).join("\\n") || data.message || "批量操作失败";
        alert(msg);
        el("lastAction").textContent = "执行失败";
        return;
      }
      if (data.warnings && data.warnings.length > 0) {
        console.log("batch warnings", data.warnings);
      }
      el("lastAction").textContent = `执行成功: ${action} / ${data.updated_count} 条`;
      await loadAssets();
    }

    function updateSummary() {
      el("summaryCount").textContent = `总计 ${state.assets.length} 条`;
      el("selectedCount").textContent = `已选 ${state.selected.size} 条`;
    }

    boot();
  </script>
</body>
</html>
"""
