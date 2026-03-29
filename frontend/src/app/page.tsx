"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth";

const FEATURES = ["Real-time voice", "Multi-agent", "Pluggable ASR/TTS/NLP", "Long-term memory", "Event tracing"];

export default function Home() {
  const router = useRouter();
  const { setAuth } = useAuthStore();
  const skip = () => { setAuth("dev_user", "dev_user", "Guest"); router.push("/conversation"); };

  return (
    <main className="flex min-h-screen flex-col items-center justify-center relative overflow-hidden" style={{ background: "var(--bg-0)" }}>
      {/* Ambient glow */}
      <div className="fixed" style={{
        top: "-15%", left: "50%", width: 600, height: 600, borderRadius: "50%",
        transform: "translateX(-50%)",
        background: "radial-gradient(circle, rgba(0,122,255,0.06) 0%, transparent 60%)",
        pointerEvents: "none",
      }} />

      <div className="relative z-10 flex flex-col items-center gap-8 animate-in">
        <div className="flex items-center justify-center w-14 h-14 rounded-2xl text-xl font-bold"
          style={{ background: "var(--accent)", color: "white" }}>S</div>

        <div className="text-center">
          <h1 className="text-[42px] font-bold tracking-[-0.03em]" style={{ color: "var(--fg)" }}>sumi.web</h1>
          <p className="text-[16px] mt-3 max-w-sm" style={{ color: "var(--fg-3)" }}>Build and deploy real-time voice AI agents</p>
        </div>

        <div className="flex flex-wrap justify-center gap-2 max-w-md">
          {FEATURES.map((f, i) => (
            <span key={f} className="text-[11px] px-3 py-1.5 rounded-full animate-in glass"
              style={{ color: "var(--fg-3)", animationDelay: `${0.1 + i * 0.05}s` }}>{f}</span>
          ))}
        </div>

        <div className="flex items-center gap-3 mt-2">
          <Link href="/login" className="btn btn-accent" style={{ padding: "10px 26px", fontSize: "14px" }}>Get started</Link>
          <Link href="/conversation" className="btn btn-primary" style={{ padding: "10px 26px", fontSize: "14px" }}>Try demo</Link>
        </div>

        <button onClick={skip} className="text-[11px] tracking-[0.04em] uppercase btn btn-ghost">Skip login</button>
      </div>
    </main>
  );
}
