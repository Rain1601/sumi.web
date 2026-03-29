import { create } from "zustand";

interface AuthState {
  userId: string | null;
  token: string | null;
  displayName: string | null;
  isAuthenticated: boolean;

  setAuth: (userId: string, token: string, displayName?: string) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  userId: null,
  token: null,
  displayName: null,
  isAuthenticated: false,

  setAuth: (userId, token, displayName) =>
    set({
      userId,
      token,
      displayName: displayName || userId,
      isAuthenticated: true,
    }),

  clearAuth: () =>
    set({
      userId: null,
      token: null,
      displayName: null,
      isAuthenticated: false,
    }),
}));
