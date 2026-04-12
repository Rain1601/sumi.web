"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth";

/* ============================================================
   Hand-drawn SVG Hero Illustration
   Condenser microphone — Anthropic style matching Muses pen
   Terracotta + cream on dark, bold confident strokes, no filters
   ============================================================ */
function HeroIllustration() {
  return (
    <svg
      viewBox="0 0 420 500"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Voice AI microphone illustration"
      style={{ width: "100%", maxWidth: 320, height: "auto" }}
    >
      {/* === Microphone head (terracotta filled, hand-drawn oval) === */}
      <path
        d="M210 68 C220 64, 232 70, 240 90 C248 110, 252 142, 253 175 C254 208, 250 235, 242 255 C234 275, 224 282, 212 283 C200 284, 190 277, 182 257 C174 237, 168 210, 167 177 C166 144, 170 112, 178 92 C186 72, 200 66, 210 68Z"
        fill="#d97757"
      />
      {/* Mic outline (cream, bold stroke) */}
      <path
        d="M210 68 C220 64, 232 70, 240 90 C248 110, 252 142, 253 175 C254 208, 250 235, 242 255 C234 275, 224 282, 212 283 C200 284, 190 277, 182 257 C174 237, 168 210, 167 177 C166 144, 170 112, 178 92 C186 72, 200 66, 210 68Z"
        stroke="rgba(255,255,255,0.9)" strokeWidth="7" strokeLinecap="round" fill="none"
      />

      {/* Mic grille detail lines (cream, horizontal) */}
      <path d="M180 115 C194 111, 222 110, 242 114"
        stroke="rgba(255,255,255,0.4)" strokeWidth="4" strokeLinecap="round" />
      <path d="M176 150 C192 146, 224 145, 246 149"
        stroke="rgba(255,255,255,0.35)" strokeWidth="4" strokeLinecap="round" />
      <path d="M174 185 C190 181, 226 180, 248 184"
        stroke="rgba(255,255,255,0.3)" strokeWidth="4" strokeLinecap="round" />
      <path d="M176 220 C192 216, 224 215, 244 219"
        stroke="rgba(255,255,255,0.25)" strokeWidth="4" strokeLinecap="round" />

      {/* === Mic stand / stem === */}
      <path d="M204 280 C207 308, 209 338, 210 368"
        stroke="rgba(255,255,255,0.88)" strokeWidth="8" strokeLinecap="round" />
      <path d="M220 278 C218 306, 214 336, 212 366"
        stroke="rgba(255,255,255,0.88)" strokeWidth="8" strokeLinecap="round" />
      {/* Center slit */}
      <path d="M211 288 L211 362"
        stroke="rgba(255,255,255,0.3)" strokeWidth="3" strokeLinecap="round" />

      {/* === Sound dots (terracotta blobs near the mic tip) === */}
      <path d="M230 358 C236 353, 242 359, 238 367 C234 375, 226 373, 228 365 C230 361, 232 357, 230 358Z"
        fill="#d97757" />
      <path d="M188 371 C192 367, 197 371, 195 377 C193 383, 186 381, 187 375Z"
        fill="#d97757" />

      {/* === Sound wave arcs (right side of mic, cream) === */}
      <path d="M262 370 C278 365, 298 362, 326 367"
        stroke="rgba(255,255,255,0.5)" strokeWidth="6" strokeLinecap="round" />
      <path d="M258 394 C276 390, 310 388, 340 392"
        stroke="rgba(255,255,255,0.38)" strokeWidth="5" strokeLinecap="round" />
      <path d="M266 418 C284 414, 315 413, 334 416"
        stroke="rgba(255,255,255,0.28)" strokeWidth="4" strokeLinecap="round" />

      {/* === Decorative Squiggle (signature hand motif) === */}
      {/* Wavy M-shape — thick cream, pressure variation */}
      <path d="M68 432 C76 409, 88 437, 101 415 C114 393, 103 435, 125 417 C147 399, 131 435, 151 422"
        stroke="rgba(255,255,255,0.92)" strokeWidth="10" strokeLinecap="round" />
      {/* Loop */}
      <path d="M151 422 C168 437, 183 422, 178 405 C173 388, 155 395, 158 415"
        stroke="rgba(255,255,255,0.88)" strokeWidth="9" strokeLinecap="round" />
      {/* Tail — pressure decreasing */}
      <path d="M158 415 C173 437, 191 434, 204 447"
        stroke="rgba(255,255,255,0.82)" strokeWidth="7" strokeLinecap="round" />
      {/* Terracotta dot at loop junction */}
      <path d="M156 413 C163 407, 167 413, 161 419 C155 425, 149 419, 156 413Z"
        fill="#d97757" />
    </svg>
  );
}

