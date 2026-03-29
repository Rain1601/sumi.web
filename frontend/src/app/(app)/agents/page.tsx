"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { listAgents, listModels, type Agent, type ProviderModel } from "@/lib/api";

function ModelTag({ type, label }: { type: string; label: string | null }) {
  if (!label) {
    return (
      <span className="badge badge-muted">
        {type.toUpperCase()}: --
      </span>
    );
  }
  return (
    <span className={`badge badge-${type}`}>
      {type.toUpperCase()}: {label}
    </span>
  );
}

export default function AgentsPage() {
  const router = useRouter();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);

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

  useEffect(() => { load(); }, [load]);

  return (
    <div className="page">
      {/* Header */}
      <div className="page-header animate-in">
        <div>
          <h1 className="page-title">Agents</h1>
          <p className="page-desc">Voice agents with configurable models and behavior</p>
        </div>
        <button onClick={() => router.push("/agents/new")} className="btn btn-primary">
          Create agent
        </button>
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
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: 16 }}>
          {agents.map((agent, i) => (
            <div
              key={agent.id}
              className="card animate-in"
              onClick={() => router.push(`/agents/${agent.id}`)}
              style={{
                padding: "24px",
                cursor: "pointer",
                animationDelay: `${i * 0.04}s`,
              }}
            >
              {/* Top row: name + status */}
              <div className="flex items-start justify-between gap-3">
                <div style={{ minWidth: 0 }}>
                  <h3 className="text-[15px] font-semibold" style={{ color: "var(--fg)" }}>
                    {agent.name_zh}
                  </h3>
                  <p className="text-[13px] mt-0.5" style={{ color: "var(--fg-3)" }}>
                    {agent.name_en}
                  </p>
                </div>
                <span
                  className="badge flex-shrink-0"
                  style={{
                    background: agent.is_active ? "var(--green-dim)" : "var(--red-dim)",
                    color: agent.is_active ? "var(--green)" : "var(--red)",
                  }}
                >
                  {agent.is_active ? "Active" : "Off"}
                </span>
              </div>

              {/* Description */}
              {agent.description_zh && (
                <p
                  className="text-[12px] mt-3 line-clamp-2"
                  style={{ color: "var(--fg-2)", lineHeight: 1.6 }}
                >
                  {agent.description_zh}
                </p>
              )}

              {/* Model badges */}
              <div className="flex flex-wrap gap-[6px] mt-4">
                <ModelTag type="asr" label={agent.asr_model_name} />
                <ModelTag type="tts" label={agent.tts_model_name} />
                <ModelTag type="nlp" label={agent.nlp_model_name} />
              </div>

              {/* Footer meta */}
              <div className="flex items-center gap-3 mt-4 pt-3" style={{ borderTop: "1px solid var(--border-1)" }}>
                <span className="badge badge-muted">{agent.language}</span>
                <span className="badge badge-muted">{agent.interruption_policy}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
