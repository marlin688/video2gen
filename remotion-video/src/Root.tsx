import { Composition } from "remotion";
import { VideoComposition } from "./VideoComposition";
import { SingleStylePreview, type SingleStyleProps } from "./SingleStylePreview";
import type { VideoCompositionProps, TimingMap } from "./types";

const FPS = 30;

/**
 * 动态计算视频总时长（基于 TTS 时长之和）
 */
const calculateMetadata = async ({
  props,
}: {
  props: VideoCompositionProps;
  defaultProps: VideoCompositionProps;
  abortSignal: AbortSignal;
  compositionId: string;
  isRendering: boolean;
}) => {
  const { timing } = props;
  const totalSeconds = Object.values(timing).reduce((sum, t) => sum + t.duration + (t.gap_after || 0), 0);
  const totalFrames = Math.ceil(totalSeconds * FPS);

  return {
    durationInFrames: Math.max(totalFrames, 1),
    fps: FPS,
    width: 1920,
    height: 1080,
  };
};

/**
 * 默认 props（空数据，实际渲染时通过 --props 传入）
 */
const defaultProps: VideoCompositionProps = {
  script: {
    title: "",
    description: "",
    tags: [],
    source_channel: "",
    total_duration_hint: 60,
    segments: [],
  },
  timing: {} as TimingMap,
  fps: FPS,
  slidesDir: "slides",
  recordingsDir: "recordings",
  sourceVideoFiles: [],
  sourceChannels: [],
  voiceoverFile: "voiceover.mp3",
  availableRecordings: [],
  theme: "tech-blue",
};

// ── 各组件预览数据 ───────────────────────────────────────────

