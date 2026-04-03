"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuthStore } from "@/stores/auth";

/* ─── Types ─── */

interface ConversationResponse {
  id: string;
  agent_id: string;
  language: string | null;
  started_at: string;
  ended_at: string | null;
  summary: string | null;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

const GRID_COLS = "160px 1fr 100px 80px 2fr";

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-US", {
    month: "short", day: "numeric", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function formatDuration(start: string, end: string | null): string {
  if (!end) return "--";
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (ms < 0) return "--";
  const secs = Math.floor(ms / 1000);
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

/* ─── Main Page ─── */

export default function HistoryPage() {
  const [conversations, setConversations] = useState<ConversationResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const token = useAuthStore(s => s.token);

  useEffect(() => {
    if (!token) { setLoading(false); return; }

    fetch(`${API_BASE}/api/conversations/`, {
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
    })
      .then(r => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((data: ConversationResponse[]) => setConversations(data))
      .catch(() => setConversations([]))
      .finally(() => setLoading(false));
  }, [token]);

  return (
    <div className="page">
      {/* Header */}
      <div className="page-header animate-in">
        <div>
          <h1 className="page-title">History</h1>
          <p className="page-desc">Conversation records</p>
        </div>
      </div>

      {/* Table header */}
      <div
        className="tbl-header animate-in"
        style={{ gridTemplateColumns: GRID_COLS, animationDelay: "0.04s" }}
      >
        <span>Date / Time</span>
        <span>Agent</span>
        <span>Duration</span>
        <span>Msgs</span>
        <span>Summary</span>
      </div>

      {/* Loading */}
      {loading && (
        <div className="py-16 text-center animate-in" style={{ color: "var(--fg-3)" }}>
          <span className="text-[13px]">Loading...</span>
        </div>
      )}

      {/* Empty state */}
      {!loading && conversations.length === 0 && (
        <div className="py-24 text-center animate-in" style={{ color: "var(--fg-3)", animationDelay: "0.06s" }}>
          <p className="text-[13px]">No conversations yet</p>
        </div>
      )}

      {/* Rows */}
      {!loading && conversations.map((c, i) => (
        <div
          key={c.id}
          className="tbl-row animate-in"
          style={{ gridTemplateColumns: GRID_COLS, animationDelay: `${0.06 + i * 0.025}s` }}
        >
          <span className="text-[13px]" style={{ color: "var(--fg-2)" }}>
            {formatDate(c.started_at)}
          </span>
          <span>
            <Link
              href={`/agents/${c.agent_id}`}
              className="text-[13px] font-medium"
              style={{ color: "var(--accent)", textDecoration: "none" }}
            >
              {c.agent_id}
            </Link>
          </span>
          <span className="text-[13px] mono" style={{ color: "var(--fg-3)" }}>
            {formatDuration(c.started_at, c.ended_at)}
          </span>
          <span className="text-[13px] mono" style={{ color: "var(--fg-3)" }}>
            --
          </span>
          <span
            className="text-[13px] truncate"
            style={{ color: "var(--fg-3)" }}
            title={c.summary || ""}
          >
            {c.summary || "--"}
          </span>
        </div>
      ))}
    </div>
  );
}
