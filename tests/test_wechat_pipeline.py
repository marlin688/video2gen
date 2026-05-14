import json
from pathlib import Path

from v2g.wechat_pipeline import build_publish_plan, make_package, score_package


def test_make_package_copies_local_images(tmp_path: Path):
    src_dir = tmp_path / "article"
    assets = src_dir / "assets"
    assets.mkdir(parents=True)
    (assets / "pro-cover.png").write_bytes(b"fake image")
    md = src_dir / "article-pro.md"
    md.write_text(
        "# MCP 很热\n\n"
        "![封面](./assets/pro-cover.png)\n\n"
        "这是一个核心判断。",
        encoding="utf-8",
    )

    pkg = make_package(tmp_path / "output", src_dir, package_id="demo")

    assert pkg.package_id == "demo"
    assert pkg.markdown_path.exists()
    assert (pkg.package_dir / "assets" / "pro-cover.png").exists()
    manifest = json.loads((pkg.package_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["title"] == "MCP 很热"
    assert len(manifest["images"]) == 1


def test_score_package_rewards_real_screenshots_and_original_visuals(tmp_path: Path):
    src_dir = tmp_path / "article"
    assets = src_dir / "assets"
    assets.mkdir(parents=True)
    names = [
        "pro-cover.png",
        "pro-map.png",
        "pro-stack.png",
        "real-01.png",
        "real-02.png",
        "real-03.png",
    ]
    for name in names:
        (assets / name).write_bytes(b"fake image")

    body = "\n\n".join(
        [
            "# MCP 很热，但 Agent 不是靠多接工具变强",
            "## 先说结论\n真正的问题不是能不能接上，而是接上以后系统还能不能保持清晰。",
            "## MCP 为什么会火\n" + "MCP 是接口层，连接外部系统。 " * 60,
            "## 接上之后的问题\n" + "工具定义、权限边界、输出噪音都会进入上下文。 " * 60,
            "## 上下文工程\n" + "上下文工程决定模型此刻应该看到什么。 " * 60,
            "## 落地顺序\n先写规则，再补验证，再整理上下文，最后精选 MCP。",
            "## 参考资料\n[1] https://example.com/a\n[2] https://example.com/b\n[3] https://example.com/c\n[4] https://example.com/d\n[5] https://example.com/e",
            "\n".join(f"![图]({ './assets/' + name })" for name in names),
            "MCP 是接口层。上下文工程，才是 Agent 真正的竞争层。",
        ]
    )
    (src_dir / "article-pro.md").write_text(body, encoding="utf-8")

    pkg = make_package(tmp_path / "output", src_dir, package_id="scored")
    report = score_package(pkg.package_dir, min_score=80)

    assert report["gate_score_pct"] >= 80
    assert report["score_pct"] < report["gate_score_pct"]
    assert report["metrics"]["real_screenshots"] == 3
    assert report["metrics"]["original_visuals"] == 3


def test_publish_plan_blocks_below_threshold(tmp_path: Path):
    src_dir = tmp_path / "article"
    src_dir.mkdir()
    (src_dir / "article-pro.md").write_text("# 太短\n\n内容太少。", encoding="utf-8")

    pkg = make_package(tmp_path / "output", src_dir, package_id="low")
    score_package(pkg.package_dir, min_score=90)
    plan = build_publish_plan(pkg.package_dir, min_score=90)

    assert plan["ready"] is False
    assert plan["reason"] == "score_below_threshold"
