"use client";

import { useState, useCallback } from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useVoiceAssistant,
} from "@livekit/components-react";
import "@livekit/components-styles";

import { useVoiceSession } from "@/hooks/useVoiceSession";
import { useAuthStore } from "@/stores/auth";
import { LiveTranscriptPanel } from "./components/TranscriptPanel";
import { AgentSwitcher } from "./components/AgentSwitcher";

/* ─── Voice Rings Visualizer ─── */
function VoiceRings({ size = 180, state }: { size?: number; state?: string }) {
  const modeClass =
    state === "speaking" ? "rings-speaking" :
    state === "thinking" ? "rings-thinking" :
    state === "listening" ? "rings-listening" : "rings-idle";

  const ringColor =
    state === "speaking" ? "var(--green)" :
    state === "thinking" ? "var(--amber)" : "var(--accent)";

  const dotClass =
    state === "speaking" ? "ring-dot ring-dot-speaking" :
    state === "thinking" ? "ring-dot ring-dot-thinking" :
    state === "listening" ? "ring-dot ring-dot-listening" : "ring-dot";

  return (
    <div className={`rings-wrap ${modeClass}`} style={{ width: size, height: size }}>
      <div className="ring" style={{ width: size * 0.5, height: size * 0.5, borderColor: ringColor, opacity: 0.5 }} />
      <div className="ring" style={{ width: size * 0.72, height: size * 0.72, borderColor: ringColor, opacity: 0.3 }} />
      <div className="ring" style={{ width: size * 0.95, height: size * 0.95, borderColor: ringColor, opacity: 0.15 }} />
      <div className={dotClass} />
    </div>
  );
}

/* ─── Connected state ─── */
function ActiveView() {
  const { state } = useVoiceAssistant();

  const isConnecting = !state || state === "disconnected" || state === "connecting";

  const label = isConnecting ? "Connecting agent..." :
    state === "listening" ? "Listening" :
    state === "thinking" ? "Processing" :
    state === "speaking" ? "Speaking" : "Ready";

  const color = isConnecting ? "var(--fg-3)" :
    state === "listening" ? "var(--accent)" :
    state === "thinking" ? "var(--amber)" :
    state === "speaking" ? "var(--green)" : "var(--fg-3)";

  return (
    <div className="flex flex-col items-center gap-4 animate-in" style={{ paddingTop: 28, paddingBottom: 8 }}>
      <VoiceRings size={160} state={isConnecting ? undefined : state} />
      <span style={{ fontSize: 14, fontWeight: 500, color, letterSpacing: "0.02em" }}>{label}</span>
    </div>
  );
}

/* ─── Idle state ─── */
function IdleView({
  onConnect, isConnecting, error, selectedAgent, onAgentChange,
}: {
  onConnect: () => void; isConnecting: boolean; error: string | null;
  selectedAgent: string; onAgentChange: (id: string) => void;
}) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center animate-in" style={{ gap: 28, paddingBottom: 60 }}>
      <VoiceRings size={220} />

      <div className="flex flex-col items-center gap-5">
        <p style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--fg-3)" }}>
          Select agent
        </p>
        <AgentSwitcher value={selectedAgent} onChange={onAgentChange} disabled={isConnecting} />
      </div>

      <button
        onClick={onConnect}
        disabled={isConnecting}
        className="btn btn-accent"
        style={{ padding: "11px 36px", fontSize: 14 }}
      >
        {isConnecting ? "Connecting..." : "Start call"}
      </button>

      <p style={{ fontSize: 13, color: "var(--fg-3)" }}>
        Begin a voice conversation with the AI agent
      </p>

      {error && (
        <p style={{ fontSize: 12, padding: "8px 16px", borderRadius: 8, color: "var(--red)", background: "var(--red-dim)" }}>
          {error}
        </p>
      )}
    </div>
  );
}

/* ─── Main ─── */
export default function ConversationPage() {
  const { serverUrl, token, isConnecting, error, connect, disconnect } = useVoiceSession();
  const { token: authToken } = useAuthStore();
  const [selectedAgent, setSelectedAgent] = useState("default");

  const handleConnect = useCallback(async () => {
    await connect(selectedAgent, authToken || "dev_user");
  }, [selectedAgent, authToken, connect]);

  return (
    <div className="flex flex-col h-screen" style={{ background: "var(--bg-0)" }}>
      <div className="flex items-center justify-between px-6 flex-shrink-0"
        style={{ height: 52, borderBottom: "1px solid var(--border-1)" }}>
        <span style={{ fontSize: 13, fontWeight: 500, color: "var(--fg-2)" }}>Conversation</span>
        {token && (
          <button onClick={disconnect} className="btn btn-secondary" style={{ fontSize: 12, padding: "5px 16px" }}>End</button>
        )}
      </div>

      {!token ? (
        <IdleView
          onConnect={handleConnect} isConnecting={isConnecting} error={error}
          selectedAgent={selectedAgent} onAgentChange={setSelectedAgent}
        />
      ) : (
        <LiveKitRoom serverUrl={serverUrl!} token={token} connect audio
          className="flex flex-col flex-1 overflow-hidden" onDisconnected={disconnect}
          onError={(err) => console.error("[LiveKit Error]", err)}>
          <div className="flex flex-col flex-1 overflow-hidden">
            <ActiveView />
            <RoomAudioRenderer />
            <div className="flex-1 overflow-hidden flex flex-col" style={{ padding: "16px 28px 12px" }}>
              <div className="card flex-1 overflow-hidden flex flex-col" style={{ padding: "14px 18px" }}>
                <p style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--fg-3)", marginBottom: 10 }}>
                  Transcript
                </p>
                <LiveTranscriptPanel />
              </div>
            </div>
          </div>
        </LiveKitRoom>
      )}
    </div>
  );
}
