"use client";

import { useEffect, useState } from "react";
import { listAgents, type Agent } from "@/lib/api";

interface AgentSwitcherProps {
  value: string;
  onChange: (agentId: string) => void;
  disabled?: boolean;
}

export function AgentSwitcher({ value, onChange, disabled }: AgentSwitcherProps) {
  const [agents, setAgents] = useState<Agent[]>([]);

  useEffect(() => {
    listAgents()
      .then(setAgents)
      .catch(() => {
        setAgents([{ id: "default", name_zh: "默认助手", name_en: "Default" } as Agent]);
      });
  }, []);

  return (
    <div className="flex flex-wrap gap-2 justify-center">
      {agents.map((agent) => (
        <button
          key={agent.id}
          onClick={() => !disabled && onChange(agent.id)}
          disabled={disabled}
          className="transition-all duration-200"
          style={{
            padding: "6px 18px",
            borderRadius: "var(--radius-full, 999px)",
            fontSize: 13,
            fontWeight: 500,
            cursor: disabled ? "not-allowed" : "pointer",
            opacity: disabled ? 0.5 : 1,
            background:
              value === agent.id ? "var(--accent)" : "var(--bg-3)",
            color: value === agent.id ? "white" : "var(--fg-2)",
            border:
              value === agent.id
                ? "1px solid var(--accent)"
                : "1px solid var(--border-2)",
            boxShadow:
              value === agent.id
                ? "0 2px 12px var(--accent-glow)"
                : "none",
          }}
        >
          {agent.name_en || agent.name_zh}
        </button>
      ))}
    </div>
  );
}
