"use client";

import { useEffect, useRef, useCallback } from "react";
import { useConversationStore } from "@/stores/conversation";

export function useTranscript(wsUrl: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const { addMessage, updateLastMessage } = useConversationStore();

  const handleEvent = useCallback(
    (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        const eventType = data.event_type as string;

        if (eventType === "asr.end" && data.data?.text) {
          addMessage({
            id: data.id,
            role: "user",
            content: data.data.text,
            timestamp: data.timestamp,
          });
        } else if (eventType === "tts.end" && data.data?.text) {
          addMessage({
            id: data.id,
            role: "assistant",
            content: data.data.text,
            timestamp: data.timestamp,
          });
        }
      } catch {
        // Ignore parse errors
      }
    },
    [addMessage, updateLastMessage]
  );

  useEffect(() => {
    if (!wsUrl) return;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    ws.onmessage = handleEvent;

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [wsUrl, handleEvent]);

  return wsRef;
}
