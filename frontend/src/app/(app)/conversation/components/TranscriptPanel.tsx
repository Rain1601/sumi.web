"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { useRoomContext } from "@livekit/components-react";
import { RoomEvent, TranscriptionSegment, Participant } from "livekit-client";

interface TranscriptEntry {
  id: string;
  role: "user" | "agent";
  text: string;
  isFinal: boolean;
  timestamp: number;
  voiceprint?: { score: number; isPrimary: boolean; isAnchor: boolean };
}

/**
 * Live transcript with voiceprint speaker tags.
 * Listens to: TranscriptionReceived (ASR/TTS text) + DataReceived (voiceprint events)
 */
export function LiveTranscriptPanel() {
  const room = useRoomContext();
  const [entries, setEntries] = useState<TranscriptEntry[]>([]);
  const [speakerStatus, setSpeakerStatus] = useState<{
    enrolled: boolean;
    lastScore: number | null;
  }>({ enrolled: false, lastScore: null });
  const endRef = useRef<HTMLDivElement>(null);

  // Pending voiceprint results keyed by text prefix
  const vpRef = useRef<Map<string, { score: number; isPrimary: boolean; isAnchor: boolean }>>(new Map());

  useEffect(() => {
    if (!room) return;

    const handleTranscription = (
      segments: TranscriptionSegment[],
      participant?: Participant,
    ) => {
      const isUser = participant?.isLocal === true;

      setEntries((prev) => {
        const next = [...prev];
        for (const seg of segments) {
          // Try to match voiceprint result
          let vp = vpRef.current.get(seg.text?.slice(0, 20));
          if (!vp) {
            // Try shorter match
            for (const [key, val] of vpRef.current.entries()) {
              if (seg.text?.startsWith(key.slice(0, 10))) {
                vp = val;
                break;
              }
            }
          }

          const existing = next.findIndex((e) => e.id === seg.id);
          const entry: TranscriptEntry = {
            id: seg.id,
            role: isUser ? "user" : "agent",
            text: seg.text,
            isFinal: seg.final,
            timestamp: Date.now(),
            voiceprint: vp,
          };
          if (existing >= 0) {
            next[existing] = entry;
          } else {
            next.push(entry);
          }
        }
        return next;
      });
    };

    // Listen for voiceprint data channel events
    const handleData = (
      payload: Uint8Array,
      participant?: Participant,
      _kind?: unknown,
      topic?: string,
    ) => {
      if (topic !== "voiceprint") return;
      try {
        const data = JSON.parse(new TextDecoder().decode(payload));
        if (data.type === "voiceprint_result") {
          const textKey = data.text?.slice(0, 20) || "";
          vpRef.current.set(textKey, {
            score: data.score,
            isPrimary: data.is_primary,
            isAnchor: data.is_anchor,
          });
          setSpeakerStatus({
            enrolled: true,
            lastScore: data.score,
          });
          // Cleanup old entries
          if (vpRef.current.size > 50) {
            const keys = Array.from(vpRef.current.keys());
            keys.slice(0, 25).forEach((k) => vpRef.current.delete(k));
          }
        }
      } catch {
        // ignore parse errors
      }
    };

    room.on(RoomEvent.TranscriptionReceived, handleTranscription);
    room.on(RoomEvent.DataReceived, handleData);
    return () => {
      room.off(RoomEvent.TranscriptionReceived, handleTranscription);
      room.off(RoomEvent.DataReceived, handleData);
    };
  }, [room]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries]);

  if (entries.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-2" style={{ color: "var(--fg-3)" }}>
        <p className="text-[13px]">聆听中... 转写文本将显示在这里</p>
        {speakerStatus.enrolled && (
          <p className="text-[10px]" style={{ color: "var(--green)" }}>声纹已注册</p>
        )}
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      {entries.map((entry) => {
        const color = entry.role === "user" ? "var(--accent)" : "var(--green)";
        const vp = entry.voiceprint;

        return (
          <div key={entry.id} className="transcript-item">
            {/* Role + voiceprint badge */}
            <div className="flex-shrink-0 pt-[1px]" style={{ width: 72 }}>
              <span style={{
                fontSize: 11, fontWeight: 600,
                letterSpacing: "0.04em", textTransform: "uppercase", color,
              }}>
                {entry.role === "user" ? "你" : "助手"}
              </span>
              {vp && entry.role === "user" && (
                <span
                  className="ml-1"
                  style={{
                    fontSize: 9,
                    fontWeight: 500,
                    color: vp.isPrimary ? "var(--green)" : "var(--red)",
                    opacity: 0.8,
                  }}
                  title={`声纹匹配: ${vp.score}`}
                >
                  {vp.isAnchor ? "●" : vp.isPrimary ? `${Math.round(vp.score * 100)}%` : "✕"}
                </span>
              )}
            </div>

            {/* Text */}
            <p style={{
              flex: 1, fontSize: 13, lineHeight: 1.65,
              color: vp && !vp.isPrimary ? "var(--fg-3)" : "var(--fg)",
              opacity: entry.isFinal ? 1 : 0.5,
              textDecoration: vp && !vp.isPrimary ? "line-through" : "none",
            }}>
              {entry.text}
            </p>
          </div>
        );
      })}
      <div ref={endRef} />
    </div>
  );
}

/**
 * Fallback transcript from message store (non-LiveKit contexts).
 */
interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
  isTruncated?: boolean;
}

export function TranscriptPanel({ messages }: { messages: Message[] }) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ color: "var(--fg-3)" }}>
        <p className="text-[13px]">转写文本将显示在这里...</p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      {messages.map((msg) => (
        <div key={msg.id} className="transcript-item">
          <span
            className="flex-shrink-0 pt-[1px]"
            style={{
              width: 52, fontSize: 11, fontWeight: 600,
              letterSpacing: "0.04em", textTransform: "uppercase",
              color: msg.role === "user" ? "var(--accent)" : msg.role === "assistant" ? "var(--green)" : "var(--fg-3)",
            }}
          >
            {msg.role === "user" ? "你" : msg.role === "assistant" ? "助手" : "系统"}
          </span>
          <p style={{
            flex: 1, fontSize: 13, lineHeight: 1.65,
            color: msg.role === "system" ? "var(--fg-3)" : "var(--fg)",
            opacity: msg.isTruncated ? 0.5 : 1,
          }}>
            {msg.content}
          </p>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}
