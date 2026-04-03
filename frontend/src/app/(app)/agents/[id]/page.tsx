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
  type Agent,
  type ProviderModel,
  type AgentVariable,
  type AgentSkill,
  type AgentTool,
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
   Model Picker (compact)
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
          audio={true}
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
  systemPrompt,
  onSystemPromptChange,
  userPrompt,
  onUserPromptChange,
  variables,
}: {
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
                <span className="mono text-[11px]" style={{ color: "var(--fg-3)" }}>{tool.tool_id}</span>
                <span className="badge badge-muted">{tool.type}</span>
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
                  <div className="field">
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
   MAIN EDITOR PAGE
   ============================================================ */
type EditorTab = "prompt" | "variables" | "skills" | "tools";

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
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [activeTab, setActiveTab] = useState<EditorTab>("prompt");
  const [rightPanelOpen, setRightPanelOpen] = useState(true);

  /* ─── Form state ─── */
  const [nameZh, setNameZh] = useState("");
  const [nameEn, setNameEn] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [userPrompt, setUserPrompt] = useState("");
  const [openingLine, setOpeningLine] = useState("");
  const [asr, setAsr] = useState<string | null>(null);
  const [tts, setTts] = useState<string | null>(null);
  const [nlp, setNlp] = useState<string | null>(null);
  const [lang, setLang] = useState("auto");
  const [intPolicy, setIntPolicy] = useState("always");
  const [isActive, setIsActive] = useState(true);
  const [voiceprintEnabled, setVoiceprintEnabled] = useState(false);
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
      setUserPrompt(agentData.user_prompt || "");
      setOpeningLine(agentData.opening_line || "");
      setAsr(agentData.asr_model_id);
      setTts(agentData.tts_model_id);
      setNlp(agentData.nlp_model_id);
      setLang(agentData.language);
      setIntPolicy(agentData.interruption_policy);
      setIsActive(agentData.is_active);
      setVoiceprintEnabled(agentData.voiceprint_enabled);
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
      const [vars, sk, tl] = await Promise.all([
        listAgentVariables(agentId).catch(() => []),
        listAgentSkills(agentId).catch(() => []),
        listAgentTools(agentId).catch(() => []),
      ]);
      setVariables(vars);
      setSkills(sk);
      setTools(tl);
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
    if (!confirm("Publish this agent? It will become available for production use.")) return;
    setPublishing(true);
    try {
      await publishAgent(agentId);
      await loadAgent();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to publish");
    } finally {
      setPublishing(false);
    }
  };

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
    { key: "variables", label: "Variables" },
    { key: "skills", label: "Skills" },
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
          background: "var(--bg-1)",
          backdropFilter: "var(--glass-blur-light)",
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

          <span className="mono text-[11px]" style={{ color: "var(--fg-3)" }}>
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

          <span className="text-[11px]" style={{ color: "var(--fg-3)" }}>
            v{agent.version ?? 1}
          </span>

          <div style={{ flex: 1 }} />

          {/* Mode buttons */}
          <button className="btn btn-secondary" style={{ fontSize: 12, padding: "5px 14px" }}>
            Create
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
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div style={{ flex: 1, overflow: "auto", padding: "24px" }}>
            {activeTab === "prompt" && (
              <PromptTab
                systemPrompt={systemPrompt}
                onSystemPromptChange={setSystemPrompt}
                userPrompt={userPrompt}
                onUserPromptChange={setUserPrompt}
                variables={variables}
              />
            )}
            {activeTab === "variables" && (
              <VariablesTab agentId={agentId} variables={variables} onReload={loadSubResources} />
            )}
            {activeTab === "skills" && (
              <SkillsTab agentId={agentId} skills={skills} onReload={loadSubResources} />
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

            {/* ASR Config */}
            <CollapsibleSection title="ASR Config">
              <ModelPicker label="Speech Recognition" type="asr" models={models} value={asr} onChange={setAsr} />
            </CollapsibleSection>

            {/* NLP Config */}
            <CollapsibleSection title="NLP Config">
              <ModelPicker label="Language Model" type="nlp" models={models} value={nlp} onChange={setNlp} />
            </CollapsibleSection>

            {/* TTS Config */}
            <CollapsibleSection title="TTS Config">
              <ModelPicker label="Text-to-Speech" type="tts" models={models} value={tts} onChange={setTts} />
            </CollapsibleSection>

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
                  label="Voiceprint (声纹识别)"
                />
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
    </div>
  );
}
