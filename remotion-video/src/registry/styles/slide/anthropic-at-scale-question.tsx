/**
 * slide.anthropic-at-scale-question — Anthropic 品牌片场景 2
 *
 * 镜头拉远：多个 UI 窗口从边缘浮现，画面中央用衬线大字问：
 * "How can you build and deploy agents at scale…"
 * 复刻 5-11s 帧。
 */

import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { StyleComponentProps } from "../../types";
import { registry } from "../../registry";
import { useTheme } from "../../theme";
import { WavyPaperBg } from "../../components/WavyPaperBg";
import { StickyNote } from "../../components/StickyNote";
import { MacosWindow } from "../../components/MacosWindow";

const monoFont = "'JetBrains Mono', 'SF Mono', monospace";

const DEFAULT_QUESTION = "How can you build and deploy\nagents at scale…";

/**
 * scene_data shape (可选)：
 *   { question?: string }   // 支持 \n 换行
 * 或用 slide_content.title 作为中央问题文案。
 */
const AnthropicAtScaleQuestion: React.FC<StyleComponentProps<"slide">> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTheme();

  const sceneData = (data.scene_data || {}) as { question?: string };
  const question = sceneData.question || data.title || DEFAULT_QUESTION;

  // 各元素从边缘"漂入"的 spring
  const enter = spring({
    frame,
    fps,
    config: { damping: 20, stiffness: 75 },
    durationInFrames: 40,
  });
  // 大字问题晚 12 帧出现
  const q = spring({
    frame: Math.max(0, frame - 12),
    fps,
    config: { damping: 18, stiffness: 95 },
    durationInFrames: 36,
  });

  return (
    <AbsoluteFill>
      <WavyPaperBg />

      {/* 左上角：小的代码窗口漂入 */}
      <div
        style={{
          position: "absolute",
          top: -40,
          left: 40,
          opacity: interpolate(enter, [0, 1], [0, 0.95]),
          transform: `translate(${interpolate(enter, [0, 1], [-120, 0])}px, ${interpolate(enter, [0, 1], [-60, 0])}px) rotate(-2deg)`,
        }}
      >
        <MacosWindow
          width={580}
          height={260}
          variant="dark"
          showHeader={false}
          bodyStyle={{
            padding: "18px 22px",
            fontSize: 14,
            fontFamily: monoFont,
            color: "#bbb",
            lineHeight: 1.55,
          }}
        >
          <div style={{ color: "#888" }}>23</div>
          <div>
            <span style={{ color: "#c586c0" }}>def</span>{" "}
            <span style={{ color: "#dcdcaa" }}>path</span>(self) -&gt; str:
          </div>
          <div style={{ paddingLeft: 18 }}>
            <span style={{ color: "#c586c0" }}>return</span>
            {' os.path.join(CHECKPOINT_DIR, self.session_id, f"'}
            {'{'}
            self.checkpoint_id
            {'}'}
            .checkpoint")
          </div>
          <div style={{ height: 8 }} />
          <div>
            <span style={{ color: "#c586c0" }}>def</span>{" "}
            <span style={{ color: "#dcdcaa" }}>size_bytes</span>(self) -&gt; int:
          </div>
          <div style={{ paddingLeft: 18 }}>
            <span style={{ color: "#c586c0" }}>try</span>: <span style={{ color: "#c586c0" }}>return</span> os.path.getsize(self.path)
          </div>
          <div style={{ paddingLeft: 18 }}>
            <span style={{ color: "#c586c0" }}>except</span> OSError: <span style={{ color: "#c586c0" }}>return</span> 0
          </div>
        </MacosWindow>
      </div>

      {/* 右上角：告警通知面板 */}
      <div
        style={{
          position: "absolute",
          top: -20,
          right: 60,
          opacity: interpolate(enter, [0, 1], [0, 1]),
          transform: `translate(${interpolate(enter, [0, 1], [120, 0])}px, ${interpolate(enter, [0, 1], [-60, 0])}px) rotate(2deg)`,
        }}
      >
        <div
          style={{
            width: 480,
            backgroundColor: "rgba(255,255,255,0.98)",
            borderRadius: 10,
            padding: "14px 18px",
            boxShadow:
              "0 20px 40px rgba(30,24,18,0.18), 0 0 0 1px rgba(0,0,0,0.06)",
            fontFamily: "'SF Pro Text', -apple-system, sans-serif",
          }}
        >
          <div style={{ fontSize: 13, color: "#999", marginBottom: 8 }}>
            ● 14:40:19  — Session state lost — agent starting over from scratch
          </div>
          {[
            { tag: "PagerDuty", level: "CRITICAL", msg: "Support agent down — 47 tickets queued", color: "#ef4444" },
            { tag: "AWS CloudWatch", level: "Lambda timeout", msg: "code-review-agent exceeded 900s", color: "#f59e0b" },
            { tag: "Sentry", level: "New issue", msg: "OutOfMemoryError in research-agent", color: "#ef4444" },
          ].map((row, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                gap: 10,
                padding: "8px 0",
                borderTop: i > 0 ? "1px solid #eee" : "none",
              }}
            >
              <div
                style={{
                  width: 6,
                  backgroundColor: row.color,
                  borderRadius: 3,
                  flexShrink: 0,
                }}
              />
              <div style={{ fontSize: 14, flex: 1 }}>
                <div style={{ fontWeight: 600, color: "#222" }}>{row.tag}</div>
                <div style={{ color: "#666", fontSize: 12 }}>
                  <span style={{ color: row.color, fontWeight: 600 }}>{row.level}:</span>{" "}
                  {row.msg}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 左下：又一个终端 */}
      <div
        style={{
          position: "absolute",
          top: 300,
          left: -60,
          opacity: interpolate(enter, [0, 1], [0, 0.9]),
          transform: `translate(${interpolate(enter, [0, 1], [-140, 0])}px, 0px) rotate(-1.5deg)`,
        }}
      >
        <MacosWindow
          width={460}
          height={420}
          variant="dark"
          title="— 84×34"
          bodyStyle={{
            padding: 20,
            fontFamily: monoFont,
            fontSize: 13,
            color: "#ccc",
            lineHeight: 1.55,
          }}
        >
          112 lines<br />
          <div style={{ opacity: 0.6 }}>aker.py) 78 lines</div>
          <div style={{ height: 12 }} />
          e across multiple<br />
          picture:<br />
          <div style={{ height: 6 }} />
          <div style={{ color: "#888" }}>.cache/</div>
          <div style={{ color: "#888" }}>847.ckpt.gz` is</div>
          <div>, and the `.bak`</div>
          <div>. The agent</div>
          <div>osing 847 steps</div>
          <div style={{ height: 8 }} />
          earch` tool can't<br />
          m`. The circuit<br />
          e `ConnectionError<br />
          state. All 3<br />
          dead upstream.<br />
          <div style={{ height: 10 }} />
          <div style={{ color: "#d97757" }}>okens)</div>
          <div style={{ color: "#a885d9" }}>tab to cycle)</div>
        </MacosWindow>
      </div>

      {/* 右下：另一个 agent terminal */}
      <div
        style={{
          position: "absolute",
          top: 290,
          right: -40,
          opacity: interpolate(enter, [0, 1], [0, 0.95]),
          transform: `translate(${interpolate(enter, [0, 1], [140, 0])}px, 0px) rotate(2deg)`,
        }}
      >
        <MacosWindow
          width={500}
          height={520}
          variant="dark"
          title="agent-runtime — claude — 84×34"
          bodyStyle={{
            padding: 20,
            fontFamily: monoFont,
            fontSize: 13,
            color: "#ccc",
            lineHeight: 1.55,
          }}
        >
          <div>
            <span style={{ color: "#3fb950" }}>●</span>{" "}
            <span style={{ fontWeight: 600, color: "#fff" }}>Write</span>(
            <span style={{ color: "#888" }}>proposal-system-</span>
          </div>
          <div style={{ paddingLeft: 16, color: "#888" }}>
            dashboard/components/
          </div>
          <div style={{ paddingLeft: 16, color: "#888" }}>
            ActivityTimeline.tsx) +87 lines
          </div>
          <div style={{ color: "#6fa86f", paddingLeft: 24 }}>✓ done</div>
          <div style={{ height: 10 }} />
          <div>2. Network outage — `web_search` tool can't</div>
          <div>reach `api.search.brave.com`. The circuit</div>
          <div>breaker hits 10 consecutive `ConnectionError</div>
          <div>failures and trips, isolating</div>
          <div>retries exhaust against a dead upstream.</div>
          <div style={{ height: 10 }} />
          <div>3. OOM kill — The sandbox container (`PID</div>
          <div>4812`) is killed with exit code 137</div>
          <div>(SIGKILL). This is the kernel OOM killer —</div>
          <div>the container's memory limit is being</div>
          <div>exceeded, likely because cold-start the</div>
          <div>step 0 reloads the full model state without</div>
          <div>the incremental checkpoint optimization.</div>
          <div style={{ height: 10 }} />
          <div style={{ color: "#d97757" }}>✻ Cogitating (26s · ↑ 570 tokens)</div>
          <div style={{ color: "#a885d9" }}>&gt;&gt; accept edits on (shift+tab to cycle)</div>
        </MacosWindow>
      </div>

      {/* 底部浏览器 dashboard 小窗 */}
      <div
        style={{
          position: "absolute",
          bottom: 40,
          left: 80,
          opacity: interpolate(enter, [0, 1], [0, 1]),
          transform: `translate(${interpolate(enter, [0, 1], [-60, 0])}px, ${interpolate(enter, [0, 1], [60, 0])}px)`,
        }}
      >
        <MacosWindow
          width={460}
          height={120}
          variant="light"
          bodyStyle={{ padding: 0, backgroundColor: "#fafafa" }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "10px 14px",
              fontSize: 13,
              fontFamily: "'SF Pro Text', -apple-system, sans-serif",
            }}
          >
            <div
              style={{
                backgroundColor: "#d97757",
                color: "#fff",
                padding: "3px 10px",
                borderRadius: 12,
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              Claude
            </div>
            <div
              style={{
                backgroundColor: "#f3f3f3",
                padding: "3px 10px",
                borderRadius: 12,
                fontSize: 12,
              }}
            >
              📊 Dashboard Support  ✕
            </div>
            <div style={{ marginLeft: "auto", fontSize: 16, color: "#bbb" }}>＋</div>
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 14px",
              borderTop: "1px solid #f0f0f0",
              fontSize: 13,
              color: "#333",
            }}
          >
            <span style={{ color: "#bbb" }}>←  →  ⟳</span>
            <span style={{ color: "#999" }}>admin.dashboard/support</span>
          </div>
        </MacosWindow>
      </div>

      {/* 中央大字问题 */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "0 260px",
          textAlign: "center",
          opacity: interpolate(q, [0, 1], [0, 1]),
          transform: `translateY(${interpolate(q, [0, 1], [30, 0])}px)`,
          zIndex: 5,
        }}
      >
        <div
          style={{
            fontFamily: t.titleFont,
            fontSize: 76,
            fontWeight: 500,
            color: t.text,
            lineHeight: 1.22,
            letterSpacing: "-0.015em",
            whiteSpace: "pre-line",
          }}
        >
          {question}
        </div>
      </div>
    </AbsoluteFill>
  );
};

registry.register(
  {
    id: "slide.anthropic-at-scale-question",
    schema: "slide",
    name: "Anthropic 规模化发问",
    description:
      "Anthropic 品牌片场景 2：多个 UI 窗口（代码/告警/终端/浏览器）从画面边缘漂入，中央衬线大字问 'How can you build and deploy agents at scale…'。复刻 5-11s 帧。",
    isDefault: false,
    tags: ["anthropic", "发问", "浮窗", "构图"],
  },
  AnthropicAtScaleQuestion,
);
export { AnthropicAtScaleQuestion };
