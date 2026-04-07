"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useAuthStore } from "@/stores/auth";

const NAV = [
  { href: "/conversation", label: "Conversation", short: "Talk" },
  { href: "/agents", label: "Agents", short: "Agents" },
  { href: "/models", label: "Models", short: "Models" },
  { href: "/history", label: "History", short: "History" },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { signOut } = useAuth();
  const { displayName, isAuthenticated } = useAuthStore();
  const pathname = usePathname();
  const isActive = (href: string) => pathname === href || (href !== "/" && pathname.startsWith(href + "/"));

  return (
    <div className="flex min-h-screen" style={{ background: "var(--bg-0)" }}>
      {/* Sidebar — visionOS glass panel, inset from edge */}
      <div className="sidebar-desktop fixed top-0 left-0 z-40 h-screen flex items-stretch" style={{ width: "var(--sidebar-w)", padding: 8 }}>
        <aside className="glass flex flex-col flex-1" style={{ borderRadius: "var(--radius-lg)" }}>
          {/* Brand */}
          <Link href="/" className="flex items-center gap-2.5 px-5 h-[52px]" style={{ textDecoration: "none" }}>
            <span className="flex items-center justify-center w-[24px] h-[24px] rounded-[7px] text-[11px] font-bold"
              style={{ background: "var(--accent)", color: "white" }}>K</span>
            <span className="text-[14px] font-semibold tracking-[-0.02em]" style={{ color: "var(--fg)" }}>
              Kodama
            </span>
          </Link>

          {/* Nav */}
          <nav className="flex-1 px-2.5 pt-2">
            <div className="space-y-[2px]">
              {NAV.map((item) => (
                <Link key={item.href} href={item.href}
                  className="nav-link" data-active={isActive(item.href) ? "true" : undefined}>
                  <span className="w-[4px] h-[4px] rounded-full flex-shrink-0"
                    style={{
                      background: isActive(item.href) ? "var(--accent)" : "transparent",
                      boxShadow: isActive(item.href) ? "0 0 6px var(--accent-glow)" : "none",
                      transition: "all 0.25s ease",
                    }} />
                  {item.label}
                </Link>
              ))}
            </div>
          </nav>

          {/* User */}
          <div className="px-3 pb-3">
            <div className="flex items-center justify-between rounded-[10px] px-3 py-2.5"
              style={{ background: "rgba(255,255,255,0.04)" }}>
              <div className="flex items-center gap-2 min-w-0">
                <span className="flex items-center justify-center w-[20px] h-[20px] rounded-full text-[8px] font-bold flex-shrink-0"
                  style={{ background: "var(--accent-dim)", color: "var(--accent)" }}>
                  {(displayName || "G")[0].toUpperCase()}
                </span>
                <span className="text-[11px] truncate" style={{ color: "var(--fg-2)" }}>
                  {displayName || "Guest"}
                </span>
              </div>
              {isAuthenticated ? (
                <button onClick={signOut} className="btn btn-ghost" style={{ padding: "2px 8px", fontSize: "10px" }}>
                  Log out
                </button>
              ) : (
                <Link href="/login" className="text-[10px] font-medium" style={{ color: "var(--accent)", textDecoration: "none" }}>Sign in</Link>
              )}
            </div>
          </div>
        </aside>
      </div>

      {/* Main */}
      <main className="flex-1" style={{ marginLeft: "var(--sidebar-w)", overflowY: "auto", height: "100vh" }}>{children}</main>

      {/* Mobile bar */}
      <nav className="mobile-bar fixed bottom-0 left-0 right-0 z-40 justify-around items-center h-[52px] glass"
        style={{ borderTop: "1px solid var(--glass-border)", borderRadius: 0 }}>
        {NAV.slice(0, 4).map((item) => (
          <Link key={item.href} href={item.href}
            className="flex flex-col items-center gap-0.5 py-1"
            style={{ color: isActive(item.href) ? "var(--fg)" : "var(--fg-3)", textDecoration: "none", fontSize: "10px", fontWeight: isActive(item.href) ? 500 : 400 }}>
            {isActive(item.href) && <span className="w-[3px] h-[3px] rounded-full" style={{ background: "var(--accent)" }} />}
            <span>{item.short}</span>
          </Link>
        ))}
      </nav>
    </div>
  );
}
