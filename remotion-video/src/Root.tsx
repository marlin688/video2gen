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
  "slide.compare-table": {
    styleId: "slide.compare-table",
    data: {
      schema: "slide",
      title: "Claude Code vs Cursor",
      bullet_points: [
        "价格: $200/月 → $20/月",
        "模型: Claude only → 多模型切换",
        "界面: 终端 CLI → GUI 编辑器",
        "Agent: 原生支持 → 插件集成",
        "隐私: 遥测上传 → 本地优先",
      ],
    },
  },
  "slide.timeline": {
    styleId: "slide.timeline",
    data: {
      schema: "slide",
      title: "AI Coding 进化史",
      bullet_points: [
        "2021.06: GitHub Copilot 发布",
        "2023.03: GPT-4 + ChatGPT Plugin",
        "2024.03: Claude 3 / Devin",
        "2024.10: Cursor 0.40 Agent Mode",
        "2025.02: Claude Code 公开发布",
      ],
    },
  },
  "slide.quote-callout": {
    styleId: "slide.quote-callout",
    data: {
      schema: "slide",
      title: "The most important thing to get great results out of Claude Code — give Claude a way to verify its work.",
      bullet_points: [
        "Boris Cherny",
        "Creator of Claude Code, @anthropic",
      ],
    },
  },
  "slide.checklist": {
    styleId: "slide.checklist",
    data: {
      schema: "slide",
      title: "私有化部署清单",
      bullet_points: [
        "Clone opencode 仓库",
        "配置 .env 指向本地模型",
        "关闭遥测 (Telemetry disabled)",
        "安装 claude-squad 多 Agent 管理",
        "验证 7 个 Agent 并行运行",
      ],
    },
  },
  "slide.numbered-steps": {
    styleId: "slide.numbered-steps",
    data: {
      schema: "slide",
      title: "三步搭建私有 Agent",
      bullet_points: [
        "Clone + 配置 API 端点",
        "启动本地模型 (Ollama)",
        "运行 Agent 并验证",
      ],
    },
  },
  "slide.feature-grid": {
    styleId: "slide.feature-grid",
    data: {
      schema: "slide",
      title: "Claude Code 核心能力",
      bullet_points: [
        "🔍 代码理解: 自动分析整个代码库上下文",
        "✏️ 智能编辑: 跨文件重构，保持一致性",
        "🧪 自动测试: 生成并运行测试用例",
        "🔒 安全扫描: 检测 AI 生成代码的漏洞",
      ],
    },
  },
  "slide.hero-text": {
    styleId: "slide.hero-text",
    data: {
      schema: "slide",
      title: "同一个模型，换一种说法，<hl>结果可能差很多</hl>",
      bullet_points: [
        "最早大模型火起来的时候...",
        "Prompt Engineering 让我们意识到：怎么问，比问什么更重要",
      ],
    },
  },
  "slide.chat-bubble": {
    styleId: "slide.chat-bubble",
    data: {
      schema: "slide",
      title: "同一个任务，不同的 Prompt",
      bullet_points: [
        "帮我总结这篇文章。",
        "---",
        ">请以资深技术编辑的身份，用三段结构总结这篇文章，先讲核心观点，再讲论证方式，最后讲局限性，每段不超过 150 字。",
        "?你到底改了什么？",
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
  "terminal.minimal": {
    styleId: "terminal.minimal",
    data: {
      schema: "terminal",
      instruction: "极简终端演示",
      session: [
        { type: "input" as const, text: "ollama run llama3.1:70b" },
        { type: "status" as const, text: "Loading model..." },
        { type: "output" as const, lines: ["Model loaded. API: localhost:11434", "OPENAI_BASE_URL=http://localhost:11434/v1 ✓"] },
        { type: "blank" as const },
        { type: "input" as const, text: "opencode start --telemetry=off" },
        { type: "output" as const, lines: ["[INFO] Telemetry disabled", "[INFO] Private Agent ready"] },
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
  "code-block.animated": {
    styleId: "code-block.animated",
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
  "code-block.diff": {
    styleId: "code-block.diff",
    data: {
      schema: "code-block",
      fileName: "src/auth.ts",
      language: "typescript",
      code: [
        "@@ -12,8 +12,12 @@",
        " function validateToken(token: string) {",
        "-  const decoded = jwt.decode(token);",
        "-  return decoded !== null;",
        "+  try {",
        "+    const decoded = jwt.verify(token, SECRET);",
        "+    return { valid: true, payload: decoded };",
        "+  } catch (err) {",
        "+    return { valid: false, error: err.message };",
        "+  }",
        " }",
      ],
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
  "social-card.github-repo": {
    styleId: "social-card.github-repo",
    data: {
      schema: "social-card",
      platform: "github" as const,
      author: "opencode-ai/opencode",
      text: "An open-source alternative to Claude Code. Terminal-first AI coding with any model — local Ollama, Gemini, or your own API endpoint.",
      language: "Go",
      stats: { stars: 11810, forks: 892 },
      subtitle: "ai,coding,terminal,open-source",
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
  "diagram.sequence": {
    styleId: "diagram.sequence",
    data: {
      schema: "diagram",
      title: "Agent Tool Use Flow",
      nodes: [
        { id: "user", label: "User" },
        { id: "agent", label: "Agent", type: "primary" as const },
        { id: "tool", label: "Tool API", type: "success" as const },
        { id: "llm", label: "LLM", type: "warning" as const },
      ],
      edges: [
        { from: "user", to: "agent", label: "prompt" },
        { from: "agent", to: "llm", label: "plan()" },
        { from: "llm", to: "agent", label: "tool_calls[]" },
        { from: "agent", to: "tool", label: "execute()" },
        { from: "tool", to: "agent", label: "result" },
        { from: "agent", to: "llm", label: "observe()" },
        { from: "llm", to: "agent", label: "response" },
        { from: "agent", to: "user", label: "answer" },
      ],
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
  // ── 结构骨架 ──
  "slide.hook-opener": {
    styleId: "slide.hook-opener",
    data: { schema: "slide", title: "你还在手写代码？", bullet_points: ["95% 的开发者不知道这个工具"], chart_hint: "" },
  },
  "slide.transition-bridge": {
    styleId: "slide.transition-bridge",
    data: { schema: "slide", title: "但是...", bullet_points: ["接下来的真实效果可能会颠覆你的认知"], chart_hint: "" },
  },
  "slide.cta-outro": {
    styleId: "slide.cta-outro",
    data: { schema: "slide", title: "如果觉得有用，别忘了", bullet_points: ["关注频道获取更多 AI 技巧", "点赞让更多人看到", "GitHub 链接在简介"], chart_hint: "" },
  },
  // ── 动态演示 ──
  "slide.typing-demo": {
    styleId: "slide.typing-demo",
    data: { schema: "slide", title: "Prompt", bullet_points: ["请以资深技术编辑的身份，", "分析这篇论文的核心创新点，", "用 3 个要点总结，每个要点附带一个具体例子。"], chart_hint: "" },
  },
  "slide.before-after": {
    styleId: "slide.before-after",
    data: { schema: "slide", title: "开发效率对比", bullet_points: ["手动写 200 行代码", "调试 2 小时", "反复查文档", "---", "Claude 10 秒生成", "自动修复 Bug", "内置最佳实践"], chart_hint: "" },
  },
  "slide.live-counter": {
    styleId: "slide.live-counter",
    data: { schema: "slide", title: "效率提升", bullet_points: ["200行 → 0行 手动代码", "120分钟 → 10秒 调试时间", "15次 → 1次 迭代次数"], chart_hint: "" },
  },
  "slide.screen-capture-mock": {
    styleId: "slide.screen-capture-mock",
    data: { schema: "slide", title: "Claude Code 操作演示", bullet_points: ["打开终端", "输入 claude 启动 Agent", "选择项目目录", "输入 prompt 描述任务", "等待 Agent 自动执行", "查看生成的代码", "运行测试验证", "完成！提交代码"], chart_hint: "" },
  },
  // ── 叙事节奏 ──
  "slide.problem-statement": {
    styleId: "slide.problem-statement",
    data: { schema: "slide", title: "Agent 系统的三大痛点", bullet_points: ["任务成功率不到 70%，随时可能跑偏", "换个模型效果就崩，完全不可迁移", "出了错没有恢复机制，只能从头来过"], chart_hint: "" },
  },
  "slide.solution-reveal": {
    styleId: "slide.solution-reveal",
    data: { schema: "slide", title: "Harness Engineering 解决方案", bullet_points: ["结构化任务拆解，每步可验证", "模型无关的执行框架，随时切换", "内置错误检测 + 自动恢复机制"], chart_hint: "" },
  },
  "slide.result-showcase": {
    styleId: "slide.result-showcase",
    data: { schema: "slide", title: "最终效果", bullet_points: ["95% 任务成功率", "3x 开发效率提升", "0 人工干预", "100% 可复现"], chart_hint: "" },
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
