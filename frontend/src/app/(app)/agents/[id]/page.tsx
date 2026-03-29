"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useVoiceAssistant,
  BarVisualizer,
} from "@livekit/components-react";
import "@livekit/components-styles";

import {
  listAgents,
  listModels,
  updateAgent,
  deleteAgent,
  type Agent,
  type ProviderModel,
} from "@/lib/api";
import { useVoiceSession } from "@/hooks/useVoiceSession";
import { useAuthStore } from "@/stores/auth";
import { LiveTranscriptPanel } from "../../../(app)/conversation/components/TranscriptPanel";

/* ─── Model Picker ─── */
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
    <div className="field">
      <div className="flex items-center gap-2">
        <span className={`badge badge-${type}`}>{type.toUpperCase()}</span>
        <label className="field-label">{label}</label>
      </div>
      <select
        value={value || ""}
        onChange={(e) => onChange(e.target.value || null)}
        className="input"
      >
        <option value="">Not selected</option>
        {filtered.map((m) => (
          <option key={m.id} value={m.id}>
            {m.name} ({m.model_name})
          </option>
        ))}
      </select>
      {!filtered.length && (
        <p className="text-[11px]" style={{ color: "var(--amber)" }}>
          No {type.toUpperCase()} models available
        </p>
      )}
    </div>
  );
}

/* ─── Active voice session inside LiveKit room ─── */
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
        style={{ width: 160, height: 80 }}
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
        <span className="text-[13px] font-medium" style={{ color: stateColor }}>
          {stateLabel}
        </span>
      </div>
    </div>
  );
}

