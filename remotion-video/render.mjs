#!/usr/bin/env node
/**
 * video2gen Remotion 渲染脚本
 *
 * 用法:
 *   node render.mjs <video_id> [--output-dir <path>]
 *
 * 自动从 v2g output 目录读取 script.json、voiceover_timing.json，
 * 将素材文件链接到 public/，然后调用 Remotion 渲染。
 */

import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// FFmpeg/FFprobe 路径（尽早初始化，后续转码需要）
let FFMPEG = "ffmpeg";
let FFPROBE = "ffprobe";
try {
  const venvPython = path.resolve(__dirname, "..", "..", "lecture2note", ".venv", "bin", "python3");
  if (fs.existsSync(venvPython)) {
    FFMPEG = execSync(`${venvPython} -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"`, { timeout: 5000 }).toString().trim();
    const probePath = path.join(path.dirname(FFMPEG), "ffprobe");
    if (fs.existsSync(probePath)) FFPROBE = probePath;
  }
} catch { /* fallback to system ffmpeg */ }

// 解析参数
const args = process.argv.slice(2);
const videoId = args[0];
if (!videoId) {
  console.error("用法: node render.mjs <video_id> [--output-dir <path>]");
  process.exit(1);
}

const outputDirIdx = args.indexOf("--output-dir");
const v2gOutputDir = outputDirIdx !== -1
  ? args[outputDirIdx + 1]
  : path.resolve(__dirname, "..", "output");

const videoDir = path.join(v2gOutputDir, videoId);
const subtitleDir = path.join(v2gOutputDir, "subtitle", videoId);

// 检查必要文件
const scriptPath = path.join(videoDir, "script.json");
const timingPath = path.join(videoDir, "voiceover_timing.json");

if (!fs.existsSync(scriptPath)) {
  console.error(`脚本不存在: ${scriptPath}`);
  process.exit(1);
}

// 读取数据
const script = JSON.parse(fs.readFileSync(scriptPath, "utf-8"));
const timing = JSON.parse(fs.readFileSync(timingPath, "utf-8"));

// 准备 public 目录（链接素材文件）
const publicDir = path.join(__dirname, "public");
fs.mkdirSync(publicDir, { recursive: true });

// 辅助: 硬拷贝文件到 public（Remotion 不支持 symlink）
// 如果源文件大小不同则覆盖（避免用旧项目的缓存）
function copyAsset(src, dst) {
  const absSrc = path.resolve(src);
  if (!fs.existsSync(absSrc)) return;
  if (fs.existsSync(dst)) {
    const srcStat = fs.statSync(absSrc);
    const dstStat = fs.statSync(dst);
    if (srcStat.isDirectory()) {
      // 目录: 如果已存在就跳过（不好比较）
      return;
    }
    if (srcStat.size === dstStat.size) return; // 大小相同则跳过
    // 大小不同，覆盖
    console.log(`   覆盖: ${path.basename(dst)} (${dstStat.size} → ${srcStat.size})`);
  }
  if (fs.statSync(absSrc).isDirectory()) {
    fs.cpSync(absSrc, dst, { recursive: true });
    console.log(`   复制目录: ${path.basename(dst)}`);
  } else {
    fs.copyFileSync(absSrc, dst);
    console.log(`   复制: ${path.basename(dst)}`);
  }
}

// 复制配音文件
copyAsset(path.join(videoDir, "voiceover.mp3"), path.join(publicDir, "voiceover.mp3"));

// 复制 slides 目录
copyAsset(path.join(videoDir, "slides"), path.join(publicDir, "slides"));

// 复制/创建 recordings 目录
const recordingsSrc = path.join(videoDir, "recordings");
const recordingsDst = path.join(publicDir, "recordings");
if (!fs.existsSync(recordingsDst)) {
  if (fs.existsSync(recordingsSrc)) {
    fs.cpSync(recordingsSrc, recordingsDst, { recursive: true });
  } else {
    fs.mkdirSync(recordingsDst, { recursive: true });
  }
}

// 准备源视频 (支持多源和单源)
const checkpointPath = path.join(videoDir, "checkpoint.json");
const sourceVideoFiles = [];
const sourceChannels = [];

function prepareSourceVideo(srcPath, destName) {
  const dst = path.join(publicDir, destName);
  if (fs.existsSync(dst)) { return; }
  if (!srcPath || !fs.existsSync(srcPath)) { return; }

  let needsTranscode = false;
  try {
    const probe = execSync(
      `${FFPROBE} -v quiet -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "${srcPath}"`,
      { timeout: 10000 }
    ).toString().trim();
    needsTranscode = probe.includes("av1") || probe.includes("vp9");
    if (needsTranscode) console.log(`   ⚠️ ${destName}: ${probe} → 转码为 H.264...`);
  } catch { needsTranscode = true; }

  if (needsTranscode) {
    try {
      execSync(
        `"${FFMPEG}" -y -i "${srcPath}" -c:v libx264 -preset fast -crf 22 -pix_fmt yuv420p -c:a aac "${dst}"`,
        { timeout: 600000, stdio: "pipe" }
      );
      console.log(`   ✅ ${destName}`);
    } catch (e) {
      console.log(`   ❌ 转码失败: ${e.message?.slice(0, 80)}`);
      fs.copyFileSync(srcPath, dst);
    }
  } else {
    fs.copyFileSync(srcPath, dst);
    console.log(`   复制: ${destName}`);
  }
}

