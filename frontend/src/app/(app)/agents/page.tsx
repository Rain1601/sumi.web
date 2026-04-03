"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { listAgents, duplicateAgent, deleteAgent, type Agent } from "@/lib/api";

/* ─── Status Badge ─── */
function StatusBadge({ status }: { status: string }) {
  const isDraft = status !== "published";
  return (
    <span
      className="badge"
      style={{
        background: isDraft ? "rgba(255,255,255,0.06)" : "var(--green-dim)",
        color: isDraft ? "var(--fg-3)" : "var(--green)",
      }}
    >
      {isDraft ? "Draft" : "Published"}
    </span>
  );
}

/* ─── Actions Dropdown ─── */
function ActionsDropdown({
  agent,
  onDuplicate,
  onDelete,
}: {
  agent: Agent;
  onDuplicate: (id: string) => void;
  onDelete: (id: string, name: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button
        onClick={(e) => {
          e.stopPropagation();
          setOpen(!open);
        }}
        className="btn btn-ghost"
        style={{
          padding: "4px 8px",
          fontSize: 16,
          lineHeight: 1,
          borderRadius: 8,
          minWidth: 32,
          minHeight: 32,
        }}
      >
        &#8942;
      </button>
      {open && (
        <div
          className="glass animate-in"
          style={{
            position: "absolute",
            right: 0,
            top: "100%",
            marginTop: 4,
            minWidth: 160,
            padding: "6px 0",
            zIndex: 50,
            borderRadius: 12,
            boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
          }}
        >
          <button
            onClick={(e) => {
              e.stopPropagation();
              setOpen(false);
              onDuplicate(agent.id);
            }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              width: "100%",
              padding: "8px 14px",
              background: "transparent",
              border: "none",
              color: "var(--fg-2)",
              fontSize: 13,
              cursor: "pointer",
              textAlign: "left",
              transition: "background 0.15s",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.06)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="9" y="9" width="13" height="13" rx="2" />
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
            </svg>
            Duplicate
          </button>
          <div style={{ height: 1, background: "rgba(255,255,255,0.06)", margin: "4px 0" }} />
          <button
            onClick={(e) => {
              e.stopPropagation();
              setOpen(false);
              onDelete(agent.id, agent.name_zh || agent.name_en);
            }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              width: "100%",
              padding: "8px 14px",
              background: "transparent",
              border: "none",
              color: "var(--red)",
              fontSize: 13,
              cursor: "pointer",
              textAlign: "left",
              transition: "background 0.15s",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "var(--red-dim)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
              <path d="M10 11v6" />
              <path d="M14 11v6" />
              <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
            </svg>
            Delete
          </button>
        </div>
      )}
    </div>
  );
}

/* ─── Pagination ─── */
const PAGE_SIZE = 15;

function Pagination({
  page,
  total,
  onPageChange,
}: {
  page: number;
  total: number;
  onPageChange: (p: number) => void;
}) {
  const totalPages = Math.ceil(total / PAGE_SIZE);
  if (totalPages <= 1) return null;

  return (
    <div
      className="flex items-center justify-between"
      style={{ padding: "16px 20px", borderTop: "1px solid rgba(255,255,255,0.06)" }}
    >
      <span className="text-[12px]" style={{ color: "var(--fg-3)" }}>
        Showing {(page - 1) * PAGE_SIZE + 1}-{Math.min(page * PAGE_SIZE, total)} of {total}
      </span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="btn btn-ghost"
          style={{ padding: "4px 10px", fontSize: 12, borderRadius: 8 }}
        >
          Previous
        </button>
        {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
          <button
            key={p}
            onClick={() => onPageChange(p)}
            className="btn"
            style={{
              padding: "4px 10px",
              fontSize: 12,
              borderRadius: 8,
              background: p === page ? "rgba(255,255,255,0.12)" : "transparent",
              color: p === page ? "var(--fg)" : "var(--fg-3)",
              border: "none",
              minWidth: 32,
            }}
          >
            {p}
          </button>
        ))}
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className="btn btn-ghost"
          style={{ padding: "4px 10px", fontSize: 12, borderRadius: 8 }}
        >
          Next
        </button>
      </div>
    </div>
  );
}

/* ─── Column grid template ─── */
const GRID_COLS = "2fr 1.2fr 0.6fr 0.8fr 1fr 48px";

