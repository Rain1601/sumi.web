"use client";

import { useRef, useEffect, useState } from "react";
import { useRoomContext } from "@livekit/components-react";
import { RoomEvent, TranscriptionSegment, Participant } from "livekit-client";

interface TranscriptEntry {
  id: string;
  role: "user" | "agent";
  text: string;
  isFinal: boolean;
  timestamp: number;
}

/**
 * Live transcript using low-level LiveKit transcription events.
 * More reliable than useTranscriptions() hook.
 */
export function LiveTranscriptPanel() {
  const room = useRoomContext();
  const [entries, setEntries] = useState<TranscriptEntry[]>([]);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!room) return;

    const localIdentity = room.localParticipant?.identity;

    const handleTranscription = (
      segments: TranscriptionSegment[],
      participant?: Participant,
    ) => {
      // Debug: log participant info to understand who sends what
      console.log("[Transcript]", {
        participantIdentity: participant?.identity,
        isLocal: participant?.isLocal,
        localIdentity,
        text: segments[0]?.text?.slice(0, 30),
      });

      // In LiveKit Agents: the agent sends both user ASR transcripts and its own speech.
      // User ASR transcripts are published on the LOCAL participant's track (isLocal=true).
      // Agent speech transcripts are published on the REMOTE agent's track (isLocal=false).
      const isUser = participant?.isLocal === true;

      setEntries((prev) => {
        const next = [...prev];
        for (const seg of segments) {
          const existing = next.findIndex((e) => e.id === seg.id);
          const entry: TranscriptEntry = {
            id: seg.id,
            role: isUser ? "user" : "agent",
            text: seg.text,
            isFinal: seg.final,
            timestamp: Date.now(),
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

    room.on(RoomEvent.TranscriptionReceived, handleTranscription);
    return () => {
      room.off(RoomEvent.TranscriptionReceived, handleTranscription);
    };
  }, [room]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries]);

  if (entries.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ color: "var(--fg-3)" }}>
        <p className="text-[13px]">Listening... transcript will appear here</p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      {entries.map((entry) => {
        const color = entry.role === "user" ? "var(--accent)" : "var(--green)";
        return (
          <div key={entry.id} className="transcript-item">
            <span
              className="flex-shrink-0 pt-[1px]"
              style={{
                width: 52, fontSize: 11, fontWeight: 600,
                letterSpacing: "0.04em", textTransform: "uppercase", color,
              }}
            >
              {entry.role === "user" ? "You" : "Agent"}
            </span>
            <p style={{
              flex: 1, fontSize: 13, lineHeight: 1.65,
              color: "var(--fg)",
              opacity: entry.isFinal ? 1 : 0.5,
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
 * Fallback transcript from message store.
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
        <p className="text-[13px]">Transcript will appear here...</p>
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
            {msg.role === "user" ? "You" : msg.role === "assistant" ? "Agent" : "Sys"}
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
