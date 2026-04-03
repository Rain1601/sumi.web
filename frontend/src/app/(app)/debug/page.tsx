"use client";

import { useState, useEffect, useReducer, useRef, useCallback } from "react";

/* ─── Types ─── */

interface TraceEvent {
  id: string;
  event_type: string;
  timestamp: number;
  duration_ms: number | null;
  data: Record<string, unknown> | null;
}

interface TurnUserData {
  text: string;
  vad_duration_ms: number | null;
  asr_latency_ms: number | null;
  timestamp: number;
}

interface TurnAgentData {
  text: string;
  nlp_ttfb_ms: number | null;
  nlp_total_ms: number | null;
  tts_first_audio_ms: number | null;
  tts_total_ms: number | null;
  tool_calls: unknown[];
}

interface TurnData {
  index: number;
  user: TurnUserData | null;
  agent: TurnAgentData | null;
  events: TraceEvent[];
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

/* ─── Reducer ─── */

type TurnsAction =
  | { type: "ADD_EVENT"; event: TraceEvent }
  | { type: "SET_TURNS"; turns: TurnData[] }
  | { type: "RESET" };

function turnsReducer(state: TurnData[], action: TurnsAction): TurnData[] {
  switch (action.type) {
    case "SET_TURNS":
      return action.turns;

    case "ADD_EVENT": {
      const event = action.event;
      const data = event.data || {};
      const turnIndex = (data.turn_index as number) ?? findCurrentTurnIndex(state);
      const newState = [...state];
      let turn = newState.find((t) => t.index === turnIndex);

      if (!turn) {
        turn = { index: turnIndex, user: null, agent: null, events: [] };
        newState.push(turn);
        newState.sort((a, b) => a.index - b.index);
      }

      // Avoid re-referencing from sorted array — find again
      const turnRef = newState.find((t) => t.index === turnIndex)!;
      turnRef.events = [...turnRef.events, event];

      if (event.event_type === "turn.user_complete") {
        turnRef.user = {
          text: (data.text as string) || "",
          vad_duration_ms: (data.vad_duration_ms as number) ?? null,
          asr_latency_ms: (data.asr_latency_ms as number) ?? event.duration_ms,
          timestamp: event.timestamp,
        };
      } else if (event.event_type === "turn.agent_complete") {
        turnRef.agent = {
          text: (data.text as string) || "",
          nlp_ttfb_ms: (data.nlp_ttfb_ms as number) ?? null,
          nlp_total_ms: (data.nlp_total_ms as number) ?? event.duration_ms,
          tts_first_audio_ms: (data.tts_first_audio_ms as number) ?? null,
          tts_total_ms: (data.tts_total_ms as number) ?? null,
          tool_calls: (data.tool_calls as unknown[]) || [],
        };
      }

      return newState;
    }

    case "RESET":
      return [];
  }
}

function findCurrentTurnIndex(turns: TurnData[]): number {
  if (turns.length === 0) return 0;
  const last = turns[turns.length - 1];
  // If last turn has agent response, next event starts a new turn
  return last.agent ? last.index + 1 : last.index;
}

/* ─── Components ─── */

function LatencyBar({
  label,
  ms,
  maxMs,
  color,
}: {
  label: string;
  ms: number;
  maxMs: number;
  color: string;
}) {
  const width = Math.min((ms / maxMs) * 100, 100);
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] w-12 shrink-0" style={{ color: "var(--fg-3)" }}>
        {label}
      </span>
      <div
        className="flex-1 h-[6px] rounded-full"
        style={{ background: "var(--bg-3)" }}
      >
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${width}%`, background: color }}
        />
      </div>
      <span className="text-[10px] mono w-14 text-right shrink-0" style={{ color: "var(--fg-3)" }}>
        {ms.toFixed(0)}ms
      </span>
    </div>
  );
}

function SummaryCard({ summary }: { summary: LatencySummary }) {
  const stats = [
    { label: "ASR avg", value: summary.asr_avg_ms, unit: "ms", color: "var(--asr)" },
    { label: "NLP TTFB", value: summary.nlp_ttfb_avg_ms, unit: "ms", color: "var(--nlp)" },
    { label: "TTS first", value: summary.tts_first_audio_avg_ms, unit: "ms", color: "var(--tts)" },
    { label: "E2E avg", value: summary.e2e_avg_ms, unit: "ms", color: "var(--accent)" },
    { label: "Turns", value: summary.total_turns, unit: "", color: "var(--fg-2)" },
    { label: "Errors", value: summary.error_count, unit: "", color: summary.error_count > 0 ? "var(--red)" : "var(--fg-3)" },
  ];

  return (
    <div className="card p-5 animate-in" style={{ animationDelay: "0.06s" }}>
      <div className="text-[11px] font-medium mb-3" style={{ color: "var(--fg-3)", letterSpacing: "0.04em", textTransform: "uppercase" }}>
        Latency Summary
      </div>
      <div className="grid grid-cols-3 gap-x-6 gap-y-3">
        {stats.map((s) => (
          <div key={s.label}>
            <div className="text-[11px]" style={{ color: "var(--fg-3)" }}>
              {s.label}
            </div>
            <div className="text-[16px] font-medium mono" style={{ color: s.color }}>
              {s.value != null ? `${typeof s.value === "number" && s.unit ? s.value.toFixed(0) : s.value}${s.unit}` : "--"}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TurnCard({
  turn,
  maxLatency,
  delay,
}: {
  turn: TurnData;
  maxLatency: number;
  delay: number;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="card p-5 animate-in" style={{ animationDelay: `${delay}s` }}>
      {/* Turn header */}
      <div className="flex items-center gap-2 mb-4">
        <span
          className="text-[11px] font-semibold px-2 py-0.5 rounded-full mono"
          style={{ background: "var(--accent-dim)", color: "var(--accent)" }}
        >
          Turn {turn.index + 1}
        </span>
        {turn.user && (
          <span className="text-[10px] mono" style={{ color: "var(--fg-3)" }}>
            {new Date(turn.user.timestamp * 1000).toISOString().slice(11, 23)}
          </span>
        )}
      </div>

      {/* User speech */}
      {turn.user && (
        <div className="mb-3">
          <div className="flex items-start gap-3 mb-2">
            <span
              className="text-[10px] font-semibold mt-0.5 shrink-0 w-12"
              style={{ color: "var(--fg-3)", letterSpacing: "0.06em" }}
            >
              YOU
            </span>
            <span className="text-[13px]" style={{ color: "var(--fg)" }}>
              {turn.user.text || "(no transcript)"}
            </span>
          </div>
          {turn.user.asr_latency_ms != null && (
            <div className="ml-15 pl-15" style={{ marginLeft: "60px" }}>
              <LatencyBar
                label="ASR"
                ms={turn.user.asr_latency_ms}
                maxMs={maxLatency}
                color="var(--asr)"
              />
            </div>
          )}
        </div>
      )}

      {/* Agent response */}
      {turn.agent && (
        <div className="mb-3">
          <div className="flex items-start gap-3 mb-2">
            <span
              className="text-[10px] font-semibold mt-0.5 shrink-0 w-12"
              style={{ color: "var(--accent)", letterSpacing: "0.06em" }}
            >
              AGENT
            </span>
            <span className="text-[13px]" style={{ color: "var(--fg)" }}>
              {turn.agent.text || "(no response)"}
            </span>
          </div>
          <div className="flex flex-col gap-1" style={{ marginLeft: "60px" }}>
            {turn.agent.nlp_ttfb_ms != null && (
              <LatencyBar
                label="NLP"
                ms={turn.agent.nlp_ttfb_ms}
                maxMs={maxLatency}
                color="var(--nlp)"
              />
            )}
            {turn.agent.tts_first_audio_ms != null && (
              <LatencyBar
                label="TTS"
                ms={turn.agent.tts_first_audio_ms}
                maxMs={maxLatency}
                color="var(--tts)"
              />
            )}
          </div>
          {turn.agent.tool_calls.length > 0 && (
            <div className="mt-2" style={{ marginLeft: "60px" }}>
              <span className="badge badge-muted">
                {turn.agent.tool_calls.length} tool call{turn.agent.tool_calls.length > 1 ? "s" : ""}
              </span>
            </div>
          )}
        </div>
      )}

      {/* No data yet */}
      {!turn.user && !turn.agent && (
        <div className="text-[12px] py-2" style={{ color: "var(--fg-3)" }}>
          Processing...
        </div>
      )}

      {/* Raw events toggle */}
      {turn.events.length > 0 && (
        <div style={{ marginLeft: "60px" }}>
          <button
            onClick={() => setExpanded(!expanded)}
            className="btn btn-ghost text-[11px] px-0 py-1"
          >
            {expanded ? "▾" : "▸"} {turn.events.length} raw event{turn.events.length !== 1 ? "s" : ""}
          </button>
          {expanded && (
            <div className="mt-2 space-y-[2px]">
              {turn.events.map((e) => (
                <div
                  key={e.id}
                  className="flex items-start gap-3 px-3 py-1.5 rounded text-[11px] mono"
                  style={{ background: "var(--bg-1)" }}
                >
                  <span style={{ color: "var(--fg-3)", whiteSpace: "nowrap" }}>
                    {new Date(e.timestamp * 1000).toISOString().slice(11, 23)}
                  </span>
                  <span
                    className="font-medium shrink-0"
                    style={{
                      color: e.event_type.startsWith("asr")
                        ? "var(--asr)"
                        : e.event_type.startsWith("tts")
                          ? "var(--tts)"
                          : e.event_type.startsWith("nlp")
                            ? "var(--nlp)"
                            : e.event_type.includes("error")
                              ? "var(--red)"
                              : "var(--fg-2)",
                    }}
                  >
                    {e.event_type}
                  </span>
                  {e.duration_ms != null && (
                    <span style={{ color: "var(--fg-3)" }}>{e.duration_ms.toFixed(1)}ms</span>
                  )}
                  <span className="break-all" style={{ color: "var(--fg-3)" }}>
                    {e.data ? JSON.stringify(e.data) : ""}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Page ─── */

export default function DebugPage() {
  const [convId, setConvId] = useState("");
  const [mode, setMode] = useState<"idle" | "live" | "loaded">("idle");
  const [turns, dispatch] = useReducer(turnsReducer, []);
  const [summary, setSummary] = useState<LatencySummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new turns
  useEffect(() => {
    if (mode === "live") {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [turns.length, mode]);

  // Cleanup WebSocket on unmount
  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  const loadHistory = useCallback(async (id: string) => {
    setError(null);
    try {
      const [turnsRes, summaryRes] = await Promise.all([
        fetch(`/api/traces/${id}/turns`),
        fetch(`/api/traces/${id}/summary`),
      ]);
      if (!turnsRes.ok) throw new Error(`Failed to load turns: ${turnsRes.status}`);
      if (!summaryRes.ok) throw new Error(`Failed to load summary: ${summaryRes.status}`);

      const turnsData: TurnData[] = await turnsRes.json();
      const summaryData: LatencySummary = await summaryRes.json();

      dispatch({ type: "SET_TURNS", turns: turnsData });
      setSummary(summaryData);
      setMode("loaded");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    }
  }, []);

  const connectLive = useCallback((id: string) => {
    if (!id) return;
    setError(null);
    dispatch({ type: "RESET" });
    setSummary(null);

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/traces/ws/${id}`);
    wsRef.current = ws;

    ws.onopen = () => setMode("live");
    ws.onclose = () => {
      if (mode === "live") {
        // After disconnect, load the full summary
        loadHistory(id);
      }
    };
    ws.onerror = () => setError("WebSocket connection failed");
    ws.onmessage = (e) => {
      try {
        const event: TraceEvent = JSON.parse(e.data);
        dispatch({ type: "ADD_EVENT", event });
      } catch {
        // ignore parse errors
      }
    };
  }, [mode, loadHistory]);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    setMode("idle");
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!convId.trim()) return;
    loadHistory(convId.trim());
  };

  // Compute max latency across all turns for scaling bars
  const maxLatency = turns.reduce((max, t) => {
    const vals = [
      t.user?.asr_latency_ms,
      t.agent?.nlp_ttfb_ms,
      t.agent?.nlp_total_ms,
      t.agent?.tts_first_audio_ms,
      t.agent?.tts_total_ms,
    ].filter((v): v is number => v != null);
    return Math.max(max, ...vals, 100);
  }, 100);

  const totalDuration = summary?.total_duration_s;

  return (
    <div className="page">
      {/* Header */}
      <div className="mb-8 animate-in">
        <h1 className="page-title">Traces</h1>
        <p className="page-desc">Turn-based conversation pipeline inspector</p>
      </div>

      {/* Session input */}
      <form
        onSubmit={handleSubmit}
        className="flex gap-2 mb-6 animate-in"
        style={{ animationDelay: "0.04s" }}
      >
        <input
          value={convId}
          onChange={(e) => setConvId(e.target.value)}
          placeholder="Conversation ID or room name"
          className="input flex-1"
        />
        <button type="submit" className="btn btn-primary" disabled={!convId.trim()}>
          Load
        </button>
        {mode === "live" ? (
          <button type="button" onClick={disconnect} className="btn btn-secondary">
            Disconnect
          </button>
        ) : (
          <button
            type="button"
            onClick={() => connectLive(convId.trim())}
            className="btn btn-accent"
            disabled={!convId.trim()}
          >
            Live
          </button>
        )}
      </form>

      {/* Session bar */}
      {mode !== "idle" && (
        <div
          className="flex items-center gap-4 px-4 py-2.5 rounded-xl mb-6 text-[12px] mono animate-in"
          style={{ background: "var(--bg-1)", border: "1px solid var(--glass-border)", animationDelay: "0.05s" }}
        >
          <span style={{ color: "var(--fg-2)" }}>
            Session: <span style={{ color: "var(--fg)" }}>{convId}</span>
          </span>
          {totalDuration != null && (
            <span style={{ color: "var(--fg-3)" }}>
              Duration: {totalDuration.toFixed(1)}s
            </span>
          )}
          <span style={{ color: "var(--fg-3)" }}>
            Turns: {turns.length}
          </span>
          {mode === "live" && (
            <span className="flex items-center gap-1.5 ml-auto">
              <span
                className="w-[6px] h-[6px] rounded-full"
                style={{ background: "var(--green)", boxShadow: "0 0 6px var(--green)" }}
              />
              <span style={{ color: "var(--green)" }}>Live</span>
            </span>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div
          className="px-4 py-3 rounded-xl mb-6 text-[13px] animate-in"
          style={{ background: "var(--red-dim)", color: "var(--red)" }}
        >
          {error}
        </div>
      )}

      {/* Summary */}
      {summary && <div className="mb-6"><SummaryCard summary={summary} /></div>}

      {/* Turns */}
      <div className="flex flex-col gap-3">
        {turns.map((turn, i) => (
          <TurnCard
            key={turn.index}
            turn={turn}
            maxLatency={maxLatency}
            delay={0.08 + i * 0.03}
          />
        ))}
      </div>

      {/* Empty state */}
      {mode !== "idle" && turns.length === 0 && !error && (
        <p
          className="text-center py-20 text-[13px] animate-in"
          style={{ color: "var(--fg-3)" }}
        >
          {mode === "live" ? "Waiting for events..." : "No trace events found for this conversation"}
        </p>
      )}

      {mode === "idle" && turns.length === 0 && (
        <p
          className="text-center py-20 text-[13px] animate-in"
          style={{ color: "var(--fg-3)", animationDelay: "0.08s" }}
        >
          Enter a conversation ID and click Load to view traces, or Live for real-time streaming
        </p>
      )}

      {/* Auto-scroll anchor */}
      <div ref={bottomRef} />
    </div>
  );
}
