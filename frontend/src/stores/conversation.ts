import { create } from "zustand";

interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
  isTruncated?: boolean;
}

interface ConversationState {
  messages: Message[];
  currentAgentId: string | null;
  isConnected: boolean;
  isSpeaking: boolean;

  addMessage: (msg: Message) => void;
  updateLastMessage: (content: string) => void;
  setAgent: (agentId: string) => void;
  setConnected: (connected: boolean) => void;
  setSpeaking: (speaking: boolean) => void;
  clearMessages: () => void;
}

export const useConversationStore = create<ConversationState>((set) => ({
  messages: [],
  currentAgentId: null,
  isConnected: false,
  isSpeaking: false,

  addMessage: (msg) =>
    set((state) => ({ messages: [...state.messages, msg] })),

  updateLastMessage: (content) =>
    set((state) => {
      const msgs = [...state.messages];
      if (msgs.length > 0) {
        msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], content };
      }
      return { messages: msgs };
    }),

  setAgent: (agentId) => set({ currentAgentId: agentId }),
  setConnected: (connected) => set({ isConnected: connected }),
  setSpeaking: (speaking) => set({ isSpeaking: speaking }),
  clearMessages: () => set({ messages: [] }),
}));
