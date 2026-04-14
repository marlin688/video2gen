"""Asset, material, and image CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import click

from v2g.checkpoint import PipelineState
from v2g.config import Config


def register_asset_commands(main: click.Group) -> None:
    @main.group()
    def material():
        """素材库管理"""

    @material.command("add")
    @click.argument("file_path", type=click.Path(exists=True))
    @click.option("--keywords", "-k", required=True, help="关键词 (逗号分隔)")
    @click.option("--desc", "-d", default="", help="素材描述")
    @click.pass_obj
    def material_add(cfg: Config, file_path, keywords, desc):
        """向素材库添加素材"""
        import shutil

        from v2g.material_library import MaterialEntry, MaterialLibrary

        lib = MaterialLibrary(db_path=cfg.output_dir / "assets.db")
        src = Path(file_path)
        dest_dir = lib.root / "recordings"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        if not dest.exists():
            shutil.copy2(src, dest)

        entry = lib.add(
            MaterialEntry(
                type="recording",
                path=str(dest),
                keywords=[k.strip() for k in keywords.split(",")],
                description=desc or src.stem,
            )
        )
        click.echo(f"✅ 已添加: {entry.id} → {dest}")

    @material.command("search")
    @click.argument("query")
    @click.pass_obj
    def material_search(cfg: Config, query):
        """搜索素材库"""
        from v2g.material_library import MaterialLibrary

        lib = MaterialLibrary(db_path=cfg.output_dir / "assets.db")
        results = lib.search(query, top_k=5)
        if not results:
            click.echo("未找到匹配素材")
            return
        for result in results:
            click.echo(
                f"  [{result.id}] {result.type} | {result.description[:50]} | "
                f"{', '.join(result.keywords[:3])}"
            )

    @material.command("list")
    @click.pass_obj
    def material_list(cfg: Config):
        """列出素材库全部素材"""
        from v2g.material_library import MaterialLibrary

        lib = MaterialLibrary(db_path=cfg.output_dir / "assets.db")
        entries = lib.list_all()
        if not entries:
            click.echo("素材库为空")
            return
        click.echo(f"📦 素材库: {len(entries)} 条")
        for entry in entries:
            click.echo(
                f"  [{entry.id}] {entry.type:10s} | "
                f"{entry.description[:40]} | {', '.join(entry.keywords[:3])}"
            )

    @main.group()
    def image():
        """自动配图（网页截图 / 搜图 / AI 生图）"""

    @image.command("prepare")
    @click.argument("project_id")
    @click.pass_obj
    def image_prepare_cmd(cfg: Config, project_id):
        """扫描 script.json，自动执行配图并填充 image_path"""
        from v2g.image_prepare import prepare_images

        click.echo(f"🖼️ 自动配图: {project_id}")
        count = prepare_images(cfg, project_id)
        if count == 0:
            click.echo("   没有需要配图的 segment（source_method 为空或 image_path 已存在）")

    @image.command("test")
    @click.argument("method", type=click.Choice(["screenshot", "search", "generate"]))
    @click.argument("query")
    @click.option("--output", "output_dir", default="output/test/images", help="输出目录")
    @click.pass_obj
    def image_test(cfg: Config, method, query, output_dir):
        """测试单种配图方式"""
        from v2g.image_source import source_image

        out = Path(output_dir)
        result = source_image(query, method, out)
        if result:
            click.echo(f"\n✅ 配图成功: {result}")
        else:
            click.echo("\n❌ 配图失败")

    @main.group()
    def assets():
        """素材库管理（入库、打标、检索、保鲜）"""

    @assets.command("ingest")
    @click.argument("project_id")
    @click.pass_obj
    def assets_ingest(cfg: Config, project_id):
        """自产素材入库：切片 + 自动打标 + 写入 SQLite"""
        from v2g.asset_ingest import ingest_from_video
        from v2g.asset_store import AssetStore

        db_path = cfg.output_dir / "assets.db"
        with AssetStore(db_path) as store:
            count = ingest_from_video(cfg, project_id, store)
            total = store.count()
            click.echo(f"✅ 入库 {count} 个片段，素材库总量: {total}")

    @assets.command("resolve")
    @click.argument("project_id")
    @click.option(
        "--strict-rights",
        is_flag=True,
        help="仅允许 rights_status=cleared 的本地素材",
    )
    @click.pass_obj
    def assets_resolve(cfg: Config, project_id, strict_rights):
        """素材解析：优先本地库命中，缺失时在线补图并回灌素材库"""
        from v2g.asset_resolver import resolve_project_assets

        click.echo(f"🧩 素材解析: {project_id} (strict_rights={strict_rights})")
        report = resolve_project_assets(
            cfg,
            project_id,
            require_cleared_rights=strict_rights,
        )
        click.echo(
            "   ✅ 完成: "
            f"检查 {report['checked_segments']} 段, "
            f"本地命中 {report['resolved_local']}, "
            f"在线补图 {report['resolved_remote']}, "
            f"未解决 {report['unresolved']}"
        )
        click.echo(
            "   细分: "
            f"图片本地/远程 {report.get('resolved_local_image', 0)}/{report.get('resolved_remote_image', 0)}, "
            f"视频本地/远程 {report.get('resolved_local_web_video', 0)}/{report.get('resolved_remote_web_video', 0)}"
        )
        if report["unknown_rights_local_hits"] > 0:
            click.echo(
                f"   ⚠️ 本地命中中有 {report['unknown_rights_local_hits']} 条版权状态未知"
            )

    @assets.command("metrics")
    @click.option("--days", default=30, type=int, help="统计窗口天数 (默认 30)")
    @click.option("--no-write", is_flag=True, help="不写文件，仅在终端输出")
    @click.pass_obj
    def assets_metrics(cfg: Config, days, no_write):
        """生成素材库运营指标（命中率/复用率/成本）"""
        from v2g.asset_metrics import build_asset_metrics

        metrics = build_asset_metrics(cfg, days=days, write_files=not no_write)
        resolve = metrics["resolve"]
        reuse = metrics["reuse"]
        lib = metrics["library"]
        cost = metrics["cost"]

        click.echo("📈 素材库指标:")
        click.echo(
            f"   命中率: 本地 {resolve['local_hit_rate']:.1%} | 远程 {resolve['remote_fetch_rate']:.1%} | 未解决 {resolve['unresolved_rate']:.1%}"
        )
        click.echo(
            f"   细分命中: 图片 {resolve['image_local_hit_rate']:.1%} | web_video {resolve['web_video_local_hit_rate']:.1%}"
        )
        click.echo(
            f"   复用: 使用 {reuse['total_usage']} 次，跨项目复用资产 {reuse['reused_assets']} 个"
        )
        click.echo(
            f"   风控: 资产总量 {lib['total_assets']}，受限资产 {lib['blocked_assets']}，版权未知占比 {lib['unknown_rate']:.1%}"
        )
        click.echo(
            f"   成本: 外采 {cost['external_fetch_count']} 次，估算成本 {cost['external_estimated_cost']}"
        )
        if not no_write:
            click.echo(f"   报告: {cfg.output_dir / 'asset_library' / 'metrics' / 'latest.json'}")

    @assets.command("review-ui")
    @click.option("--host", default="127.0.0.1", help="监听地址")
    @click.option("--port", default=8877, type=int, help="监听端口")
    @click.option("--open-browser", is_flag=True, help="启动后自动打开浏览器")
    @click.pass_obj
    def assets_review_ui(cfg: Config, host, port, open_browser):
        """启动素材审核台 Web UI（批量 approve/block/set tags）"""
        from v2g.asset_review_ui import run_asset_review_ui

        run_asset_review_ui(
            cfg,
            host=host,
            port=port,
            open_browser=open_browser,
        )

    @assets.command("extract")
    @click.argument("project_id")
    @click.pass_obj
    def assets_extract(cfg: Config, project_id):
        """提取脚本结构特征 → 写入 assets.db（用于历史 pattern 分析）"""
        from v2g.asset_store import AssetStore
        from v2g.feature_extractor import extract_features

        script_path = cfg.output_dir / project_id / "script.json"
        if not script_path.exists():
            raise click.ClickException(f"script.json 不存在: {script_path}")

        feat = extract_features(script_path, project_id)
        click.echo(
            f"📊 脚本特征: {feat.segment_count} 段, "
            f"A:{feat.material_a_ratio:.0%} B:{feat.material_b_ratio:.0%} C:{feat.material_c_ratio:.0%}, "
            f"{feat.schema_diversity} 种 schema"
        )
        click.echo(
            f"   旁白: 均 {feat.avg_narration_len:.0f} 字, "
            f"范围 [{feat.min_narration_len}, {feat.max_narration_len}]"
        )
        click.echo(f"   Schema: {', '.join(feat.schemas_used)}")
        click.echo(f"   Hook: {feat.hook_type}")

        db_path = cfg.output_dir / "assets.db"
        with AssetStore(db_path) as store:
            store.upsert_video_features(feat)
        click.echo("   ✅ 特征已写入 assets.db")

    @assets.command("refresh")
    @click.pass_obj
    def assets_refresh(cfg: Config):
        """月度保鲜扫描：标记过期素材"""
        from v2g.asset_store import AssetStore

        db_path = cfg.output_dir / "assets.db"
        with AssetStore(db_path) as store:
            marked = store.mark_stale()
            stale = store.count_stale()
            total = store.count()
            click.echo(f"🔄 本次标记 {marked} 个素材为 possibly_outdated")
            click.echo(f"   素材库: {total} 总量, {stale} 个过期")

    @assets.command("stats")
    @click.pass_obj
    def assets_stats(cfg: Config):
        """查看素材库统计"""
        from v2g.asset_store import AssetStore

        db_path = cfg.output_dir / "assets.db"
        if not db_path.exists():
            click.echo("❌ 素材库不存在，请先运行 v2g assets ingest")
            return

        with AssetStore(db_path) as store:
            total = store.count()
            stale = store.count_stale()
            click.echo("📊 素材库统计:")
            click.echo(f"   总量: {total}")
            click.echo(f"   过期: {stale}")

            engagement = store.aggregate_engagement()
            if engagement:
                click.echo("\n   📈 留存表现 (样本≥5):")
                for combo, score in engagement.items():
                    emoji = "↑" if score > 0 else "↓" if score < 0 else "→"
                    click.echo(f"      {emoji} {combo}: {score:+.2f}")

    @assets.command("list")
    @click.option("--query", default="", help="按关键词搜索（命中 notes/tags 等）")
    @click.option("--type", "visual_type", default="", help="按 visual_type 过滤")
    @click.option("--status", "rights_status", default="", help="按版权状态过滤")
    @click.option("--all", "show_all", is_flag=True, help="包含 reusable=0 素材")
    @click.option("--limit", default=30, type=int, help="最多展示数量")
    @click.pass_obj
    def assets_list(cfg: Config, query, visual_type, rights_status, show_all, limit):
        """列出素材（支持筛选和关键词检索）"""
        from v2g.asset_store import AssetStore

        db_path = cfg.output_dir / "assets.db"
        if not db_path.exists():
            click.echo("❌ 素材库不存在，请先运行 v2g assets ingest/resolve")
            return

        with AssetStore(db_path) as store:
            if query.strip():
                assets = store.search_text(query, limit=limit, reusable_only=not show_all)
                if visual_type:
                    assets = [a for a in assets if a.visual_type == visual_type]
                if rights_status:
                    assets = [a for a in assets if a.rights_status == rights_status]
            else:
                assets = store.list_assets(
                    reusable_only=not show_all,
                    visual_type=visual_type or None,
                    rights_status=rights_status or None,
                    limit=limit,
                )

        if not assets:
            click.echo("未找到匹配素材")
            return

        click.echo(f"📦 素材列表 ({len(assets)} 条):")
        for a in assets:
            click.echo(
                f"  [{a.clip_id}] {a.visual_type}/{a.mood} | rights={a.rights_status} "
                f"| reusable={int(a.reusable)} | {Path(a.file_path).name}"
            )
            if a.tags:
                click.echo(f"     tags: {', '.join(a.tags[:6])}")

    @assets.command("show")
    @click.argument("asset_id")
    @click.pass_obj
    def assets_show(cfg: Config, asset_id):
        """查看单个素材详情（含最近使用记录）"""
        from v2g.asset_store import AssetStore

        db_path = cfg.output_dir / "assets.db"
        with AssetStore(db_path) as store:
            asset = store.get(asset_id)
            if not asset:
                click.echo(f"❌ 素材不存在: {asset_id}")
                return
            usage = store.list_recent_usage(asset_id=asset_id, limit=10)

        click.echo(f"🧾 素材详情: {asset.clip_id}")
        click.echo(f"   file: {asset.file_path}")
        click.echo(f"   visual_type: {asset.visual_type}")
        click.echo(f"   mood: {asset.mood}")
        click.echo(f"   rights: {asset.rights_status}")
        click.echo(f"   license: {asset.license_type or '-'} / {asset.license_scope or '-'}")
        click.echo(f"   source: {asset.source_kind} | {asset.source_url or '-'}")
        click.echo(f"   reusable: {asset.reusable} | freshness: {asset.freshness}")
        click.echo(f"   expires_at: {asset.expires_at or '-'}")
        click.echo(f"   tags: {', '.join(asset.tags) if asset.tags else '-'}")
        click.echo(f"   products: {', '.join(asset.product) if asset.product else '-'}")
        click.echo(f"   notes: {asset.notes or '-'}")

        if usage:
            click.echo("\n   最近使用:")
            for row in usage:
                click.echo(
                    f"    - [{row.get('used_at', '')}] {row.get('project_id', '')} "
                    f"seg_{row.get('segment_id', 0)} role={row.get('asset_role', '')}"
                )
        else:
            click.echo("\n   最近使用: 暂无")

    @assets.command("set")
    @click.argument("asset_id")
    @click.option("--status", "rights_status", default=None, help="rights_status: cleared/unknown/restricted/expired")
    @click.option("--license-type", default=None, help="license_type")
    @click.option("--license-scope", default=None, help="license_scope")
    @click.option("--expires-at", default=None, help="到期日期 YYYY-MM-DD")
    @click.option("--reusable", default=None, type=click.Choice(["true", "false"]), help="是否可复用")
    @click.option("--mood", default=None, help="mood 标签")
    @click.option("--tags", default=None, help="逗号分隔标签")
    @click.option("--products", default=None, help="逗号分隔产品标签")
    @click.option("--note", default=None, help="更新备注")
    @click.option("--source-url", default=None, help="来源 URL")
    @click.option("--source-kind", default=None, help="source_kind")
    @click.option("--file-path", default=None, help="更新文件路径")
    @click.pass_obj
    def assets_set(
        cfg: Config,
        asset_id,
        rights_status,
        license_type,
        license_scope,
        expires_at,
        reusable,
        mood,
        tags,
        products,
        note,
        source_url,
        source_kind,
        file_path,
    ):
        """更新素材字段（版权/标签/可复用性）"""
        from v2g.asset_store import AssetStore

        updates = {
            "rights_status": rights_status,
            "license_type": license_type,
            "license_scope": license_scope,
            "expires_at": expires_at,
            "reusable": None if reusable is None else (reusable == "true"),
            "mood": mood,
            "tags": _split_csv(tags),
            "product": _split_csv(products),
            "notes": note,
            "source_url": source_url,
            "source_kind": source_kind,
            "file_path": file_path,
        }
        if all(v is None for v in updates.values()):
            raise click.ClickException("没有可更新字段，请至少传一个 --option")

        db_path = cfg.output_dir / "assets.db"
        with AssetStore(db_path) as store:
            updated = store.update_asset(asset_id, **updates)
            if not updated:
                raise click.ClickException(f"素材不存在: {asset_id}")

        click.echo(f"✅ 已更新: {asset_id}")
        click.echo(
            f"   rights={updated.rights_status}, reusable={updated.reusable}, "
            f"expires_at={updated.expires_at or '-'}"
        )

    @assets.command("approve")
    @click.argument("asset_id")
    @click.option("--scope", default="commercial", help="license_scope")
    @click.option("--license-type", default="manual_approved", help="license_type")
    @click.pass_obj
    def assets_approve(cfg: Config, asset_id, scope, license_type):
        """审批素材为可商用（cleared）"""
        from v2g.asset_store import AssetStore

        db_path = cfg.output_dir / "assets.db"
        with AssetStore(db_path) as store:
            updated = store.update_asset(
                asset_id,
                rights_status="cleared",
                license_scope=scope,
                license_type=license_type,
                reusable=True,
            )
            if not updated:
                raise click.ClickException(f"素材不存在: {asset_id}")
        click.echo(f"✅ 已审批: {asset_id} (scope={scope})")

    @assets.command("block")
    @click.argument("asset_id")
    @click.option("--reason", default="rights blocked", help="封禁原因")
    @click.pass_obj
    def assets_block(cfg: Config, asset_id, reason):
        """封禁素材（restricted + reusable=0）"""
        from v2g.asset_store import AssetStore

        db_path = cfg.output_dir / "assets.db"
        with AssetStore(db_path) as store:
            updated = store.update_asset(
                asset_id,
                rights_status="restricted",
                reusable=False,
                notes=reason,
            )
            if not updated:
                raise click.ClickException(f"素材不存在: {asset_id}")
        click.echo(f"⛔ 已封禁: {asset_id}")

    @assets.command("remove")
    @click.argument("asset_id")
    @click.option("--delete-file", is_flag=True, help="同时删除磁盘文件（谨慎）")
    @click.pass_obj
    def assets_remove(cfg: Config, asset_id, delete_file):
        """移除素材（可选删除文件）"""
        from v2g.asset_store import AssetStore

        db_path = cfg.output_dir / "assets.db"
        with AssetStore(db_path) as store:
            asset = store.get(asset_id)
            if not asset:
                raise click.ClickException(f"素材不存在: {asset_id}")

            removed = store.delete(asset_id)
            if not removed:
                raise click.ClickException(f"移除失败: {asset_id}")

        click.echo(f"🗑️ 已移除素材记录: {asset_id}")
        if delete_file:
            p = Path(asset.file_path)
            if p.exists():
                p.unlink()
                click.echo(f"   已删除文件: {p}")
            else:
                click.echo(f"   文件不存在，跳过: {p}")

    @assets.command("usage")
    @click.option("--asset-id", default=None, help="按 asset_id 过滤")
    @click.option("--project-id", default=None, help="按 project_id 过滤")
    @click.option("--limit", default=50, type=int, help="最多展示数量")
    @click.pass_obj
    def assets_usage(cfg: Config, asset_id, project_id, limit):
        """查看素材使用记录（asset_usage）"""
        from v2g.asset_store import AssetStore

        db_path = cfg.output_dir / "assets.db"
        with AssetStore(db_path) as store:
            rows = store.list_recent_usage(
                asset_id=asset_id,
                project_id=project_id,
                limit=limit,
            )
        if not rows:
            click.echo("暂无使用记录")
            return

        click.echo(f"📚 使用记录 ({len(rows)} 条):")
        for row in rows:
            click.echo(
                f"  - [{row.get('used_at', '')}] asset={row.get('asset_id', '')} "
                f"project={row.get('project_id', '')} seg_{row.get('segment_id', 0)} "
                f"role={row.get('asset_role', '')}"
            )

    @assets.command("annotate")
    @click.argument("project_id")
    @click.option(
        "--retention",
        "retention_csv",
        required=True,
        type=click.Path(exists=True),
        help="B 站留存率 CSV 文件路径",
    )
    @click.pass_obj
    def assets_annotate(cfg: Config, project_id, retention_csv):
        """完播率回标：将留存曲线映射到 segment"""
        from v2g.asset_store import AssetStore
        from v2g.retention import annotate_retention, print_retention_report

        db_path = cfg.output_dir / "assets.db"
        with AssetStore(db_path) as store:
            results = annotate_retention(cfg, project_id, Path(retention_csv), store)
            print_retention_report(results, project_id)

    @assets.command("fetch")
    @click.argument("project_id")
    @click.option("--bvid", required=True, help="B站 BV 号或视频链接")
    @click.pass_obj
    def assets_fetch(cfg: Config, project_id, bvid):
        """拉取 B站视频数据：公开 stats + 创作中心诊断(可选)"""
        from v2g.asset_store import AssetStore
        from v2g.bilibili import fetch_play_diagnosis, fetch_video_stats, extract_bvid

        bv = extract_bvid(bvid)
        if not bv:
            raise click.ClickException(f"无法解析 BV 号: {bvid}")

        click.echo(f"📊 获取视频数据: {bv}")
        stats = fetch_video_stats(bv)
        if not stats:
            raise click.ClickException("获取视频数据失败")

        click.echo(f"   标题: {stats.title}")
        click.echo(
            f"   播放: {stats.view_count:,}  点赞: {stats.like_count:,}  "
            f"投币: {stats.coin_count:,}  收藏: {stats.fav_count:,}"
        )

        diag = None
        if cfg.bilibili_sessdata:
            click.echo("🔄 获取创作中心诊断...")
            diag = fetch_play_diagnosis(bv, cfg.bilibili_sessdata, cfg.bilibili_bili_jct)
            if diag:
                click.echo(
                    f"   互动率: {diag.interact_rate / 100:.2f}%  "
                    f"流失率: {diag.crash_rate / 100:.2f}%  "
                    f"播转粉: {diag.play_trans_fan_rate / 100:.2f}%"
                )
                if diag.viewer_tags:
                    click.echo(f"   受众标签: {', '.join(diag.viewer_tags[:5])}")
                if diag.tip:
                    click.echo(f"   诊断: {diag.tip}")
            else:
                click.echo("   ⚠️ 诊断数据未获取到")
        else:
            click.echo("   💡 配置 BILIBILI_SESSDATA 可获取互动率/流失率/受众标签")

        db_path = cfg.output_dir / "assets.db"
        with AssetStore(db_path) as store:
            store.upsert_video_stats(
                bvid=bv,
                project_id=project_id,
                title=stats.title,
                view_count=stats.view_count,
                like_count=stats.like_count,
                coin_count=stats.coin_count,
                fav_count=stats.fav_count,
                share_count=stats.share_count,
                danmaku_count=stats.danmaku_count,
                reply_count=stats.reply_count,
                duration=stats.duration,
                interact_rate=diag.interact_rate if diag else 0,
                crash_rate=diag.crash_rate if diag else 0,
                play_trans_fan_rate=diag.play_trans_fan_rate if diag else 0,
                viewer_tags=diag.viewer_tags if diag else [],
                tip=diag.tip if diag else "",
            )
            click.echo("   ✅ 数据已写入 assets.db")

        state = PipelineState.load(cfg.output_dir, project_id)
        if not state.bvid:
            state.bvid = bv
            state.save(cfg.output_dir)
            click.echo(f"   ✅ BV 号已存入 checkpoint: {bv}")

    @assets.command("fetch-all")
    @click.pass_obj
    def assets_fetch_all(cfg: Config):
        """批量更新所有已关联 BV 号的视频数据"""
        import time

        from v2g.asset_store import AssetStore
        from v2g.bilibili import fetch_video_stats

        db_path = cfg.output_dir / "assets.db"
        if not db_path.exists():
            click.echo("素材库为空，请先用 assets fetch 关联视频")
            return

        with AssetStore(db_path) as store:
            pairs = store.all_bvids()
            if not pairs:
                pairs = _scan_bvids_from_checkpoints(cfg)
                if not pairs:
                    click.echo("未找到任何已关联的 BV 号")
                    return

            click.echo(f"📊 批量更新 {len(pairs)} 个视频...")
            updated = 0
            for i, (bvid, project_id) in enumerate(pairs):
                if i > 0:
                    time.sleep(1.0)
                stats = fetch_video_stats(bvid)
                if stats:
                    store.upsert_video_stats(
                        bvid=bvid,
                        project_id=project_id,
                        title=stats.title,
                        view_count=stats.view_count,
                        like_count=stats.like_count,
                        coin_count=stats.coin_count,
                        fav_count=stats.fav_count,
                        share_count=stats.share_count,
                        danmaku_count=stats.danmaku_count,
                        reply_count=stats.reply_count,
                        duration=stats.duration,
                    )
                    click.echo(f"   ✅ {bvid} ({project_id}): {stats.view_count:,} 播放")
                    updated += 1
                else:
                    click.echo(f"   ⚠️ {bvid} 获取失败")

            click.echo(f"\n✅ 更新完成: {updated}/{len(pairs)} 个视频")

    @assets.command("context")
    @click.option("--limit", default=30, type=int, help="最大素材数")
    @click.pass_obj
    def assets_context(cfg: Config, limit):
        """输出 LLM context 格式的素材列表"""
        from v2g.asset_store import AssetStore

        db_path = cfg.output_dir / "assets.db"
        if not db_path.exists():
            click.echo("素材库为空")
            return

        with AssetStore(db_path) as store:
            ctx = store.to_context(limit=limit)
            if ctx:
                click.echo(ctx)
            else:
                click.echo("素材库为空")

    @assets.command("prefetch")
    @click.option("--twitter", default=None, help="逗号分隔的 Twitter 用户名")
    @click.option("--person", default=None, help="逗号分隔的人物名（英文）")
    @click.option("--refresh", is_flag=True, help="强制重新下载（忽略缓存）")
    @click.pass_obj
    def assets_prefetch(cfg: Config, twitter, person, refresh):
        """预取素材：Twitter 头像 / 人物照片 / Meme 模板"""
        from v2g.asset_prefetch import prefetch_all

        out_dir = cfg.output_dir / "prefetch"
        twitter_users = [u.strip() for u in twitter.split(",")] if twitter else None
        persons = [p.strip() for p in person.split(",")] if person else None

        results = prefetch_all(
            out_dir,
            twitter_users=twitter_users,
            persons=persons,
            refresh=refresh,
        )
        click.echo(f"✅ 预取完成: {len(results)} 个素材")


def _scan_bvids_from_checkpoints(cfg: Config) -> list[tuple[str, str]]:
    """从 output/ 下的 checkpoint.json 中扫描 bvid。"""
    pairs = []
    output_dir = cfg.output_dir
    if not output_dir.exists():
        return pairs
    for cp_path in output_dir.glob("*/checkpoint.json"):
        try:
            data = json.loads(cp_path.read_text(encoding="utf-8"))
            bvid = data.get("bvid", "")
            if bvid:
                project_id = data.get("project_id") or data.get("video_id") or cp_path.parent.name
                pairs.append((bvid, project_id))
        except Exception:
            continue
    return pairs


def _split_csv(raw: str | None) -> list[str] | None:
    """Split comma separated values; None means 'not provided'."""
    if raw is None:
        return None
    vals = [v.strip() for v in raw.split(",") if v.strip()]
    return vals
