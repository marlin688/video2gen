#!/usr/bin/env node
/**
 * video2gen Remotion 渲染脚本
 *
 * 用法:
 *   node render.mjs <video_id> [--output-dir <path>] [--sources-dir <path>]
 *
 * 目录结构:
 *   sources/{video_id}/          — 输入素材 (视频 + 字幕)
 *   output/{project_id}/         — 项目工作目录
 *     voiceover/full.mp3         — TTS 配音
 *     voiceover/timing.json      — 时间轴
 *     slides/                    — 幻灯片
 *     recordings/                — 录屏
 *     final/video.mp4            — 最终视频
 *     final/subtitles.srt        — SRT 字幕
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
  console.error("用法: node render.mjs <video_id> [--output-dir <path>] [--sources-dir <path>]");
  process.exit(1);
}

const outputDirIdx = args.indexOf("--output-dir");
const v2gOutputDir = outputDirIdx !== -1
  ? args[outputDirIdx + 1]
  : path.resolve(__dirname, "..", "output");

const sourcesDirIdx = args.indexOf("--sources-dir");
const sourcesDir = sourcesDirIdx !== -1
  ? args[sourcesDirIdx + 1]
  : path.resolve(__dirname, "..", "sources");

const videoDir = path.join(v2gOutputDir, videoId);
const finalDir = path.join(videoDir, "final");
fs.mkdirSync(finalDir, { recursive: true });

// 检查必要文件
const scriptPath = path.join(videoDir, "script.json");

// 查找 timing.json（新路径优先，向后兼容旧路径）
let timingPath = path.join(videoDir, "voiceover", "timing.json");
if (!fs.existsSync(timingPath)) {
  timingPath = path.join(videoDir, "voiceover_timing.json");
}

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
function copyAsset(src, dst) {
  const absSrc = path.resolve(src);
  if (!fs.existsSync(absSrc)) return;
  if (fs.existsSync(dst)) {
    const srcStat = fs.statSync(absSrc);
    const dstStat = fs.statSync(dst);
    if (srcStat.isDirectory()) return;
    if (srcStat.size === dstStat.size) return;
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

// 复制配音文件（新路径优先，向后兼容旧路径）
let voiceoverSrc = path.join(videoDir, "voiceover", "full.mp3");
if (!fs.existsSync(voiceoverSrc)) {
  voiceoverSrc = path.join(videoDir, "voiceover.mp3");
}
copyAsset(voiceoverSrc, path.join(publicDir, "voiceover.mp3"));

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

/**
 * 查找源视频文件: 依次在 sources/{video_id}/, output/subtitle/{video_id}/ 中搜索
 */
