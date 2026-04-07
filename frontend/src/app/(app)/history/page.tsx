"use client";

import { useEffect, useState, useCallback } from "react";
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

interface PaginatedResponse {
  items: ConversationResponse[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const PAGE_SIZE = 10;
const GRID_COLS = "160px 1fr 100px 80px 2fr 40px";

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("zh-CN", {
    month: "short", day: "numeric",
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
  const [deleting, setDeleting] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const token = useAuthStore(s => s.token);

  const fetchPage = useCallback(async (p: number) => {
    setLoading(true);
    const base = token
      ? `${API_BASE}/api/conversations/`
      : `${API_BASE}/api/conversations/all`;

    const url = `${base}?page=${p}&page_size=${PAGE_SIZE}`;
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    try {
      const r = await fetch(url, { headers });
      if (!r.ok) throw new Error(`${r.status}`);
      const data: PaginatedResponse = await r.json();
      setConversations(data.items);
      setTotalPages(data.total_pages);
      setTotal(data.total);
      setPage(data.page);
    } catch {
      setConversations([]);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchPage(1); }, [fetchPage]);

  const handleDelete = async (id: string) => {
    if (!confirm("删除此对话记录？")) return;
    setDeleting(id);
    try {
      const r = await fetch(`${API_BASE}/api/conversations/${id}`, { method: "DELETE" });
      if (r.ok) {
        // Re-fetch current page after delete
        fetchPage(page);
      }
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="page">
      {/* Header */}
      <div className="page-header animate-in">
        <div>
          <h1 className="page-title">对话历史</h1>
          <p className="page-desc">
            共 {total} 条记录
            {totalPages > 1 && ` · 第 ${page}/${totalPages} 页`}
          </p>
        </div>
      </div>

      {/* Table header */}
      <div
        className="tbl-header animate-in"
        style={{ gridTemplateColumns: GRID_COLS, animationDelay: "0.04s" }}
      >
        <span>时间</span>
        <span>Agent</span>
        <span>时长</span>
        <span>消息</span>
        <span>摘要</span>
        <span></span>
      </div>

      {/* Loading */}
      {loading && (
        <div className="py-16 text-center animate-in" style={{ color: "var(--fg-3)" }}>
          <span className="text-[13px]">加载中...</span>
        </div>
      )}

      {/* Empty state */}
      {!loading && conversations.length === 0 && (
        <div className="py-24 text-center animate-in" style={{ color: "var(--fg-3)", animationDelay: "0.06s" }}>
          <p className="text-[13px]">暂无对话记录</p>
        </div>
      )}

      {/* Rows */}
      {!loading && conversations.map((c, i) => (
        <div
          key={c.id}
          className="tbl-row animate-in"
          style={{ gridTemplateColumns: GRID_COLS, animationDelay: `${0.06 + i * 0.02}s` }}
        >
          <span className="text-[13px]" style={{ color: "var(--fg-2)" }}>
            <Link href={`/history/${c.id}`} style={{ color: "inherit", textDecoration: "none" }}>
              {formatDate(c.started_at)}
            </Link>
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
          <button
            onClick={(e) => { e.stopPropagation(); handleDelete(c.id); }}
            disabled={deleting === c.id}
            className="tbl-delete-btn"
            title="删除"
            style={{ opacity: deleting === c.id ? 0.3 : undefined }}
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
              <path d="M5.5 5.5a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m2.5.5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0zm3 .5a.5.5 0 0 1-.5-.5.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6a.5.5 0 0 1 .5-.5"/>
              <path d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1 0-2H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1M4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4z"/>
            </svg>
          </button>
        </div>
      ))}

      {/* Pagination */}
      {!loading && totalPages > 1 && (
        <div
          className="flex items-center justify-center gap-2 animate-in"
          style={{ padding: "20px 0", animationDelay: "0.15s" }}
        >
          <button
            onClick={() => fetchPage(page - 1)}
            disabled={page <= 1}
            className="btn btn-ghost"
            style={{ fontSize: 12, padding: "5px 12px", opacity: page <= 1 ? 0.3 : 1 }}
          >
            上一页
          </button>

          {/* Page numbers */}
          {Array.from({ length: totalPages }, (_, i) => i + 1)
            .filter(p => p === 1 || p === totalPages || Math.abs(p - page) <= 2)
            .reduce<(number | "...")[]>((acc, p, idx, arr) => {
              if (idx > 0 && p - (arr[idx - 1]) > 1) acc.push("...");
              acc.push(p);
              return acc;
            }, [])
            .map((p, idx) =>
              p === "..." ? (
                <span key={`dots-${idx}`} style={{ color: "var(--fg-3)", fontSize: 12, padding: "0 4px" }}>...</span>
              ) : (
                <button
                  key={p}
                  onClick={() => fetchPage(p as number)}
                  className="btn btn-ghost"
                  style={{
                    fontSize: 12,
                    padding: "5px 10px",
                    fontWeight: p === page ? 600 : 400,
                    color: p === page ? "var(--accent)" : "var(--fg-3)",
                    background: p === page ? "var(--accent-dim, rgba(217,119,87,0.1))" : "transparent",
                  }}
                >
                  {p}
                </button>
              )
            )}

          <button
            onClick={() => fetchPage(page + 1)}
            disabled={page >= totalPages}
            className="btn btn-ghost"
            style={{ fontSize: 12, padding: "5px 12px", opacity: page >= totalPages ? 0.3 : 1 }}
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
}
