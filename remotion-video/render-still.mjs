/**
 * 快速渲染单个 slide 组件为 PNG，用于预览。
 * 用法: node render-still.mjs
 */

import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// 测试数据：取几种不同布局
const testSegments = [
  {
    id: 1, type: "body", material: "A",
    narration_zh: "test",
    slide_content: {
      title: "封号玄学终结者",
      bullet_points: [
        "换IP: 无效",
        "换卡: 无效",
        "换设备: 无效",
        "真正原因: source map 泄露后 Anthropic 加强了风控策略",
      ],
      chart_hint: "",
    },
  },
  {
    id: 4, type: "body", material: "A",
    narration_zh: "test",
    slide_content: {
      title: "Claude Code 五层架构拆解",
      bullet_points: [
        "第1层: 入口层 — CLI 解析与环境初始化",
        "第2层: 对话编排层 — QueryEngine.ts（4.6万行）",
        "第3层: 提示词记忆层 — 三层记忆 + 9段式压缩",
        "第4层: 工具执行层 — 85个斜杠命令 + 12种内置工具",
        "第5层: 安全审计层 — 权限引擎 + 沙箱隔离",
      ],
      chart_hint: "",
    },
  },
  {
    id: 6, type: "body", material: "A",
    narration_zh: "test",
    slide_content: {
      title: "源码里的四个隐藏功能",
      bullet_points: [
        "卧底模式: 检测到 Anthropic 员工时自动抹除 AI 痕迹",
        "KAIROS 守护进程: 永不离线的后台 Agent，空闲时整理记忆",
        "情绪遥测: 追踪爆粗口频率与连续 continue 次数",
        "内部标记: user_type=ant 解锁隐藏开关",
      ],
      chart_hint: "网格布局",
    },
  },
];

async function main() {
  console.log("Bundling...");
  const bundled = await bundle({
    entryPoint: path.join(__dirname, "src/index.ts"),
    webpackOverride: (config) => config,
  });

  const outDir = path.join(__dirname, "out", "stills");
  const { mkdirSync } = await import("fs");
  mkdirSync(outDir, { recursive: true });

  for (const seg of testSegments) {
    const script = {
      title: "test",
      description: "",
      tags: [],
      source_channel: "",
      total_duration_hint: 60,
      segments: [seg],
    };

    const timing = {
      [String(seg.id)]: { file: "test.mp3", duration: 8, text_length: 20 },
    };

    const inputProps = {
      script,
      timing,
      fps: 30,
      slidesDir: "slides",
      recordingsDir: "recordings",
      sourceVideoFiles: [],
      sourceChannels: [],
      voiceoverFile: "voiceover.mp3",
      availableRecordings: [],
    };

    console.log(`Rendering seg ${seg.id}: "${seg.slide_content.title}"...`);

    const composition = await selectComposition({
      serveUrl: bundled,
      id: "V2GVideo",
      inputProps,
    });

    const outputPath = path.join(outDir, `slide_seg${seg.id}.png`);

    await renderStill({
      serveUrl: bundled,
      composition,
      output: outputPath,
      inputProps,
      frame: 60, // ~2s in, animations should be done
      imageFormat: "png",
    });

    console.log(`  → ${outputPath}`);
  }

  console.log("\nDone! Check out/stills/");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
