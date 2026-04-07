"use client";

import { useEffect, useState, useRef } from "react";
import { listAgents, type Agent } from "@/lib/api";

interface AgentSwitcherProps {
  value: string;
  onChange: (agentId: string) => void;
  disabled?: boolean;
}

export function AgentSwitcher({ value, onChange, disabled }: AgentSwitcherProps) {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listAgents()
      .then(setAgents)
      .catch(() => {
        setAgents([{ id: "default", name_zh: "默认助手", name_en: "Default" } as Agent]);
      });
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const selected = agents.find((a) => a.id === value);
  const label = selected ? (selected.name_zh || selected.name_en || selected.id) : "选择 Agent";

  return (
    <div ref={ref} className="relative" style={{ minWidth: 200 }}>
      {/* Trigger button */}
      <button
        onClick={() => !disabled && setOpen((v) => !v)}
        disabled={disabled}
        className="transition-all duration-200"
        style={{
          width: "100%",
          padding: "9px 16px",
          borderRadius: 10,
          fontSize: 13,
          fontWeight: 500,
          cursor: disabled ? "not-allowed" : "pointer",
          opacity: disabled ? 0.5 : 1,
          background: "var(--bg-2)",
          color: "var(--fg)",
          border: "1px solid var(--border-2)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
        }}
      >
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {label}
        </span>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style={{ flexShrink: 0, transform: open ? "rotate(180deg)" : "none", transition: "transform 0.15s" }}>
          <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {/* Dropdown */}
      {open && (
        <div
          className="absolute z-50"
          style={{
            top: "calc(100% + 6px)",
            left: 0,
            right: 0,
            maxHeight: 280,
            overflowY: "auto",
            borderRadius: 10,
            background: "var(--bg-1)",
            border: "1px solid var(--border-2)",
            boxShadow: "0 8px 32px rgba(0,0,0,0.18)",
            padding: "4px 0",
          }}
        >
          {agents.map((agent) => {
            const isSelected = value === agent.id;
            return (
              <button
                key={agent.id}
                onClick={() => {
                  onChange(agent.id);
                  setOpen(false);
                }}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "flex-start",
                  width: "100%",
                  padding: "8px 14px",
                  fontSize: 13,
                  fontWeight: isSelected ? 600 : 400,
                  cursor: "pointer",
                  background: isSelected ? "var(--accent-dim, rgba(99,102,241,0.1))" : "transparent",
                  color: isSelected ? "var(--accent)" : "var(--fg)",
                  border: "none",
                  textAlign: "left",
                  transition: "background 0.1s",
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) (e.currentTarget.style.background = "var(--bg-3)");
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) (e.currentTarget.style.background = "transparent");
                }}
              >
                <span>{agent.name_zh || agent.name_en || agent.id}</span>
                {agent.name_en && agent.name_zh && (
                  <span style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 1 }}>
                    {agent.name_en}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
