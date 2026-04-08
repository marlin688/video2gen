## 专用模板：Claude Code + Obsidian 教程骨架

当主题同时涉及 Claude Code 与 Obsidian 时，优先复用以下骨架，避免泛化讲解。

### 目标
- 输出一个“可复现 + 可迁移”的工作流教程，而不是工具介绍。
- 观众看完后应能在 15 分钟内搭出最小可用流程（MVP）。

### 推荐段落骨架（10 段）
1. `intro` / `B` / `browser.default`
说明最终效果（Claude Code 在终端 + Obsidian 知识库联动），画面直接展示目标状态。

2. `intro` / `A` / `diagram.default`
讲清问题背景：为什么单用 Claude Code 或单用 Obsidian 都不够。

3. `body` / `A` / `hero-stat.default`
前置条件与版本矩阵（系统、Node/Python、插件版本、模型端点）。

4. `body` / `B` / `code-block.default`
步骤 1：初始化 `CLAUDE.md` + Obsidian Vault 目录结构。

5. `body` / `B` / `browser.default`
步骤 2：在 Obsidian 中配置模板/命令面板，关联项目上下文。

6. `body` / `A` / `diagram.default`
讲原理：任务流从“需求笔记 -> 结构化指令 -> Agent 执行 -> 结果回写”。

7. `body` / `B` / `code-block.default`
步骤 3：演示一次真实任务（输入、执行、输出、回写）。

8. `body` / `A` / `slide.tech-dark`
踩坑与修复 1-2：路径错误、上下文污染、模板失效、权限问题。

9. `outro` / `B` / `browser.default`
官方默认流程 vs 推荐流程，对比适用边界（个人/团队、本地/云端）。

10. `outro` / `A` / `slide.tech-dark`
行动清单：1 个文件 + 1 条命令 + 1 个检查点（可立即执行）。

### 硬性约束（本模板生效时）
- 至少 2 段明确“报错/失败 -> 排查 -> 修复”。
- 至少 1 段包含版本号或环境前置信息。
- 至少 1 段包含“适用场景/不适用场景”边界描述。
- outro 必须出现文件名（如 `CLAUDE.md`）、命令、验证点（如“看到某输出即成功”）。
