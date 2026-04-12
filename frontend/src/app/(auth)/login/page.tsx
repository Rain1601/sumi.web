"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useAuthStore } from "@/stores/auth";

export default function LoginPage() {
  const { signInWithGoogle, signInWithGitHub, signInWithEmail, signUpWithEmail } = useAuth();
  const { setAuth } = useAuthStore();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSignUp, setIsSignUp] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleEmailAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (isSignUp) {
        await signUpWithEmail(email, password);
        setError("Check your email to confirm your account.");
      } else {
        await signInWithEmail(email, password);
        router.push("/conversation");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  const skip = () => {
    setAuth("dev_user", "dev_user", "Guest");
    router.push("/conversation");
  };

  return (
    <main className="flex min-h-screen items-center justify-center" style={{ background: "var(--bg-0)" }}>
      <div className="w-full max-w-[360px] px-6 animate-in">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-5">
            <span className="flex items-center justify-center w-[30px] h-[30px] rounded-[8px] text-[13px] font-bold"
              style={{ background: "var(--fg)", color: "var(--bg-0)" }}>K</span>
            <span className="text-[16px] font-semibold" style={{ color: "var(--fg)" }}>Kodama</span>
          </div>
          <p className="text-[13px]" style={{ color: "var(--fg-3)" }}>
            {isSignUp ? "Create your account" : "Sign in to continue"}
          </p>
        </div>

        {/* OAuth */}
        <div className="space-y-2 mb-6">
          <button onClick={async () => { try { await signInWithGitHub(); router.push("/conversation"); } catch (err) { setError(err instanceof Error ? err.message : "GitHub login failed"); } }}
            className="flex w-full items-center justify-center gap-2.5 h-[42px] rounded-[var(--radius-full)] text-[13px] font-medium"
            style={{ background: "var(--bg-2)", color: "var(--fg)", border: "1px solid var(--border-2)", cursor: "pointer", transition: "all 0.15s ease" }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--border-3)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border-2)"; }}
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
            </svg>
            Continue with GitHub
          </button>
          <button onClick={async () => { try { await signInWithGoogle(); router.push("/conversation"); } catch (err) { setError(err instanceof Error ? err.message : "Google login failed"); } }}
            className="flex w-full items-center justify-center gap-2.5 h-[42px] rounded-[var(--radius-full)] text-[13px] font-medium"
            style={{ background: "var(--bg-2)", color: "var(--fg)", border: "1px solid var(--border-2)", cursor: "pointer", transition: "all 0.15s ease" }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--border-3)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border-2)"; }}
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            Continue with Google
          </button>
        </div>

        <div className="flex items-center gap-3 mb-6">
          <div className="h-px flex-1" style={{ background: "var(--border-1)" }} />
          <span className="text-[11px]" style={{ color: "var(--fg-3)" }}>or</span>
          <div className="h-px flex-1" style={{ background: "var(--border-1)" }} />
        </div>

        {/* Email form */}
        <form onSubmit={handleEmailAuth} className="space-y-3 mb-6">
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
            placeholder="Email" required className="input" style={{ height: 42 }} />
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
            placeholder="Password" required minLength={6} className="input" style={{ height: 42 }} />
          {error && <p className="text-[12px]" style={{ color: "var(--red)" }}>{error}</p>}
          <button type="submit" disabled={loading} className="btn btn-primary w-full" style={{ height: 42, fontSize: 13 }}>
            {loading ? "..." : isSignUp ? "Sign Up" : "Sign In"}
          </button>
        </form>

        <div className="flex flex-col items-center gap-3">
          <p className="text-[12px]" style={{ color: "var(--fg-3)" }}>
            {isSignUp ? "Have an account?" : "No account?"}{" "}
            <button onClick={() => { setIsSignUp(!isSignUp); setError(null); }}
              style={{ color: "var(--accent)", background: "none", border: "none", cursor: "pointer", fontSize: "12px" }}>
              {isSignUp ? "Sign in" : "Sign up"}
            </button>
          </p>
          {process.env.NODE_ENV === "development" && (
            <button onClick={skip}
              className="text-[11px] tracking-[0.04em] uppercase"
              style={{ color: "var(--fg-3)", background: "none", border: "none", cursor: "pointer", transition: "color 0.15s" }}
              onMouseEnter={(e) => { e.currentTarget.style.color = "var(--fg-2)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = "var(--fg-3)"; }}
            >Skip login (dev)</button>
          )}
        </div>
      </div>
    </main>
  );
}
