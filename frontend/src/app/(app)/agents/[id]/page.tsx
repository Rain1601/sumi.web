"use client";

import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { useRouter, useParams } from "next/navigation";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useVoiceAssistant,
  BarVisualizer,
} from "@livekit/components-react";
import "@livekit/components-styles";

import {
  getAgent,
  listModels,
  updateAgent,
  deleteAgent,
  publishAgent,
  listAgentVariables,
  createAgentVariable,
  updateAgentVariable,
  deleteAgentVariable,
  listAgentSkills,
  createAgentSkill,
  updateAgentSkill,
  deleteAgentSkill,
  listAgentTools,
  createAgentTool,
  updateAgentTool,
  deleteAgentTool,
  listAgentRules,
  createAgentRule,
  updateAgentRule,
  deleteAgentRule,
  listAgentVersions,
  rollbackAgentVersion,
  initAgentFromAudio,
  runConversationTest,
  runVoiceTest,
  type Agent,
  type AudioInitEvent,
  type ConversationTestEvent,
  type VoiceTestEvent,
  type ProviderModel,
  type AgentVariable,
  type AgentSkill,
  type AgentTool,
  type AgentRule,
  type AgentVersionSummary,
  type TaskChainConfig,
  type TaskDef,
  runTool,
  type ToolRunResult,
} from "@/lib/api";
import { useVoiceSession } from "@/hooks/useVoiceSession";
import { useAuthStore } from "@/stores/auth";
import { LiveTranscriptPanel } from "../../conversation/components/TranscriptPanel";

/* ============================================================
   Utility: extract ${variable} references from text
   ============================================================ */
function extractVariableRefs(text: string): string[] {
  const matches = text.match(/\$\{(\w+)\}/g);
  if (!matches) return [];
  return [...new Set(matches.map((m) => m.slice(2, -1)))];
}

/* ============================================================
   Toggle Switch component
   ============================================================ */
function Toggle({
  value,
  onChange,
  label,
}: {
  value: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!value)}
      className="flex items-center justify-between gap-3 w-full"
      style={{
        padding: "10px 0",
        background: "transparent",
        border: "none",
        cursor: "pointer",
      }}
    >
      <span className="text-[13px]" style={{ color: "var(--fg-2)" }}>{label}</span>
      <div
        style={{
          width: 40,
          height: 22,
          borderRadius: 11,
          background: value ? "var(--accent)" : "rgba(255,255,255,0.1)",
          transition: "background 0.2s",
          position: "relative",
          flexShrink: 0,
        }}
      >
        <div
          style={{
            width: 18,
            height: 18,
            borderRadius: "50%",
            background: "white",
            position: "absolute",
            top: 2,
            left: value ? 20 : 2,
            transition: "left 0.2s",
            boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
          }}
        />
      </div>
    </button>
  );
}

/* ============================================================
   Collapsible section
   ============================================================ */
function CollapsibleSection({
  title,
  defaultOpen = false,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          width: "100%",
          padding: "12px 0",
          background: "transparent",
          border: "none",
          cursor: "pointer",
          color: "var(--fg-2)",
          fontSize: 13,
          fontWeight: 500,
        }}
      >
        <span>{title}</span>
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{
            transform: open ? "rotate(180deg)" : "rotate(0deg)",
            transition: "transform 0.2s",
          }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      {open && <div style={{ paddingBottom: 16 }}>{children}</div>}
    </div>
  );
}

/* ============================================================
   Model Picker (compact) — kept for potential reuse
   ============================================================ */
function ModelPicker({
  label,
  type,
  models,
  value,
  onChange,
}: {
  label: string;
  type: string;
  models: ProviderModel[];
  value: string | null;
  onChange: (v: string | null) => void;
}) {
  const filtered = models.filter((m) => m.provider_type === type && m.is_active);
  return (
    <div className="field" style={{ gap: 4 }}>
      <div className="flex items-center gap-2">
        <span className={`badge badge-${type}`}>{type.toUpperCase()}</span>
        <label className="field-label">{label}</label>
      </div>
      <select
        value={value || ""}
        onChange={(e) => onChange(e.target.value || null)}
        className="input"
        style={{ fontSize: 12 }}
      >
        <option value="">Not selected</option>
        {filtered.map((m) => (
          <option key={m.id} value={m.id}>
            {m.name} ({m.model_name})
          </option>
        ))}
      </select>
    </div>
  );
}

/* ============================================================
   Inline Pipeline Config — display + hover-to-edit
   ============================================================ */
function PipelineConfigRow({
  label,
  type,
  models,
  value,
  onChange,
}: {
  label: string;
  type: "asr" | "nlp" | "tts";
  models: ProviderModel[];
  value: string | null;
  onChange: (v: string | null) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [hovered, setHovered] = useState(false);
  const selectRef = useRef<HTMLSelectElement>(null);

  const filtered = useMemo(
    () => models.filter((m) => m.provider_type === type && m.is_active),
    [models, type],
  );
  const current = models.find((m) => m.id === value);

  const colorMap = { asr: "var(--asr)", nlp: "var(--nlp)", tts: "var(--tts)" };
  const color = colorMap[type];

  useEffect(() => {
    if (editing && selectRef.current) {
      selectRef.current.focus();
    }
  }, [editing]);

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => { setHovered(false); setEditing(false); }}
      onClick={() => !editing && setEditing(true)}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "6px 8px",
        marginLeft: -8,
        marginRight: -8,
        borderRadius: 6,
        cursor: editing ? "default" : "pointer",
        background: hovered ? "var(--bg-hover)" : "transparent",
        transition: "background 0.15s ease",
      }}
    >
      {/* Label */}
      <span
        style={{
          fontSize: 10,
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          color,
          width: 28,
          flexShrink: 0,
        }}
      >
        {label}
      </span>

      {/* Value / Editor */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {editing ? (
          <select
            ref={selectRef}
            value={value || ""}
            onChange={(e) => {
              onChange(e.target.value || null);
              setEditing(false);
            }}
            onBlur={() => setEditing(false)}
            style={{
              width: "100%",
              fontSize: 11,
              padding: "3px 6px",
              background: "var(--bg-elevated)",
              border: "1px solid var(--border-light)",
              borderRadius: 4,
              color: "var(--text-primary)",
              outline: "none",
              fontFamily: "var(--font-mono, monospace)",
              cursor: "pointer",
            }}
          >
            <option value="">Not selected</option>
            {filtered.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name} ({m.model_name})
              </option>
            ))}
          </select>
        ) : (
          <span
            className="truncate block"
            style={{
              fontSize: 11,
              color: current ? "var(--text-secondary)" : "var(--text-muted)",
              fontFamily: "var(--font-mono, monospace)",
            }}
          >
            {current ? current.model_name : "not set"}
          </span>
        )}
      </div>

      {/* Edit hint */}
      {hovered && !editing && (
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{ color: "var(--text-muted)", flexShrink: 0, opacity: 0.6 }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      )}
    </div>
  );
}

function PipelineConfig({
  models,
  asr,
  nlp,
  tts,
  onAsrChange,
  onNlpChange,
  onTtsChange,
}: {
  models: ProviderModel[];
  asr: string | null;
  nlp: string | null;
  tts: string | null;
  onAsrChange: (v: string | null) => void;
  onNlpChange: (v: string | null) => void;
  onTtsChange: (v: string | null) => void;
}) {
  return (
    <div style={{ borderBottom: "1px solid var(--border-light)", padding: "12px 0" }}>
      <p
        className="text-[10px] font-semibold uppercase tracking-[0.1em] mb-1"
        style={{ color: "var(--text-muted)" }}
      >
        Pipeline
      </p>
      <div className="flex flex-col gap-[1px]">
        <PipelineConfigRow label="ASR" type="asr" models={models} value={asr} onChange={onAsrChange} />
        <PipelineConfigRow label="NLP" type="nlp" models={models} value={nlp} onChange={onNlpChange} />
        <PipelineConfigRow label="TTS" type="tts" models={models} value={tts} onChange={onTtsChange} />
      </div>
    </div>
  );
}

/* ============================================================
   Active voice visualizer inside LiveKit room
   ============================================================ */
function ActiveVoice() {
  const { state, audioTrack } = useVoiceAssistant();

  const stateLabel =
    state === "listening"
      ? "Listening"
      : state === "thinking"
        ? "Processing"
        : state === "speaking"
          ? "Speaking"
          : "Connected";

  const stateColor =
    state === "listening"
      ? "var(--accent)"
      : state === "thinking"
        ? "var(--amber)"
        : state === "speaking"
          ? "var(--green)"
          : "var(--fg-3)";

  return (
    <div className="flex flex-col items-center gap-3">
      <div
        className="relative flex items-center justify-center"
        style={{ width: 140, height: 60 }}
      >
        <BarVisualizer
          state={state}
          barCount={5}
          trackRef={audioTrack}
          style={{ width: "100%", height: "100%" }}
        />
      </div>
      <div className="flex items-center gap-2">
        <span
          className="w-[6px] h-[6px] rounded-full"
          style={{ background: stateColor, boxShadow: `0 0 8px ${stateColor}` }}
        />
        <span className="text-[12px] font-medium" style={{ color: stateColor }}>
          {stateLabel}
        </span>
      </div>
    </div>
  );
}

/* ============================================================
   Test Audio section (right panel)
   ============================================================ */
function TestAudioSection({ agentId }: { agentId: string }) {
  const { serverUrl, token, isConnecting, error, connect, disconnect } = useVoiceSession();
  const { token: authToken } = useAuthStore();

  const handleConnect = useCallback(async () => {
    await connect(agentId, authToken || "dev_user");
  }, [agentId, authToken, connect]);

  return (
    <div>
      {!token ? (
        <div className="flex flex-col items-center gap-3" style={{ padding: "16px 0" }}>
          <div className="relative" style={{ width: 80, height: 80 }}>
            <div className="pulse-ring" style={{ width: 80, height: 80, animationDelay: "0s" }} />
            <div className="pulse-ring" style={{ width: 80, height: 80, animationDelay: "0.8s" }} />
            <button
              onClick={handleConnect}
              disabled={isConnecting}
              className="absolute inset-0 m-auto w-[44px] h-[44px] rounded-full flex items-center justify-center z-10 transition-all duration-200"
              style={{
                background: "var(--accent)",
                boxShadow: "0 0 24px var(--accent-glow)",
                cursor: isConnecting ? "wait" : "pointer",
                opacity: isConnecting ? 0.6 : 1,
              }}
            >
              {isConnecting ? (
                <span className="text-[10px] font-medium" style={{ color: "white" }}>...</span>
              ) : (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="9" y="2" width="6" height="12" rx="3" />
                  <path d="M5 10a7 7 0 0 0 14 0" />
                  <line x1="12" y1="19" x2="12" y2="22" />
                </svg>
              )}
            </button>
          </div>
          <p className="text-[11px]" style={{ color: "var(--fg-3)" }}>
            {isConnecting ? "Connecting..." : "Tap to start test"}
          </p>
          {error && (
            <p
              className="text-[11px] px-3 py-1 rounded-lg"
              style={{ color: "var(--red)", background: "var(--red-dim)" }}
            >
              {error}
            </p>
          )}
        </div>
      ) : (
        <LiveKitRoom
          serverUrl={serverUrl!}
          token={token}
          connect={true}
          audio={{ echoCancellation: true, noiseSuppression: true, autoGainControl: true }}
          className="flex flex-col flex-1 min-h-0 w-full"
          onDisconnected={disconnect}
          onError={(err) => console.error("[LiveKit]", err)}
        >
          <div className="flex flex-col items-center gap-3">
            <ActiveVoice />
            <RoomAudioRenderer />
            <button
              onClick={disconnect}
              className="btn btn-secondary"
              style={{ fontSize: 11, padding: "4px 14px" }}
            >
              End session
            </button>
          </div>
          <div className="flex-1 flex flex-col min-h-0 mt-3">
            <p
              className="text-[10px] font-semibold uppercase tracking-[0.1em] mb-2"
              style={{ color: "var(--fg-3)" }}
            >
              Transcript
            </p>
            <div
              className="card flex-1 overflow-y-auto"
              style={{ padding: "10px 12px", minHeight: 100, maxHeight: 240 }}
            >
              <LiveTranscriptPanel />
            </div>
          </div>
        </LiveKitRoom>
      )}
    </div>
  );
}

/* ============================================================
   Tab: Prompt
   ============================================================ */
