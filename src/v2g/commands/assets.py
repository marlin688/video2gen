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
