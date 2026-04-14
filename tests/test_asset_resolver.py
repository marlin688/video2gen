import json
from pathlib import Path

import v2g.asset_resolver as asset_resolver
from v2g.asset_store import AssetMeta, AssetStore
from v2g.config import Config


def _cfg(tmp_path: Path) -> Config:
    cfg = Config()
    cfg.output_dir = tmp_path / "output"
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    return cfg


def _write_script(project_dir: Path, segments: list[dict]) -> None:
    payload = {
        "title": "demo",
        "description": "",
        "tags": [],
        "segments": segments,
    }
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "script.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_script(project_dir: Path) -> dict:
    return json.loads((project_dir / "script.json").read_text(encoding="utf-8"))


def test_resolver_prefers_local_library_asset(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    project_id = "proj-local-hit"
    project_dir = cfg.output_dir / project_id

    source_img = tmp_path / "library" / "openai-ui.png"
    source_img.parent.mkdir(parents=True, exist_ok=True)
    source_img.write_bytes(b"fake-image")

    with AssetStore(cfg.output_dir / "assets.db") as store:
        store.insert(
            AssetMeta(
                clip_id="img-local-1",
                source_video="manual-library",
                time_range_start=0,
                time_range_end=0,
                duration=0,
                captured_date="2026-04-14",
                visual_type="image_overlay",
                tags=["openai", "ui", "dashboard"],
                product=["openai"],
                mood="explain",
                reusable=True,
                freshness="current",
                file_path=str(source_img),
                source_kind="manual_upload",
                rights_status="cleared",
                license_type="manual",
                license_scope="commercial",
            )
        )

    _write_script(
        project_dir,
        [
            {
                "id": 1,
                "type": "body",
                "material": "A",
                "narration_zh": "这里展示 OpenAI 控制台 UI",
                "component": "image-overlay.default",
                "image_content": {
                    "source_method": "search",
                    "source_query": "OpenAI dashboard UI",
                    "image_path": "",
                },
            }
        ],
    )

    def _should_not_call(*args, **kwargs):
        raise AssertionError("source_image should not be called when local asset matches")

    monkeypatch.setattr(asset_resolver, "source_image", _should_not_call)

    report = asset_resolver.resolve_project_assets(cfg, project_id)
    assert report["resolved_local"] == 1
    assert report["resolved_remote"] == 0
    assert report["unresolved"] == 0

    script = _read_script(project_dir)
    image_path = script["segments"][0]["image_content"]["image_path"]
    assert image_path.startswith("images/seg_1_img_")
    assert (project_dir / image_path).exists()


def test_resolver_fallbacks_to_remote_and_ingests_library(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    project_id = "proj-remote-fallback"
    project_dir = cfg.output_dir / project_id

    _write_script(
        project_dir,
        [
            {
                "id": 2,
                "type": "intro",
                "material": "A",
                "narration_zh": "我们来看 agent 的热点图",
                "component": "image-overlay.default",
                "image_content": {
                    "source_method": "search",
                    "source_query": "AI agent heatmap",
                    "image_path": "",
                },
            }
        ],
    )

    def _fake_source_image(query: str, method: str, output_dir: Path, **kwargs):
        assert query == "AI agent heatmap"
        assert method == "search"
        output_dir.mkdir(parents=True, exist_ok=True)
        out = output_dir / "search_ai_agent_heatmap.jpg"
        out.write_bytes(b"remote-image-bytes")
        return out

    monkeypatch.setattr(asset_resolver, "source_image", _fake_source_image)

    report = asset_resolver.resolve_project_assets(cfg, project_id)
    assert report["resolved_local"] == 0
    assert report["resolved_remote"] == 1
    assert report["unresolved"] == 0

    script = _read_script(project_dir)
    rel = script["segments"][0]["image_content"]["image_path"]
    assert rel == "images/search_ai_agent_heatmap.jpg"
    assert (project_dir / rel).exists()

    with AssetStore(cfg.output_dir / "assets.db") as store:
        assets = store.search_text("agent heatmap", limit=5)
        assert assets, "remote asset should be inserted into assets.db"
        remote = assets[0]
        assert remote.source_kind == "search_download"
        assert remote.rights_status == "unknown"
        assert "asset_library/images" in remote.file_path
        assert Path(remote.file_path).exists()


def test_resolver_strict_rights_rejects_unknown_local_asset(tmp_path):
    cfg = _cfg(tmp_path)
    project_id = "proj-strict-rights"
    project_dir = cfg.output_dir / project_id

    unknown_img = tmp_path / "library" / "unknown-rights.png"
    unknown_img.parent.mkdir(parents=True, exist_ok=True)
    unknown_img.write_bytes(b"unknown")

    with AssetStore(cfg.output_dir / "assets.db") as store:
        store.insert(
            AssetMeta(
                clip_id="img-unknown-rights",
                source_video="manual-library",
                time_range_start=0,
                time_range_end=0,
                duration=0,
                captured_date="2026-04-14",
                visual_type="image_overlay",
                tags=["finance", "chart"],
                product=["other"],
                mood="explain",
                reusable=True,
                freshness="current",
                file_path=str(unknown_img),
                source_kind="manual_upload",
                rights_status="unknown",
            )
        )

    _write_script(
        project_dir,
        [
            {
                "id": 3,
                "type": "body",
                "material": "A",
                "narration_zh": "这是一个 finance chart",
                "component": "image-overlay.default",
                "image_content": {
                    "source_method": "",
                    "source_query": "finance chart",
                    "image_path": "",
                },
            }
        ],
    )

    report = asset_resolver.resolve_project_assets(
        cfg,
        project_id,
        require_cleared_rights=True,
    )
    assert report["resolved_local"] == 0
    assert report["resolved_remote"] == 0
    assert report["unresolved"] == 1

    script = _read_script(project_dir)
    assert script["segments"][0]["image_content"]["image_path"] == ""


def test_resolver_prefers_local_web_video_asset(tmp_path):
    cfg = _cfg(tmp_path)
    project_id = "proj-web-local"
    project_dir = cfg.output_dir / project_id

    source_video = tmp_path / "library" / "web" / "demo.mp4"
    source_video.parent.mkdir(parents=True, exist_ok=True)
    source_video.write_bytes(b"fake-video")

    with AssetStore(cfg.output_dir / "assets.db") as store:
        store.insert(
            AssetMeta(
                clip_id="web-local-1",
                source_video="manual-library",
                time_range_start=0,
                time_range_end=0,
                duration=0,
                captured_date="2026-04-14",
                visual_type="web_video",
                tags=["agent", "demo"],
                product=["openai"],
                mood="demo",
                reusable=True,
                freshness="current",
                file_path=str(source_video),
                source_kind="manual_upload",
                rights_status="cleared",
            )
        )

    _write_script(
        project_dir,
        [
            {
                "id": 4,
                "type": "body",
                "material": "C",
                "narration_zh": "这里展示 agent 产品演示视频",
                "component": "web-video.default",
                "web_video": {
                    "search_query": "agent product demo",
                    "source_url": "",
                },
            }
        ],
    )

    report = asset_resolver.resolve_project_assets(cfg, project_id)
    assert report["resolved_local_web_video"] == 1
    assert report["resolved_remote_web_video"] == 0

    script = _read_script(project_dir)
    source_name = script["segments"][0]["web_video"]["source_url"]
    assert source_name.endswith(".mp4")
    assert (project_dir / "web_videos" / source_name).exists()

    with AssetStore(cfg.output_dir / "assets.db") as store:
        usage = store.usage_stats()
        assert usage["total_usage"] >= 1
        assert usage["top_assets"][0]["asset_id"] == "web-local-1"


def test_resolver_remote_web_video_ingest(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    project_id = "proj-web-remote"
    project_dir = cfg.output_dir / project_id

    _write_script(
        project_dir,
        [
            {
                "id": 5,
                "type": "body",
                "material": "C",
                "narration_zh": "这里引用外部发布会视频",
                "component": "web-video.default",
                "web_video": {
                    "search_query": "openai launch demo",
                    "source_url": "",
                },
            }
        ],
    )

    def _fake_download_web_video(*, project_dir: Path, seg_id: int, source_url: str, search_query: str):
        out = project_dir / "web_videos" / f"seg_{seg_id}.mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"downloaded-web-video")
        return out, "search_query"

    monkeypatch.setattr(asset_resolver, "_download_web_video", _fake_download_web_video)

    report = asset_resolver.resolve_project_assets(cfg, project_id)
    assert report["resolved_remote_web_video"] == 1
    assert report["unresolved"] == 0

    script = _read_script(project_dir)
    source_name = script["segments"][0]["web_video"]["source_url"]
    assert source_name == "seg_5.mp4"
    assert (project_dir / "web_videos" / source_name).exists()

    with AssetStore(cfg.output_dir / "assets.db") as store:
        found = store.search(visual_type="web_video", limit=5)
        assert found
        assert "asset_library/web_videos" in found[0].file_path
