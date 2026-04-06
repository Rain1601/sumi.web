"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth";

/* ============================================================
   Hand-drawn SVG Hero Illustration
   Voice AI pipeline: microphone → ASR → NLP → TTS → speaker
   Anthropic style: terracotta + cream on dark, organic wobble
   ============================================================ */
function HeroIllustration() {
  return (
    <svg
      viewBox="0 0 480 320"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Voice AI pipeline illustration"
      style={{ width: "100%", maxWidth: 520, height: "auto" }}
    >
      {/* ─── Color vars (consumed via style attr) ─── */}
      {/* --bg: #1a1816, --terracotta: #d97757, --cream: #faf8f4 */}

      <defs>
        {/* Wobble filter — medium sketch */}
        <filter id="sketch" x="-5%" y="-5%" width="110%" height="110%">
          <feTurbulence
            type="turbulence"
            baseFrequency="0.025"
            numOctaves="4"
            seed="42"
            result="turb"
          />
          <feDisplacementMap
            in="SourceGraphic"
            in2="turb"
            scale="3"
            xChannelSelector="R"
            yChannelSelector="G"
          />
        </filter>

        {/* Lighter filter for structural elements */}
        <filter id="sketch-light" x="-5%" y="-5%" width="110%" height="110%">
          <feTurbulence
            type="turbulence"
            baseFrequency="0.03"
            numOctaves="4"
            seed="17"
            result="turb"
          />
          <feDisplacementMap
            in="SourceGraphic"
            in2="turb"
            scale="2.5"
            xChannelSelector="R"
            yChannelSelector="G"
          />
        </filter>
      </defs>

      <style>{`
        .draw-stroke {
          stroke-dasharray: 1000;
          stroke-dashoffset: 1000;
          animation: drawIn 2.5s cubic-bezier(0.25, 0.46, 0.45, 0.94) forwards;
        }
        .draw-stroke.d1 { animation-delay: 0.3s; }
        .draw-stroke.d2 { animation-delay: 0.6s; }
        .draw-stroke.d3 { animation-delay: 0.9s; }
        .draw-stroke.d4 { animation-delay: 1.2s; }
        .draw-stroke.d5 { animation-delay: 1.5s; }
        .draw-stroke.d6 { animation-delay: 1.8s; }
        @keyframes drawIn { to { stroke-dashoffset: 0; } }

        .fade-fill {
          opacity: 0;
          animation: fillIn 0.8s ease forwards;
        }
        .fade-fill.f1 { animation-delay: 0.8s; }
        .fade-fill.f2 { animation-delay: 1.1s; }
        .fade-fill.f3 { animation-delay: 1.4s; }
        .fade-fill.f4 { animation-delay: 1.7s; }
        .fade-fill.f5 { animation-delay: 2.0s; }
        @keyframes fillIn { to { opacity: 1; } }

        .float-a {
          animation: floatA 7s ease-in-out infinite;
          animation-delay: 3s;
        }
        .float-b {
          animation: floatB 6s ease-in-out infinite;
          animation-delay: 3.5s;
        }
        @keyframes floatA {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-6px); }
        }
        @keyframes floatB {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(5px); }
        }

        @media (prefers-reduced-motion: reduce) {
          .draw-stroke { animation: none; stroke-dashoffset: 0; }
          .fade-fill { animation: none; opacity: 1; }
          .float-a, .float-b { animation: none; }
        }
      `}</style>

      {/* ═══════ MAIN FILTERED GROUP ═══════ */}
      <g filter="url(#sketch)">

        {/* ─── Connecting lines (cream, double-stroke) ─── */}

        {/* Line: Mic node → ASR node */}
        {/* Ghost pass */}
        <path
          d="M92 162 C120 155, 145 148, 168 152"
          stroke="#faf8f4"
          strokeWidth="5"
          strokeLinecap="round"
          fill="none"
          opacity="0.3"
          className="draw-stroke"
        />
        {/* Main pass */}
        <path
          d="M90 160 C118 153, 143 146, 170 150"
          stroke="#faf8f4"
          strokeWidth="4"
          strokeLinecap="round"
          fill="none"
          className="draw-stroke"
        />

        {/* Line: ASR → NLP (center) */}
        {/* Ghost */}
        <path
          d="M210 152 C225 140, 248 135, 270 142"
          stroke="#d97757"
          strokeWidth="5.5"
          strokeLinecap="round"
          fill="none"
          opacity="0.35"
          className="draw-stroke d1"
        />
        {/* Main */}
        <path
          d="M208 150 C223 138, 246 133, 272 140"
          stroke="#d97757"
          strokeWidth="4.5"
          strokeLinecap="round"
          fill="none"
          className="draw-stroke d1"
        />

        {/* Line: NLP → TTS */}
        {/* Ghost */}
        <path
          d="M318 148 C338 152, 358 160, 378 168"
          stroke="#d97757"
          strokeWidth="5.5"
          strokeLinecap="round"
          fill="none"
          opacity="0.35"
          className="draw-stroke d2"
        />
        {/* Main */}
        <path
          d="M320 146 C340 150, 360 158, 380 166"
          stroke="#d97757"
          strokeWidth="4.5"
          strokeLinecap="round"
          fill="none"
          className="draw-stroke d2"
        />

        {/* Line: TTS → Speaker */}
        {/* Ghost */}
        <path
          d="M418 170 C430 168, 442 165, 454 160"
          stroke="#faf8f4"
          strokeWidth="4.5"
          strokeLinecap="round"
          fill="none"
          opacity="0.3"
          className="draw-stroke d3"
        />
        {/* Main */}
        <path
          d="M416 168 C428 166, 440 163, 452 158"
          stroke="#faf8f4"
          strokeWidth="3.5"
          strokeLinecap="round"
          fill="none"
          className="draw-stroke d3"
        />

        {/* ─── Nodes (terracotta filled blobs — path not geometry) ─── */}

        {/* Node 1: Microphone (left) — larger */}
        <g className="float-a">
          <path
            d="M72 142 C82 138, 92 140, 96 150 C100 160, 95 172, 85 176 C75 180, 64 175, 60 165 C56 155, 62 144, 72 142Z"
            fill="#d97757"
            className="fade-fill f1"
          />
          {/* Mic icon sketch lines inside */}
          <path
            d="M75 155 C76 150, 80 147, 84 148"
            stroke="#faf8f4"
            strokeWidth="2"
            strokeLinecap="round"
            fill="none"
            opacity="0.7"
            className="draw-stroke d4"
          />
          <path
            d="M73 163 C76 166, 82 167, 86 164"
            stroke="#faf8f4"
            strokeWidth="1.5"
            strokeLinecap="round"
            fill="none"
            opacity="0.5"
            className="draw-stroke d4"
          />
        </g>

        {/* Node 2: ASR */}
        <g className="float-b">
          <path
            d="M180 134 C192 130, 204 135, 206 147 C208 159, 200 168, 188 170 C176 172, 168 164, 170 152 C172 140, 178 136, 180 134Z"
            fill="#d97757"
            className="fade-fill f2"
          />
        </g>

        {/* Node 3: NLP (center — largest, the "brain") */}
        <g className="float-a">
          <path
            d="M278 118 C296 114, 316 120, 320 138 C324 156, 314 172, 296 176 C278 180, 264 170, 260 152 C256 134, 266 120, 278 118Z"
            fill="#d97757"
            className="fade-fill f3"
          />
          {/* Brain detail — small inner loops */}
          <path
            d="M282 140 C286 134, 296 132, 302 138 C308 144, 305 152, 298 155"
            stroke="#faf8f4"
            strokeWidth="2"
            strokeLinecap="round"
            fill="none"
            opacity="0.6"
            className="draw-stroke d5"
          />
          <path
            d="M285 155 C288 160, 296 162, 302 158"
            stroke="#faf8f4"
            strokeWidth="1.5"
            strokeLinecap="round"
            fill="none"
            opacity="0.4"
            className="draw-stroke d5"
          />
        </g>

        {/* Node 4: TTS */}
        <g className="float-b">
          <path
            d="M392 152 C404 148, 414 154, 416 166 C418 178, 410 186, 398 188 C386 190, 378 182, 380 170 C382 158, 388 154, 392 152Z"
            fill="#d97757"
            className="fade-fill f4"
          />
        </g>

        {/* ─── Voice wave squiggle (decorative, below the pipeline) ─── */}
        {/* Pressure variation: thick start → thin end */}

        {/* Segment 1 — thick */}
        <path
          d="M120 220 C140 210, 160 230, 180 218"
          stroke="#faf8f4"
          strokeWidth="6"
          strokeLinecap="round"
          fill="none"
          opacity="0.6"
          className="draw-stroke d4"
        />
        {/* Segment 2 — medium */}
        <path
          d="M180 218 C200 206, 218 232, 240 220"
          stroke="#faf8f4"
          strokeWidth="5"
          strokeLinecap="round"
          fill="none"
          opacity="0.5"
          className="draw-stroke d5"
        />
        {/* Segment 3 — thinner */}
        <path
          d="M240 220 C260 208, 278 228, 298 216"
          stroke="#faf8f4"
          strokeWidth="4"
          strokeLinecap="round"
          fill="none"
          opacity="0.4"
          className="draw-stroke d5"
        />
        {/* Segment 4 — thin tail */}
        <path
          d="M298 216 C312 210, 328 222, 345 215"
          stroke="#faf8f4"
          strokeWidth="3"
          strokeLinecap="round"
          fill="none"
          opacity="0.3"
          className="draw-stroke d6"
        />

        {/* ─── Small accent dots (decorative) ─── */}
        <path
          d="M155 190 C158 188, 161 190, 160 193 C159 196, 155 197, 154 194 C153 191, 155 190, 155 190Z"
          fill="#d97757"
          opacity="0.6"
          className="fade-fill f4"
        />
        <path
          d="M340 195 C343 193, 346 195, 345 198 C344 201, 340 202, 339 199 C338 196, 340 195, 340 195Z"
          fill="#d97757"
          opacity="0.5"
          className="fade-fill f5"
        />
      </g>

      {/* ─── Labels (lighter filter for text-like elements) ─── */}
      <g filter="url(#sketch-light)">
        {/* ASR label */}
        <text
          x="185"
          y="196"
          fill="#faf8f4"
          fontSize="10"
          fontFamily="'IBM Plex Mono', monospace"
          fontWeight="500"
          opacity="0.55"
          className="fade-fill f2"
        >
          ASR
        </text>
        {/* NLP label */}
        <text
          x="280"
          y="200"
          fill="#faf8f4"
          fontSize="10"
          fontFamily="'IBM Plex Mono', monospace"
          fontWeight="500"
          opacity="0.55"
          className="fade-fill f3"
        >
          NLP
        </text>
        {/* TTS label */}
        <text
          x="390"
          y="210"
          fill="#faf8f4"
          fontSize="10"
          fontFamily="'IBM Plex Mono', monospace"
          fontWeight="500"
          opacity="0.55"
          className="fade-fill f4"
        >
          TTS
        </text>
      </g>
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
      className="flex min-h-screen flex-col items-center relative overflow-hidden"
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

      {/* ═══ Hero Section ═══ */}
      <section
        className="relative z-10 flex flex-col items-center gap-6 w-full"
        style={{ paddingTop: "10vh", paddingBottom: 48 }}
      >
        {/* Logo */}
        <div
          className="flex items-center justify-center w-14 h-14 rounded-2xl text-xl font-bold animate-in"
          style={{ background: "var(--accent)", color: "white" }}
        >
          S
        </div>

        {/* Title + subtitle */}
        <div className="text-center animate-in" style={{ animationDelay: "0.05s" }}>
          <h1
            className="text-[48px] font-bold tracking-[-0.04em]"
            style={{ color: "var(--fg)" }}
          >
            sumi.web
          </h1>
          <p
            className="text-[17px] mt-3 max-w-md mx-auto"
            style={{ color: "var(--fg-3)", lineHeight: 1.6 }}
          >
            Build, test, and deploy real-time voice AI agents
            with pluggable models and long-term memory
          </p>
        </div>

        {/* CTAs */}
        <div
          className="flex items-center gap-3 mt-1 animate-in"
          style={{ animationDelay: "0.1s" }}
        >
          <Link
            href="/login"
            className="btn btn-accent"
            style={{ padding: "11px 28px", fontSize: "14px" }}
          >
            Get Started
          </Link>
          <Link
            href="/conversation"
            className="btn btn-primary"
            style={{ padding: "11px 28px", fontSize: "14px" }}
          >
            Try Demo
          </Link>
        </div>

        <button
          onClick={skip}
          className="text-[11px] tracking-[0.04em] uppercase btn btn-ghost animate-in"
          style={{ animationDelay: "0.15s" }}
        >
          Skip login
        </button>
      </section>

      {/* ═══ SVG Illustration ═══ */}
      <section
        className="relative z-10 w-full flex justify-center animate-in"
        style={{ animationDelay: "0.2s", padding: "0 24px" }}
      >
        <HeroIllustration />
      </section>

      {/* ═══ Feature Cards ═══ */}
      <section
        className="relative z-10 w-full"
        style={{ maxWidth: 800, padding: "48px 24px 80px" }}
      >
        <div className="grid grid-cols-2 gap-4" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
          {FEATURES.map((f, i) => (
            <div
              key={f.title}
              className="card animate-in"
              style={{
                padding: "20px 22px",
                animationDelay: `${0.3 + i * 0.06}s`,
              }}
            >
              <div
                className="flex items-center justify-center w-9 h-9 rounded-lg mb-3"
                style={{
                  background: "var(--accent-light)",
                  color: "var(--accent-text)",
                }}
              >
                {f.icon}
              </div>
              <h3
                className="text-[14px] font-semibold mb-1"
                style={{ color: "var(--fg)" }}
              >
                {f.title}
              </h3>
              <p className="text-[12px]" style={{ color: "var(--fg-3)", lineHeight: 1.5 }}>
                {f.desc}
              </p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