/* ─── Test conversation panel (right side) ─── */
function TestPanel({ agentId }: { agentId: string }) {
  const { serverUrl, token, isConnecting, error, connect, disconnect } =
    useVoiceSession();
  const { token: authToken } = useAuthStore();

  const handleConnect = useCallback(async () => {
    await connect(agentId, authToken || "dev_user");
  }, [agentId, authToken, connect]);

  return (
    <div className="flex flex-col h-full gap-5">
      <div>
        <p
          className="text-[10px] font-semibold uppercase tracking-[0.1em]"
          style={{ color: "var(--fg-3)" }}
        >
          Test conversation
        </p>
        <p className="text-[11px] mt-1" style={{ color: "var(--fg-3)" }}>
          Try this agent with a live voice session
        </p>
      </div>

      {/* Orb / connect area */}
      <div
        className="card flex flex-col items-center justify-center"
        style={{ padding: "28px 20px" }}
      >
        {!token ? (
          <div className="flex flex-col items-center gap-4">
            <div className="relative" style={{ width: 100, height: 100 }}>
              <div
                className="pulse-ring"
                style={{ width: 100, height: 100, animationDelay: "0s" }}
              />
              <div
                className="pulse-ring"
                style={{ width: 100, height: 100, animationDelay: "0.8s" }}
              />
              <button
                onClick={handleConnect}
                disabled={isConnecting}
                className="absolute inset-0 m-auto w-[52px] h-[52px] rounded-full flex items-center justify-center z-10 transition-all duration-200"
                style={{
                  background: "var(--accent)",
                  boxShadow: "0 0 24px var(--accent-glow)",
                  cursor: isConnecting ? "wait" : "pointer",
                  opacity: isConnecting ? 0.6 : 1,
                }}
              >
                {isConnecting ? (
                  <span
                    className="text-[11px] font-medium"
                    style={{ color: "white" }}
                  >
                    ...
                  </span>
                ) : (
                  <svg
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="white"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <rect x="9" y="2" width="6" height="12" rx="3" />
                    <path d="M5 10a7 7 0 0 0 14 0" />
                    <line x1="12" y1="19" x2="12" y2="22" />
                  </svg>
                )}
              </button>
            </div>
            <p className="text-[12px]" style={{ color: "var(--fg-3)" }}>
              {isConnecting ? "Connecting..." : "Tap to start"}
            </p>
            {error && (
              <p
                className="text-[11px] px-3 py-1.5 rounded-lg"
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
                style={{ fontSize: 12, padding: "5px 16px" }}
              >
                End session
              </button>
            </div>

            {/* Live transcript — inside LiveKitRoom so it receives transcription events */}
            <div className="flex-1 flex flex-col min-h-0 mt-4">
              <p
                className="text-[10px] font-semibold uppercase tracking-[0.1em] mb-2"
                style={{ color: "var(--fg-3)" }}
              >
                Transcript
              </p>
              <div className="card flex-1 overflow-y-auto" style={{ padding: "14px 16px", minHeight: 120 }}>
                <LiveTranscriptPanel />
              </div>
            </div>
          </LiveKitRoom>
        )}
      </div>
    </div>
  );
}

/* ─── Main detail page ─── */
export default function AgentDetailPage() {
  const router = useRouter();
  const params = useParams();
  const agentId = params.id as string;

  const [agent, setAgent] = useState<Agent | null>(null);
  const [models, setModels] = useState<ProviderModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Form state
  const [nameZh, setNameZh] = useState("");
  const [nameEn, setNameEn] = useState("");
  const [descZh, setDescZh] = useState("");
  const [descEn, setDescEn] = useState("");
  const [prompt, setPrompt] = useState("");
  const [asr, setAsr] = useState<string | null>(null);
  const [tts, setTts] = useState<string | null>(null);
  const [nlp, setNlp] = useState<string | null>(null);
  const [lang, setLang] = useState("auto");
  const [intPolicy, setIntPolicy] = useState("always");
  const [isActive, setIsActive] = useState(true);

  const load = useCallback(async () => {
    try {
      const [agents, modelList] = await Promise.all([
        listAgents(),
        listModels(),
      ]);
      setModels(modelList);
      const found = agents.find((a) => a.id === agentId);
      if (!found) {
        router.replace("/agents");
        return;
      }
      setAgent(found);
      setNameZh(found.name_zh);
      setNameEn(found.name_en);
      setDescZh(found.description_zh || "");
      setDescEn(found.description_en || "");
      setPrompt(found.system_prompt);
      setAsr(found.asr_model_id);
      setTts(found.tts_model_id);
      setNlp(found.nlp_model_id);
      setLang(found.language);
      setIntPolicy(found.interruption_policy);
      setIsActive(found.is_active);
    } catch (err) {
      console.error("Failed to load agent:", err);
      router.replace("/agents");
    } finally {
      setLoading(false);
    }
  }, [agentId, router]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateAgent(agentId, {
        name_zh: nameZh,
        name_en: nameEn,
        description_zh: descZh || null,
        description_en: descEn || null,
        system_prompt: prompt,
        asr_model_id: asr,
        tts_model_id: tts,
        nlp_model_id: nlp,
        language: lang,
        interruption_policy: intPolicy,
        is_active: isActive,
      });
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Delete agent "${nameEn || nameZh}"? This cannot be undone.`)) return;
    setDeleting(true);
    try {
      await deleteAgent(agentId);
      router.replace("/agents");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete");
      setDeleting(false);
    }
  };

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

  return (
    <div className="detail-layout">
      {/* ─── LEFT: Configuration form ─── */}
      <div className="detail-main">
        {/* Top bar */}
        <div className="flex items-center justify-between mb-8 animate-in">
          <div className="flex items-center gap-3">
            <button
              onClick={() => router.push("/agents")}
              className="btn btn-ghost"
              style={{ padding: "6px 10px" }}
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M19 12H5" />
                <polyline points="12 19 5 12 12 5" />
              </svg>
            </button>
            <div>
              <h1 className="text-[18px] font-semibold" style={{ color: "var(--fg)" }}>
                {agent.name_zh}
                <span className="ml-2 text-[14px] font-normal" style={{ color: "var(--fg-3)" }}>
                  / {agent.name_en}
                </span>
              </h1>
            </div>
          </div>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="btn btn-danger"
            style={{ fontSize: 12 }}
          >
            {deleting ? "Deleting..." : "Delete agent"}
          </button>
        </div>

        {/* Form */}
        <div className="space-y-6 animate-in" style={{ animationDelay: "0.05s" }}>
          {/* Names */}
          <div>
            <p
              className="text-[10px] font-semibold uppercase tracking-[0.1em] mb-4"
              style={{ color: "var(--fg-3)" }}
            >
              Identity
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div className="field">
                <label className="field-label">Name (Chinese)</label>
                <input
                  value={nameZh}
                  onChange={(e) => setNameZh(e.target.value)}
                  className="input"
                  placeholder="助手名称"
                  required
                />
              </div>
              <div className="field">
                <label className="field-label">Name (English)</label>
                <input
                  value={nameEn}
                  onChange={(e) => setNameEn(e.target.value)}
                  className="input"
                  placeholder="Agent Name"
                  required
                />
              </div>
            </div>
          </div>

          {/* Descriptions */}
          <div className="grid grid-cols-2 gap-4">
            <div className="field">
              <label className="field-label">Description (Chinese)</label>
              <input
                value={descZh}
                onChange={(e) => setDescZh(e.target.value)}
                className="input"
                placeholder="简要描述..."
              />
            </div>
            <div className="field">
              <label className="field-label">Description (English)</label>
              <input
                value={descEn}
                onChange={(e) => setDescEn(e.target.value)}
                className="input"
                placeholder="Brief description..."
              />
            </div>
          </div>

          {/* System prompt */}
          <div className="field">
            <label className="field-label">System prompt</label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={6}
              className="input mono"
              placeholder="You are a helpful voice assistant..."
              style={{ fontSize: 12, lineHeight: 1.6 }}
            />
          </div>

          {/* Models section */}
          <div
            className="pt-6 space-y-5"
            style={{ borderTop: "1px solid var(--border-1)" }}
          >
            <p
              className="text-[10px] font-semibold uppercase tracking-[0.1em]"
              style={{ color: "var(--fg-3)" }}
            >
              Models
            </p>
            <ModelPicker
              label="Speech Recognition"
              type="asr"
              models={models}
              value={asr}
              onChange={setAsr}
            />
            <ModelPicker
              label="Text-to-Speech"
              type="tts"
              models={models}
              value={tts}
              onChange={setTts}
            />
            <ModelPicker
              label="Language Model"
              type="nlp"
              models={models}
              value={nlp}
              onChange={setNlp}
            />
          </div>

          {/* Behavior */}
          <div
            className="pt-6 space-y-4"
            style={{ borderTop: "1px solid var(--border-1)" }}
          >
            <p
              className="text-[10px] font-semibold uppercase tracking-[0.1em]"
              style={{ color: "var(--fg-3)" }}
            >
              Behavior
            </p>
            <div className="grid grid-cols-3 gap-4">
              <div className="field">
                <label className="field-label">Language</label>
                <select
                  value={lang}
                  onChange={(e) => setLang(e.target.value)}
                  className="input"
                >
                  <option value="auto">Auto</option>
                  <option value="zh">Chinese</option>
                  <option value="en">English</option>
                </select>
              </div>
              <div className="field">
                <label className="field-label">Interruption</label>
                <select
                  value={intPolicy}
                  onChange={(e) => setIntPolicy(e.target.value)}
                  className="input"
                >
                  <option value="always">Always</option>
                  <option value="sentence_boundary">Sentence end</option>
                  <option value="never">Never</option>
                </select>
              </div>
              <div className="field">
                <label className="field-label">Status</label>
                <select
                  value={isActive ? "active" : "inactive"}
                  onChange={(e) => setIsActive(e.target.value === "active")}
                  className="input"
                >
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                </select>
              </div>
            </div>
          </div>

          {/* Save button */}
          <div
            className="flex justify-end pt-6"
            style={{ borderTop: "1px solid var(--border-1)" }}
          >
            <button
              onClick={handleSave}
              disabled={saving}
              className="btn btn-primary"
            >
              {saving ? "Saving..." : "Save changes"}
            </button>
          </div>
        </div>
      </div>

      {/* ─── RIGHT: Test conversation ─── */}
      <div className="detail-side">
        <TestPanel agentId={agentId} />
      </div>
    </div>
  );
}
