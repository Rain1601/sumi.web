"use client";

import { useEffect, useState, useMemo, useRef, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/stores/auth";

/* ─── Types ─── */

interface TraceEvent {
  id: string;
  event_type: string;
  timestamp: number;
  duration_ms: number | null;
  data: Record<string, unknown> | null;
}

interface Message {
  id: string;
  role: string;
  content: string;
  started_at: string;
  ended_at: string | null;
  audio_url?: string | null;
}

interface LatencySummary {
  total_turns: number;
  total_duration_s: number | null;
  error_count: number;
  asr_avg_ms: number | null;
  nlp_ttfb_avg_ms: number | null;
  tts_first_audio_avg_ms: number | null;
  e2e_avg_ms: number | null;
}

/** A resolved time span on the timeline */
interface TimelineBlock {
  type: "vad" | "asr" | "nlp" | "tts" | "interruption" | "hangup" | "tool" | "memory" | "error";
  startS: number; // seconds from session start
  durationS: number;
  label: string;
  detail?: string;
  color: string;
  isInterruption?: boolean;
  probability?: number;
  /** Sub-type marker for point events (TTFB, first-audio, etc.) */
  marker?: "ttfb" | "first_audio" | "resume";
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

/** Extract conversation messages from trace events when messages API is unavailable */
function extractMessagesFromEvents(events: TraceEvent[]): Message[] {
  const msgs: Message[] = [];
  for (const ev of events) {
    const data = ev.data || {};
    if (ev.event_type === "turn.user_complete" && data.asr_result) {
      msgs.push({
        id: ev.id,
        role: "user",
        content: data.asr_result as string,
        started_at: new Date((data.user_speech_start_time as number || ev.timestamp) * 1000).toISOString(),
        ended_at: new Date(ev.timestamp * 1000).toISOString(),
      });
    } else if (ev.event_type === "turn.agent_complete" && data.nlp_result) {
      msgs.push({
        id: ev.id,
        role: "assistant",
        content: data.nlp_result as string,
        started_at: new Date((data.nlp_request_time as number || ev.timestamp) * 1000).toISOString(),
        ended_at: new Date(ev.timestamp * 1000).toISOString(),
      });
    }
  }
  return msgs;
}

const LANE_COLORS: Record<string, string> = {
  vad: "var(--green)",
  asr: "var(--asr)",
  nlp: "var(--nlp)",
  tts: "var(--tts)",
  tool: "var(--amber)",
  memory: "var(--accent)",
  interruption: "var(--red)",
  error: "var(--red)",
  hangup: "var(--red)",
};

const LANE_LABELS: Record<string, string> = {
  vad: "VAD",
  asr: "ASR",
  nlp: "NLP",
  tts: "TTS",
  tool: "Tools",
  memory: "Memory",
  interruption: "Interruption",
  error: "Errors",
  hangup: "Hangup",
};

const LANE_ORDER = ["vad", "asr", "nlp", "tts", "tool", "memory", "interruption", "error"];

/* ─── Helpers ─── */

function formatTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = (s % 60).toFixed(1);
  return m > 0 ? `${m}:${sec.padStart(4, "0")}` : `${sec}s`;
}

function formatMs(ms: number | null): string {
  if (ms == null) return "--";
  return `${ms.toFixed(0)}ms`;
}

function buildTimeline(events: TraceEvent[], sessionStart: number): TimelineBlock[] {
  const blocks: TimelineBlock[] = [];
  const pending: Record<string, number> = {}; // type → start timestamp

  for (const ev of events) {
    const t = ev.timestamp - sessionStart;
    const data = ev.data || {};

    switch (ev.event_type) {
      /* ─── VAD ─── */
      case "vad.speech_start":
        pending["vad"] = t;
        break;
      case "vad.speech_end": {
        const start = pending["vad"] ?? t;
        const dur = (data.duration_ms as number ?? 0) / 1000;
        blocks.push({ type: "vad", startS: start, durationS: dur || (t - start), label: "", color: LANE_COLORS.vad });
        delete pending["vad"];
        break;
      }

      /* ─── ASR ─── */
      case "asr.end": {
        const text = (data.transcript as string) || "";
        const latency = (data.duration_ms as number) ?? (data.latency_ms as number) ?? 0;
        blocks.push({
          type: "asr", startS: Math.max(0, t - latency / 1000), durationS: latency / 1000 || 0.1,
          label: text.slice(0, 30), detail: text, color: LANE_COLORS.asr,
        });
        break;
      }

      /* ─── NLP ─── */
      case "nlp.start":
        pending["nlp"] = t;
        break;
      case "nlp.first_token": {
        // TTFB marker — thin block on NLP lane
        blocks.push({
          type: "nlp", startS: t, durationS: 0.05,
          label: "TTFB", detail: `First token at ${formatTime(t)}`,
          color: "var(--nlp)", marker: "ttfb",
        });
        break;
      }
      case "nlp.end": {
        // If we have a pending NLP start, close it with nlp.end
        if (pending["nlp"] != null) {
          const dur = (data.duration_ms as number ?? 0) / 1000;
          blocks.push({
            type: "nlp", startS: pending["nlp"], durationS: dur || (t - pending["nlp"]),
            label: `${data.token_count ?? ""}tok`, color: LANE_COLORS.nlp,
            detail: `tokens=${data.token_count ?? "?"} chunks=${data.total_chunks ?? "?"} ctx=${data.ctx_tokens_est ?? "?"}`,
          });
          delete pending["nlp"];
        }
        break;
      }
      case "tts.start": {
        // Fallback: if nlp.end didn't fire, close NLP here
        if (pending["nlp"] != null) {
          blocks.push({
            type: "nlp", startS: pending["nlp"], durationS: t - pending["nlp"],
            label: "", color: LANE_COLORS.nlp,
          });
          delete pending["nlp"];
        }
        pending["tts"] = t;
        break;
      }

      /* ─── TTS ─── */
      case "tts.first_audio": {
        blocks.push({
          type: "tts", startS: t, durationS: 0.05,
          label: "1st audio", detail: `First audio frame at ${formatTime(t)}`,
          color: "var(--tts)", marker: "first_audio",
        });
        break;
      }
      case "tts.end": {
        const start = pending["tts"] ?? t;
        const dur = (data.total_ms as number ?? (data.duration_ms as number) ?? 0) / 1000;
        blocks.push({
          type: "tts", startS: start, durationS: dur || (t - start),
          label: (data.text as string || "").slice(0, 30), detail: data.text as string, color: LANE_COLORS.tts,
        });
        delete pending["tts"];
        break;
      }

      /* ─── Tool calls ─── */
      case "nlp.tool_call": {
        const toolName = (data.tool_name as string) || (data.request as Record<string, unknown>)?.tool_name as string || "tool";
        const durMs = data.duration_ms as number ?? ev.duration_ms ?? 0;
        const result = data.result as Record<string, unknown>;
        const success = result?.success as boolean ?? true;
        blocks.push({
          type: "tool", startS: Math.max(0, t - durMs / 1000), durationS: durMs / 1000 || 0.2,
          label: toolName,
          detail: `${toolName} ${success ? "ok" : "FAIL"} ${durMs.toFixed(0)}ms`,
          color: success ? LANE_COLORS.tool : "var(--red)",
        });
        break;
      }

      /* ─── Memory ─── */
      case "memory.query": {
        const facts = data.facts_count as number ?? 0;
        const vectors = data.vectors_count as number ?? 0;
        blocks.push({
          type: "memory", startS: t, durationS: 0.2,
          label: "Query",
          detail: `facts=${facts} vectors=${vectors}`,
          color: LANE_COLORS.memory,
        });
        break;
      }
      case "memory.update": {
        const segs = data.segments_count as number ?? 0;
        const facts = data.facts_count as number ?? 0;
        blocks.push({
          type: "memory", startS: t, durationS: 0.2,
          label: "Save",
          detail: `segments=${segs} facts=${facts}`,
          color: LANE_COLORS.memory,
        });
        break;
      }

      /* ─── Interruptions ─── */
      case "pipeline.interruption": {
        const isTrue = data.is_interruption as boolean;
        const prob = data.probability as number ?? 0;
        blocks.push({
          type: "interruption", startS: t, durationS: 0.3,
          label: isTrue ? "Interrupt" : "Backchannel",
          detail: `prob=${(prob * 100).toFixed(0)}% spoken="${(data.agent_text_spoken as string || "").slice(0, 50)}"`,
          color: isTrue ? "var(--red)" : "var(--amber)",
          isInterruption: isTrue, probability: prob,
        });
        break;
      }
      case "pipeline.interruption_resume": {
        blocks.push({
          type: "interruption", startS: t, durationS: 0.15,
          label: "Resume", detail: `resumed=${data.resumed}`,
          color: "var(--green)", marker: "resume",
        });
        break;
      }

      /* ─── Errors ─── */
      case "error": {
        const source = data.source as string ?? "";
        const message = data.message as string ?? "";
        blocks.push({
          type: "error", startS: t, durationS: 0.4,
          label: source || "Error",
          detail: message.slice(0, 200),
          color: LANE_COLORS.error,
        });
        break;
      }

      /* ─── Lifecycle ─── */
      case "hangup.detected": {
        const goodbyes = data.consecutive_goodbyes as number ?? 0;
        blocks.push({
          type: "hangup", startS: t, durationS: 0.5,
          label: "Hangup Detected",
          detail: `LLM detected ${goodbyes} consecutive goodbyes`,
          color: "var(--red)",
        });
        break;
      }
      case "session.end": {
        const totalMs = data.total_duration_ms as number ?? 0;
        const turns = data.total_turns as number ?? 0;
        blocks.push({
          type: "hangup", startS: t, durationS: 0.5,
          label: "Session End",
          detail: `turns=${turns} duration=${(totalMs / 1000).toFixed(1)}s`,
          color: "var(--red)",
        });
        break;
      }
    }
  }

  return blocks;
}

/* ─── Components ─── */

function SummaryBar({ summary }: { summary: LatencySummary }) {
  const stats = [
    { label: "Turns", value: summary.total_turns, color: "var(--fg-2)" },
    { label: "ASR avg", value: summary.asr_avg_ms, unit: "ms", color: "var(--asr)" },
    { label: "NLP TTFB", value: summary.nlp_ttfb_avg_ms, unit: "ms", color: "var(--nlp)" },
    { label: "TTS first", value: summary.tts_first_audio_avg_ms, unit: "ms", color: "var(--tts)" },
    { label: "E2E", value: summary.e2e_avg_ms, unit: "ms", color: "var(--accent)" },
    { label: "Errors", value: summary.error_count, color: summary.error_count > 0 ? "var(--red)" : "var(--fg-3)" },
  ];

  return (
    <div className="flex gap-6 px-5 py-3 rounded-xl" style={{ background: "var(--bg-1)", border: "1px solid var(--border)" }}>
      {stats.map((s) => (
        <div key={s.label} className="flex items-baseline gap-1.5">
          <span className="text-[11px]" style={{ color: "var(--fg-3)" }}>{s.label}</span>
          <span className="text-[14px] font-medium mono" style={{ color: s.color }}>
            {s.value != null ? `${typeof s.value === "number" && s.unit ? s.value.toFixed(0) : s.value}${s.unit || ""}` : "--"}
          </span>
        </div>
      ))}
    </div>
  );
}

function TimelineLane({
  lane,
  blocks,
  totalS,
  onBlockClick,
}: {
  lane: string;
  blocks: TimelineBlock[];
  totalS: number;
  onBlockClick?: (timeS: number) => void;
}) {
  const [hoveredId, setHoveredId] = useState<number | null>(null);

  return (
    <div className="tl-lane" data-lane={lane}>
      <div className="tl-lane-label">{LANE_LABELS[lane]}</div>
      <div className="tl-lane-track" style={{ cursor: onBlockClick ? "pointer" : undefined }}
        onClick={(e) => {
          if (!onBlockClick || totalS <= 0) return;
          const rect = e.currentTarget.getBoundingClientRect();
          const x = e.clientX - rect.left;
          const ratio = x / rect.width;
          onBlockClick(ratio * totalS);
        }}>
        {blocks.map((b, i) => {
          const left = totalS > 0 ? (b.startS / totalS) * 100 : 0;
          const width = totalS > 0 ? Math.max((b.durationS / totalS) * 100, 0.4) : 0;
          const isInterrupt = b.type === "interruption";
          const isMarker = !!b.marker;

          return (
            <div
              key={i}
              className={`tl-block ${isInterrupt ? "tl-block-interrupt" : ""} ${isMarker ? "tl-block-marker" : ""}`}
              style={{
                left: `${left}%`,
                width: isInterrupt || isMarker ? "3px" : `${width}%`,
                background: b.color,
                opacity: (isInterrupt && !b.isInterruption) ? 0.5 : isMarker ? 0.7 : 0.85,
                cursor: onBlockClick ? "pointer" : undefined,
                borderLeft: isMarker ? `2px dashed ${b.color}` : undefined,
              }}
              onMouseEnter={() => setHoveredId(i)}
              onMouseLeave={() => setHoveredId(null)}
              onClick={() => onBlockClick?.(b.startS)}
            >
              {hoveredId === i && (
                <div className="tl-tooltip">
                  <div className="font-medium">{b.marker ? b.label : LANE_LABELS[b.type]}</div>
                  {!b.marker && b.label && <div>{b.label}</div>}
                  <div className="mono" style={{ color: "var(--fg-3)" }}>
                    {formatTime(b.startS)} / {(b.durationS * 1000).toFixed(0)}ms
                  </div>
                  {b.detail && <div style={{ color: "var(--fg-3)", maxWidth: 280, wordBreak: "break-all" }}>{b.detail}</div>}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Timeline({ blocks, totalS, cursorS, onBlockClick }: { blocks: TimelineBlock[]; totalS: number; cursorS?: number | null; onBlockClick?: (timeS: number) => void }) {
  const laneBlocks = useMemo(() => {
    const map: Record<string, TimelineBlock[]> = {};
    for (const l of LANE_ORDER) map[l] = [];
    for (const b of blocks) {
      if (map[b.type]) map[b.type].push(b);
    }
    return map;
  }, [blocks]);

  // Generate tick marks — aim for 8-12 ticks max
  const ticks = useMemo(() => {
    if (totalS <= 0) return [];
    const maxTicks = 10;
    const rawStep = totalS / maxTicks;
    // Round to nice intervals
    const niceSteps = [0.5, 1, 2, 5, 10, 15, 20, 30, 60, 120, 300];
    const step = niceSteps.find(s => s >= rawStep) ?? rawStep;
    const result: number[] = [];
    for (let t = 0; t <= totalS + step * 0.1; t += step) result.push(t);
    return result;
  }, [totalS]);

  // Only render lanes that have blocks
  const activeLanes = LANE_ORDER.filter((l) => laneBlocks[l].length > 0);

  return (
    <div className="card p-5">
      <div className="text-[11px] font-medium mb-3" style={{ color: "var(--fg-3)", letterSpacing: "0.04em", textTransform: "uppercase" }}>
        Pipeline Timeline
      </div>

      {/* Time axis */}
      <div className="tl-axis">
        <div style={{ width: 52, flexShrink: 0 }} />
        <div className="tl-axis-track">
          {ticks.map((t) => (
            <span
              key={t}
              className="tl-tick"
              style={{ left: `${(t / totalS) * 100}%` }}
            >
              {formatTime(t)}
            </span>
          ))}
        </div>
      </div>

      {/* Lanes with cursor overlay */}
      <div style={{ position: "relative" }}>
        {activeLanes.map((lane) => (
          <TimelineLane key={lane} lane={lane} blocks={laneBlocks[lane]} totalS={totalS} onBlockClick={onBlockClick} />
        ))}

        {/* Session end marker (hangup line) */}
        {blocks.filter(b => b.type === "hangup").map((b, i) => (
          <div
            key={`hangup-${i}`}
            style={{
              position: "absolute", top: 0, bottom: 0, width: 2, zIndex: 8, pointerEvents: "none",
              left: `calc(52px + (100% - 52px) * ${b.startS / totalS})`,
              background: "var(--red)", opacity: 0.6,
            }}
          />
        ))}

        {/* Cursor line synced to current message */}
        {cursorS != null && totalS > 0 && (
          <div
            className="tl-cursor"
            style={{ left: `calc(52px + (100% - 52px) * ${cursorS / totalS})` }}
          />
        )}
      </div>

      {activeLanes.length === 0 && (
        <div className="text-center py-8 text-[13px]" style={{ color: "var(--fg-3)" }}>
          No pipeline events
        </div>
      )}
    </div>
  );
}

function AudioPlayButton({ url }: { url: string }) {
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const toggle = useCallback(() => {
    if (!audioRef.current) {
      const audio = new Audio(`${API_BASE}/api/${url}`);
      audio.onended = () => setPlaying(false);
      audio.onerror = () => setPlaying(false);
      audioRef.current = audio;
    }

    if (playing) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      setPlaying(false);
    } else {
      audioRef.current.play();
      setPlaying(true);
    }
  }, [playing, url]);

  return (
    <button
      onClick={toggle}
      className="audio-play-btn"
      title={playing ? "Stop" : "Play audio"}
      style={{
        color: playing ? "var(--accent)" : "var(--fg-3)",
      }}
    >
      {playing ? (
        <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
          <rect x="3" y="3" width="4" height="10" rx="1" />
          <rect x="9" y="3" width="4" height="10" rx="1" />
        </svg>
      ) : (
        <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
          <path d="M4 2.5v11l9-5.5z" />
        </svg>
      )}
    </button>
  );
}

function ConversationPanel({
  messages,
  interruptions,
  sessionStart,
  onSelectTime,
  currentIdx,
  onSetIdx,
}: {
  messages: Message[];
  interruptions: TimelineBlock[];
  sessionStart: number;
  onSelectTime?: (timeS: number) => void;
  currentIdx: number;
  onSetIdx: (idx: number) => void;
}) {
  const setCurrentIdx = onSetIdx;

  // Merge messages and interruptions into a single timeline
  type Item = { type: "message"; msg: Message; ts: number } | { type: "interrupt"; block: TimelineBlock; ts: number };

  const items = useMemo(() => {
    const result: Item[] = [];
    for (const m of messages) {
      result.push({ type: "message", msg: m, ts: new Date(m.started_at).getTime() / 1000 });
    }
    for (const b of interruptions) {
      if (b.isInterruption) {
        result.push({ type: "interrupt", block: b, ts: sessionStart + b.startS });
      }
    }
    result.sort((a, b) => a.ts - b.ts);
    return result;
  }, [messages, interruptions, sessionStart]);

  const canPrev = currentIdx > 0;
  const canNext = currentIdx < items.length - 1;
  const currentItem = items[currentIdx] ?? null;

  // Notify parent of current message time for timeline cursor sync
  useEffect(() => {
    if (!currentItem || !onSelectTime) return;
    const relativeS = currentItem.ts - sessionStart;
    onSelectTime(relativeS);
  }, [currentIdx, currentItem, sessionStart, onSelectTime]);

  // Find adjacent interruption for current message
  const adjacentInterrupt = useMemo(() => {
    if (!currentItem || currentItem.type !== "message") return null;
    // Check if next item is an interruption
    const next = items[currentIdx + 1];
    if (next?.type === "interrupt") return next.block;
    // Check if previous item is an interruption
    const prev = items[currentIdx - 1];
    if (prev?.type === "interrupt") return prev.block;
    return null;
  }, [items, currentIdx, currentItem]);

  const renderMessage = (m: Message) => {
    const isUser = m.role === "user";
    const isAgent = m.role === "assistant";
    const time = new Date(m.started_at);
    const timeStr = time.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

    return (
      <div className="px-5 py-4">
        {/* Role icon + label */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div
              className="conv-role-icon"
              style={{ background: isUser ? "var(--accent)" : "var(--green)" }}
            >
              {isUser ? (
                <svg width="12" height="12" viewBox="0 0 16 16" fill="white">
                  <path d="M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6m2-3a2 2 0 1 1-4 0 2 2 0 0 1 4 0m4 8c0 1-1 1-1 1H3s-1 0-1-1 1-4 6-4 6 3 6 4"/>
                </svg>
              ) : (
                <svg width="12" height="12" viewBox="0 0 16 16" fill="white">
                  <path d="M6 12.5a.5.5 0 0 1 .5-.5h3a.5.5 0 0 1 0 1h-3a.5.5 0 0 1-.5-.5M3 8.062C3 6.76 4.235 5.765 5.53 5.886a26.6 26.6 0 0 0 4.94 0C11.765 5.765 13 6.76 13 8.062v1.157a.93.93 0 0 1-.765.935c-.845.147-2.34.346-4.235.346s-3.39-.2-4.235-.346A.93.93 0 0 1 3 9.219zm4.542-.827a.25.25 0 0 0-.217.068l-.92.9a25 25 0 0 1-1.871-.183.25.25 0 0 0-.068.495c.55.076 1.232.149 2.02.193a.25.25 0 0 0 .189-.071l.754-.736.847 1.71a.25.25 0 0 0 .404.062l.932-.97a25 25 0 0 0 1.922-.188.25.25 0 0 0-.068-.495c-.538.074-1.207.145-1.98.189a.25.25 0 0 0-.166.076l-.672.7-.86-1.74a.25.25 0 0 0-.246-.14"/>
                </svg>
              )}
            </div>
            <span
              className="text-[11px] font-semibold"
              style={{
                color: isUser ? "var(--accent)" : "var(--green)",
                letterSpacing: "0.04em",
              }}
            >
              {isUser ? "User" : "Agent"}
            </span>
            {m.audio_url && <AudioPlayButton url={m.audio_url} />}
          </div>
          <span className="text-[10px] mono" style={{ color: "var(--fg-3)" }}>{timeStr}</span>
        </div>

        {/* Message content */}
        <div className="text-[13px]" style={{ color: "var(--fg)", lineHeight: 1.7 }}>
          {m.content || "(empty)"}
        </div>

        {/* Adjacent interruption badge */}
        {adjacentInterrupt && (
          <div
            className="mt-3 px-3 py-1.5 rounded-lg flex items-center gap-2"
            style={{ background: "var(--red-dim)", border: "1px solid color-mix(in srgb, var(--red) 30%, transparent)" }}
          >
            <span className="text-[10px] font-semibold" style={{ color: "var(--red)" }}>INTERRUPTED</span>
            <span className="text-[10px] mono" style={{ color: "var(--fg-3)" }}>
              prob {((adjacentInterrupt.probability ?? 0) * 100).toFixed(0)}%
            </span>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="card p-0" style={{ minWidth: 300 }}>
      {/* Header with count + nav */}
      <div
        className="px-5 py-3 flex items-center justify-between"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium" style={{ color: "var(--fg-3)", letterSpacing: "0.04em", textTransform: "uppercase" }}>
            Conversation
          </span>
          {messages.length > 0 && (
            <span className="text-[11px] mono" style={{ color: "var(--fg-3)" }}>
              {currentIdx + 1} / {items.length}
            </span>
          )}
        </div>
      </div>

      {/* Message card */}
      <div style={{ minHeight: 140 }}>
        {currentItem ? (
          currentItem.type === "message" ? (
            renderMessage(currentItem.msg)
          ) : (
            // If current item is an interruption, show it and auto-advance
            <div className="px-5 py-4">
              <div
                className="px-4 py-3 rounded-lg flex items-center gap-2"
                style={{ background: "var(--red-dim)", border: "1px solid color-mix(in srgb, var(--red) 30%, transparent)" }}
              >
                <span className="text-[11px] font-semibold" style={{ color: "var(--red)" }}>INTERRUPTED</span>
                <span className="text-[11px] mono" style={{ color: "var(--fg-3)" }}>
                  prob {((currentItem.block.probability ?? 0) * 100).toFixed(0)}%
                </span>
                {currentItem.block.detail && (
                  <span className="text-[11px]" style={{ color: "var(--fg-3)" }}>{currentItem.block.detail}</span>
                )}
              </div>
            </div>
          )
        ) : (
          <div className="text-center py-12 text-[13px]" style={{ color: "var(--fg-3)" }}>
            No messages
          </div>
        )}
      </div>

      {/* Navigation arrows */}
      {items.length > 1 && (
        <div
          className="flex items-center justify-between px-5 py-2.5"
          style={{ borderTop: "1px solid var(--border)" }}
        >
          <button
            onClick={() => canPrev && setCurrentIdx(currentIdx - 1)}
            disabled={!canPrev}
            className="conv-nav-btn"
            style={{ opacity: canPrev ? 1 : 0.25 }}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path fillRule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0"/>
            </svg>
          </button>

          {/* Counter or dot indicators */}
          {items.length > 16 ? (
            <span className="text-[12px] mono" style={{ color: "var(--fg-3)" }}>
              {currentIdx + 1} / {items.length}
            </span>
          ) : (
            <div className="flex items-center gap-1.5">
              {items.map((item, i) => (
                <button
                  key={i}
                  onClick={() => setCurrentIdx(i)}
                  className="conv-dot"
                  style={{
                    background: i === currentIdx
                      ? (item.type === "interrupt" ? "var(--red)" : item.type === "message" && item.msg.role === "user" ? "var(--accent)" : "var(--green)")
                      : "var(--bg-hover)",
                    width: i === currentIdx ? 8 : 6,
                    height: i === currentIdx ? 8 : 6,
                  }}
                />
              ))}
            </div>
          )}

          <button
            onClick={() => canNext && setCurrentIdx(currentIdx + 1)}
            disabled={!canNext}
            className="conv-nav-btn"
            style={{ opacity: canNext ? 1 : 0.25 }}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path fillRule="evenodd" d="M4.646 1.646a.5.5 0 0 1 .708 0l6 6a.5.5 0 0 1 0 .708l-6 6a.5.5 0 0 1-.708-.708L10.293 8 4.646 2.354a.5.5 0 0 1 0-.708"/>
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}

/* ─── Page ─── */

export default function ConversationDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const token = useAuthStore((s) => s.token);

  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [summary, setSummary] = useState<LatencySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;

    setLoading(true);
    setError(null);

    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    Promise.all([
      fetch(`${API_BASE}/api/traces/${id}`).then((r) => r.ok ? r.json() : []),
      fetch(`${API_BASE}/api/traces/${id}/summary`).then((r) => r.ok ? r.json() : null),
      fetch(`${API_BASE}/api/conversations/${id}/messages`, { headers }).then((r) => r.ok ? r.json() : []),
    ])
      .then(([evts, sum, msgs]) => {
        setEvents(evts);
        setSummary(sum);
        // If messages API failed (no auth), extract from trace events
        if (msgs.length === 0 && evts.length > 0) {
          setMessages(extractMessagesFromEvents(evts));
        } else {
          setMessages(msgs);
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  // Compute timeline data
  const sessionStart = useMemo(() => {
    if (events.length === 0) return 0;
    return events[0].timestamp;
  }, [events]);

  const totalS = useMemo(() => {
    // Use the actual event time range (not session duration which includes idle time)
    if (events.length < 2) return 0;
    return events[events.length - 1].timestamp - sessionStart;
  }, [events, sessionStart]);

  const blocks = useMemo(() => buildTimeline(events, sessionStart), [events, sessionStart]);
  const interruptions = useMemo(() => blocks.filter((b) => b.type === "interruption"), [blocks]);
  const [cursorS, setCursorS] = useState<number | null>(null);
  const [convIdx, setConvIdx] = useState(0);

  // Build items list (same as ConversationPanel) for timeline→conversation mapping
  const convItems = useMemo(() => {
    type Item = { ts: number };
    const result: Item[] = [];
    for (const m of messages) {
      result.push({ ts: new Date(m.started_at).getTime() / 1000 });
    }
    for (const b of interruptions) {
      if (b.isInterruption) result.push({ ts: sessionStart + b.startS });
    }
    result.sort((a, b) => a.ts - b.ts);
    return result;
  }, [messages, interruptions, sessionStart]);

  // Timeline click → jump to nearest conversation item
  const handleTimelineClick = useCallback((timeS: number) => {
    if (convItems.length === 0) return;
    const clickTs = sessionStart + timeS;
    let bestIdx = 0;
    let bestDist = Infinity;
    for (let i = 0; i < convItems.length; i++) {
      const dist = Math.abs(convItems[i].ts - clickTs);
      if (dist < bestDist) { bestDist = dist; bestIdx = i; }
    }
    setConvIdx(bestIdx);
  }, [convItems, sessionStart]);

  if (loading) {
    return (
      <div className="page">
        <div className="py-24 text-center text-[13px] animate-in" style={{ color: "var(--fg-3)" }}>
          Loading conversation...
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      {/* Header */}
      <div className="page-header animate-in">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Link href="/history" className="text-[13px]" style={{ color: "var(--fg-3)", textDecoration: "none" }}>
              History
            </Link>
            <span style={{ color: "var(--fg-3)" }}>/</span>
            <span className="text-[13px] mono" style={{ color: "var(--fg-2)" }}>{id.slice(0, 8)}</span>
          </div>
          <h1 className="page-title">Conversation Detail</h1>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[12px] mono" style={{ color: "var(--fg-3)" }}>
            {totalS > 0 ? formatTime(totalS) : "--"}
          </span>
        </div>
      </div>

      {error && (
        <div className="px-4 py-3 rounded-xl mb-6 text-[13px] animate-in" style={{ background: "var(--red-dim)", color: "var(--red)" }}>
          {error}
        </div>
      )}

      {/* Summary */}
      {summary && (
        <div className="mb-5 animate-in" style={{ animationDelay: "0.04s" }}>
          <SummaryBar summary={summary} />
        </div>
      )}

      {/* Pipeline Timeline — full width */}
      <div className="mb-5 animate-in" style={{ animationDelay: "0.06s" }}>
        <Timeline blocks={blocks} totalS={totalS} cursorS={cursorS} onBlockClick={handleTimelineClick} />
      </div>

      {/* Conversation panel — full width */}
      <div className="animate-in" style={{ animationDelay: "0.08s", maxWidth: 640 }}>
        <ConversationPanel messages={messages} interruptions={interruptions} sessionStart={sessionStart} onSelectTime={setCursorS} currentIdx={convIdx} onSetIdx={setConvIdx} />
      </div>

      {/* Raw events count */}
      <div className="mt-5 text-[11px] mono animate-in" style={{ color: "var(--fg-3)", animationDelay: "0.08s" }}>
        {events.length} trace events / {interruptions.length} interruption{interruptions.length !== 1 ? "s" : ""}
      </div>
    </div>
  );
}
