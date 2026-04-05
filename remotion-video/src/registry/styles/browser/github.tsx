/**
 * browser.github — GitHub 仓库文件浏览器
 *
 * 模拟 GitHub 暗色主题的仓库页面：
 * - 顶部仓库名 + tab 栏（Code/Issues/PR/Actions）
 * - 分支选择器 + 面包屑路径
 * - Commit 信息栏
 * - 文件/文件夹列表（带图标和 commit message）
 * - 底部 README 预览区
 *
 * 参考：Code AI Labs 视频 40-42s GitHub 文件浏览器效果。
 */

import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import React from "react";
import type { StyleComponentProps, BrowserData } from "../../types";
import { registry } from "../../registry";

/* ═══════════════ GitHub 暗色主题配色 ═══════════════ */
const GH = {
  pageBg: "#0d1117",
  headerBg: "#010409",
  headerBorder: "#21262d",
  cardBg: "#161b22",
  cardBorder: "#30363d",
  text: "#e6edf3",
  textDim: "#8b949e",
  textMuted: "#484f58",
  link: "#58a6ff",
  green: "#3fb950",
  tabUnderline: "#f78166",
  branchBg: "#21262d",
  branchBorder: "#363b42",
  rowHover: "rgba(177,186,196,0.06)",
  badgeBg: "rgba(110,118,129,0.4)",
  mono: "'SF Mono', 'Fira Code', 'JetBrains Mono', monospace",
  sans: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
};

/* ═══════════════ 图标 ═══════════════ */

function FolderIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 16 16" fill={GH.textDim}>
      <path d="M1.75 1A1.75 1.75 0 0 0 0 2.75v10.5C0 14.216.784 15 1.75 15h12.5A1.75 1.75 0 0 0 16 13.25v-8.5A1.75 1.75 0 0 0 14.25 3H7.5a.25.25 0 0 1-.2-.1l-.9-1.2C6.07 1.26 5.55 1 5 1H1.75Z" />
    </svg>
  );
}

function FileIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 16 16" fill={GH.textDim}>
      <path d="M2 1.75C2 .784 2.784 0 3.75 0h6.586c.464 0 .909.184 1.237.513l2.914 2.914c.329.328.513.773.513 1.237v9.586A1.75 1.75 0 0 1 13.25 16h-9.5A1.75 1.75 0 0 1 2 14.25Zm1.75-.25a.25.25 0 0 0-.25.25v12.5c0 .138.112.25.25.25h9.5a.25.25 0 0 0 .25-.25V6h-2.75A1.75 1.75 0 0 1 9 4.25V1.5Zm6.75.062V4.25c0 .138.112.25.25.25h2.688l-.011-.013-2.914-2.914-.013-.011Z" />
    </svg>
  );
}

function GitBranchIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill={GH.textDim}>
      <path d="M9.5 3.25a2.25 2.25 0 1 1 3 2.122V6A2.5 2.5 0 0 1 10 8.5H6a1 1 0 0 0-1 1v1.128a2.251 2.251 0 1 1-1.5 0V5.372a2.25 2.25 0 1 1 1.5 0v1.836A2.493 2.493 0 0 1 6 7h4a1 1 0 0 0 1-1v-.628A2.25 2.25 0 0 1 9.5 3.25Z" />
    </svg>
  );
}

/* ═══════════════ 主组件 ═══════════════ */