if (fs.existsSync(checkpointPath)) {
  const cp = JSON.parse(fs.readFileSync(checkpointPath, "utf-8"));

  if (cp.sources && cp.sources.length > 0) {
    // 多源模式
    console.log(`   多源模式: ${cp.sources.length} 个视频`);
    for (let i = 0; i < cp.sources.length; i++) {
      const src = cp.sources[i];
      const destName = `source_${i}.mp4`;
      let videoPath = src.source_video_path;

      // fallback: 在 subtitle 目录找
      if (!videoPath || !fs.existsSync(videoPath)) {
        const subDir = path.join(v2gOutputDir, "subtitle", src.video_id);
        if (fs.existsSync(subDir)) {
          const vFiles = fs.readdirSync(subDir).filter(
            f => [".mp4", ".webm", ".mkv"].some(ext => f.endsWith(ext)) && !f.endsWith(".part")
          );
          if (vFiles.length > 0) videoPath = path.join(subDir, vFiles[0]);
        }
      }

      if (videoPath && fs.existsSync(videoPath)) {
        prepareSourceVideo(videoPath, destName);
        sourceVideoFiles.push(destName);
      } else {
        console.log(`   ⚠️ 源视频 ${i} 不可用: ${src.video_id}`);
        sourceVideoFiles.push("");
      }
      sourceChannels.push(src.channel_name || `Source ${i}`);
    }
  } else if (cp.source_video && fs.existsSync(cp.source_video)) {
    // 单源模式
    prepareSourceVideo(cp.source_video, "source_0.mp4");
    sourceVideoFiles.push("source_0.mp4");
    sourceChannels.push(cp.source_channel || "");
  }
}

// fallback: subtitle 目录
if (sourceVideoFiles.length === 0 && fs.existsSync(subtitleDir)) {
  const vFiles = fs.readdirSync(subtitleDir).filter(
    f => [".mp4", ".webm", ".mkv"].some(ext => f.endsWith(ext)) && !f.endsWith(".part")
  );
  if (vFiles.length > 0) {
    prepareSourceVideo(path.join(subtitleDir, vFiles[0]), "source_0.mp4");
    sourceVideoFiles.push("source_0.mp4");
    sourceChannels.push("");
  }
}

if (sourceVideoFiles.length === 0) {
  console.log("   ⚠️ 未找到任何源视频");
}

// Chrome 浏览器路径
const chromePath = process.env.REMOTION_CHROME_EXECUTABLE
  || path.join(
    process.env.HOME || "",
    "Library/Caches/ms-playwright/chromium_headless_shell-1208/chrome-headless-shell-mac-arm64/chrome-headless-shell"
  );

// 扫描已有录屏文件
const availableRecordings = [];
const recDir = path.join(publicDir, "recordings");
if (fs.existsSync(recDir)) {
  for (const f of fs.readdirSync(recDir)) {
    const m = f.match(/^seg_(\d+)\.(mp4|mov|webm|mkv)$/);
    if (m) availableRecordings.push(parseInt(m[1]));
  }
}
console.log(`   录屏素材: ${availableRecordings.length > 0 ? availableRecordings.map(id => `seg_${id}`).join(", ") : "无"}`);

// 构建 props
const inputProps = {
  script,
  timing,
  fps: 30,
  slidesDir: "slides",
  recordingsDir: "recordings",
  sourceVideoFiles,
  sourceChannels,
  voiceoverFile: "voiceover.mp3",
  availableRecordings,
};

console.log("🎬 Remotion 渲染");
console.log(`   视频 ID: ${videoId}`);
console.log(`   段落数: ${script.segments.length}`);
console.log(`   Chrome: ${chromePath}`);

async function main() {
  // 1. Bundle
  console.log("📦 打包 Remotion 项目...");
  const bundled = await bundle({
    entryPoint: path.join(__dirname, "src/index.ts"),
    webpackOverride: (config) => config,
  });

  // 2. 获取 composition 元数据
  console.log("📐 计算视频参数...");
  const composition = await selectComposition({
    serveUrl: bundled,
    id: "V2GVideo",
    inputProps,
    browserExecutable: chromePath,
  });

  console.log(`   分辨率: ${composition.width}x${composition.height}`);
  console.log(`   时长: ${composition.durationInFrames} 帧 (${(composition.durationInFrames / 30).toFixed(1)}s)`);

  // 3. 渲染
  const outputPath = path.join(videoDir, "final_remotion.mp4");
  console.log(`🎨 渲染中... → ${outputPath}`);

  await renderMedia({
    composition,
    serveUrl: bundled,
    codec: "h264",
    outputLocation: outputPath,
    inputProps,
    browserExecutable: chromePath,
    onProgress: ({ progress }) => {
      if (Math.round(progress * 100) % 10 === 0) {
        process.stdout.write(`\r   进度: ${Math.round(progress * 100)}%`);
      }
    },
  });

  console.log(`\n✅ 渲染完成: ${outputPath}`);
  const stats = fs.statSync(outputPath);
  console.log(`   文件大小: ${(stats.size / 1024 / 1024).toFixed(1)}MB`);
}

main().catch((err) => {
  console.error("❌ 渲染失败:", err.message);
  process.exit(1);
});