function findSourceVideo(videoId) {
  const searchDirs = [
    path.join(sourcesDir, videoId),                             // sources/{video_id} (新路径)
    path.join(v2gOutputDir, "subtitle", videoId),               // output/subtitle/{video_id} (旧路径)
  ];
  for (const dir of searchDirs) {
    if (!fs.existsSync(dir)) continue;
    const vFiles = fs.readdirSync(dir).filter(
      f => [".mp4", ".webm", ".mkv"].some(ext => f.endsWith(ext)) && !f.endsWith(".part")
    );
    if (vFiles.length > 0) return path.join(dir, vFiles[0]);
  }
  return null;
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

      // fallback: 在 sources/ 或 output/subtitle/ 目录找
      if (!videoPath || !fs.existsSync(videoPath)) {
        videoPath = findSourceVideo(src.video_id);
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

// fallback: 在 sources/ 目录直接搜索
if (sourceVideoFiles.length === 0) {
  const videoPath = findSourceVideo(videoId);
  if (videoPath) {
    prepareSourceVideo(videoPath, "source_0.mp4");
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

// 主题: 从 checkpoint 或环境变量读取（默认 tech-blue）
const themeId = (() => {
  if (process.env.V2G_THEME) return process.env.V2G_THEME;
  if (fs.existsSync(checkpointPath)) {
    const cp = JSON.parse(fs.readFileSync(checkpointPath, "utf-8"));
    if (cp.theme) return cp.theme;
  }
  return "tech-blue";
})();
console.log(`   主题: ${themeId}`);

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
  theme: themeId,
};

// ═══ SRT 字幕生成 ═══

// 尝试加载 word_timing.json (mlx-whisper 词级对齐)
const wordTimingPath = path.join(outputDir, "voiceover", "word_timing.json");
let wordTiming = null;
if (fs.existsSync(wordTimingPath)) {
  wordTiming = JSON.parse(fs.readFileSync(wordTimingPath, "utf-8"));
  console.log(`   词级对齐: ✅ (${Object.keys(wordTiming).length} 段)`);
} else {
  console.log(`   词级对齐: ❌ 使用字符均分`);
}

/**
 * 从 word_timing 生成精确 SRT entries (按 ≤36 字符打包)
 */
function splitFromWordTiming(words, segDuration) {
  if (!words || words.length === 0) return [{ text: "", start: 0, end: segDuration }];

  const entries = [];
  let buf = "";
  let bufStart = words[0].start;

  for (const w of words) {
    if (buf.length + w.word.length > 36 && buf.length > 0) {
      // flush
      entries.push({ text: buf, start: bufStart, end: w.start });
      buf = w.word;
      bufStart = w.start;
    } else {
      buf += w.word;
    }
  }
  if (buf) {
    entries.push({ text: buf, start: bufStart, end: words[words.length - 1].end });
  }
  return entries;
}

function splitNarration(text, durationSec) {
  const parts = text.split(/(?<=[。！？；])/).filter(p => p.trim());
  if (parts.length === 0) return [{ text, start: 0, end: durationSec }];

  const merged = [];
  for (const p of parts) {
    if (merged.length > 0 && merged[merged.length - 1].length < 6) {
      merged[merged.length - 1] += p;
    } else {
      merged.push(p.trim());
    }
  }

  const final = [];
  for (const m of merged) {
    if (m.length <= 36) {
      final.push(m);
    } else {
      const subs = m.split(/(?<=[，,])/).filter(s => s.trim());
      let buf = "";
      for (const s of subs) {
        if (buf.length + s.length <= 36) {
          buf += s;
        } else {
          if (buf) final.push(buf);
          buf = s;
        }
      }
      if (buf) final.push(buf);
    }
  }

  const totalChars = final.reduce((a, f) => a + f.length, 0) || 1;
  const entries = [];
  let t = 0;
  for (const txt of final) {
    const dur = (durationSec * txt.length) / totalChars;
    entries.push({ text: txt, start: t, end: t + dur });
    t += dur;
  }
  return entries;
}

function formatSrtTime(sec) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  const ms = Math.round((sec % 1) * 1000);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")},${String(ms).padStart(3, "0")}`;
}

function generateSrt(script, timing) {
  const lines = [];
  let idx = 1;
  let currentTime = 0;

  for (const seg of script.segments) {
    const t = timing[String(seg.id)];
    if (!t) continue;
    const duration = t.duration;

    if (seg.narration_zh) {
      // 优先使用 word_timing (mlx-whisper 精确对齐)，否则回退字符均分
      const segWords = wordTiming && wordTiming[String(seg.id)];
      const entries = segWords
        ? splitFromWordTiming(segWords, duration)
        : splitNarration(seg.narration_zh, duration);
      for (const e of entries) {
        const absStart = currentTime + e.start;
        const absEnd = currentTime + e.end;
        lines.push(`${idx}`);
        lines.push(`${formatSrtTime(absStart)} --> ${formatSrtTime(absEnd)}`);
        lines.push(e.text);
        lines.push("");
        idx++;
      }
    }

    currentTime += duration;
  }
  return lines.join("\n");
}

// 生成 SRT 字幕到 final/ 目录
const srtContent = generateSrt(script, timing);
const srtPath = path.join(finalDir, "subtitles.srt");
fs.writeFileSync(srtPath, srtContent, "utf-8");
console.log(`📝 字幕文件: ${srtPath}`);

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

  // 3. 渲染到 final/ 目录
  const outputPath = path.join(finalDir, "video.mp4");
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

  console.log(`\n✅ 渲染完成!`);
  const stats = fs.statSync(outputPath);
  console.log(`   视频: ${outputPath} (${(stats.size / 1024 / 1024).toFixed(1)}MB)`);
  console.log(`   字幕: ${srtPath}`);

  // 4. 清理 public/ 缓存（避免跨项目污染）
  console.log("🧹 清理 public/ 缓存...");
  const cleanTargets = ["voiceover.mp3", "slides", "recordings"];
  // 清理源视频缓存
  for (const f of fs.readdirSync(publicDir)) {
    if (f.startsWith("source_") && f.endsWith(".mp4")) cleanTargets.push(f);
    if (f.startsWith("src-video")) cleanTargets.push(f);
  }
  for (const target of cleanTargets) {
    const p = path.join(publicDir, target);
    if (!fs.existsSync(p)) continue;
    if (fs.statSync(p).isDirectory()) {
      fs.rmSync(p, { recursive: true });
    } else {
      fs.unlinkSync(p);
    }
  }
  console.log("   ✅ 已清理");
}

main().catch((err) => {
  console.error("❌ 渲染失败:", err.message);
  process.exit(1);
});