const BrowserGithub: React.FC<StyleComponentProps<"browser">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const repo = data.repoInfo;
  if (!repo) {
    // 无 repoInfo 时降级为简单显示
    return (
      <AbsoluteFill style={{ background: GH.pageBg, color: GH.text, padding: 80, fontSize: 36 }}>
        browser.github requires repoInfo data
      </AbsoluteFill>
    );
  }

  const branch = repo.branch || "main";
  const pathParts = repo.path || [];
  const files = repo.files || [];

  // 动画
  const headerP = spring({ frame, fps, config: { damping: 18, stiffness: 100 }, durationInFrames: 15 });
  const tableP = spring({ frame: Math.max(0, frame - 8), fps, config: { damping: 16, stiffness: 80 }, durationInFrames: 20 });

  // 鼠标光标位置计算（逐行向下移动）
  // 表头区域大约在 y=280，每行高度约 45px，从 frame 35 开始移动
  const ROW_HEIGHT = 45;
  const TABLE_TOP = 295;
  const CURSOR_START_FRAME = 35;
  const FRAMES_PER_ROW = 20;
  const totalRows = (pathParts.length > 0 ? 1 : 0) + files.length; // .. row + file rows
  const cursorProgress = Math.max(0, frame - CURSOR_START_FRAME) / FRAMES_PER_ROW;
  const cursorRow = Math.min(cursorProgress, totalRows - 0.2);
  const cursorY = TABLE_TOP + (pathParts.length > 0 ? 1 : 0) * ROW_HEIGHT + cursorRow * ROW_HEIGHT;
  const cursorX = 350 + Math.sin(cursorProgress * 0.8) * 30; // 轻微左右晃动
  const cursorVisible = frame >= CURSOR_START_FRAME && cursorRow < totalRows + 0.5;

  return (
    <AbsoluteFill style={{ background: GH.pageBg, fontFamily: GH.sans }}>
      {/* ── Header: 仓库名 + tabs ── */}
      <div style={{
        background: GH.headerBg,
        borderBottom: `1px solid ${GH.headerBorder}`,
        padding: "16px 48px 0",
        opacity: interpolate(headerP, [0, 1], [0, 1]),
      }}>
        {/* 仓库名 */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
          <svg width="20" height="20" viewBox="0 0 16 16" fill={GH.textDim}>
            <path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z" />
          </svg>
          <span style={{ fontSize: 22, color: GH.link }}>{repo.owner}</span>
          <span style={{ fontSize: 22, color: GH.textDim }}>/</span>
          <span style={{ fontSize: 22, color: GH.link, fontWeight: 700 }}>{repo.repo}</span>
        </div>

        {/* Tab 栏 */}
        <div style={{ display: "flex", gap: 0 }}>
          {[
            { label: "Code", active: true },
            { label: "Issues", badge: repo.issues },
            { label: "Pull requests", badge: repo.pullRequests },
            { label: "Actions" },
            { label: "Security" },
          ].map((tab, i) => (
            <div key={i} style={{
              padding: "10px 20px",
              fontSize: 17,
              color: tab.active ? GH.text : GH.textDim,
              fontWeight: tab.active ? 600 : 400,
              borderBottom: tab.active ? `2px solid ${GH.tabUnderline}` : "2px solid transparent",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}>
              {tab.label}
              {tab.badge && (
                <span style={{
                  background: GH.badgeBg,
                  borderRadius: 10,
                  padding: "1px 8px",
                  fontSize: 14,
                  color: GH.textDim,
                }}>
                  {tab.badge}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ── 分支 + 面包屑 ── */}
      <div style={{
        padding: "20px 48px 0",
        display: "flex",
        alignItems: "center",
        gap: 16,
        opacity: interpolate(headerP, [0, 1], [0, 1]),
      }}>
        {/* 分支选择器 */}
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          background: GH.branchBg,
          border: `1px solid ${GH.branchBorder}`,
          borderRadius: 8,
          padding: "6px 14px",
          fontSize: 16,
          color: GH.text,
        }}>
          <GitBranchIcon />
          <span>{branch}</span>
          <span style={{ color: GH.textMuted, marginLeft: 4 }}>▾</span>
        </div>

        {/* 面包屑路径 */}
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          fontSize: 20,
          fontFamily: GH.mono,
        }}>
          <span style={{ color: GH.link, fontWeight: 700 }}>{repo.repo}</span>
          {pathParts.map((part, i) => (
            <React.Fragment key={i}>
              <span style={{ color: GH.textDim }}>/</span>
              <span style={{
                color: i === pathParts.length - 1 ? GH.text : GH.link,
                fontWeight: i === pathParts.length - 1 ? 700 : 400,
                background: i === pathParts.length - 1 ? "rgba(56,139,253,0.15)" : "transparent",
                padding: i === pathParts.length - 1 ? "2px 8px" : 0,
                borderRadius: 6,
              }}>
                {part}
              </span>
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* ── Commit 栏 ── */}
      {repo.commitMessage && (
        <div style={{
          margin: "16px 48px 0",
          padding: "12px 20px",
          background: GH.cardBg,
          border: `1px solid ${GH.cardBorder}`,
          borderRadius: "8px 8px 0 0",
          display: "flex",
          alignItems: "center",
          gap: 12,
          fontSize: 16,
          opacity: interpolate(tableP, [0, 1], [0, 1]),
        }}>
          {/* 头像占位 */}
          <div style={{
            width: 28, height: 28, borderRadius: "50%",
            background: `hsl(${(repo.commitAuthor || "").length * 47 % 360}, 50%, 45%)`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 14, color: "#fff", fontWeight: 700,
          }}>
            {(repo.commitAuthor || "?").charAt(0).toUpperCase()}
          </div>
          <span style={{ color: GH.text, fontWeight: 600 }}>
            {repo.commitAuthor}
          </span>
          <span style={{ color: GH.textDim, flex: 1 }}>
            {repo.commitMessage}
          </span>
          {repo.commitHash && (
            <span style={{ color: GH.link, fontFamily: GH.mono, fontSize: 14 }}>
              {repo.commitHash}
            </span>
          )}
        </div>
      )}

      {/* ── 文件列表 ── */}
      <div style={{
        margin: repo.commitMessage ? "0 48px" : "16px 48px 0",
        border: `1px solid ${GH.cardBorder}`,
        borderTop: repo.commitMessage ? "none" : undefined,
        borderRadius: repo.commitMessage ? "0 0 8px 8px" : 8,
        overflow: "hidden",
        opacity: interpolate(tableP, [0, 1], [0, 1]),
        transform: `translateY(${interpolate(tableP, [0, 1], [20, 0])}px)`,
      }}>
        {/* 表头 */}
        <div style={{
          display: "flex",
          padding: "10px 20px",
          borderBottom: `1px solid ${GH.cardBorder}`,
          background: GH.cardBg,
        }}>
          <span style={{ flex: 1, fontSize: 15, fontWeight: 600, color: GH.textDim }}>Name</span>
          <span style={{ flex: 1, fontSize: 15, fontWeight: 600, color: GH.textDim }}>Last commit message</span>
        </div>

        {/* 返回上层 */}
        {pathParts.length > 0 && (
          <div style={{
            display: "flex",
            padding: "10px 20px",
            borderBottom: `1px solid ${GH.cardBorder}`,
            alignItems: "center",
            gap: 12,
          }}>
            <FolderIcon />
            <span style={{ color: GH.link, fontSize: 17 }}>..</span>
          </div>
        )}

        {/* 文件行（含鼠标逐行扫过高亮动画） */}
        {files.map((file, i) => {
          const rowDelay = 12 + i * 4;
          const rowP = spring({
            frame: Math.max(0, frame - rowDelay),
            fps,
            config: { damping: 18, stiffness: 100 },
            durationInFrames: 15,
          });

          // 鼠标扫过高亮：每行停留 20 帧，与鼠标光标同步
          const scanStart = CURSOR_START_FRAME + 5 + i * FRAMES_PER_ROW;
          const scanEnd = scanStart + 20;
          const isScanActive = frame >= scanStart && frame < scanEnd;
          // highlight 字段标记的行在扫描结束后保持高亮
          const isStaticHighlight = file.highlight && frame >= scanEnd;
          const isHighlighted = isScanActive || isStaticHighlight;

          return (
            <div key={i} style={{
              display: "flex",
              padding: "10px 20px",
              borderBottom: i < files.length - 1 ? `1px solid ${GH.cardBorder}` : "none",
              alignItems: "center",
              opacity: interpolate(rowP, [0, 1], [0, 1]),
              background: isHighlighted ? GH.rowHover : "transparent",
              transition: "background 0.15s",
            }}>
              <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 12 }}>
                {file.type === "dir" ? <FolderIcon /> : <FileIcon />}
                <span style={{
                  color: GH.link,
                  fontSize: 17,
                  fontFamily: GH.mono,
                  background: isHighlighted ? "rgba(56,139,253,0.15)" : "transparent",
                  padding: isHighlighted ? "2px 8px" : "2px 0",
                  borderRadius: 6,
                }}>
                  {file.name}
                </span>
              </div>
              {file.commitMessage && (
                <span style={{
                  flex: 1,
                  color: GH.textDim,
                  fontSize: 16,
                }}>
                  {file.commitMessage}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* ── README 预览区 ── */}
      {data.contentLines.length > 0 && (
        <div style={{
          margin: "20px 48px 0",
          padding: "20px 28px",
          background: GH.cardBg,
          border: `1px solid ${GH.cardBorder}`,
          borderRadius: 8,
          opacity: interpolate(
            frame, [25, 35], [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
          ),
        }}>
          <div style={{
            fontSize: 16,
            color: GH.textDim,
            fontWeight: 600,
            marginBottom: 16,
            fontFamily: GH.mono,
          }}>
            README.md
          </div>
          {data.contentLines.map((line, i) => (
            <div key={i} style={{
              fontSize: line.startsWith("#") ? 28 : 18,
              fontWeight: line.startsWith("#") ? 700 : 400,
              color: line.startsWith("#") ? GH.text : GH.textDim,
              marginBottom: line === "" ? 12 : 6,
              fontFamily: GH.sans,
            }}>
              {line.replace(/^#+\s*/, "")}
            </div>
          ))}
        </div>
      )}

      {/* ── 鼠标光标 ── */}
      {cursorVisible && (
        <div style={{
          position: "absolute",
          left: cursorX,
          top: cursorY,
          zIndex: 100,
          pointerEvents: "none" as const,
          filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.5))",
          opacity: interpolate(
            frame,
            [CURSOR_START_FRAME, CURSOR_START_FRAME + 5],
            [0, 1],
            { extrapolateRight: "clamp", extrapolateLeft: "clamp" },
          ),
        }}>
          <svg width="28" height="34" viewBox="0 0 24 28" fill="none">
            <path
              d="M5.5 0L5.5 22.5L10.5 17.5L15.5 26L19.5 24L14.5 15.5L21.5 15.5L5.5 0Z"
              fill="white"
              stroke="black"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      )}
    </AbsoluteFill>
  );
};

/* ═══════════════ 注册 ═══════════════ */

registry.register(
  {
    id: "browser.github",
    schema: "browser",
    name: "GitHub 仓库浏览器",
    description:
      "GitHub 暗色主题仓库页面：仓库名 + tab 栏 + 分支选择器 + 面包屑路径 + " +
      "commit 信息 + 文件/文件夹列表 + README 预览。需设置 repoInfo 字段。" +
      "适合展示开源项目、代码仓库、插件目录。",
    isDefault: false,
    tags: ["GitHub", "仓库", "代码", "开源"],
  },
  BrowserGithub,
);

export { BrowserGithub };