/* ============================================================
   Feature card data
   ============================================================ */
const FEATURES = [
  {
    title: "Real-time Voice",
    desc: "WebRTC audio pipeline with < 500ms E2E latency",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
        <line x1="12" y1="19" x2="12" y2="23" />
      </svg>
    ),
  },
  {
    title: "Function Calling",
    desc: "Weather, search, datetime — agents call real tools",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
      </svg>
    ),
  },
  {
    title: "Long-term Memory",
    desc: "ChromaDB vectors + structured facts across sessions",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
        <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
        <line x1="12" y1="22.08" x2="12" y2="12" />
      </svg>
    ),
  },
  {
    title: "Pluggable Providers",
    desc: "Swap ASR/NLP/TTS models per agent — Claude, GPT, Qwen",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
        <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
      </svg>
    ),
  },
];

/* ============================================================
   HOME PAGE
   ============================================================ */
export default function Home() {
  const router = useRouter();
  const { setAuth } = useAuthStore();
  const skip = () => {
    setAuth("dev_user", "dev_user", "Guest");
    router.push("/conversation");
  };

  return (
    <main
      className="flex h-screen flex-col items-center relative overflow-hidden"
      style={{ background: "var(--bg-0)" }}
    >
      {/* Ambient glow — terracotta tint */}
      <div
        className="fixed pointer-events-none"
        style={{
          top: "-10%",
          left: "50%",
          width: 700,
          height: 700,
          borderRadius: "50%",
          transform: "translateX(-50%)",
          background:
            "radial-gradient(circle, rgba(217,119,87,0.06) 0%, transparent 60%)",
        }}
      />

      {/* ═══ Hero — illustration + text + buttons, vertically centered ═══ */}
      <section
        className="relative z-10 flex flex-col items-center justify-center flex-1 w-full"
        style={{ paddingBottom: 16 }}
      >
        {/* Illustration */}
        <div className="animate-in" style={{ marginBottom: -12 }}>
          <HeroIllustration />
        </div>

        {/* Title */}
        <h1
          className="text-[44px] font-bold tracking-[-0.04em] animate-in"
          style={{ color: "var(--fg)", animationDelay: "0.05s" }}
        >
          Kodama
        </h1>

        {/* Subtitle */}
        <p
          className="text-[15px] mt-1 animate-in"
          style={{ color: "var(--fg-3)", fontStyle: "italic", animationDelay: "0.08s" }}
        >
          Real-time Voice AI Agent Platform
        </p>

        {/* CTAs */}
        <div
          className="flex items-center gap-3 mt-5 animate-in"
          style={{ animationDelay: "0.12s" }}
        >
          <Link
            href="/login"
            className="btn btn-accent"
            style={{ padding: "10px 26px", fontSize: "14px" }}
          >
            Get Started
          </Link>
          <Link
            href="/conversation"
            className="btn btn-primary"
            style={{ padding: "10px 26px", fontSize: "14px" }}
          >
            Try Demo
          </Link>
        </div>

        {process.env.NODE_ENV === "development" && (
          <button
            onClick={skip}
            className="text-[11px] tracking-[0.04em] uppercase btn btn-ghost mt-3 animate-in"
            style={{ animationDelay: "0.15s" }}
          >
            Skip login
          </button>
        )}
      </section>

      {/* ═══ Feature row — bottom of viewport, horizontal ═══ */}
      <section
        className="relative z-10 w-full flex-shrink-0"
        style={{ borderTop: "1px solid rgba(255,255,255,0.06)", padding: "16px 0" }}
      >
        <div
          className="flex justify-center gap-8 animate-in"
          style={{ maxWidth: 800, margin: "0 auto", padding: "0 24px", animationDelay: "0.25s" }}
        >
          {FEATURES.map((f) => (
            <div key={f.title} className="flex items-center gap-3" style={{ flex: 1, maxWidth: 200 }}>
              <div
                className="flex items-center justify-center flex-shrink-0"
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 8,
                  background: "var(--accent-light)",
                  color: "var(--accent-text)",
                }}
              >
                {f.icon}
              </div>
              <div>
                <h3 className="text-[12px] font-semibold" style={{ color: "var(--fg)" }}>
                  {f.title}
                </h3>
                <p className="text-[10px]" style={{ color: "var(--fg-3)", lineHeight: 1.4 }}>
                  {f.desc}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
