"use client";

import { useState } from "react";

interface TraceEvent {
  id: string; event_type: string; timestamp: number;
  duration_ms: number | null; data: Record<string, unknown> | null;
}

export default function DebugPage() {
  const [convId, setConvId] = useState("");
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [connected, setConnected] = useState(false);

  const connect = () => {
    if (!convId) return;
    const ws = new WebSocket(`ws://localhost:8000/api/traces/ws/${convId}`);
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (e) => setEvents(prev => [...prev, JSON.parse(e.data)]);
  };

  return (
    <div className="page">
      <div className="mb-8 animate-in">
        <h1 className="page-title">Traces</h1>
        <p className="page-desc">Real-time pipeline event inspector</p>
      </div>

      <div className="flex gap-2 mb-8 animate-in" style={{ animationDelay: "0.04s" }}>
        <input value={convId} onChange={e => setConvId(e.target.value)}
          placeholder="Room name or conversation ID" className="input flex-1" />
        <button onClick={connect} className="btn btn-primary">
          {connected ? "Connected" : "Connect"}
        </button>
      </div>

      <div className="space-y-[4px]">
        {events.map((e, i) => (
          <div key={e.id} className="flex items-start gap-4 px-4 py-2.5 rounded-lg text-[12px] mono animate-in"
            style={{ background: "var(--bg-1)", animationDelay: `${i * 0.02}s` }}
          >
            <span style={{ color: "var(--fg-3)", whiteSpace: "nowrap" }}>
              {new Date(e.timestamp * 1000).toISOString().slice(11, 23)}
            </span>
            <span className="font-medium" style={{
              color: e.event_type.startsWith("asr") ? "var(--asr)"
                : e.event_type.startsWith("tts") ? "var(--tts)"
                : e.event_type.startsWith("nlp") ? "var(--nlp)"
                : "var(--fg-2)",
              whiteSpace: "nowrap",
            }}>{e.event_type}</span>
            {e.duration_ms != null && <span style={{ color: "var(--fg-3)" }}>{e.duration_ms.toFixed(1)}ms</span>}
            <span className="break-all" style={{ color: "var(--fg-3)" }}>
              {e.data ? JSON.stringify(e.data) : ""}
            </span>
          </div>
        ))}
        {events.length === 0 && (
          <p className="text-center py-20 text-[13px] animate-in" style={{ color: "var(--fg-3)" }}>
            {connected ? "Waiting for events..." : "Connect to a conversation to see pipeline events"}
          </p>
        )}
      </div>
    </div>
  );
}