/* ─── Main Page ─── */
export default function AgentsPage() {
  const router = useRouter();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    try {
      const a = await listAgents();
      setAgents(a);
    } catch (err) {
      console.error("Failed to load agents:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleDuplicate = async (id: string) => {
    try {
      await duplicateAgent(id);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to duplicate agent");
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Delete agent "${name}"? This cannot be undone.`)) return;
    try {
      await deleteAgent(id);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete agent");
    }
  };

  /* Filter + paginate */
  const filtered = agents.filter((a) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      a.name_zh.toLowerCase().includes(q) ||
      a.name_en.toLowerCase().includes(q) ||
      a.id.toLowerCase().includes(q) ||
      (a.description_zh || "").toLowerCase().includes(q) ||
      (a.description_en || "").toLowerCase().includes(q)
    );
  });

  const paginated = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  // Reset to page 1 when search changes
  useEffect(() => {
    setPage(1);
  }, [search]);

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return "--";
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    } catch {
      return "--";
    }
  };

  return (
    <div className="page">
      {/* Header */}
      <div className="page-header animate-in">
        <div>
          <h1 className="page-title">All Agents</h1>
          <p className="page-desc">
            {agents.length} agent{agents.length !== 1 ? "s" : ""} total
          </p>
        </div>
        <button onClick={() => router.push("/agents/new")} className="btn btn-accent">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Create an Agent
        </button>
      </div>

      {/* Search */}
      <div className="animate-in" style={{ animationDelay: "0.03s", marginBottom: 20 }}>
        <div style={{ position: "relative", maxWidth: 400 }}>
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="var(--fg-3)"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", pointerEvents: "none" }}
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input"
            placeholder="Search by name, ID, or description..."
            style={{ paddingLeft: 36 }}
          />
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="text-center py-24 animate-in" style={{ color: "var(--fg-3)" }}>
          <p className="text-[13px]">Loading agents...</p>
        </div>
      ) : agents.length === 0 ? (
        <div className="text-center py-24 animate-in" style={{ color: "var(--fg-3)" }}>
          <p className="text-[13px]">No agents yet</p>
          <button
            onClick={() => router.push("/agents/new")}
            className="text-[13px] mt-2"
            style={{ color: "var(--accent)", background: "none", border: "none", cursor: "pointer" }}
          >
            Create your first agent
          </button>
        </div>
      ) : (
        <div
          className="animate-in"
          style={{
            animationDelay: "0.05s",
            border: "1px solid var(--glass-border)",
            borderRadius: "var(--radius)",
            overflow: "hidden",
          }}
        >
          {/* Table header */}
          <div
            className="table-header"
            style={{ gridTemplateColumns: GRID_COLS }}
          >
            <span>Agent Name</span>
            <span>Agent ID</span>
            <span>Version</span>
            <span>Status</span>
            <span>Last Edited</span>
            <span />
          </div>

          {/* Table rows */}
          {paginated.length === 0 ? (
            <div className="text-center py-12" style={{ color: "var(--fg-3)" }}>
              <p className="text-[13px]">No agents match your search</p>
            </div>
          ) : (
            paginated.map((agent, i) => (
              <div
                key={agent.id}
                className="table-row animate-in"
                style={{
                  gridTemplateColumns: GRID_COLS,
                  animationDelay: `${i * 0.02}s`,
                }}
                onClick={() => router.push(`/agents/${agent.id}`)}
              >
                {/* Agent Name */}
                <div style={{ minWidth: 0 }}>
                  <span
                    className="text-[13px] font-medium"
                    style={{
                      color: "var(--fg)",
                      cursor: "pointer",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      display: "block",
                    }}
                  >
                    {agent.name_zh}
                  </span>
                  {agent.name_en && (
                    <span
                      className="text-[11px]"
                      style={{
                        color: "var(--fg-3)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        display: "block",
                      }}
                    >
                      {agent.name_en}
                    </span>
                  )}
                </div>

                {/* Agent ID */}
                <span
                  className="mono text-[12px]"
                  style={{
                    color: "var(--fg-3)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                  title={agent.id}
                >
                  {agent.id.slice(0, 8)}...
                </span>

                {/* Version */}
                <span className="text-[13px]" style={{ color: "var(--fg-2)" }}>
                  v{agent.version ?? 1}
                </span>

                {/* Status */}
                <StatusBadge status={agent.status ?? "draft"} />

                {/* Last Edited */}
                <span className="text-[12px]" style={{ color: "var(--fg-3)" }}>
                  {formatDate(agent.updated_at)}
                </span>

                {/* Actions */}
                <ActionsDropdown
                  agent={agent}
                  onDuplicate={handleDuplicate}
                  onDelete={handleDelete}
                />
              </div>
            ))
          )}

          {/* Pagination */}
          <Pagination page={page} total={filtered.length} onPageChange={setPage} />
        </div>
      )}
    </div>
  );
}
