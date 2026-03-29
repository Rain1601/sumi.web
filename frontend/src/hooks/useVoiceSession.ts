"use client";

import { useState, useCallback } from "react";
import { connectToAgent } from "@/lib/livekit";

interface VoiceSessionState {
  serverUrl: string | null;
  token: string | null;
  roomName: string | null;
  isConnecting: boolean;
  error: string | null;
}

export function useVoiceSession() {
  const [state, setState] = useState<VoiceSessionState>({
    serverUrl: null,
    token: null,
    roomName: null,
    isConnecting: false,
    error: null,
  });

  const connect = useCallback(async (agentId: string, userToken: string) => {
    setState((s) => ({ ...s, isConnecting: true, error: null }));
    try {
      const result = await connectToAgent(agentId, userToken);
      setState({
        serverUrl: result.serverUrl,
        token: result.token,
        roomName: result.roomName,
        isConnecting: false,
        error: null,
      });
      return result;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Connection failed";
      setState((s) => ({ ...s, isConnecting: false, error: msg }));
      throw err;
    }
  }, []);

  const disconnect = useCallback(() => {
    setState({
      serverUrl: null,
      token: null,
      roomName: null,
      isConnecting: false,
      error: null,
    });
  }, []);

  return { ...state, connect, disconnect };
}
