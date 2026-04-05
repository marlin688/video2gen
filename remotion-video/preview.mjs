#!/usr/bin/env node
/**
 * video2gen 静帧预览：渲染每段 segment 的关键帧 PNG。
 *
 * 用法:
 *   node preview.mjs <video_id> [--output-dir <path>] [--sources-dir <path>]
 *
 * 输出:
 *   output/{video_id}/preview/seg_{n}.png  — 各段关键帧
 *
 * 比完整渲染快 10x+，用于人工审核视觉效果。
 */

import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// 解析参数
const args = process.argv.slice(2);
const videoId = args[0];
if (!videoId) {
  console.error("用法: node preview.mjs <video_id> [--output-dir <path>]");
  process.exit(1);
}

const outputDirIdx = args.indexOf("--output-dir");
const v2gOutputDir = outputDirIdx !== -1
  ? args[outputDirIdx + 1]
  : path.resolve(__dirname, "..", "output");

const videoDir = path.join(v2gOutputDir, videoId);

// 检查必要文件
const scriptPath = path.join(videoDir, "script.json");
let timingPath = path.join(videoDir, "voiceover", "timing.json");
if (!fs.existsSync(timingPath)) {
  timingPath = path.join(videoDir, "voiceover_timing.json");
}

if (!fs.existsSync(scriptPath)) {
  console.error(`脚本不存在: ${scriptPath}`);
  process.exit(1);
}
if (!fs.existsSync(timingPath)) {
  console.error(`timing 不存在: ${timingPath}`);
  process.exit(1);
}

const script = JSON.parse(fs.readFileSync(scriptPath, "utf-8"));
const timing = JSON.parse(fs.readFileSync(timingPath, "utf-8"));

// 准备 public 目录（最小化：只拷贝 slides，不拷贝视频/录屏/音频）
const publicDir = path.join(__dirname, "public");
fs.mkdirSync(publicDir, { recursive: true });

// 复制 slides
const slidesSrc = path.join(videoDir, "slides");
const slidesDst = path.join(publicDir, "slides");
if (fs.existsSync(slidesSrc)) {
  fs.cpSync(slidesSrc, slidesDst, { recursive: true });
}

// 复制 images（图片叠加素材，preview 需要显示）
const imagesSrc = path.join(videoDir, "images");
const imagesDst = path.join(publicDir, "images");
if (fs.existsSync(imagesSrc)) {
  fs.cpSync(imagesSrc, imagesDst, { recursive: true });
}

// 空 recordings 目录（preview 不需要录屏）
const recDst = path.join(publicDir, "recordings");
if (!fs.existsSync(recDst)) fs.mkdirSync(recDst, { recursive: true });

// 主题
const checkpointPath = path.join(videoDir, "checkpoint.json");
const themeId = (() => {
  if (process.env.V2G_THEME) return process.env.V2G_THEME;
  if (fs.existsSync(checkpointPath)) {
    try {
      const cp = JSON.parse(fs.readFileSync(checkpointPath, "utf-8"));
      if (cp.theme) return cp.theme;
    } catch {}
  }
  return "tech-blue";
})();

// 输出目录
const previewDir = path.join(videoDir, "preview");
fs.mkdirSync(previewDir, { recursive: true });

console.log(`🖼️  静帧预览: ${videoId}`);
console.log(`   段落数: ${script.segments.length}`);
console.log(`   主题: ${themeId}`);

async function main() {
  console.log("📦 打包 Remotion 项目...");
  const bundled = await bundle({
    entryPoint: path.join(__dirname, "src/index.ts"),
    webpackOverride: (config) => config,
  });

  let rendered = 0;
  for (const seg of script.segments) {
    const t = timing[String(seg.id)];
    if (!t) continue;

    // 构建单段 props
    const singleScript = {
      title: script.title || "",
      description: script.description || "",
      tags: script.tags || [],
      source_channel: script.source_channel || "",
      total_duration_hint: t.duration,
      segments: [seg],
    };
    const singleTiming = { [String(seg.id)]: t };

    const inputProps = {
      script: singleScript,
      timing: singleTiming,
      fps: 30,
      slidesDir: "slides",
      recordingsDir: "recordings",
      sourceVideoFiles: [],
      sourceChannels: [],
      voiceoverFile: "voiceover.mp3",
      availableRecordings: [],
      theme: themeId,
    };

    const composition = await selectComposition({
      serveUrl: bundled,
      id: "V2GVideo",
      inputProps,
    });

    const outputPath = path.join(previewDir, `seg_${seg.id}.png`);

    await renderStill({
      serveUrl: bundled,
      composition,
      output: outputPath,
      inputProps,
      frame: 60, // ~2s, 动画完成
      imageFormat: "png",
    });

    const material = seg.material || "?";
    const comp = seg.component || `${material}-default`;
    console.log(`   ✅ seg_${seg.id} [${material}] ${comp} → ${path.basename(outputPath)}`);
    rendered++;
  }

  // 清理 public（和 render.mjs 一致）
  try {
    if (fs.existsSync(slidesDst)) fs.rmSync(slidesDst, { recursive: true, force: true });
  } catch {}

  console.log(`\n🎉 预览完成: ${rendered} 张`);
  console.log(`   📂 ${previewDir}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