function PromptTab({
  role,
  onRoleChange,
  goal,
  onGoalChange,
  systemPrompt,
  onSystemPromptChange,
  userPrompt,
  onUserPromptChange,
  variables,
}: {
  role: string;
  onRoleChange: (v: string) => void;
  goal: string;
  onGoalChange: (v: string) => void;
  systemPrompt: string;
  onSystemPromptChange: (v: string) => void;
  userPrompt: string;
  onUserPromptChange: (v: string) => void;
  variables: AgentVariable[];
}) {
  const allPromptText = systemPrompt + " " + userPrompt;
  const refs = extractVariableRefs(allPromptText);
  const matchedVars = variables.filter((v) => refs.includes(v.code));

  return (
    <div className="space-y-5">
      {/* Role Definition */}
      <div className="field">
        <label className="field-label">Role (角色定义)</label>
        <textarea
          value={role}
          onChange={(e) => onRoleChange(e.target.value)}
          rows={3}
          className="input"
          placeholder="定义 Agent 的人设、语气、性格和边界。例如：你是一个专业、友好的金融顾问，说话简洁有力..."
          style={{ fontSize: 12, lineHeight: 1.7 }}
        />
        <p className="text-[10px] mt-1" style={{ color: "var(--text-muted)" }}>
          Persona, tone, and behavioral boundaries for the agent
        </p>
      </div>

      {/* Agent Goal */}
      <div className="field">
        <label className="field-label">Target (对话目标)</label>
        <textarea
          value={goal}
          onChange={(e) => onGoalChange(e.target.value)}
          rows={3}
          className="input"
          placeholder="描述 Agent 的核心任务目标，例如：帮助用户回答问题、查询天气、搜索信息..."
          style={{ fontSize: 12, lineHeight: 1.7 }}
        />
        <p className="text-[10px] mt-1" style={{ color: "var(--text-muted)" }}>
          Goal is injected at the top of system prompt to guide the agent&apos;s behavior
        </p>
      </div>

      {/* System Prompt */}
      <div className="field">
        <label className="field-label">System Prompt</label>
        <textarea
          value={systemPrompt}
          onChange={(e) => onSystemPromptChange(e.target.value)}
          rows={10}
          className="input mono"
          placeholder="You are a helpful voice assistant..."
          style={{ fontSize: 12, lineHeight: 1.7 }}
        />
      </div>

      {/* User Prompt */}
      <div className="field">
        <div className="flex items-center justify-between">
          <label className="field-label">User Prompt</label>
          <span className="text-[10px]" style={{ color: "var(--fg-3)" }}>
            Use {"${variable}"} to reference variables
          </span>
        </div>
        <textarea
          value={userPrompt}
          onChange={(e) => onUserPromptChange(e.target.value)}
          rows={6}
          className="input mono"
          placeholder="The user's name is ${name}. Their preference is ${preference}..."
          style={{ fontSize: 12, lineHeight: 1.7 }}
        />
      </div>

      {/* Referenced variables */}
      {matchedVars.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.1em] mb-2" style={{ color: "var(--fg-3)" }}>
            Referenced Variables
          </p>
          <div className="flex flex-wrap gap-2">
            {matchedVars.map((v) => (
              <span
                key={v.id}
                className="badge"
                style={{ background: "var(--accent-dim)", color: "var(--accent)" }}
              >
                ${"{" + v.code + "}"}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ============================================================
   Tab: Variables
   ============================================================ */
function VariablesTab({
  agentId,
  variables,
  onReload,
}: {
  agentId: string;
  variables: AgentVariable[];
  onReload: () => void;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", code: "", type: "string", default_value: "", description: "" });
  const [adding, setAdding] = useState(false);
  const [saving, setSaving] = useState(false);

  const startAdd = () => {
    setForm({ name: "", code: "", type: "string", default_value: "", description: "" });
    setAdding(true);
    setEditingId(null);
  };

  const startEdit = (v: AgentVariable) => {
    setForm({ name: v.name, code: v.code, type: v.type, default_value: v.default_value, description: v.description });
    setEditingId(v.id);
    setAdding(false);
  };

  const handleSave = async () => {
    if (!form.name.trim() || !form.code.trim()) return;
    setSaving(true);
    try {
      if (adding) {
        await createAgentVariable(agentId, form);
      } else if (editingId) {
        await updateAgentVariable(agentId, editingId, form);
      }
      setAdding(false);
      setEditingId(null);
      onReload();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to save variable");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (varId: string) => {
    if (!confirm("Delete this variable?")) return;
    try {
      await deleteAgentVariable(agentId, varId);
      onReload();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete");
    }
  };

  const cancel = () => {
    setAdding(false);
    setEditingId(null);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.1em]" style={{ color: "var(--fg-3)" }}>
          Variables ({variables.length})
        </p>
        <button onClick={startAdd} className="btn btn-secondary" style={{ fontSize: 11, padding: "4px 12px" }}>
          + Add Variable
        </button>
      </div>

      {/* Inline form for add/edit */}
      {(adding || editingId) && (
        <div className="card" style={{ padding: 16, marginBottom: 12 }}>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div className="field">
              <label className="field-label">Name</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" placeholder="Variable Name" style={{ fontSize: 12 }} />
            </div>
            <div className="field">
              <label className="field-label">Code</label>
              <input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} className="input mono" placeholder="variable_code" style={{ fontSize: 12 }} />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3 mb-3">
            <div className="field">
              <label className="field-label">Type</label>
              <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} className="input" style={{ fontSize: 12 }}>
                <option value="string">String</option>
                <option value="number">Number</option>
                <option value="boolean">Boolean</option>
                <option value="enum">Enum</option>
              </select>
            </div>
            <div className="field" style={{ gridColumn: "span 2" }}>
              <label className="field-label">Default Value</label>
              <input value={form.default_value} onChange={(e) => setForm({ ...form, default_value: e.target.value })} className="input" placeholder="default" style={{ fontSize: 12 }} />
            </div>
          </div>
          <div className="field mb-3">
            <label className="field-label">Description</label>
            <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input" placeholder="Describe this variable..." style={{ fontSize: 12 }} />
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={cancel} className="btn btn-ghost" style={{ fontSize: 11, padding: "4px 12px" }}>Cancel</button>
            <button onClick={handleSave} disabled={saving} className="btn btn-accent" style={{ fontSize: 11, padding: "4px 12px" }}>
              {saving ? "Saving..." : editingId ? "Update" : "Add"}
            </button>
          </div>
        </div>
      )}

      {/* Variable list */}
      {variables.length === 0 && !adding ? (
        <div className="text-center py-8" style={{ color: "var(--fg-3)" }}>
          <p className="text-[12px]">No variables defined</p>
          <p className="text-[11px] mt-1">Variables let you parameterize prompts with {"${code}"}</p>
        </div>
      ) : (
        <div>
          {/* Table header */}
          {variables.length > 0 && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1.2fr 1fr 0.7fr 1fr 1.5fr 60px",
                padding: "6px 12px",
                fontSize: 10,
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                color: "var(--fg-3)",
                borderBottom: "1px solid rgba(255,255,255,0.06)",
              }}
            >
              <span>Name</span>
              <span>Code</span>
              <span>Type</span>
              <span>Default</span>
              <span>Description</span>
              <span />
            </div>
          )}
          {variables.map((v) => (
            <div
              key={v.id}
              style={{
                display: "grid",
                gridTemplateColumns: "1.2fr 1fr 0.7fr 1fr 1.5fr 60px",
                padding: "10px 12px",
                fontSize: 13,
                alignItems: "center",
                borderBottom: "1px solid rgba(255,255,255,0.03)",
                transition: "background 0.15s",
              }}
              className="hover:bg-[rgba(255,255,255,0.02)]"
            >
              <span style={{ color: "var(--fg)" }}>{v.name}</span>
              <span className="mono text-[12px]" style={{ color: "var(--accent)" }}>${"{" + v.code + "}"}</span>
              <span className="badge badge-muted">{v.type}</span>
              <span className="text-[12px]" style={{ color: "var(--fg-3)" }}>{v.default_value || "--"}</span>
              <span className="text-[12px]" style={{ color: "var(--fg-3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{v.description || "--"}</span>
              <div className="flex gap-1">
                <button
                  onClick={() => startEdit(v)}
                  className="btn btn-ghost"
                  style={{ padding: "2px 6px", fontSize: 11 }}
                >
                  Edit
                </button>
                <button
                  onClick={() => handleDelete(v.id)}
                  className="btn btn-danger"
                  style={{ padding: "2px 6px", fontSize: 11 }}
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" /></svg>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ============================================================
   Tab: Skills
   ============================================================ */
function SkillsTab({
  agentId,
  skills,
  onReload,
}: {
  agentId: string;
  skills: AgentSkill[];
  onReload: () => void;
}) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ name: "", code: "", description: "", content: "", sort_order: 0 });
  const [editContent, setEditContent] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const startAdd = () => {
    setForm({ name: "", code: "", description: "", content: "", sort_order: skills.length });
    setAdding(true);
  };

  const handleAdd = async () => {
    if (!form.name.trim() || !form.code.trim()) return;
    setSaving(true);
    try {
      await createAgentSkill(agentId, form);
      setAdding(false);
      onReload();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to add skill");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveContent = async (skill: AgentSkill) => {
    const newContent = editContent[skill.id];
    if (newContent === undefined) return;
    setSaving(true);
    try {
      await updateAgentSkill(agentId, skill.id, { content: newContent });
      onReload();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to update skill");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (skillId: string) => {
    if (!confirm("Delete this skill?")) return;
    try {
      await deleteAgentSkill(agentId, skillId);
      onReload();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete");
    }
  };

  const sorted = [...skills].sort((a, b) => a.sort_order - b.sort_order);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.1em]" style={{ color: "var(--fg-3)" }}>
          Skills ({skills.length})
        </p>
        <button onClick={startAdd} className="btn btn-secondary" style={{ fontSize: 11, padding: "4px 12px" }}>
          + Add Skill
        </button>
      </div>

      {adding && (
        <div className="card" style={{ padding: 16, marginBottom: 12 }}>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div className="field">
              <label className="field-label">Name</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" placeholder="Skill Name" style={{ fontSize: 12 }} />
            </div>
            <div className="field">
              <label className="field-label">Code</label>
              <input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} className="input mono" placeholder="skill_code" style={{ fontSize: 12 }} />
            </div>
          </div>
          <div className="field mb-3">
            <label className="field-label">Description</label>
            <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input" placeholder="What does this skill do?" style={{ fontSize: 12 }} />
          </div>
          <div className="field mb-3">
            <label className="field-label">Content (Markdown)</label>
            <textarea value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} rows={5} className="input mono" placeholder="Skill content in Markdown..." style={{ fontSize: 12, lineHeight: 1.6 }} />
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setAdding(false)} className="btn btn-ghost" style={{ fontSize: 11, padding: "4px 12px" }}>Cancel</button>
            <button onClick={handleAdd} disabled={saving} className="btn btn-accent" style={{ fontSize: 11, padding: "4px 12px" }}>
              {saving ? "Adding..." : "Add Skill"}
            </button>
          </div>
        </div>
      )}

      {sorted.length === 0 && !adding ? (
        <div className="text-center py-8" style={{ color: "var(--fg-3)" }}>
          <p className="text-[12px]">No skills defined</p>
          <p className="text-[11px] mt-1">Skills are reusable knowledge blocks injected into prompts</p>
        </div>
      ) : (
        sorted.map((skill) => {
          const isExpanded = expandedId === skill.id;
          return (
            <div key={skill.id} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
              <div
                className="flex items-center gap-3"
                style={{
                  padding: "10px 0",
                  cursor: "pointer",
                  transition: "background 0.15s",
                }}
                onClick={() => setExpandedId(isExpanded ? null : skill.id)}
              >
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="var(--fg-3)"
                  strokeWidth="2"
                  style={{ transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)", transition: "transform 0.2s", flexShrink: 0 }}
                >
                  <polyline points="9 18 15 12 9 6" />
                </svg>
                <span className="text-[13px] font-medium" style={{ color: "var(--fg)", flex: 1 }}>{skill.name}</span>
                <span className="mono text-[11px]" style={{ color: "var(--fg-3)" }}>{skill.code}</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(skill.id);
                  }}
                  className="btn btn-danger"
                  style={{ padding: "2px 6px", fontSize: 11 }}
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" /></svg>
                </button>
              </div>
              {isExpanded && (
                <div style={{ paddingBottom: 12, paddingLeft: 24 }}>
                  {skill.description && (
                    <p className="text-[12px] mb-2" style={{ color: "var(--fg-3)" }}>{skill.description}</p>
                  )}
                  <div className="field">
                    <label className="field-label">Content (Markdown)</label>
                    <textarea
                      value={editContent[skill.id] ?? skill.content}
                      onChange={(e) => setEditContent({ ...editContent, [skill.id]: e.target.value })}
                      rows={6}
                      className="input mono"
                      style={{ fontSize: 12, lineHeight: 1.6 }}
                    />
                  </div>
                  {editContent[skill.id] !== undefined && editContent[skill.id] !== skill.content && (
                    <div className="flex justify-end mt-2">
                      <button onClick={() => handleSaveContent(skill)} disabled={saving} className="btn btn-accent" style={{ fontSize: 11, padding: "4px 12px" }}>
                        {saving ? "Saving..." : "Save Content"}
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })
      )}
    </div>
  );
}

/* ============================================================
   Tab: Tools
   ============================================================ */
function ToolRunner({ toolId, schema }: { toolId: string; schema: Record<string, unknown> | null }) {
  const properties = (schema?.properties ?? {}) as Record<string, { type?: string; description?: string; default?: string }>;
  const required = new Set((schema?.required ?? []) as string[]);
  const paramNames = Object.keys(properties);

  const [params, setParams] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const [k, v] of Object.entries(properties)) {
      init[k] = v.default ?? "";
    }
    return init;
  });
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ToolRunResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async () => {
    setRunning(true);
    setResult(null);
    setError(null);
    try {
      const p: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(params)) {
        if (v.trim()) p[k] = v.trim();
      }
      const res = await runTool(toolId, p);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Execution failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div
      style={{
        marginTop: 8,
        padding: "10px 12px",
        borderRadius: 6,
        background: "var(--bg-secondary)",
        border: "1px solid var(--border-light)",
      }}
    >
      <p
        className="text-[10px] font-semibold uppercase tracking-[0.06em] mb-2"
        style={{ color: "var(--text-muted)" }}
      >
        Test Run
      </p>

      {/* Parameter inputs generated from schema */}
      {paramNames.length > 0 ? (
        <div className="flex flex-col gap-2 mb-3">
          {paramNames.map((name) => {
            const prop = properties[name];
            return (
              <div key={name} className="flex items-center gap-2">
                <label
                  className="text-[11px] font-medium shrink-0"
                  style={{
                    color: required.has(name) ? "var(--text-secondary)" : "var(--text-muted)",
                    width: 80,
                    textAlign: "right",
                    fontFamily: "var(--font-mono, monospace)",
                  }}
                >
                  {name}
                  {required.has(name) && <span style={{ color: "var(--accent)" }}>*</span>}
                </label>
                <input
                  value={params[name] ?? ""}
                  onChange={(e) => setParams({ ...params, [name]: e.target.value })}
                  placeholder={prop?.description || name}
                  className="input"
                  style={{
                    fontSize: 11,
                    padding: "4px 8px",
                    flex: 1,
                    fontFamily: "var(--font-mono, monospace)",
                  }}
                  onKeyDown={(e) => e.key === "Enter" && handleRun()}
                />
              </div>
            );
          })}
        </div>
      ) : (
        <p className="text-[11px] mb-3" style={{ color: "var(--text-muted)" }}>No parameters</p>
      )}

      {/* Run button */}
      <button
        onClick={handleRun}
        disabled={running}
        style={{
          fontSize: 11,
          padding: "5px 16px",
          background: running ? "var(--bg-hover)" : "var(--accent)",
          color: running ? "var(--text-muted)" : "#fff",
          border: "none",
          borderRadius: 5,
          cursor: running ? "wait" : "pointer",
          fontWeight: 600,
          display: "flex",
          alignItems: "center",
          gap: 5,
          transition: "all 0.15s ease",
        }}
      >
        {running ? (
          <>
            <span
              style={{
                width: 10,
                height: 10,
                border: "2px solid var(--text-muted)",
                borderTopColor: "transparent",
                borderRadius: "50%",
                animation: "spin 0.6s linear infinite",
              }}
            />
            Running...
          </>
        ) : (
          <>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor" stroke="none">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
            Execute
          </>
        )}
      </button>

      {/* Result */}
      {result && (
        <div
          style={{
            marginTop: 8,
            padding: "8px 10px",
            borderRadius: 5,
            background: result.success ? "var(--accent-lighter)" : "var(--red-dim)",
            border: `1px solid ${result.success ? "var(--border-light)" : "rgba(248,113,113,0.2)"}`,
          }}
        >
          <div className="flex items-center gap-2 mb-1">
            <span
              className="text-[10px] font-semibold uppercase"
              style={{ color: result.success ? "var(--accent-text)" : "var(--red)" }}
            >
              {result.success ? "Success" : "Failed"}
            </span>
            <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>
              {result.duration_ms}ms
            </span>
          </div>
          <pre
            style={{
              fontSize: 11,
              lineHeight: 1.5,
              color: "var(--text-secondary)",
              fontFamily: "var(--font-mono, monospace)",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              margin: 0,
            }}
          >
            {result.output}
          </pre>
        </div>
      )}

      {/* Error */}
      {error && (
        <div
          style={{
            marginTop: 8,
            padding: "6px 10px",
            borderRadius: 5,
            background: "var(--red-dim)",
            border: "1px solid rgba(248,113,113,0.2)",
          }}
        >
          <span className="text-[11px]" style={{ color: "var(--red)" }}>{error}</span>
        </div>
      )}
    </div>
  );
}

function ToolsTab({
  agentId,
  tools,
  onReload,
}: {
  agentId: string;
  tools: AgentTool[];
  onReload: () => void;
}) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ name: "", tool_id: "", type: "sync", description: "", parameters_schema: "{}" });
  const [editSchema, setEditSchema] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [showRunner, setShowRunner] = useState<string | null>(null);

  const startAdd = () => {
    setForm({ name: "", tool_id: "", type: "sync", description: "", parameters_schema: "{}" });
    setAdding(true);
  };

  const handleAdd = async () => {
    if (!form.name.trim() || !form.tool_id.trim()) return;
    setSaving(true);
    try {
      let schema: Record<string, unknown> = {};
      try { schema = JSON.parse(form.parameters_schema); } catch { /* use empty */ }
      await createAgentTool(agentId, {
        name: form.name,
        tool_id: form.tool_id,
        type: form.type,
        description: form.description,
        parameters_schema: schema,
      });
      setAdding(false);
      onReload();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to add tool");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveSchema = async (tool: AgentTool) => {
    const raw = editSchema[tool.id];
    if (raw === undefined) return;
    setSaving(true);
    try {
      const schema = JSON.parse(raw);
      await updateAgentTool(agentId, tool.id, { parameters_schema: schema });
      onReload();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Invalid JSON or save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (toolId: string) => {
    if (!confirm("Delete this tool?")) return;
    try {
      await deleteAgentTool(agentId, toolId);
      onReload();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete");
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.1em]" style={{ color: "var(--fg-3)" }}>
          Tools ({tools.length})
        </p>
        <button onClick={startAdd} className="btn btn-secondary" style={{ fontSize: 11, padding: "4px 12px" }}>
          + Add Tool
        </button>
      </div>

      {adding && (
        <div className="card" style={{ padding: 16, marginBottom: 12 }}>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div className="field">
              <label className="field-label">Name</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" placeholder="Tool Name" style={{ fontSize: 12 }} />
            </div>
            <div className="field">
              <label className="field-label">Tool ID</label>
              <input value={form.tool_id} onChange={(e) => setForm({ ...form, tool_id: e.target.value })} className="input mono" placeholder="tool_id" style={{ fontSize: 12 }} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div className="field">
              <label className="field-label">Type</label>
              <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} className="input" style={{ fontSize: 12 }}>
                <option value="sync">Sync</option>
                <option value="async">Async</option>
              </select>
            </div>
            <div className="field">
              <label className="field-label">Description</label>
              <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input" placeholder="What does this tool do?" style={{ fontSize: 12 }} />
            </div>
          </div>
          <div className="field mb-3">
            <label className="field-label">Parameters Schema (JSON)</label>
            <textarea value={form.parameters_schema} onChange={(e) => setForm({ ...form, parameters_schema: e.target.value })} rows={4} className="input mono" style={{ fontSize: 12, lineHeight: 1.6 }} />
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setAdding(false)} className="btn btn-ghost" style={{ fontSize: 11, padding: "4px 12px" }}>Cancel</button>
            <button onClick={handleAdd} disabled={saving} className="btn btn-accent" style={{ fontSize: 11, padding: "4px 12px" }}>
              {saving ? "Adding..." : "Add Tool"}
            </button>
          </div>
        </div>
      )}

      {tools.length === 0 && !adding ? (
        <div className="text-center py-8" style={{ color: "var(--fg-3)" }}>
          <p className="text-[12px]">No tools configured</p>
          <p className="text-[11px] mt-1">Tools let the agent call external APIs and services</p>
        </div>
      ) : (
        tools.map((tool) => {
          const isExpanded = expandedId === tool.id;
          const schemaStr = editSchema[tool.id] ?? JSON.stringify(tool.parameters_schema, null, 2);
          const isRunnerOpen = showRunner === tool.id;
          return (
            <div key={tool.id} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
              <div
                className="flex items-center gap-3"
                style={{ padding: "10px 0", cursor: "pointer" }}
                onClick={() => setExpandedId(isExpanded ? null : tool.id)}
              >
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="var(--fg-3)"
                  strokeWidth="2"
                  style={{ transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)", transition: "transform 0.2s", flexShrink: 0 }}
                >
                  <polyline points="9 18 15 12 9 6" />
                </svg>
                <span className="text-[13px] font-medium" style={{ color: "var(--fg)", flex: 1 }}>{tool.name}</span>

                {/* Run button */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowRunner(isRunnerOpen ? null : tool.id);
                    if (!isExpanded) setExpandedId(tool.id);
                  }}
                  title="Test run this tool"
                  style={{
                    padding: "3px 10px",
                    fontSize: 10,
                    fontWeight: 600,
                    background: isRunnerOpen ? "var(--accent)" : "transparent",
                    color: isRunnerOpen ? "#fff" : "var(--text-muted)",
                    border: isRunnerOpen ? "1px solid var(--accent)" : "1px solid var(--border-light)",
                    borderRadius: 4,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                    transition: "all 0.15s ease",
                  }}
                >
                  <svg width="8" height="8" viewBox="0 0 24 24" fill="currentColor" stroke="none">
                    <polygon points="5 3 19 12 5 21 5 3" />
                  </svg>
                  Run
                </button>

                <span className="mono text-[11px]" style={{ color: "var(--fg-3)" }}>{tool.tool_id}</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(tool.id);
                  }}
                  className="btn btn-danger"
                  style={{ padding: "2px 6px", fontSize: 11 }}
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" /></svg>
                </button>
              </div>
              {isExpanded && (
                <div style={{ paddingBottom: 12, paddingLeft: 24 }}>
                  {tool.description && (
                    <p className="text-[12px] mb-2" style={{ color: "var(--fg-3)" }}>{tool.description}</p>
                  )}

                  {/* Tool Runner */}
                  {isRunnerOpen && (
                    <ToolRunner toolId={tool.tool_id} schema={tool.parameters_schema} />
                  )}

                  <div className="field" style={{ marginTop: isRunnerOpen ? 12 : 0 }}>
                    <label className="field-label">Parameters Schema (JSON)</label>
                    <textarea
                      value={schemaStr}
                      onChange={(e) => setEditSchema({ ...editSchema, [tool.id]: e.target.value })}
                      rows={8}
                      className="input mono"
                      style={{ fontSize: 11, lineHeight: 1.6 }}
                    />
                  </div>
                  {editSchema[tool.id] !== undefined && editSchema[tool.id] !== JSON.stringify(tool.parameters_schema, null, 2) && (
                    <div className="flex justify-end mt-2">
                      <button onClick={() => handleSaveSchema(tool)} disabled={saving} className="btn btn-accent" style={{ fontSize: 11, padding: "4px 12px" }}>
                        {saving ? "Saving..." : "Save Schema"}
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })
      )}
    </div>
  );
}

/* ============================================================
   Tab: Rules
   ============================================================ */
function RulesTab({
  agentId,
  rules,
  onReload,
}: {
  agentId: string;
  rules: AgentRule[];
  onReload: () => void;
}) {
  const [adding, setAdding] = useState(false);
  const [newType, setNewType] = useState<"forbidden" | "required" | "format">("forbidden");
  const [newContent, setNewContent] = useState("");

  const handleAdd = async () => {
    if (!newContent.trim()) return;
    await createAgentRule(agentId, { rule_type: newType, content: newContent.trim() });
    setNewContent("");
    setAdding(false);
    onReload();
  };

  const handleDelete = async (ruleId: string) => {
    await deleteAgentRule(agentId, ruleId);
    onReload();
  };

  const handleToggle = async (rule: AgentRule) => {
    await updateAgentRule(agentId, rule.id, { is_active: !rule.is_active });
    onReload();
  };

  const typeLabels: Record<string, { label: string; icon: string; color: string }> = {
    forbidden: { label: "Forbidden", icon: "🚫", color: "#ef4444" },
    required: { label: "Required", icon: "✅", color: "#22c55e" },
    format: { label: "Format", icon: "📐", color: "#3b82f6" },
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-[12px]" style={{ color: "var(--fg-3)" }}>
          Rules constrain agent behavior — what it must/must not do.
        </p>
        <button onClick={() => setAdding(!adding)} className="btn btn-primary" style={{ padding: "4px 12px", fontSize: 11 }}>
          + Add Rule
        </button>
      </div>

      {adding && (
        <div className="card" style={{ padding: 16 }}>
          <div className="flex gap-3 items-start">
            <select
              value={newType}
              onChange={(e) => setNewType(e.target.value as typeof newType)}
              className="input"
              style={{ fontSize: 12, width: 140 }}
            >
              <option value="forbidden">Forbidden (禁止)</option>
              <option value="required">Required (必须)</option>
              <option value="format">Format (格式)</option>
            </select>
            <input
              value={newContent}
              onChange={(e) => setNewContent(e.target.value)}
              className="input"
              style={{ fontSize: 12, flex: 1 }}
              placeholder="Rule content..."
              onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            />
            <button onClick={handleAdd} className="btn btn-primary" style={{ padding: "6px 12px", fontSize: 11 }}>
              Save
            </button>
          </div>
        </div>
      )}

      {rules.length === 0 && !adding && (
        <div className="text-center py-12" style={{ color: "var(--fg-3)" }}>
          <p className="text-[13px]">No rules yet. Add rules to constrain agent behavior.</p>
        </div>
      )}

      <div className="space-y-2">
        {rules.map((rule) => {
          const info = typeLabels[rule.rule_type] || typeLabels.format;
          return (
            <div
              key={rule.id}
              className="flex items-center gap-3"
              style={{
                padding: "10px 14px",
                borderRadius: 8,
                background: "var(--bg-elevated)",
                border: "1px solid rgba(255,255,255,0.04)",
                opacity: rule.is_active ? 1 : 0.5,
              }}
            >
              <span style={{ fontSize: 14 }}>{info.icon}</span>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 600,
                  textTransform: "uppercase",
                  color: info.color,
                  width: 70,
                  flexShrink: 0,
                }}
              >
                {info.label}
              </span>
              <span style={{ fontSize: 12, color: "var(--fg-2)", flex: 1 }}>{rule.content}</span>
              <button
                onClick={() => handleToggle(rule)}
                style={{
                  fontSize: 10,
                  padding: "2px 8px",
                  borderRadius: 4,
                  border: "1px solid rgba(255,255,255,0.1)",
                  background: "transparent",
                  color: "var(--fg-3)",
                  cursor: "pointer",
                }}
              >
                {rule.is_active ? "Disable" : "Enable"}
              </button>
              <button
                onClick={() => handleDelete(rule.id)}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "var(--fg-3)",
                  cursor: "pointer",
                  padding: 4,
                }}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" /></svg>
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ============================================================
   Tab: Task Chain
   ============================================================ */
function TaskChainTab({
  taskChain,
  onTaskChainChange,
  skills,
}: {
  taskChain: TaskChainConfig | null;
  onTaskChainChange: (v: TaskChainConfig | null) => void;
  skills: AgentSkill[];
}) {
  const chain = taskChain || { tasks: [], entry_task: "" };

  const addTask = () => {
    const id = `task_${Date.now()}`;
    const updated: TaskChainConfig = {
      ...chain,
      tasks: [...chain.tasks, {
        id,
        name: "New Task",
        goal: "",
        skill_code: "",
        max_turns: 5,
        on_success: "",
        on_failure: "",
      }],
      entry_task: chain.entry_task || id,
    };
    onTaskChainChange(updated);
  };

  const updateTask = (idx: number, patch: Partial<TaskDef>) => {
    const tasks = [...chain.tasks];
    tasks[idx] = { ...tasks[idx], ...patch };
    onTaskChainChange({ ...chain, tasks });
  };

  const removeTask = (idx: number) => {
    const tasks = chain.tasks.filter((_, i) => i !== idx);
    const entry = chain.entry_task === chain.tasks[idx].id ? (tasks[0]?.id || "") : chain.entry_task;
    onTaskChainChange({ ...chain, tasks, entry_task: entry });
  };

  const taskIds = chain.tasks.map((t) => t.id);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[12px]" style={{ color: "var(--fg-3)" }}>
            Define the SOP as a task chain. Each task has a goal, skill, and transitions.
          </p>
        </div>
        <button onClick={addTask} className="btn btn-primary" style={{ padding: "4px 12px", fontSize: 11 }}>
          + Add Task
        </button>
      </div>

      {/* Entry task selector */}
      {chain.tasks.length > 0 && (
        <div className="field" style={{ gap: 4 }}>
          <label className="field-label">Entry Task (入口任务)</label>
          <select
            value={chain.entry_task}
            onChange={(e) => onTaskChainChange({ ...chain, entry_task: e.target.value })}
            className="input"
            style={{ fontSize: 12, width: 200 }}
          >
            {chain.tasks.map((t) => (
              <option key={t.id} value={t.id}>{t.name || t.id}</option>
            ))}
          </select>
        </div>
      )}

      {chain.tasks.length === 0 && (
        <div className="text-center py-12" style={{ color: "var(--fg-3)" }}>
          <p className="text-[13px]">No tasks yet. Add tasks to define the conversation flow.</p>
        </div>
      )}

      {/* Task cards */}
      <div className="space-y-3">
        {chain.tasks.map((task, idx) => (
          <div
            key={task.id}
            style={{
              padding: 16,
              borderRadius: 10,
              background: "var(--bg-elevated)",
              border: chain.entry_task === task.id
                ? "1px solid var(--accent)"
                : "1px solid rgba(255,255,255,0.06)",
            }}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span style={{ fontSize: 11, color: "var(--fg-3)", fontFamily: "monospace" }}>#{idx + 1}</span>
                <input
                  value={task.name}
                  onChange={(e) => updateTask(idx, { name: e.target.value })}
                  className="input"
                  style={{ fontSize: 13, fontWeight: 500, width: 200, padding: "4px 8px" }}
                  placeholder="Task name"
                />
                {task.terminal && (
                  <span style={{ fontSize: 10, color: "var(--accent)", fontWeight: 600 }}>TERMINAL</span>
                )}
              </div>
              <button
                onClick={() => removeTask(idx)}
                style={{ background: "transparent", border: "none", color: "var(--fg-3)", cursor: "pointer", padding: 4 }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" /></svg>
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3" style={{ fontSize: 12 }}>
              <div className="field" style={{ gap: 2 }}>
                <label className="field-label">ID</label>
                <input value={task.id} onChange={(e) => updateTask(idx, { id: e.target.value })} className="input mono" style={{ fontSize: 11, padding: "4px 8px" }} />
              </div>
              <div className="field" style={{ gap: 2 }}>
                <label className="field-label">Skill</label>
                <select
                  value={task.skill_code || ""}
                  onChange={(e) => updateTask(idx, { skill_code: e.target.value || undefined })}
                  className="input"
                  style={{ fontSize: 11, padding: "4px 8px" }}
                >
                  <option value="">None</option>
                  {skills.map((s) => (
                    <option key={s.id} value={s.code}>{s.name} ({s.code})</option>
                  ))}
                </select>
              </div>
              <div className="field col-span-2" style={{ gap: 2 }}>
                <label className="field-label">Goal (目标)</label>
                <input value={task.goal} onChange={(e) => updateTask(idx, { goal: e.target.value })} className="input" style={{ fontSize: 11, padding: "4px 8px" }} />
              </div>
              <div className="field col-span-2" style={{ gap: 2 }}>
                <label className="field-label">Success Condition</label>
                <input value={task.success_condition || ""} onChange={(e) => updateTask(idx, { success_condition: e.target.value })} className="input" style={{ fontSize: 11, padding: "4px 8px" }} />
              </div>
              <div className="field" style={{ gap: 2 }}>
                <label className="field-label">Max Turns</label>
                <input type="number" value={task.max_turns || ""} onChange={(e) => updateTask(idx, { max_turns: parseInt(e.target.value) || undefined })} className="input" style={{ fontSize: 11, padding: "4px 8px", width: 80 }} />
              </div>
              <div className="field" style={{ gap: 2 }}>
                <label className="field-label">Terminal?</label>
                <select
                  value={task.terminal ? "yes" : "no"}
                  onChange={(e) => updateTask(idx, { terminal: e.target.value === "yes" })}
                  className="input"
                  style={{ fontSize: 11, padding: "4px 8px", width: 80 }}
                >
                  <option value="no">No</option>
                  <option value="yes">Yes</option>
                </select>
              </div>
              {!task.terminal && (
                <>
                  <div className="field" style={{ gap: 2 }}>
                    <label className="field-label">On Success →</label>
                    <select value={task.on_success || ""} onChange={(e) => updateTask(idx, { on_success: e.target.value || undefined })} className="input" style={{ fontSize: 11, padding: "4px 8px" }}>
                      <option value="">—</option>
                      {taskIds.filter((id) => id !== task.id).map((id) => (
                        <option key={id} value={id}>{chain.tasks.find((t) => t.id === id)?.name || id}</option>
                      ))}
                    </select>
                  </div>
                  <div className="field" style={{ gap: 2 }}>
                    <label className="field-label">On Failure →</label>
                    <select value={task.on_failure || ""} onChange={(e) => updateTask(idx, { on_failure: e.target.value || undefined })} className="input" style={{ fontSize: 11, padding: "4px 8px" }}>
                      <option value="">—</option>
                      {taskIds.filter((id) => id !== task.id).map((id) => (
                        <option key={id} value={id}>{chain.tasks.find((t) => t.id === id)?.name || id}</option>
                      ))}
                    </select>
                  </div>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ============================================================
   AUDIO INIT MODAL
   ============================================================ */
type AudioInitStep = "idle" | "selecting" | "transcribing" | "transcript_review" | "analyzing" | "result_review" | "error";

/* ============================================================
   Conversation Test Modal
   ============================================================ */

type ConvTestStep = "config" | "running" | "evaluating" | "complete" | "error";

interface ConvTurn {
  role: "agent" | "user";
  content: string;
  turn: number;
}

interface ConvEvaluation {
  scores: Record<string, number>;
  overall: number;
  analysis: string;
  suggestions: string[];
}

function ConversationTestModal({
  onClose,
  agentId,
  defaultScenario = "",
}: {
  onClose: () => void;
  agentId: string;
  defaultScenario?: string;
}) {
  const [step, setStep] = useState<ConvTestStep>("config");
  const [scenario, setScenario] = useState(defaultScenario);
  const [persona, setPersona] = useState("");
  const [maxTurns, setMaxTurns] = useState(10);
  const [evaluate, setEvaluate] = useState(true);
  const [model, setModel] = useState("claude-sonnet-4-20250514");
  const [turns, setTurns] = useState<ConvTurn[]>([]);
  const [evaluation, setEvaluation] = useState<ConvEvaluation | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [activeTab, setActiveTab] = useState<"conversation" | "evaluation">("conversation");
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new turns arrive
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  const handleStart = useCallback(async () => {
    if (!scenario.trim()) return;
    setStep("running");
    setTurns([]);
    setEvaluation(null);
    setErrorMsg("");

    try {
      await runConversationTest(
        agentId,
        { scenario, persona, max_turns: maxTurns, evaluate, model },
        (event: ConversationTestEvent) => {
          switch (event.type) {
            case "turn": {
              const t = event.data as unknown as ConvTurn;
              setTurns((prev) => [...prev, t]);
              break;
            }
            case "progress":
              if (event.data.step === "evaluating") setStep("evaluating");
              break;
            case "evaluation":
              setEvaluation(event.data as unknown as ConvEvaluation);
              setStep("complete");
              setActiveTab("evaluation");
              break;
            case "done":
              if (step !== "complete") setStep("complete");
              break;
            case "error":
              setErrorMsg((event.data.message as string) || "未知错误");
              setStep("error");
              break;
          }
        },
      );
      // If no evaluation was requested, mark complete when stream ends
      if (!evaluate) setStep("complete");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "测试失败");
      setStep("error");
    }
  }, [agentId, scenario, persona, maxTurns, evaluate, model, step]);

  const handleRetry = useCallback(() => {
    handleStart();
  }, [handleStart]);

  const handleReset = useCallback(() => {
    setStep("config");
    setTurns([]);
    setEvaluation(null);
    setErrorMsg("");
  }, []);

  const currentTurn = turns.length;
  const scoreLabels: Record<string, string> = {
    task_completion: "任务完成度",
    naturalness: "对话自然度",
    rule_compliance: "规则遵守度",
    handling_difficulty: "异常处理",
    tone_consistency: "语气一致性",
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content-wide" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 800 }}>
        {/* Header */}
        <div className="flex items-center justify-between" style={{ marginBottom: 16 }}>
          <h2 className="text-[15px] font-semibold" style={{ color: "var(--fg)" }}>
            {step === "config" && "对话测试"}
            {step === "running" && `对话测试 — Round ${currentTurn}/${maxTurns}`}
            {step === "evaluating" && "对话测试 — 评估中..."}
            {step === "complete" && "对话测试 — 完成"}
            {step === "error" && "对话测试 — 错误"}
          </h2>
          <button
            onClick={onClose}
            style={{
              background: "none", border: "none", color: "var(--fg-3)",
              fontSize: 18, cursor: "pointer", padding: "4px 8px",
            }}
          >
            &times;
          </button>
        </div>

        {/* Config Step */}
        {step === "config" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <label className="text-[12px] font-medium" style={{ color: "var(--fg-2)", display: "block", marginBottom: 6 }}>
                场景描述 *
              </label>
              <textarea
                value={scenario}
                onChange={(e) => setScenario(e.target.value)}
                placeholder="例：客户车险即将到期，接到续保电话。客户去年未出险，对价格敏感。"
                rows={3}
                style={{
                  width: "100%", padding: "10px 12px", borderRadius: 8,
                  background: "var(--bg)", border: "1px solid var(--border-light)",
                  color: "var(--fg)", fontSize: 13, resize: "vertical",
                }}
              />
            </div>
            <div>
              <label className="text-[12px] font-medium" style={{ color: "var(--fg-2)", display: "block", marginBottom: 6 }}>
                模拟用户人设（留空自动生成）
              </label>
              <textarea
                value={persona}
                onChange={(e) => setPersona(e.target.value)}
                placeholder="例：35岁男性程序员，性格直爽，做决定比较快"
                rows={2}
                style={{
                  width: "100%", padding: "10px 12px", borderRadius: 8,
                  background: "var(--bg)", border: "1px solid var(--border-light)",
                  color: "var(--fg)", fontSize: 13, resize: "vertical",
                }}
              />
            </div>
            <div style={{ display: "flex", gap: 24, alignItems: "center" }}>
              <div style={{ flex: 1 }}>
                <label className="text-[12px] font-medium" style={{ color: "var(--fg-2)", display: "block", marginBottom: 6 }}>
                  对话轮数: {maxTurns}
                </label>
                <input
                  type="range"
                  min={4}
                  max={24}
                  value={maxTurns}
                  onChange={(e) => setMaxTurns(Number(e.target.value))}
                  style={{ width: "100%" }}
                />
              </div>
              <div style={{ flex: 1 }}>
                <label className="text-[12px] font-medium" style={{ color: "var(--fg-2)", display: "block", marginBottom: 6 }}>
                  模型
                </label>
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  style={{
                    width: "100%", padding: "8px 10px", borderRadius: 8,
                    background: "var(--bg)", border: "1px solid var(--border-light)",
                    color: "var(--fg)", fontSize: 13,
                  }}
                >
                  <option value="claude-sonnet-4-20250514">Claude Sonnet 4</option>
                  <option value="claude-haiku-4-5-20251001">Claude Haiku 4.5</option>
                  <option value="gpt-4o">GPT-4o</option>
                  <option value="qwen-max">Qwen Max</option>
                </select>
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                id="conv-test-eval"
                checked={evaluate}
                onChange={(e) => setEvaluate(e.target.checked)}
              />
              <label htmlFor="conv-test-eval" className="text-[13px]" style={{ color: "var(--fg-2)", cursor: "pointer" }}>
                对话结束后自动评估
              </label>
            </div>
            <button
              className="btn btn-primary"
              onClick={handleStart}
              disabled={!scenario.trim()}
              style={{ alignSelf: "center", padding: "8px 32px", fontSize: 13 }}
            >
              开始测试
            </button>
          </div>
        )}

        {/* Running / Evaluating / Complete — Conversation Display */}
        {step !== "config" && (
          <div>
            {/* Tabs (only show when complete with evaluation) */}
            {step === "complete" && evaluation && (
              <div style={{ display: "flex", gap: 0, marginBottom: 16, borderBottom: "1px solid var(--border-light)" }}>
                <button
                  onClick={() => setActiveTab("conversation")}
                  style={{
                    padding: "8px 20px", fontSize: 13, cursor: "pointer",
                    background: "none", border: "none",
                    color: activeTab === "conversation" ? "var(--accent)" : "var(--fg-3)",
                    borderBottom: activeTab === "conversation" ? "2px solid var(--accent)" : "2px solid transparent",
                    fontWeight: activeTab === "conversation" ? 600 : 400,
                  }}
                >
                  对话
                </button>
                <button
                  onClick={() => setActiveTab("evaluation")}
                  style={{
                    padding: "8px 20px", fontSize: 13, cursor: "pointer",
                    background: "none", border: "none",
                    color: activeTab === "evaluation" ? "var(--accent)" : "var(--fg-3)",
                    borderBottom: activeTab === "evaluation" ? "2px solid var(--accent)" : "2px solid transparent",
                    fontWeight: activeTab === "evaluation" ? 600 : 400,
                  }}
                >
                  评估
                </button>
              </div>
            )}

            {/* Conversation Tab */}
            {(activeTab === "conversation" || !evaluation) && (
              <div style={{
                maxHeight: 420, overflowY: "auto", padding: "8px 0",
                display: "flex", flexDirection: "column", gap: 12,
              }}>
                {turns.map((t, i) => (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      flexDirection: t.role === "agent" ? "row" : "row-reverse",
                      gap: 10,
                      alignItems: "flex-start",
                    }}
                  >
                    <div style={{
                      width: 28, height: 28, borderRadius: "50%", flexShrink: 0,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 13, fontWeight: 600,
                      background: t.role === "agent" ? "var(--accent)" : "rgba(255,255,255,0.08)",
                      color: t.role === "agent" ? "#fff" : "var(--fg-2)",
                    }}>
                      {t.role === "agent" ? "A" : "U"}
                    </div>
                    <div style={{
                      maxWidth: "75%", padding: "10px 14px", borderRadius: 12,
                      fontSize: 13, lineHeight: 1.6,
                      background: t.role === "agent"
                        ? "rgba(var(--accent-rgb, 99,102,241), 0.12)"
                        : "rgba(255,255,255,0.05)",
                      color: "var(--fg)",
                    }}>
                      <div style={{ fontSize: 11, color: "var(--fg-3)", marginBottom: 4 }}>
                        {t.role === "agent" ? "Agent" : "模拟用户"} &middot; Round {t.turn}
                      </div>
                      {t.content}
                    </div>
                  </div>
                ))}

                {/* Loading indicator */}
                {(step === "running") && (
                  <div style={{
                    display: "flex", gap: 10, alignItems: "center",
                    padding: "8px 0", color: "var(--fg-3)", fontSize: 13,
                  }}>
                    <span className="spinner" style={{ width: 16, height: 16 }} />
                    生成中...
                  </div>
                )}

                {step === "evaluating" && (
                  <div style={{
                    display: "flex", gap: 10, alignItems: "center",
                    padding: "12px 0", color: "var(--fg-3)", fontSize: 13,
                  }}>
                    <span className="spinner" style={{ width: 16, height: 16 }} />
                    正在评估对话质量...
                  </div>
                )}

                <div ref={chatEndRef} />
              </div>
            )}

            {/* Evaluation Tab */}
            {activeTab === "evaluation" && evaluation && (
              <div style={{ maxHeight: 420, overflowY: "auto", padding: "8px 0" }}>
                {/* Overall Score */}
                <div style={{
                  textAlign: "center", marginBottom: 20, padding: "16px 0",
                  borderBottom: "1px solid var(--border-light)",
                }}>
                  <div style={{ fontSize: 36, fontWeight: 700, color: "var(--accent)" }}>
                    {evaluation.overall}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--fg-3)" }}>综合评分 / 10</div>
                </div>

                {/* Score Bars */}
                <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 20 }}>
                  {Object.entries(evaluation.scores).map(([key, score]) => (
                    <div key={key} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <span style={{ fontSize: 12, color: "var(--fg-2)", width: 80, flexShrink: 0 }}>
                        {scoreLabels[key] || key}
                      </span>
                      <div style={{
                        flex: 1, height: 8, borderRadius: 4,
                        background: "rgba(255,255,255,0.06)",
                      }}>
                        <div style={{
                          width: `${(score as number) * 10}%`, height: "100%", borderRadius: 4,
                          background: (score as number) >= 7 ? "var(--accent)" : (score as number) >= 5 ? "#f59e0b" : "#ef4444",
                          transition: "width 0.5s ease",
                        }} />
                      </div>
                      <span style={{ fontSize: 13, fontWeight: 600, color: "var(--fg)", width: 24, textAlign: "right" }}>
                        {score as number}
                      </span>
                    </div>
                  ))}
                </div>

                {/* Analysis */}
                <div style={{ marginBottom: 16 }}>
                  <div className="text-[12px] font-medium" style={{ color: "var(--fg-2)", marginBottom: 6 }}>分析</div>
                  <div style={{ fontSize: 13, lineHeight: 1.7, color: "var(--fg)", padding: "10px 14px", borderRadius: 8, background: "rgba(255,255,255,0.03)" }}>
                    {evaluation.analysis}
                  </div>
                </div>

                {/* Suggestions */}
                {evaluation.suggestions.length > 0 && (
                  <div>
                    <div className="text-[12px] font-medium" style={{ color: "var(--fg-2)", marginBottom: 6 }}>改进建议</div>
                    <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 6 }}>
                      {evaluation.suggestions.map((s, i) => (
                        <li key={i} style={{
                          fontSize: 13, lineHeight: 1.6, color: "var(--fg)",
                          padding: "8px 12px", borderRadius: 8,
                          background: "rgba(255,255,255,0.03)",
                          borderLeft: "3px solid var(--accent)",
                        }}>
                          {s}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* Error state */}
            {step === "error" && (
              <div style={{
                padding: "16px", marginTop: 12, borderRadius: 8,
                background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.2)",
                color: "#fca5a5", fontSize: 13,
              }}>
                {errorMsg}
              </div>
            )}

            {/* Action buttons */}
            {(step === "complete" || step === "error") && (
              <div style={{ display: "flex", gap: 10, justifyContent: "center", marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--border-light)" }}>
                <button className="btn btn-secondary" onClick={handleRetry} style={{ fontSize: 12, padding: "6px 20px" }}>
                  重新测试
                </button>
                <button className="btn btn-ghost" onClick={handleReset} style={{ fontSize: 12, padding: "6px 20px" }}>
                  换场景
                </button>
                <button className="btn btn-ghost" onClick={onClose} style={{ fontSize: 12, padding: "6px 20px" }}>
                  关闭
                </button>
              </div>
            )}

            {/* Stop button during running */}
            {step === "running" && (
              <div style={{ display: "flex", justifyContent: "center", marginTop: 16 }}>
                <button className="btn btn-ghost" onClick={onClose} style={{ fontSize: 12, padding: "6px 20px" }}>
                  停止测试
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ============================================================
   Voice Test Modal — Phase 1 (text) + Phase 2 (audio)
   ============================================================ */

function VoiceTestModal({
  onClose,
  agentId,
  defaultScenario = "",
}: {
  onClose: () => void;
  agentId: string;
  defaultScenario?: string;
}) {
  const [step, setStep] = useState<ConvTestStep>("config");
  const [scenario, setScenario] = useState(defaultScenario);
  const [persona, setPersona] = useState("");
  const [maxTurns, setMaxTurns] = useState(10);
  const [evaluate, setEvaluate] = useState(true);
  const [model, setModel] = useState("claude-sonnet-4-20250514");
  const [audioEnabled, setAudioEnabled] = useState(false);
  const [agentTtsModelId, setAgentTtsModelId] = useState("");
  const [testerTtsModelId, setTesterTtsModelId] = useState("");
  const [ttsModels, setTtsModels] = useState<ProviderModel[]>([]);
  const [turns, setTurns] = useState<ConvTurn[]>([]);
  const [audioStatuses, setAudioStatuses] = useState<Record<number, string>>({});
  const [evaluation, setEvaluation] = useState<ConvEvaluation | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [activeTab, setActiveTab] = useState<"conversation" | "evaluation">("conversation");
  const [totalDuration, setTotalDuration] = useState(0);
  // LiveKit spectator connection
  const [lkUrl, setLkUrl] = useState("");
  const [lkToken, setLkToken] = useState("");
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Load TTS models when audio is enabled
  useEffect(() => {
    if (audioEnabled && ttsModels.length === 0) {
      listModels("tts").then(setTtsModels).catch(() => {});
    }
  }, [audioEnabled, ttsModels.length]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  const handleStart = useCallback(async () => {
    if (!scenario.trim()) return;
    setStep("running");
    setTurns([]);
    setEvaluation(null);
    setErrorMsg("");
    setAudioStatuses({});
    setLkUrl("");
    setLkToken("");

    try {
      await runVoiceTest(
        agentId,
        {
          scenario, persona, max_turns: maxTurns, evaluate, model,
          audio_enabled: audioEnabled,
          agent_tts_model_id: audioEnabled && agentTtsModelId ? agentTtsModelId : undefined,
          tester_tts_model_id: audioEnabled && testerTtsModelId ? testerTtsModelId : undefined,
        },
        (event: VoiceTestEvent) => {
          switch (event.type) {
            case "config": {
              // Phase 2: connect to LiveKit room as spectator
              const cfg = event.data as Record<string, unknown>;
              if (cfg.audio_enabled && cfg.spectator_token && cfg.livekit_url) {
                setLkUrl(cfg.livekit_url as string);
                setLkToken(cfg.spectator_token as string);
              }
              break;
            }
            case "voice_turn": {
              const raw = event.data as Record<string, unknown>;
              const role = raw.role === "tester" ? "user" as const : raw.role as "agent";
              setTurns((prev) => [...prev, { role, content: raw.content as string, turn: raw.turn as number }]);
              break;
            }
            case "audio_status": {
              const turn = event.data.turn as number;
              const status = event.data.status as string;
              setAudioStatuses((prev) => ({ ...prev, [turn]: status }));
              break;
            }
            case "progress":
              if (event.data.step === "evaluating") setStep("evaluating");
              break;
            case "evaluation":
              setEvaluation(event.data as unknown as ConvEvaluation);
              setStep("complete");
              setActiveTab("evaluation");
              break;
            case "done":
              setTotalDuration(event.data.total_duration_ms as number || 0);
              if (step !== "complete") setStep("complete");
              break;
            case "error":
              setErrorMsg((event.data.message as string) || "未知错误");
              setStep("error");
              break;
          }
        },
      );
      if (!evaluate) setStep("complete");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "测试失败");
      setStep("error");
    }
  }, [agentId, scenario, persona, maxTurns, evaluate, model, audioEnabled, agentTtsModelId, testerTtsModelId, step]);

  const handleRetry = useCallback(() => { handleStart(); }, [handleStart]);
  const handleReset = useCallback(() => {
    setStep("config"); setTurns([]); setEvaluation(null); setErrorMsg(""); setAudioStatuses({});
    setLkUrl(""); setLkToken("");
  }, []);

  const currentTurn = turns.length;
  const scoreLabels: Record<string, string> = {
    task_completion: "任务完成度", naturalness: "对话自然度", rule_compliance: "规则遵守度",
    handling_difficulty: "异常处理", tone_consistency: "语气一致性",
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content-wide" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 800 }}>
        {/* Header */}
        <div className="flex items-center justify-between" style={{ marginBottom: 16 }}>
          <h2 className="text-[15px] font-semibold" style={{ color: "var(--fg)" }}>
            {step === "config" && "语音对抗测试"}
            {step === "running" && <>{`语音对抗 — Round ${currentTurn}/${maxTurns}`}{lkToken && <span style={{ marginLeft: 8, fontSize: 11, color: "#4ade80" }}>&#9679; 语音播放中</span>}</>}
            {step === "evaluating" && "语音对抗 — 评估中..."}
            {step === "complete" && `语音对抗 — 完成${totalDuration ? ` (${(totalDuration / 1000).toFixed(1)}s)` : ""}`}
            {step === "error" && "语音对抗 — 错误"}
          </h2>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "var(--fg-3)", fontSize: 18, cursor: "pointer", padding: "4px 8px" }}>&times;</button>
        </div>

        {/* Config */}
        {step === "config" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <label className="text-[12px] font-medium" style={{ color: "var(--fg-2)", display: "block", marginBottom: 6 }}>场景描述 *</label>
              <textarea value={scenario} onChange={(e) => setScenario(e.target.value)} placeholder="例：客户车险即将到期，接到续保电话。客户去年未出险，对价格敏感。" rows={3}
                style={{ width: "100%", padding: "10px 12px", borderRadius: 8, background: "var(--bg)", border: "1px solid var(--border-light)", color: "var(--fg)", fontSize: 13, resize: "vertical" }} />
            </div>
            <div>
              <label className="text-[12px] font-medium" style={{ color: "var(--fg-2)", display: "block", marginBottom: 6 }}>模拟用户人设（留空自动生成）</label>
              <textarea value={persona} onChange={(e) => setPersona(e.target.value)} placeholder="例：35岁男性程序员，性格直爽" rows={2}
                style={{ width: "100%", padding: "10px 12px", borderRadius: 8, background: "var(--bg)", border: "1px solid var(--border-light)", color: "var(--fg)", fontSize: 13, resize: "vertical" }} />
            </div>
            <div style={{ display: "flex", gap: 24, alignItems: "center" }}>
              <div style={{ flex: 1 }}>
                <label className="text-[12px] font-medium" style={{ color: "var(--fg-2)", display: "block", marginBottom: 6 }}>对话轮数: {maxTurns}</label>
                <input type="range" min={4} max={24} value={maxTurns} onChange={(e) => setMaxTurns(Number(e.target.value))} style={{ width: "100%" }} />
              </div>
              <div style={{ flex: 1 }}>
                <label className="text-[12px] font-medium" style={{ color: "var(--fg-2)", display: "block", marginBottom: 6 }}>模型</label>
                <select value={model} onChange={(e) => setModel(e.target.value)}
                  style={{ width: "100%", padding: "8px 10px", borderRadius: 8, background: "var(--bg)", border: "1px solid var(--border-light)", color: "var(--fg)", fontSize: 13 }}>
                  <option value="claude-sonnet-4-20250514">Claude Sonnet 4</option>
                  <option value="claude-haiku-4-5-20251001">Claude Haiku 4.5</option>
                  <option value="gpt-4o">GPT-4o</option>
                  <option value="qwen-max">Qwen Max</option>
                </select>
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input type="checkbox" id="voice-test-eval" checked={evaluate} onChange={(e) => setEvaluate(e.target.checked)} />
                <label htmlFor="voice-test-eval" className="text-[13px]" style={{ color: "var(--fg-2)", cursor: "pointer" }}>对话结束后自动评估</label>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input type="checkbox" id="voice-test-audio" checked={audioEnabled} onChange={(e) => setAudioEnabled(e.target.checked)} />
                <label htmlFor="voice-test-audio" className="text-[13px]" style={{ color: "var(--fg-2)", cursor: "pointer" }}>启用语音（TTS + LiveKit 实时播放）</label>
              </div>
            </div>
            {audioEnabled && (
              <div style={{ display: "flex", gap: 16 }}>
                <div style={{ flex: 1 }}>
                  <label className="text-[12px] font-medium" style={{ color: "var(--fg-2)", display: "block", marginBottom: 6 }}>Agent TTS 音色</label>
                  <select value={agentTtsModelId} onChange={(e) => setAgentTtsModelId(e.target.value)}
                    style={{ width: "100%", padding: "8px 10px", borderRadius: 8, background: "var(--bg)", border: "1px solid var(--border-light)", color: "var(--fg)", fontSize: 13 }}>
                    <option value="">使用 Agent 默认 TTS</option>
                    {ttsModels.map((m) => <option key={m.id} value={m.id}>{m.name} ({m.provider_name})</option>)}
                  </select>
                </div>
                <div style={{ flex: 1 }}>
                  <label className="text-[12px] font-medium" style={{ color: "var(--fg-2)", display: "block", marginBottom: 6 }}>Tester TTS 音色</label>
                  <select value={testerTtsModelId} onChange={(e) => setTesterTtsModelId(e.target.value)}
                    style={{ width: "100%", padding: "8px 10px", borderRadius: 8, background: "var(--bg)", border: "1px solid var(--border-light)", color: "var(--fg)", fontSize: 13 }}>
                    <option value="">默认 TTS</option>
                    {ttsModels.map((m) => <option key={m.id} value={m.id}>{m.name} ({m.provider_name})</option>)}
                  </select>
                </div>
              </div>
            )}
            <button className="btn btn-primary" onClick={handleStart} disabled={!scenario.trim()} style={{ alignSelf: "center", padding: "8px 32px", fontSize: 13 }}>
              开始语音对抗
            </button>
          </div>
        )}

        {/* LiveKit spectator: auto-play both agent voices */}
        {lkUrl && lkToken && (
          <LiveKitRoom serverUrl={lkUrl} token={lkToken} connect audio={true} style={{ display: "none" }}>
            <RoomAudioRenderer />
          </LiveKitRoom>
        )}

        {/* Running / Complete */}
        {step !== "config" && (
          <div>
            {/* Tabs */}
            {step === "complete" && evaluation && (
              <div style={{ display: "flex", gap: 0, marginBottom: 16, borderBottom: "1px solid var(--border-light)" }}>
                {(["conversation", "evaluation"] as const).map((tab) => (
                  <button key={tab} onClick={() => setActiveTab(tab)}
                    style={{ padding: "8px 20px", fontSize: 13, cursor: "pointer", background: "none", border: "none",
                      color: activeTab === tab ? "var(--accent)" : "var(--fg-3)",
                      borderBottom: activeTab === tab ? "2px solid var(--accent)" : "2px solid transparent",
                      fontWeight: activeTab === tab ? 600 : 400 }}>
                    {tab === "conversation" ? "对话" : "评估"}
                  </button>
                ))}
              </div>
            )}

            {/* Conversation */}
            {(activeTab === "conversation" || !evaluation) && (
              <div style={{ maxHeight: 420, overflowY: "auto", padding: "8px 0", display: "flex", flexDirection: "column", gap: 12 }}>
                {turns.map((t, i) => (
                  <div key={i} style={{ display: "flex", flexDirection: t.role === "agent" ? "row" : "row-reverse", gap: 10, alignItems: "flex-start" }}>
                    <div style={{ width: 28, height: 28, borderRadius: "50%", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 13, fontWeight: 600, background: t.role === "agent" ? "var(--accent)" : "rgba(255,255,255,0.08)", color: t.role === "agent" ? "#fff" : "var(--fg-2)" }}>
                      {t.role === "agent" ? "A" : "T"}
                    </div>
                    <div style={{ maxWidth: "75%", padding: "10px 14px", borderRadius: 12, fontSize: 13, lineHeight: 1.6,
                      background: t.role === "agent" ? "rgba(var(--accent-rgb, 99,102,241), 0.12)" : "rgba(255,255,255,0.05)", color: "var(--fg)" }}>
                      <div style={{ fontSize: 11, color: "var(--fg-3)", marginBottom: 4, display: "flex", alignItems: "center", gap: 6 }}>
                        <span>{t.role === "agent" ? "Agent" : "Tester"} &middot; Round {t.turn}</span>
                        {audioStatuses[t.turn] === "speaking" && <span style={{ color: "var(--accent)" }}>&#9834;</span>}
                        {audioStatuses[t.turn] === "finished" && <span style={{ color: "var(--fg-3)" }}>&#10003;</span>}
                      </div>
                      {t.content}
                    </div>
                  </div>
                ))}
                {step === "running" && (
                  <div style={{ display: "flex", gap: 10, alignItems: "center", padding: "8px 0", color: "var(--fg-3)", fontSize: 13 }}>
                    <span className="spinner" style={{ width: 16, height: 16 }} /> 生成中...
                  </div>
                )}
                {step === "evaluating" && (
                  <div style={{ display: "flex", gap: 10, alignItems: "center", padding: "12px 0", color: "var(--fg-3)", fontSize: 13 }}>
                    <span className="spinner" style={{ width: 16, height: 16 }} /> 正在评估对话质量...
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>
            )}

            {/* Evaluation */}
            {activeTab === "evaluation" && evaluation && (
              <div style={{ maxHeight: 420, overflowY: "auto", padding: "8px 0" }}>
                <div style={{ textAlign: "center", marginBottom: 20, padding: "16px 0", borderBottom: "1px solid var(--border-light)" }}>
                  <div style={{ fontSize: 36, fontWeight: 700, color: "var(--accent)" }}>{evaluation.overall}</div>
                  <div style={{ fontSize: 12, color: "var(--fg-3)" }}>综合评分 / 10</div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 20 }}>
                  {Object.entries(evaluation.scores).map(([key, score]) => (
                    <div key={key} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <span style={{ fontSize: 12, color: "var(--fg-2)", width: 80, flexShrink: 0 }}>{scoreLabels[key] || key}</span>
                      <div style={{ flex: 1, height: 8, borderRadius: 4, background: "rgba(255,255,255,0.06)" }}>
                        <div style={{ width: `${(score as number) * 10}%`, height: "100%", borderRadius: 4,
                          background: (score as number) >= 7 ? "var(--accent)" : (score as number) >= 5 ? "#f59e0b" : "#ef4444", transition: "width 0.5s ease" }} />
                      </div>
                      <span style={{ fontSize: 13, fontWeight: 600, color: "var(--fg)", width: 24, textAlign: "right" }}>{score as number}</span>
                    </div>
                  ))}
                </div>
                <div style={{ marginBottom: 16 }}>
                  <div className="text-[12px] font-medium" style={{ color: "var(--fg-2)", marginBottom: 6 }}>分析</div>
                  <div style={{ fontSize: 13, lineHeight: 1.7, color: "var(--fg)", padding: "10px 14px", borderRadius: 8, background: "rgba(255,255,255,0.03)" }}>{evaluation.analysis}</div>
                </div>
                {evaluation.suggestions.length > 0 && (
                  <div>
                    <div className="text-[12px] font-medium" style={{ color: "var(--fg-2)", marginBottom: 6 }}>改进建议</div>
                    <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 6 }}>
                      {evaluation.suggestions.map((s, i) => (
                        <li key={i} style={{ fontSize: 13, lineHeight: 1.6, color: "var(--fg)", padding: "8px 12px", borderRadius: 8, background: "rgba(255,255,255,0.03)", borderLeft: "3px solid var(--accent)" }}>{s}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* Error */}
            {step === "error" && (
              <div style={{ padding: "16px", marginTop: 12, borderRadius: 8, background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.2)", color: "#fca5a5", fontSize: 13 }}>{errorMsg}</div>
            )}

            {/* Actions */}
            {(step === "complete" || step === "error") && (
              <div style={{ display: "flex", gap: 10, justifyContent: "center", marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--border-light)" }}>
                <button className="btn btn-secondary" onClick={handleRetry} style={{ fontSize: 12, padding: "6px 20px" }}>重新测试</button>
                <button className="btn btn-ghost" onClick={handleReset} style={{ fontSize: 12, padding: "6px 20px" }}>换场景</button>
                <button className="btn btn-ghost" onClick={onClose} style={{ fontSize: 12, padding: "6px 20px" }}>关闭</button>
              </div>
            )}
            {step === "running" && (
              <div style={{ display: "flex", justifyContent: "center", marginTop: 16 }}>
                <button className="btn btn-ghost" onClick={onClose} style={{ fontSize: 12, padding: "6px 20px" }}>停止测试</button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

interface AudioInitResult {
  role?: string;
  goal?: string;
  opening_line?: string;
  task_chain?: Record<string, unknown>;
  skills?: Record<string, unknown>[];
  rules?: Record<string, unknown>[];
  system_prompt?: string;
}

function AudioInitModal({
  step,
  onClose,
  agentId,
  onApply,
}: {
  step: AudioInitStep;
  onClose: () => void;
  agentId: string;
  onApply: (result: AudioInitResult) => void;
}) {
  const [currentStep, setCurrentStep] = useState<AudioInitStep>(step);
  const [progressMsg, setProgressMsg] = useState("");
  const [transcript, setTranscript] = useState<{ text: string; turns: { speaker: string; text: string }[] } | null>(null);
  const [result, setResult] = useState<AudioInitResult | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(async (file: File) => {
    setSelectedFile(file);
    setCurrentStep("transcribing");
    setProgressMsg("正在上传文件...");

    try {
      await initAgentFromAudio(agentId, file, (event: AudioInitEvent) => {
        switch (event.type) {
          case "progress":
            setProgressMsg((event.data.message as string) || "处理中...");
            if (event.data.step === "analyzing") {
              setCurrentStep("analyzing");
            }
            break;
          case "transcript":
            setTranscript(event.data as { text: string; turns: { speaker: string; text: string }[] });
            setCurrentStep("transcript_review");
            break;
          case "result":
            setResult(event.data as AudioInitResult);
            setCurrentStep("result_review");
            break;
          case "error":
            setErrorMsg((event.data.message as string) || "未知错误");
            setCurrentStep("error");
            break;
          case "done":
            if (!result) setCurrentStep("result_review");
            break;
        }
      });
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "上传失败");
      setCurrentStep("error");
    }
  }, [agentId, result]);

  const continueToAnalysis = useCallback(() => {
    // After transcript review, the SSE stream continues automatically
    // If we already have a result, go to result_review
    if (result) {
      setCurrentStep("result_review");
    } else {
      setCurrentStep("analyzing");
      setProgressMsg("正在分析对话结构...");
    }
  }, [result]);

  if (currentStep === "idle") return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content-wide" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between" style={{ marginBottom: 20 }}>
          <h2 className="text-[15px] font-semibold" style={{ color: "var(--fg)" }}>
            {currentStep === "selecting" && "Audio Init — Upload Conversation"}
            {currentStep === "transcribing" && "Audio Init — Transcribing"}
            {currentStep === "transcript_review" && "Audio Init — Transcript Review"}
            {currentStep === "analyzing" && "Audio Init — Analyzing"}
            {currentStep === "result_review" && "Audio Init — SOP Extracted"}
            {currentStep === "error" && "Audio Init — Error"}
          </h2>
          <button onClick={onClose} className="btn btn-ghost" style={{ padding: "4px 8px" }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12" /></svg>
          </button>
        </div>

        {/* Step: File Selection */}
        {currentStep === "selecting" && (
          <div>
            <div
              className={`drop-zone ${dragOver ? "drag-over" : ""}`}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                const f = e.dataTransfer.files[0];
                if (f) handleFile(f);
              }}
              onClick={() => fileInputRef.current?.click()}
            >
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ margin: "0 auto 12px", opacity: 0.5 }}>
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
              <p className="text-[14px]" style={{ marginBottom: 4 }}>Drag & drop audio file here</p>
              <p className="text-[12px]" style={{ color: "var(--fg-3)" }}>Supports MP3, WAV, M4A (max 100MB)</p>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*"
              style={{ display: "none" }}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleFile(f);
              }}
            />
          </div>
        )}

        {/* Step: Transcribing / Analyzing */}
        {(currentStep === "transcribing" || currentStep === "analyzing") && (
          <div style={{ textAlign: "center", padding: "40px 0" }}>
            <div className="spinner" style={{
              width: 32, height: 32, border: "3px solid rgba(255,255,255,0.1)",
              borderTopColor: "var(--accent)", borderRadius: "50%",
              animation: "spin 0.8s linear infinite", margin: "0 auto 16px",
            }} />
            <p className="text-[14px]" style={{ color: "var(--fg-2)" }}>{progressMsg}</p>
            {selectedFile && (
              <p className="text-[12px] mt-2" style={{ color: "var(--fg-3)" }}>{selectedFile.name}</p>
            )}
          </div>
        )}

        {/* Step: Transcript Review */}
        {currentStep === "transcript_review" && transcript && (
          <div>
            <div style={{
              maxHeight: 400, overflowY: "auto", padding: 16,
              background: "rgba(0,0,0,0.2)", borderRadius: 8, marginBottom: 16,
            }}>
              {transcript.turns.length > 0 ? (
                transcript.turns.map((turn, i) => (
                  <div key={i} style={{ marginBottom: 8 }}>
                    <span className="text-[11px] font-medium" style={{
                      color: turn.speaker.includes("0") || turn.speaker === "A" ? "var(--accent)" : "var(--green)",
                    }}>
                      {turn.speaker}
                    </span>
                    <p className="text-[13px]" style={{ color: "var(--fg-2)", marginTop: 2 }}>{turn.text}</p>
                  </div>
                ))
              ) : (
                <pre className="text-[12px]" style={{ color: "var(--fg-2)", whiteSpace: "pre-wrap" }}>{transcript.text}</pre>
              )}
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={onClose} className="btn btn-ghost" style={{ fontSize: 13 }}>Cancel</button>
              <button onClick={continueToAnalysis} className="btn btn-accent" style={{ fontSize: 13 }}>
                Analyze & Extract SOP
              </button>
            </div>
          </div>
        )}

        {/* Step: Result Review */}
        {currentStep === "result_review" && result && (
          <div>
            <div style={{ maxHeight: 450, overflowY: "auto" }}>
              {/* Role */}
              {result.role && (
                <div style={{ marginBottom: 16 }}>
                  <label className="field-label">Role</label>
                  <div className="text-[13px]" style={{ color: "var(--fg-2)", padding: "8px 12px", background: "rgba(0,0,0,0.15)", borderRadius: 6 }}>
                    {result.role}
                  </div>
                </div>
              )}

              {/* Goal */}
              {result.goal && (
                <div style={{ marginBottom: 16 }}>
                  <label className="field-label">Target</label>
                  <div className="text-[13px]" style={{ color: "var(--fg-2)", padding: "8px 12px", background: "rgba(0,0,0,0.15)", borderRadius: 6 }}>
                    {result.goal}
                  </div>
                </div>
              )}

              {/* Opening Line */}
              {result.opening_line && (
                <div style={{ marginBottom: 16 }}>
                  <label className="field-label">Opening Line</label>
                  <div className="text-[13px]" style={{ color: "var(--fg-2)", padding: "8px 12px", background: "rgba(0,0,0,0.15)", borderRadius: 6 }}>
                    {result.opening_line}
                  </div>
                </div>
              )}

              {/* Task Chain */}
              {result.task_chain && (
                <div style={{ marginBottom: 16 }}>
                  <label className="field-label">Task Chain ({((result.task_chain as { tasks?: unknown[] }).tasks || []).length} stages)</label>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8, padding: "8px 0" }}>
                    {((result.task_chain as { tasks?: { id: string; name: string }[] }).tasks || []).map((t, i) => (
                      <span key={i} className="badge" style={{ background: "rgba(255,255,255,0.06)", color: "var(--fg-2)" }}>
                        {t.name}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Skills */}
              {result.skills && result.skills.length > 0 && (
                <div style={{ marginBottom: 16 }}>
                  <label className="field-label">Skills ({result.skills.length})</label>
                  {result.skills.map((s, i) => (
                    <div key={i} className="text-[12px]" style={{
                      padding: "6px 10px", marginTop: 4, background: "rgba(0,0,0,0.1)", borderRadius: 6,
                      color: "var(--fg-2)",
                    }}>
                      <strong>{(s as { name?: string }).name}</strong> — {(s as { description?: string }).description || ""}
                    </div>
                  ))}
                </div>
              )}

              {/* Rules */}
              {result.rules && result.rules.length > 0 && (
                <div style={{ marginBottom: 16 }}>
                  <label className="field-label">Rules ({result.rules.length})</label>
                  {result.rules.map((r, i) => (
                    <div key={i} className="text-[12px]" style={{
                      padding: "6px 10px", marginTop: 4, background: "rgba(0,0,0,0.1)", borderRadius: 6,
                      color: "var(--fg-2)",
                    }}>
                      <span className="badge badge-muted" style={{ marginRight: 6, fontSize: 10 }}>{(r as { rule_type?: string }).rule_type}</span>
                      {(r as { content?: string }).content}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2" style={{ marginTop: 16 }}>
              <button onClick={onClose} className="btn btn-ghost" style={{ fontSize: 13 }}>Cancel</button>
              <button
                onClick={() => { onApply(result); onClose(); }}
                className="btn btn-accent"
                style={{ fontSize: 13 }}
              >
                Apply to Agent
              </button>
            </div>
          </div>
        )}

        {/* Step: Error */}
        {currentStep === "error" && (
          <div style={{ textAlign: "center", padding: "32px 0" }}>
            <p className="text-[14px]" style={{ color: "var(--red)", marginBottom: 16 }}>{errorMsg}</p>
            <div className="flex justify-center gap-2">
              <button onClick={onClose} className="btn btn-ghost" style={{ fontSize: 13 }}>Close</button>
              <button
                onClick={() => { setCurrentStep("selecting"); setErrorMsg(""); }}
                className="btn btn-secondary"
                style={{ fontSize: 13 }}
              >
                Try Again
              </button>
            </div>
          </div>
        )}
      </div>
      <style jsx>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}

/* ============================================================
   MAIN EDITOR PAGE
   ============================================================ */
type EditorTab = "prompt" | "task_chain" | "variables" | "skills" | "tools" | "rules";

export default function AgentDetailPage() {
  const router = useRouter();
  const params = useParams();
  const agentId = params.id as string;

  /* ─── Core state ─── */
  const [agent, setAgent] = useState<Agent | null>(null);
  const [models, setModels] = useState<ProviderModel[]>([]);
  const [variables, setVariables] = useState<AgentVariable[]>([]);
  const [skills, setSkills] = useState<AgentSkill[]>([]);
  const [tools, setTools] = useState<AgentTool[]>([]);
  const [rules, setRules] = useState<AgentRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [activeTab, setActiveTab] = useState<EditorTab>("prompt");
  const [rightPanelOpen, setRightPanelOpen] = useState(true);
  const [versions, setVersions] = useState<AgentVersionSummary[]>([]);
  const [showVersionPanel, setShowVersionPanel] = useState(false);
  const [audioInitStep, setAudioInitStep] = useState<AudioInitStep>("idle");
  const [convTestOpen, setConvTestOpen] = useState(false);
  const [voiceTestOpen, setVoiceTestOpen] = useState(false);

  /* ─── Form state ─── */
  const [nameZh, setNameZh] = useState("");
  const [nameEn, setNameEn] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [goal, setGoal] = useState("");
  const [userPrompt, setUserPrompt] = useState("");
  const [openingLine, setOpeningLine] = useState("");
  const [asr, setAsr] = useState<string | null>(null);
  const [tts, setTts] = useState<string | null>(null);
  const [nlp, setNlp] = useState<string | null>(null);
  const [lang, setLang] = useState("auto");
  const [intPolicy, setIntPolicy] = useState("always");
  const [isActive, setIsActive] = useState(true);
  const [voiceprintEnabled, setVoiceprintEnabled] = useState(false);
  const [role, setRole] = useState("");
  const [taskChain, setTaskChain] = useState<TaskChainConfig | null>(null);
  const [noiseDetection, setNoiseDetection] = useState(false);
  const [multiSpeaker, setMultiSpeaker] = useState(false);
  const [subtitleAlignment, setSubtitleAlignment] = useState(false);

  /* ─── Load data ─── */
  const loadAgent = useCallback(async () => {
    try {
      const [agentData, modelList] = await Promise.all([
        getAgent(agentId),
        listModels(),
      ]);
      setAgent(agentData);
      setModels(modelList);
      setNameZh(agentData.name_zh);
      setNameEn(agentData.name_en);
      setSystemPrompt(agentData.system_prompt || "");
      setGoal(agentData.goal || "");
      setUserPrompt(agentData.user_prompt || "");
      setOpeningLine(agentData.opening_line || "");
      setAsr(agentData.asr_model_id);
      setTts(agentData.tts_model_id);
      setNlp(agentData.nlp_model_id);
      setLang(agentData.language);
      setIntPolicy(agentData.interruption_policy);
      setIsActive(agentData.is_active);
      setVoiceprintEnabled(agentData.voiceprint_enabled);
      setRole(agentData.role || "");
      setTaskChain(agentData.task_chain || null);
      const cc = agentData.call_control || {};
      setNoiseDetection(!!cc.noise_detection);
      setMultiSpeaker(!!cc.multi_speaker);
      setSubtitleAlignment(!!cc.subtitle_alignment);
    } catch (err) {
      console.error("Failed to load agent:", err);
      router.replace("/agents");
    } finally {
      setLoading(false);
    }
  }, [agentId, router]);

  const loadSubResources = useCallback(async () => {
    try {
      const [vars, sk, tl, rl, vs] = await Promise.all([
        listAgentVariables(agentId).catch(() => []),
        listAgentSkills(agentId).catch(() => []),
        listAgentTools(agentId).catch(() => []),
        listAgentRules(agentId).catch(() => []),
        listAgentVersions(agentId).catch(() => []),
      ]);
      setVariables(vars);
      setSkills(sk);
      setTools(tl);
      setRules(rl);
      setVersions(vs);
    } catch {
      // sub-resources may not exist yet
    }
  }, [agentId]);

  useEffect(() => {
    loadAgent();
    loadSubResources();
  }, [loadAgent, loadSubResources]);

  /* ─── Save ─── */
  const handleSave = async () => {
    setSaving(true);
    try {
      const callControl: Record<string, unknown> = {
        noise_detection: noiseDetection,
        multi_speaker: multiSpeaker,
        subtitle_alignment: subtitleAlignment,
      };
      await updateAgent(agentId, {
        name_zh: nameZh,
        name_en: nameEn,
        system_prompt: systemPrompt,
        goal: goal || null,
        role: role || null,
        task_chain: taskChain,
        user_prompt: userPrompt || null,
        opening_line: openingLine || null,
        asr_model_id: asr,
        tts_model_id: tts,
        nlp_model_id: nlp,
        language: lang,
        interruption_policy: intPolicy,
        is_active: isActive,
        voiceprint_enabled: voiceprintEnabled,
        call_control: callControl,
      });
      await loadAgent();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  /* ─── Publish ─── */
  const handlePublish = async () => {
    const summary = prompt("Publish this agent?\nOptional: describe what changed in this version:");
    if (summary === null) return; // user cancelled
    setPublishing(true);
    try {
      await publishAgent(agentId, summary || undefined);
      await loadAgent();
      await loadSubResources(); // reload versions
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to publish");
    } finally {
      setPublishing(false);
    }
  };

  /* ─── Rollback ─── */
  const handleRollback = async (versionId: string, versionNum: number) => {
    if (!confirm(`Rollback to v${versionNum}? Current config will be overwritten and status set to Draft.`)) return;
    try {
      await rollbackAgentVersion(agentId, versionId);
      await loadAgent();
      await loadSubResources();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to rollback");
    }
  };

  /* ─── Audio Init Apply ─── */
  const handleAudioInitApply = useCallback(async (result: AudioInitResult) => {
    try {
      // 1. Set local form state
      if (result.role) setRole(result.role);
      if (result.goal) setGoal(result.goal);
      if (result.opening_line) setOpeningLine(result.opening_line);
      if (result.task_chain) setTaskChain(result.task_chain as unknown as TaskChainConfig);
      if (result.system_prompt) setSystemPrompt(result.system_prompt);

      // 2. Create skills via API
      if (result.skills && result.skills.length > 0) {
        for (let idx = 0; idx < result.skills.length; idx++) {
          const s = result.skills[idx] as Record<string, unknown>;
          try {
            await createAgentSkill(agentId, {
              name: (s.name as string) || "Unnamed Skill",
              code: (s.code as string) || (s.name as string || "skill").toLowerCase().replace(/\s+/g, "_"),
              description: (s.description as string) || "",
              content: (s.content as string) || "",
              skill_type: (s.skill_type as "free" | "qa" | "logic_tree") || "qa",
              qa_pairs: s.qa_pairs as Record<string, unknown> | undefined,
              sort_order: typeof s.sort_order === "number" ? s.sort_order : idx,
            });
          } catch (e) {
            console.warn("Failed to create skill:", e);
          }
        }
      }

      // 3. Create rules via API
      if (result.rules && result.rules.length > 0) {
        for (const rule of result.rules) {
          try {
            await createAgentRule(agentId, {
              rule_type: (rule as { rule_type?: string }).rule_type || "must",
              content: (rule as { content?: string }).content || "",
            });
          } catch (e) {
            console.warn("Failed to create rule:", e);
          }
        }
      }

      // 4. Reload sub-resources to reflect new skills/rules
      await loadSubResources();
    } catch (err) {
      console.error("Failed to apply audio init result:", err);
      alert("部分配置应用失败，请检查");
    }
  }, [agentId, loadSubResources]);

  /* ─── Loading state ─── */
  if (loading) {
    return (
      <div className="page">
        <div className="text-center py-24" style={{ color: "var(--fg-3)" }}>
          <p className="text-[13px]">Loading agent...</p>
        </div>
      </div>
    );
  }

  if (!agent) return null;

  const isDraft = (agent.status ?? "draft") !== "published";

  const tabs: { key: EditorTab; label: string }[] = [
    { key: "prompt", label: "Prompt" },
    { key: "task_chain", label: "Task Chain" },
    { key: "skills", label: "Skills" },
    { key: "rules", label: "Rules" },
    { key: "variables", label: "Variables" },
    { key: "tools", label: "Tools" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 56px)" }}>
      {/* ═══ TOP BAR ═══ */}
      <div
        className="animate-in"
        style={{
          padding: "12px 24px",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
          flexShrink: 0,
        }}
      >
        {/* Row 1: Nav + Name + Actions */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push("/agents")}
            className="btn btn-ghost"
            style={{ padding: "4px 8px" }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
          </button>

          <h1 className="text-[16px] font-semibold" style={{ color: "var(--fg)" }}>
            {nameZh || "Untitled Agent"}
          </h1>

          <span
            className="mono text-[11px]"
            style={{ color: "var(--fg-3)", cursor: "pointer" }}
            title={`Click to copy: ${agent.id}`}
            onClick={(e) => {
              e.stopPropagation();
              navigator.clipboard.writeText(agent.id);
              const el = e.currentTarget;
              el.textContent = "Copied!";
              el.style.color = "var(--green)";
              setTimeout(() => {
                el.textContent = `ID: ${agent.id.slice(0, 8)}`;
                el.style.color = "var(--fg-3)";
              }, 1200);
            }}
          >
            ID: {agent.id.slice(0, 8)}
          </span>

          <span
            className="badge"
            style={{
              background: isDraft ? "rgba(255,255,255,0.06)" : "var(--green-dim)",
              color: isDraft ? "var(--fg-3)" : "var(--green)",
            }}
          >
            {isDraft ? "Draft" : "Published"}
          </span>

          <span
            className="text-[11px]"
            style={{ color: "var(--fg-3)", cursor: "pointer", textDecoration: "underline", textDecorationStyle: "dotted", textUnderlineOffset: 3 }}
            onClick={() => setShowVersionPanel(!showVersionPanel)}
            title="Click to view version history"
          >
            v{agent.version ?? 1}
            {versions.length > 0 && ` (${versions.length} versions)`}
          </span>

          <div style={{ flex: 1 }} />

          {/* Mode buttons */}
          <button
            className="btn btn-secondary"
            style={{ fontSize: 12, padding: "5px 14px" }}
            onClick={() => setVoiceTestOpen(true)}
          >
            Voice
          </button>
          <button
            className="btn btn-secondary"
            style={{ fontSize: 12, padding: "5px 14px" }}
            onClick={() => setConvTestOpen(true)}
          >
            Test
          </button>
          <button
            className="btn btn-secondary"
            style={{ fontSize: 12, padding: "5px 14px" }}
            onClick={() => setAudioInitStep("selecting")}
          >
            Audio Init
          </button>
          <button
            className="btn btn-ghost"
            style={{ fontSize: 12, padding: "5px 14px" }}
            onClick={() => setRightPanelOpen(!rightPanelOpen)}
          >
            {rightPanelOpen ? "Hide Debug" : "Debug"}
          </button>

          <button
            onClick={handleSave}
            disabled={saving}
            className="btn btn-primary"
            style={{ fontSize: 12 }}
          >
            {saving ? "Saving..." : "Save"}
          </button>

          <button
            onClick={handlePublish}
            disabled={publishing}
            className="btn btn-accent"
            style={{ fontSize: 12 }}
          >
            {publishing ? "Publishing..." : "Publish"}
          </button>
        </div>

        {/* Row 2: Pipeline badges + opening line */}
        <div className="flex items-center gap-3 mt-2">
          <span className="text-[11px]" style={{ color: "var(--fg-3)" }}>Pipeline:</span>
          <span className="badge badge-asr">ASR</span>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--fg-3)" strokeWidth="2"><path d="M5 12h14" /><polyline points="12 5 19 12 12 19" /></svg>
          <span className="badge badge-nlp">NLP</span>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--fg-3)" strokeWidth="2"><path d="M5 12h14" /><polyline points="12 5 19 12 12 19" /></svg>
          <span className="badge badge-tts">TTS</span>

          <div style={{ width: 1, height: 16, background: "rgba(255,255,255,0.08)", margin: "0 8px" }} />

          <span className="text-[11px]" style={{ color: "var(--fg-3)" }}>Opening:</span>
          <input
            value={openingLine}
            onChange={(e) => setOpeningLine(e.target.value)}
            className="input"
            placeholder="Hello, how can I help you today?"
            style={{
              flex: 1,
              maxWidth: 400,
              fontSize: 12,
              padding: "4px 10px",
              height: 28,
            }}
          />
        </div>
      </div>

      {/* ═══ VERSION HISTORY PANEL ═══ */}
      {showVersionPanel && (
        <div
          className="animate-in"
          style={{
            borderBottom: "1px solid rgba(255,255,255,0.06)",
            background: "rgba(255,255,255,0.02)",
            padding: "12px 24px",
            maxHeight: 240,
            overflowY: "auto",
            flexShrink: 0,
          }}
        >
          <div className="flex items-center justify-between" style={{ marginBottom: 8 }}>
            <span className="text-[12px] font-medium" style={{ color: "var(--fg-2)" }}>
              Version History
            </span>
            <button
              onClick={() => setShowVersionPanel(false)}
              className="btn btn-ghost"
              style={{ padding: "2px 8px", fontSize: 11 }}
            >
              Close
            </button>
          </div>

          {versions.length === 0 ? (
            <p className="text-[12px]" style={{ color: "var(--fg-3)" }}>
              No published versions yet. Publish to create the first version snapshot.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {versions.map((v) => (
                <div
                  key={v.id}
                  className="flex items-center gap-3"
                  style={{
                    padding: "8px 12px",
                    borderRadius: 8,
                    background: v.version === agent.version ? "rgba(255,255,255,0.06)" : "transparent",
                    border: v.version === agent.version ? "1px solid rgba(255,255,255,0.08)" : "1px solid transparent",
                  }}
                >
                  <span className="text-[12px] font-medium" style={{ color: "var(--fg)", minWidth: 32 }}>
                    v{v.version}
                  </span>
                  <span className="text-[11px]" style={{ color: "var(--fg-3)", flex: 1 }}>
                    {v.change_summary || "No description"}
                  </span>
                  <span className="text-[11px] mono" style={{ color: "var(--fg-3)" }}>
                    {v.created_at ? new Date(v.created_at).toLocaleDateString("en-US", {
                      month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                    }) : "--"}
                  </span>
                  {v.version !== agent.version && (
                    <button
                      onClick={() => handleRollback(v.id, v.version)}
                      className="btn btn-ghost"
                      style={{
                        padding: "3px 10px",
                        fontSize: 11,
                        color: "var(--accent)",
                        borderRadius: 6,
                      }}
                    >
                      Rollback
                    </button>
                  )}
                  {v.version === agent.version && (
                    <span className="badge" style={{ background: "var(--green-dim)", color: "var(--green)", fontSize: 10 }}>
                      Current
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ═══ MAIN CONTENT ═══ */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* ─── LEFT PANEL (~60%) ─── */}
        <div
          style={{
            flex: rightPanelOpen ? "0 0 60%" : "1",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            borderRight: rightPanelOpen ? "1px solid rgba(255,255,255,0.04)" : "none",
            transition: "flex 0.3s ease",
          }}
        >
          {/* Tab bar */}
          <div
            style={{
              display: "flex",
              gap: 0,
              borderBottom: "1px solid rgba(255,255,255,0.06)",
              padding: "0 24px",
              flexShrink: 0,
            }}
          >
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                style={{
                  padding: "10px 18px",
                  fontSize: 13,
                  fontWeight: activeTab === tab.key ? 500 : 400,
                  color: activeTab === tab.key ? "var(--fg)" : "var(--fg-3)",
                  background: "transparent",
                  border: "none",
                  borderBottom: activeTab === tab.key ? "2px solid var(--accent)" : "2px solid transparent",
                  cursor: "pointer",
                  transition: "all 0.15s",
                }}
              >
                {tab.label}
                {tab.key === "variables" && variables.length > 0 && (
                  <span className="ml-1 text-[10px]" style={{ color: "var(--fg-3)" }}>({variables.length})</span>
                )}
                {tab.key === "skills" && skills.length > 0 && (
                  <span className="ml-1 text-[10px]" style={{ color: "var(--fg-3)" }}>({skills.length})</span>
                )}
                {tab.key === "tools" && tools.length > 0 && (
                  <span className="ml-1 text-[10px]" style={{ color: "var(--fg-3)" }}>({tools.length})</span>
                )}
                {tab.key === "rules" && rules.length > 0 && (
                  <span className="ml-1 text-[10px]" style={{ color: "var(--fg-3)" }}>({rules.length})</span>
                )}
                {tab.key === "task_chain" && taskChain && taskChain.tasks.length > 0 && (
                  <span className="ml-1 text-[10px]" style={{ color: "var(--fg-3)" }}>({taskChain.tasks.length})</span>
                )}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div style={{ flex: 1, overflow: "auto", padding: "24px" }}>
            {activeTab === "prompt" && (
              <PromptTab
                role={role}
                onRoleChange={setRole}
                goal={goal}
                onGoalChange={setGoal}
                systemPrompt={systemPrompt}
                onSystemPromptChange={setSystemPrompt}
                userPrompt={userPrompt}
                onUserPromptChange={setUserPrompt}
                variables={variables}
              />
            )}
            {activeTab === "task_chain" && (
              <TaskChainTab
                taskChain={taskChain}
                onTaskChainChange={setTaskChain}
                skills={skills}
              />
            )}
            {activeTab === "variables" && (
              <VariablesTab agentId={agentId} variables={variables} onReload={loadSubResources} />
            )}
            {activeTab === "skills" && (
              <SkillsTab agentId={agentId} skills={skills} onReload={loadSubResources} />
            )}
            {activeTab === "rules" && (
              <RulesTab agentId={agentId} rules={rules} onReload={loadSubResources} />
            )}
            {activeTab === "tools" && (
              <ToolsTab agentId={agentId} tools={tools} onReload={loadSubResources} />
            )}
          </div>
        </div>

        {/* ─── RIGHT PANEL (~40%) ─── */}
        {rightPanelOpen && (
          <div
            style={{
              flex: "0 0 40%",
              display: "flex",
              flexDirection: "column",
              overflow: "auto",
              padding: "20px 24px",
            }}
          >
            {/* Test Audio */}
            <CollapsibleSection title="Test Audio" defaultOpen={true}>
              <TestAudioSection agentId={agentId} />
            </CollapsibleSection>

            {/* Pipeline Config — inline editable, hover to switch models */}
            <PipelineConfig
              models={models}
              asr={asr}
              nlp={nlp}
              tts={tts}
              onAsrChange={setAsr}
              onNlpChange={setNlp}
              onTtsChange={setTts}
            />

            {/* Call Control */}
            <CollapsibleSection title="Call Control">
              <div>
                <Toggle
                  value={noiseDetection}
                  onChange={setNoiseDetection}
                  label="Noise Detection (噪音检测)"
                />
                <div className="field" style={{ padding: "10px 0", gap: 4 }}>
                  <span className="text-[13px]" style={{ color: "var(--fg-2)" }}>Interruption Mode (打断模式)</span>
                  <select
                    value={intPolicy}
                    onChange={(e) => setIntPolicy(e.target.value)}
                    className="input"
                    style={{ fontSize: 12 }}
                  >
                    <option value="always">Always</option>
                    <option value="sentence_boundary">Sentence End</option>
                    <option value="never">Never</option>
                  </select>
                </div>
                <Toggle
                  value={voiceprintEnabled}
                  onChange={setVoiceprintEnabled}
                  label="Primary Speaker Only (只识别主说话人)"
                />
                {voiceprintEnabled && (
                  <p style={{ fontSize: 11, color: "var(--fg-3)", margin: "-4px 0 4px 0", lineHeight: 1.4 }}>
                    First speaker auto-enrolled as anchor. Non-matching voices ignored to avoid noise interference.
                  </p>
                )}
                <Toggle
                  value={multiSpeaker}
                  onChange={setMultiSpeaker}
                  label="Multi-Speaker Detection (多人声检测)"
                />
                <Toggle
                  value={subtitleAlignment}
                  onChange={setSubtitleAlignment}
                  label="Subtitle Alignment (字幕对齐)"
                />
              </div>
            </CollapsibleSection>

            {/* Behavior */}
            <CollapsibleSection title="Behavior">
              <div className="space-y-3">
                <div className="field">
                  <label className="field-label">Agent Name (Chinese)</label>
                  <input value={nameZh} onChange={(e) => setNameZh(e.target.value)} className="input" style={{ fontSize: 12 }} />
                </div>
                <div className="field">
                  <label className="field-label">Agent Name (English)</label>
                  <input value={nameEn} onChange={(e) => setNameEn(e.target.value)} className="input" style={{ fontSize: 12 }} />
                </div>
                <div className="field">
                  <label className="field-label">Language</label>
                  <select value={lang} onChange={(e) => setLang(e.target.value)} className="input" style={{ fontSize: 12 }}>
                    <option value="auto">Auto</option>
                    <option value="zh">Chinese</option>
                    <option value="en">English</option>
                  </select>
                </div>
                <div className="field">
                  <label className="field-label">Status</label>
                  <select
                    value={isActive ? "active" : "inactive"}
                    onChange={(e) => setIsActive(e.target.value === "active")}
                    className="input"
                    style={{ fontSize: 12 }}
                  >
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                  </select>
                </div>
              </div>
            </CollapsibleSection>
          </div>
        )}
      </div>

      {/* Audio Init Modal */}
      {audioInitStep !== "idle" && (
        <AudioInitModal
          step={audioInitStep}
          onClose={() => setAudioInitStep("idle")}
          agentId={agentId}
          onApply={handleAudioInitApply}
        />
      )}

      {/* Conversation Test Modal */}
      {convTestOpen && (
        <ConversationTestModal
          onClose={() => setConvTestOpen(false)}
          agentId={agentId}
          defaultScenario={agent?.test_scenario || ""}
        />
      )}

      {/* Voice Test Modal */}
      {voiceTestOpen && (
        <VoiceTestModal
          onClose={() => setVoiceTestOpen(false)}
          agentId={agentId}
          defaultScenario={agent?.test_scenario || ""}
        />
      )}
    </div>
  );
}
