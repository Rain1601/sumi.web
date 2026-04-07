"use client";

import { useEffect, useCallback } from "react";
import {
  signInWithPopup,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut as firebaseSignOut,
  GoogleAuthProvider,
  GithubAuthProvider,
  onAuthStateChanged,
} from "firebase/auth";
import { getFirebaseAuth } from "@/lib/firebase";
import { useAuthStore } from "@/stores/auth";

const googleProvider = new GoogleAuthProvider();
const githubProvider = new GithubAuthProvider();

export function useAuth() {
  const { setAuth, clearAuth, isAuthenticated } = useAuthStore();

  useEffect(() => {
    const auth = getFirebaseAuth();
    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      if (user) {
        const token = await user.getIdToken();
        setAuth(
          user.uid,
          token,
          user.displayName || user.email || undefined
        );
      } else {
        clearAuth();
      }
    });
    return () => unsubscribe();
  }, [setAuth, clearAuth]);

  // Auto-refresh token before expiry
  useEffect(() => {
    const interval = setInterval(async () => {
      const auth = getFirebaseAuth();
      const user = auth.currentUser;
      if (user) {
        const token = await user.getIdToken(true);
        setAuth(user.uid, token, user.displayName || user.email || undefined);
      }
    }, 50 * 60 * 1000); // Refresh every 50 minutes (tokens expire in 60)
    return () => clearInterval(interval);
  }, [setAuth]);

  const signInWithGoogle = useCallback(async () => {
    const auth = getFirebaseAuth();
    await signInWithPopup(auth, googleProvider);
  }, []);

  const signInWithGitHub = useCallback(async () => {
    const auth = getFirebaseAuth();
    await signInWithPopup(auth, githubProvider);
  }, []);

  const signInWithEmail = useCallback(
    async (email: string, password: string) => {
      const auth = getFirebaseAuth();
      await signInWithEmailAndPassword(auth, email, password);
    },
    []
  );

  const signUpWithEmail = useCallback(
    async (email: string, password: string) => {
      const auth = getFirebaseAuth();
      await createUserWithEmailAndPassword(auth, email, password);
    },
    []
  );

  const signOut = useCallback(async () => {
    const auth = getFirebaseAuth();
    await firebaseSignOut(auth);
    clearAuth();
  }, [clearAuth]);

  return {
    isAuthenticated,
    signInWithGoogle,
    signInWithGitHub,
    signInWithEmail,
    signUpWithEmail,
    signOut,
  };
}
