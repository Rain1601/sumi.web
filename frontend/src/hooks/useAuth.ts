"use client";

import { useEffect, useCallback } from "react";
import { createClient } from "@/lib/supabase";
import { useAuthStore } from "@/stores/auth";

export function useAuth() {
  const { setAuth, clearAuth, isAuthenticated } = useAuthStore();
  const supabase = createClient();

  useEffect(() => {
    // Check initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        setAuth(
          session.user.id,
          session.access_token,
          session.user.user_metadata?.full_name || session.user.email || undefined
        );
      }
    });

    // Listen for auth changes
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) {
        setAuth(
          session.user.id,
          session.access_token,
          session.user.user_metadata?.full_name || session.user.email || undefined
        );
      } else {
        clearAuth();
      }
    });

    return () => subscription.unsubscribe();
  }, [supabase, setAuth, clearAuth]);

  const signInWithGoogle = useCallback(async () => {
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/conversation` },
    });
  }, [supabase]);

  const signInWithGitHub = useCallback(async () => {
    await supabase.auth.signInWithOAuth({
      provider: "github",
      options: { redirectTo: `${window.location.origin}/conversation` },
    });
  }, [supabase]);

  const signInWithEmail = useCallback(
    async (email: string, password: string) => {
      const { error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });
      if (error) throw error;
    },
    [supabase]
  );

  const signUpWithEmail = useCallback(
    async (email: string, password: string) => {
      const { error } = await supabase.auth.signUp({ email, password });
      if (error) throw error;
    },
    [supabase]
  );

  const signOut = useCallback(async () => {
    await supabase.auth.signOut();
    clearAuth();
  }, [supabase, clearAuth]);

  return {
    isAuthenticated,
    signInWithGoogle,
    signInWithGitHub,
    signInWithEmail,
    signUpWithEmail,
    signOut,
  };
}
