"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useVoiceAssistant,
} from "@livekit/components-react";
import "@livekit/components-styles";

import { useVoiceSession } from "@/hooks/useVoiceSession";
import { useAuthStore } from "@/stores/auth";
import { checkWorkerStatus, restartWorker } from "@/lib/api";
import { LiveTranscriptPanel } from "./components/TranscriptPanel";
import { AgentSwitcher } from "./components/AgentSwitcher";

/* ─── Hand-drawn Microphone Visualizer ─── */
function VoiceRings({ size = 180, state }: { size?: number; state?: string }) {
  const color =
    state === "speaking" ? "#6ec87a" :
    state === "thinking" ? "#e0a458" : "#d97757";

  const cream = "rgba(255,255,255,0.88)";

  const modeClass =
    state === "speaking" ? "hd-speaking" :
    state === "thinking" ? "hd-thinking" :
    state === "listening" ? "hd-listening" : "hd-idle";

  return (
    <div className={`hd-mic ${modeClass}`} style={{ width: size, height: size, position: "relative", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <svg viewBox="0 0 200 240" fill="none" style={{ width: "80%", height: "80%" }}>
        {/* Mic head — terracotta filled blob */}
        <path
          className="hd-mic-head"
          d="M100 22 C108 20, 118 24, 124 38 C130 52, 132 72, 132 92 C132 112, 130 128, 124 140 C118 152, 110 156, 101 156 C92 156, 84 152, 78 140 C72 128, 68 112, 68 92 C68 72, 70 52, 76 38 C82 24, 92 20, 100 22Z"
          fill={color}
          style={{ transition: "fill 0.4s ease" }}
        />
        {/* Mic outline */}
        <path
          d="M100 22 C108 20, 118 24, 124 38 C130 52, 132 72, 132 92 C132 112, 130 128, 124 140 C118 152, 110 156, 101 156 C92 156, 84 152, 78 140 C72 128, 68 112, 68 92 C68 72, 70 52, 76 38 C82 24, 92 20, 100 22Z"
          stroke={cream} strokeWidth="4" strokeLinecap="round" fill="none"
        />

        {/* Grille lines */}
        <path d="M78 55 C86 53, 112 52, 124 55" stroke="rgba(255,255,255,0.35)" strokeWidth="2.5" strokeLinecap="round" />
        <path d="M74 78 C84 75, 114 74, 128 77" stroke="rgba(255,255,255,0.3)" strokeWidth="2.5" strokeLinecap="round" />
        <path d="M74 101 C84 98, 114 97, 128 100" stroke="rgba(255,255,255,0.25)" strokeWidth="2.5" strokeLinecap="round" />
        <path d="M76 124 C86 121, 112 120, 126 123" stroke="rgba(255,255,255,0.2)" strokeWidth="2.5" strokeLinecap="round" />

        {/* Stem */}
        <path d="M96 154 C97 168, 98 182, 99 196" stroke={cream} strokeWidth="4.5" strokeLinecap="round" />
        <path d="M106 153 C105 167, 104 181, 103 195" stroke={cream} strokeWidth="4.5" strokeLinecap="round" />

        {/* Base line */}
        <path d="M80 196 C88 194, 112 193, 122 196" stroke={cream} strokeWidth="4" strokeLinecap="round" />

        {/* Sound wave arcs — animated per state */}
        <path className="hd-wave hd-w1" d="M140 68 C150 78, 152 98, 148 112"
          stroke={color} strokeWidth="3" strokeLinecap="round" fill="none"
          style={{ transition: "stroke 0.4s ease" }} />
        <path className="hd-wave hd-w2" d="M152 52 C168 68, 170 108, 162 128"
          stroke={color} strokeWidth="2.5" strokeLinecap="round" fill="none"
          style={{ transition: "stroke 0.4s ease" }} />
        <path className="hd-wave hd-w3" d="M164 38 C184 60, 186 116, 174 142"
          stroke={color} strokeWidth="2" strokeLinecap="round" fill="none"
          style={{ transition: "stroke 0.4s ease" }} />

        {/* Left side waves (mirror, subtle) */}
        <path className="hd-wave hd-w1" d="M60 68 C50 78, 48 98, 52 112"
          stroke={color} strokeWidth="3" strokeLinecap="round" fill="none"
          style={{ transition: "stroke 0.4s ease" }} />
        <path className="hd-wave hd-w2" d="M48 52 C32 68, 30 108, 38 128"
          stroke={color} strokeWidth="2.5" strokeLinecap="round" fill="none"
          style={{ transition: "stroke 0.4s ease" }} />
      </svg>
    </div>
  );
}

/* ─── Connected state ─── */
function ActiveView({ onTimeout }: { onTimeout?: () => void }) {
  const { state } = useVoiceAssistant();
  const [timedOut, setTimedOut] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>(null);

  const isConnecting = !state || state === "disconnected" || state === "connecting";

  useEffect(() => {
    if (isConnecting) {
      timeoutRef.current = setTimeout(() => {
        setTimedOut(true);
      }, 15000);
    } else {
      setTimedOut(false);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    }
    return () => { if (timeoutRef.current) clearTimeout(timeoutRef.current); };
  }, [isConnecting]);

  const label = timedOut ? "Agent 未响应" :
    isConnecting ? "正在连接..." :
    state === "listening" ? "聆听中" :
    state === "thinking" ? "思考中" :
    state === "speaking" ? "回复中" : "就绪";

  const color = timedOut ? "var(--red)" :
    isConnecting ? "var(--fg-3)" :
    state === "listening" ? "var(--accent)" :
    state === "thinking" ? "var(--amber)" :
    state === "speaking" ? "var(--green)" : "var(--fg-3)";

  return (
    <div className="flex flex-col items-center gap-4 animate-in" style={{ paddingTop: 28, paddingBottom: 8 }}>
      <VoiceRings size={160} state={timedOut ? undefined : isConnecting ? undefined : state} />
      <span style={{ fontSize: 14, fontWeight: 500, color, letterSpacing: "0.02em" }}>{label}</span>
      {timedOut && (
        <div className="flex flex-col items-center gap-2">
          <p style={{ fontSize: 12, color: "var(--fg-3)" }}>Worker 可能未启动或连接异常</p>
          <button onClick={onTimeout} className="btn btn-secondary" style={{ fontSize: 12, padding: "5px 16px" }}>
            断开并重试
          </button>
        </div>
      )}
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
  const [workerOk, setWorkerOk] = useState<boolean | null>(null);
  const [workerMsg, setWorkerMsg] = useState("");
  const [restarting, setRestarting] = useState(false);

  const doCheck = useCallback(() => {
    setWorkerOk(null);
    checkWorkerStatus()
      .then((s) => { setWorkerOk(s.available); setWorkerMsg(s.message); })
      .catch(() => { setWorkerOk(false); setWorkerMsg("无法检查 Worker 状态"); });
  }, []);

  useEffect(() => { doCheck(); }, [doCheck]);

  const handleRestart = async () => {
    setRestarting(true);
    setWorkerMsg("正在重启...");
    try {
      const r = await restartWorker();
      setWorkerMsg(r.message);
      // Wait for worker to initialize then re-check
      setTimeout(doCheck, 4000);
    } catch {
      setWorkerMsg("重启失败");
      setWorkerOk(false);
    } finally {
      setRestarting(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center animate-in" style={{ gap: 28, paddingBottom: 60 }}>
      <VoiceRings size={220} />

      <div className="flex flex-col items-center gap-5">
        <p style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", color: "var(--fg-3)" }}>
          选择 Agent
        </p>
        <AgentSwitcher value={selectedAgent} onChange={onAgentChange} disabled={isConnecting} />
      </div>

      <button
        onClick={onConnect}
        disabled={isConnecting}
        className="btn btn-accent"
        style={{ padding: "11px 36px", fontSize: 14 }}
      >
        {isConnecting ? "连接中..." : "开始通话"}
      </button>

      <p style={{ fontSize: 13, color: "var(--fg-3)" }}>
        与 AI Agent 进行实时语音对话
      </p>

      {/* Worker status indicator */}
      <div className="flex items-center gap-2" style={{ fontSize: 12 }}>
        <span style={{
          width: 6, height: 6, borderRadius: "50%", display: "inline-block",
          background: workerOk === null ? "var(--fg-3)" : workerOk ? "var(--green)" : "var(--red)",
        }} />
        <span style={{ color: workerOk === false ? "var(--red)" : "var(--fg-3)" }}>
          {workerOk === null ? "检查 Worker..." : workerMsg}
        </span>
        <button onClick={doCheck} className="btn btn-ghost" style={{ fontSize: 11, padding: "2px 8px" }}>
          刷新
        </button>
        <button onClick={handleRestart} disabled={restarting} className="btn btn-ghost" style={{ fontSize: 11, padding: "2px 8px", color: "var(--amber)" }}>
          {restarting ? "重启中..." : "重启 Worker"}
        </button>
      </div>

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
        <span style={{ fontSize: 13, fontWeight: 500, color: "var(--fg-2)" }}>语音对话</span>
        {token && (
          <button onClick={disconnect} className="btn btn-secondary" style={{ fontSize: 12, padding: "5px 16px" }}>结束通话</button>
        )}
      </div>

      {!token ? (
        <IdleView
          onConnect={handleConnect} isConnecting={isConnecting} error={error}
          selectedAgent={selectedAgent} onAgentChange={setSelectedAgent}
        />
      ) : (
        <LiveKitRoom serverUrl={serverUrl!} token={token} connect
          audio={{ echoCancellation: true, noiseSuppression: true, autoGainControl: true }}
          className="flex flex-col flex-1 overflow-hidden" onDisconnected={disconnect}
          onError={(err) => console.error("[LiveKit Error]", err)}>
          <div className="flex flex-col flex-1 overflow-hidden">
            <ActiveView onTimeout={disconnect} />
            <RoomAudioRenderer />
            <div className="flex-1 overflow-hidden flex flex-col" style={{ padding: "16px 28px 12px" }}>
              <div className="card flex-1 overflow-hidden flex flex-col" style={{ padding: "14px 18px" }}>
                <p style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.06em", color: "var(--fg-3)", marginBottom: 10 }}>
                  实时转写
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
