from datetime import date
from pathlib import Path
from types import SimpleNamespace

from v2g.scout import auto_post


def test_build_plist_includes_env_and_chain_arguments(tmp_path: Path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".env").write_text("X_CONSUMER_KEY=x\n", encoding="utf-8")

    plist = auto_post._build_plist(
        "/usr/local/bin/v2g",
        str(project_dir),
        [9, 11],
        publish_format="chain",
        version="long",
    )

    assert "<string>--env</string>" in plist
    assert f"<string>{project_dir / '.env'}</string>" in plist
    assert "<string>--format</string>" in plist
    assert "<string>chain</string>" in plist
    assert "<string>--version</string>" in plist
    assert "<string>long</string>" in plist


def test_run_auto_post_chain_routes_to_chain_publisher(monkeypatch, tmp_path: Path):
    cfg = SimpleNamespace(
        obsidian_vault_path=tmp_path,
        scout_db_path=tmp_path / "scout.db",
    )
    ideation_file = tmp_path / "scout" / "ideation" / "topic.md"
    chain_file = tmp_path / "scout" / "chain" / "2026-06-07-demo-chain.md"
    chain_file.parent.mkdir(parents=True)
    chain_file.write_text("# demo", encoding="utf-8")

    calls = {}

    monkeypatch.setattr(auto_post, "_ensure_scout_done", lambda cfg, vault, today: None)
    monkeypatch.setattr(
        auto_post,
        "_pick_next_topic",
        lambda cfg, vault, today: ("AI 存储产业链", ideation_file),
    )

    import v2g.scout.chain as chain_mod
    import v2g.scout.x_publisher as publisher_mod

    def fake_run_chain(cfg, topic, today=None):
        calls["chain"] = {"topic": topic, "today": today}
        return chain_file

    def fake_publish_chain(cfg, file_path, version, dry_run, force, yes=False):
        calls["publish"] = {
            "file_path": file_path,
            "version": version,
            "dry_run": dry_run,
            "force": force,
            "yes": yes,
        }

    monkeypatch.setattr(chain_mod, "run_chain", fake_run_chain)
    monkeypatch.setattr(publisher_mod, "run_publish_chain", fake_publish_chain)

    auto_post.run_auto_post(
        cfg,
        dry_run=True,
        force=False,
        yes=True,
        publish_format="chain",
        version="long",
    )

    assert calls["chain"]["topic"] == "AI 存储产业链"
    assert calls["chain"]["today"] == date.today()
    assert calls["publish"] == {
        "file_path": str(chain_file),
        "version": "long",
        "dry_run": True,
        "force": False,
        "yes": True,
    }