const PREVIEWS: Record<string, SingleStyleProps> = {
  // ── slide ──
  "slide.tech-dark": {
    styleId: "slide.tech-dark",
    data: {
      schema: "slide",
      title: "AI Agent 架构演进",
      bullet_points: [
        "ReAct → Plan-and-Execute → Multi-Agent",
        "工具调用从 1 个到 N 个并行",
        "上下文管理: 滑动窗口 → RAG → 长期记忆",
      ],
      chart_hint: "steps",
    },
  },
  "slide.chalk-board": {
    styleId: "slide.chalk-board",
    data: {
      schema: "slide",
      title: "三种部署方案对比",
      bullet_points: [
        "云端 API: 零运维，按量付费，数据上云",
        "本地 Ollama: 零成本，完全隔离，算力受限",
        "混合方案: 敏感数据本地，非敏感走云端",
      ],
      chart_hint: "compare",
    },
  },
  "slide.glass-morphism": {
    styleId: "slide.glass-morphism",
    data: {
      schema: "slide",
      title: "2024 AI Coding 趋势",
      bullet_points: [
        "Cursor / Windsurf / Claude Code 三足鼎立",
        "Agent 模式成为标配: 自主规划 + 执行 + 验证",
        "MCP 协议统一工具生态",
        "多模态编程: 截图 → 代码",
      ],
    },
  },
  // ── terminal ──
  "terminal.aurora": {
    styleId: "terminal.aurora",
    data: {
      schema: "terminal",
      instruction: "演示 Claude Code 终端操作",
      session: [
        { type: "input" as const, text: "claude 'refactor the auth module'" },
        { type: "status" as const, text: "Thinking..." },
        { type: "tool" as const, name: "Read", target: "src/auth.ts", result: "Read 142 lines" },
        { type: "tool" as const, name: "Edit", target: "src/auth.ts", result: "Updated 3 functions" },
        { type: "output" as const, lines: ["✓ Refactored auth module", "  - Extracted validateToken()", "  - Removed dead code (38 lines)"] },
        { type: "blank" as const },
        { type: "status" as const, text: "Done in 12.3s · 2.1k tokens" },
      ],
    },
  },
  "terminal.vscode": {
    styleId: "terminal.vscode",
    data: {
      schema: "terminal",
      instruction: "VS Code 终端操作",
      session: [
        { type: "input" as const, text: "npm run test -- --coverage" },
        { type: "output" as const, lines: [
          "PASS  src/utils.test.ts (4 tests)",
          "PASS  src/api.test.ts (8 tests)",
          "FAIL  src/auth.test.ts (2 tests)",
          "",
          "Test Suites: 1 failed, 2 passed, 3 total",
          "Tests:       2 failed, 12 passed, 14 total",
          "Coverage:    87.3%",
        ]},
        { type: "input" as const, text: "# Fix failing tests" },
      ],
    },
  },
  // ── code-block ──
  "code-block.default": {
    styleId: "code-block.default",
    data: {
      schema: "code-block",
      fileName: "src/agent.ts",
      language: "typescript",
      code: [
        "import { Claude } from '@anthropic-ai/sdk';",
        "",
        "async function runAgent(task: string) {",
        "  const client = new Claude();",
        "  const tools = [fetchUrl, readFile, searchGithub];",
        "",
        "  // Phase 1: Plan",
        "  const plan = await client.plan(task, tools);",
        "",
        "  // Phase 2: Execute with tool use",
        "  for (const step of plan.steps) {",
        "    const result = await step.execute();",
        "    if (result.error) break;",
        "  }",
        "}",
      ],
      highlightLines: [7, 8, 11, 12],
      annotations: { "7": "先规划再执行", "11": "逐步调用工具" },
    },
  },
  // ── social-card ──
  "social-card.default": {
    styleId: "social-card.default",
    data: {
      schema: "social-card",
      platform: "twitter" as const,
      author: "@bcherny",
      text: "In the next version of Claude Code, we're introducing two new Skills: /simplify and /batch. I have been using both daily, and am excited to share them with everyone.",
      stats: { likes: 2847, retweets: 521, replies: 183 },
      subtitle: "Claude Code @anthropic",
    },
  },
  // ── diagram ──
  "diagram.default": {
    styleId: "diagram.default",
    data: {
      schema: "diagram",
      title: "Agent Pipeline",
      nodes: [
        { id: "fetch", label: "Fetch URLs", type: "primary" as const },
        { id: "outline", label: "Generate Outline", type: "default" as const },
        { id: "review", label: "Human Review", type: "warning" as const },
        { id: "script", label: "Write Script", type: "success" as const },
        { id: "render", label: "Render Video", type: "success" as const },
      ],
      edges: [
        { from: "fetch", to: "outline", label: "raw data" },
        { from: "outline", to: "review" },
        { from: "review", to: "script", label: "approved" },
        { from: "script", to: "render", label: "final" },
      ],
      direction: "LR" as const,
    },
  },
  "diagram.tree-card": {
    styleId: "diagram.tree-card",
    data: {
      schema: "diagram",
      title: "/tech-debt tailored per project",
      nodes: [
        { id: "root", label: "~/my-project", subtitle: "main repo" },
        {
          id: "app1", label: "SaaS App", type: "primary" as const,
          subtitle: "React + Node",
          items: [
            { text: "3 duplicated hooks", tag: "duplication" },
            { text: "unused components", tag: "unused" },
            { text: "missing TypeScript", tag: "types" },
          ],
          status: "✓ Complete",
        },
        {
          id: "app2", label: "CLI Tool", type: "warning" as const,
          subtitle: "Rust",
          items: [
            { text: "repeated error handling", tag: "pattern" },
            { text: "stale dependencies", tag: "deps" },
          ],
        },
        {
          id: "app3", label: "REST API", type: "danger" as const,
          subtitle: "Python + FastAPI",
          items: [
            { text: "N+1 query patterns", tag: "perf" },
            { text: "duplicate validators", tag: "duplication" },
            { text: "dead endpoints", tag: "unused" },
          ],
        },
      ],
      edges: [
        { from: "root", to: "app1" },
        { from: "root", to: "app2" },
        { from: "root", to: "app3" },
      ],
    },
  },
  "diagram.pipeline": {
    styleId: "diagram.pipeline",
    data: {
      schema: "diagram",
      title: "Skillify Workflow",
      nodes: [
        { id: "brainstorm", label: "BRAINSTORM", icon: "💬", keywords: ["record", "session"] },
        { id: "refine", label: "REFINE", type: "warning" as const, icon: "🔄", keywords: ["iterate", "process"] },
        { id: "extract", label: "EXTRACT", type: "primary" as const, icon: "⚙️", keywords: ["identify", "patterns"] },
        { id: "output", label: "skill.md", type: "success" as const, icon: "📄", keywords: ["reusable", "skill"], items: [{ text: "reusable skill" }] },
      ],
      edges: [
        { from: "brainstorm", to: "refine" },
        { from: "refine", to: "extract" },
        { from: "extract", to: "output" },
      ],
      direction: "LR" as const,
    },
  },
  "diagram.dual-card": {
    styleId: "diagram.dual-card",
    data: {
      schema: "diagram",
      nodes: [
        {
          id: "agent", label: "Agent", type: "primary" as const,
          subtitle: "making changes",
          items: [
            { text: "src/auth.ts", tag: "modified" },
            { text: "src/middleware.ts", tag: "modified" },
            { text: "src/session.ts", tag: "created" },
          ],
          status: "needs confirmation...",
        },
        {
          id: "verify", label: "/verify", type: "warning" as const,
          subtitle: "skill",
          items: [
            { text: "TypeScript build", tag: "0 errors" },
            { text: "Unit tests", tag: "::" },
            { text: "Integration tests", tag: "□" },
            { text: "Lint & format", tag: "□" },
          ],
        },
      ],
      edges: [{ from: "agent", to: "verify" }],
    },
  },
  // ── hero-stat ──
  "hero-stat.default": {
    styleId: "hero-stat.default",
    data: {
      schema: "hero-stat",
      stats: [
        { value: "11.8K", label: "GitHub Stars", trend: "up" as const },
        { value: "6.8K", label: "Forks", trend: "up" as const },
        { value: "$0", label: "Monthly Cost", oldValue: "$200", trend: "down" as const },
      ],
    },
  },
  "hero-stat.progress": {
    styleId: "hero-stat.progress",
    data: {
      schema: "hero-stat",
      stats: [
        { value: "92%", label: "reuse", trend: "up" as const },
        { value: "88%", label: "quality", trend: "neutral" as const },
        { value: "95%", label: "efficiency", trend: "up" as const },
        { value: "73%", label: "coverage", trend: "down" as const },
      ],
      footnote: "evaluation metrics",
    },
  },
  // ── browser ──
  "browser.default": {
    styleId: "browser.default",
    data: {
      schema: "browser",
      url: "https://github.com/anthropics/claude-code",
      tabTitle: "anthropics/claude-code",
      pageTitle: "Claude Code",
      contentLines: [
        "An agentic coding tool that lives in your terminal.",
        "",
        "Claude Code understands your codebase, helps you write code,",
        "fix bugs, and ship features — all from the command line.",
        "",
        "⭐ 25.6K stars  |  🔀 2.1K forks  |  MIT License",
      ],
      theme: "dark" as const,
    },
  },
  "browser.github": {
    styleId: "browser.github",
    data: {
      schema: "browser",
      url: "https://github.com/anthropics/claude-code",
      tabTitle: "anthropics/claude-code",
      contentLines: [
        "# Frontend Design Plugin",
        "",
        "Generates distinctive, production-grade frontend interfaces that avoid generic AI aesthetics.",
      ],
      repoInfo: {
        owner: "anthropics",
        repo: "claude-code",
        branch: "main",
        path: ["plugins", "frontend-design"],
        commitAuthor: "ThariqS and claude",
        commitMessage: "feat: Add plugin.json metadata for frontend-design plugin",
        commitHash: "c91e3f2",
        files: [
          { name: ".claude-plugin", type: "dir" as const, commitMessage: "feat: Add plugin.json metadata for frontend-design plugin" },
          { name: "skills/frontend-design", type: "dir" as const, commitMessage: "feat: Add frontend-design plugin to marketplace", highlight: true },
          { name: "README.md", type: "file" as const, commitMessage: "feat: Add frontend-design plugin to marketplace" },
        ],
        stars: "5k+",
        issues: "416",
        pullRequests: "28",
      },
    },
  },
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const AnyComposition = Composition as any;

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* 主合成（生产渲染用） */}
      <AnyComposition
        id="V2GVideo"
        component={VideoComposition}
        durationInFrames={FPS * 60}
        fps={FPS}
        width={1920}
        height={1080}
        defaultProps={defaultProps}
        calculateMetadata={calculateMetadata}
      />

      {/* 各组件独立预览（Composition ID 不能含点号，用连字符替换） */}
      {Object.entries(PREVIEWS).map(([id, props]) => (
        <AnyComposition
          key={id}
          id={id.replace(/\./g, "-")}
          component={SingleStylePreview}
          durationInFrames={FPS * 6}
          fps={FPS}
          width={1920}
          height={1080}
          defaultProps={props}
        />
      ))}
    </>
  );
};
