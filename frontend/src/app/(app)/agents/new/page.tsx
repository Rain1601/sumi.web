"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { listModels, createAgent, type ProviderModel } from "@/lib/api";

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

/* ─── Create agent page ─── */
export default function NewAgentPage() {
  const router = useRouter();
  const [models, setModels] = useState<ProviderModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Form state with defaults
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

  useEffect(() => {
    listModels()
      .then(setModels)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleCreate = async () => {
    if (!nameZh.trim() || !nameEn.trim()) {
      alert("Agent name (both Chinese and English) is required.");
      return;
    }
    setSaving(true);
    try {
      const agent = await createAgent({
        name_zh: nameZh.trim(),
        name_en: nameEn.trim(),
        description_zh: descZh.trim() || undefined,
        description_en: descEn.trim() || undefined,
        system_prompt: prompt.trim() || undefined,
        asr_model_id: asr || undefined,
        tts_model_id: tts || undefined,
        nlp_model_id: nlp || undefined,
        language: lang,
        interruption_policy: intPolicy,
      });
      router.replace(`/agents/${agent.id}`);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to create agent");
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="page">
        <div className="text-center py-24" style={{ color: "var(--fg-3)" }}>
          <p className="text-[13px]">Loading...</p>
        </div>
      </div>
    );
  }

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
            <h1 className="text-[18px] font-semibold" style={{ color: "var(--fg)" }}>
              Create new agent
            </h1>
          </div>
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
            <div className="grid grid-cols-2 gap-4">
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
            </div>
          </div>

          {/* Create button */}
          <div
            className="flex justify-end gap-3 pt-6"
            style={{ borderTop: "1px solid var(--border-1)" }}
          >
            <button
              onClick={() => router.push("/agents")}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button
              onClick={handleCreate}
              disabled={saving || !nameZh.trim() || !nameEn.trim()}
              className="btn btn-accent"
            >
              {saving ? "Creating..." : "Create agent"}
            </button>
          </div>
        </div>
      </div>

      {/* ─── RIGHT: Placeholder panel ─── */}
      <div className="detail-side">
        <div className="flex flex-col h-full gap-5">
          <div>
            <p
              className="text-[10px] font-semibold uppercase tracking-[0.1em]"
              style={{ color: "var(--fg-3)" }}
            >
              Test conversation
            </p>
            <p className="text-[11px] mt-1" style={{ color: "var(--fg-3)" }}>
              Save the agent first to test it with a live voice session
            </p>
          </div>

          <div
            className="card flex-1 flex flex-col items-center justify-center"
            style={{ padding: "28px 20px", minHeight: 200 }}
          >
            <div
              className="w-[52px] h-[52px] rounded-full flex items-center justify-center"
              style={{ background: "var(--bg-3)" }}
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="var(--fg-3)"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <rect x="9" y="2" width="6" height="12" rx="3" />
                <path d="M5 10a7 7 0 0 0 14 0" />
                <line x1="12" y1="19" x2="12" y2="22" />
              </svg>
            </div>
            <p
              className="text-[12px] mt-3"
              style={{ color: "var(--fg-3)" }}
            >
              Create the agent first
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
