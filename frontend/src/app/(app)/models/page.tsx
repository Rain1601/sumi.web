"use client";

import { useEffect, useState, useCallback } from "react";
import {
  listModels, createModel, updateModel, deleteModel, getProviderOptions,
  type ProviderModel, type ProviderOption,
} from "@/lib/api";

/* ─── Gateway dot ─── */
function GatewayDot() {
  const [ok, setOk] = useState<boolean | null>(null);
  useEffect(() => {
    fetch("/api/models/gateway").then(r => r.json()).then(d => setOk(d.has_api_key)).catch(() => setOk(false));
  }, []);
  if (ok === null) return null;
  return (
    <span className="flex items-center gap-1.5">
      <span className="w-[5px] h-[5px] rounded-full" style={{ background: ok ? "var(--green)" : "var(--amber)" }} />
      <span className="text-[11px]" style={{ color: "var(--fg-3)" }}>{ok ? "Connected" : "Not configured"}</span>
    </span>
  );
}

/* ─── Provider source badge ─── */
function SourceBadge({ providerName }: { providerName: string }) {
  const isDashscope = providerName === "dashscope";
  return (
    <span
      className="text-[9px] font-semibold px-[6px] py-[2px] rounded-[4px] uppercase tracking-[0.05em]"
      style={{
        background: isDashscope ? "rgba(255,106,0,0.12)" : "rgba(0,122,255,0.12)",
        color: isDashscope ? "#FF6A00" : "#007AFF",
      }}
    >
      {isDashscope ? "百炼" : "AIHubMix"}
    </span>
  );
}

/* ─── Model Card (compact) ─── */
function ModelCard({ model, onEdit, onDelete }: {
  model: ProviderModel; onEdit: () => void; onDelete: () => void;
}) {
  const configEntries = Object.entries(model.config);
  return (
    <div className="card animate-in" style={{ padding: "16px 18px", display: "flex", flexDirection: "column", gap: 8 }}>
      <div className="flex items-start justify-between gap-2">
        <div style={{ minWidth: 0 }}>
          <div className="flex items-center gap-2">
            <p className="text-[13px] font-medium truncate" style={{ color: "var(--fg)" }}>{model.name}</p>
            <SourceBadge providerName={model.provider_name} />
          </div>
          <p className="text-[11px] mono mt-0.5 truncate" style={{ color: "var(--fg-3)" }}>{model.model_name}</p>
        </div>
        <div className="flex items-center gap-0.5 flex-shrink-0">
          <button onClick={onEdit} className="text-[11px] px-2 py-0.5"
            style={{ color: "var(--fg-3)", background: "none", border: "none", cursor: "pointer" }}
          >Edit</button>
          <button onClick={onDelete} className="text-[11px] px-2 py-0.5"
            style={{ color: "var(--fg-3)", background: "none", border: "none", cursor: "pointer" }}
          >Del</button>
        </div>
      </div>
      {configEntries.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {configEntries.map(([k, v]) => (
            <span key={k} className="text-[10px] mono px-1.5 py-0.5 rounded"
              style={{ background: "var(--bg-3)", color: "var(--fg-3)" }}>
              {k}={String(v)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Add Dialog (inline, no dropdown for type — use tabs) ─── */
function AddDialog({ options, onClose, onCreated }: {
  options: Record<string, ProviderOption[]>; onClose: () => void; onCreated: () => void;
}) {
  const [type, setType] = useState("nlp");
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [name, setName] = useState("");
  const [config, setConfig] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const providers = options[type] || [];
  const current = providers.find(p => p.name === provider);

  useEffect(() => { if (providers.length) { setProvider(providers[0].name); setModel(""); } }, [type, options]);
  useEffect(() => { if (current?.models?.length) setModel(current.models[0]); }, [current]);
  useEffect(() => { if (current && model) setName(`${current.label.split(" (")[0]} — ${model}`); }, [current, model]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setSaving(true);
    try {
      const c: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(config)) if (v) c[k] = isNaN(Number(v)) ? v : Number(v);
      await createModel({ name, provider_type: type, provider_name: provider, model_name: model, config: c });
      onCreated(); onClose();
    } catch (err) { alert(err instanceof Error ? err.message : "Error"); }
    finally { setSaving(false); }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <form onClick={e => e.stopPropagation()} onSubmit={submit} className="modal-content space-y-5">
        <div>
          <h2 className="text-[16px] font-semibold" style={{ color: "var(--fg)" }}>Add model</h2>
          <p className="text-[12px] mt-1" style={{ color: "var(--fg-3)" }}>All models route through AIHubMix</p>
        </div>
        <div className="flex gap-[6px]">
          {["nlp", "asr", "tts"].map(t => (
            <button key={t} type="button" onClick={() => setType(t)}
              className="btn" style={{
                padding: "5px 14px", fontSize: 11, letterSpacing: "0.04em",
                background: type === t ? "var(--fg)" : "var(--bg-3)",
                color: type === t ? "var(--bg-0)" : "var(--fg-3)",
              }}>{t.toUpperCase()}</button>
          ))}
        </div>
        <div className="field">
          <label className="field-label">Provider</label>
          <select value={provider} onChange={e => setProvider(e.target.value)} className="input">
            {providers.map(p => <option key={p.name} value={p.name}>{p.label}</option>)}
          </select>
        </div>
        <div className="field">
          <label className="field-label">Model</label>
          <select value={model} onChange={e => setModel(e.target.value)} className="input">
            {(current?.models || []).map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
        <div className="field">
          <label className="field-label">Display name</label>
          <input value={name} onChange={e => setName(e.target.value)} required className="input" />
        </div>
        {current?.config_schema && Object.keys(current.config_schema).length > 0 && (
          <div className="space-y-2">
            <label className="field-label">Config</label>
            {Object.entries(current.config_schema).map(([k, tp]) => (
              <div key={k} className="flex items-center gap-3">
                <span className="text-[11px] w-20 mono" style={{ color: "var(--fg-3)" }}>{k}</span>
                {k === "voice" && current.voices ? (
                  <select value={config[k]||""} onChange={e => setConfig({...config,[k]:e.target.value})} className="input flex-1">
                    <option value="">default</option>
                    {current.voices.map(v => <option key={v} value={v}>{v}</option>)}
                  </select>
                ) : (
                  <input type={tp==="number"?"number":"text"} step="0.1"
                    value={config[k]||""} onChange={e => setConfig({...config,[k]:e.target.value})}
                    placeholder={k==="temperature"?"0.7":k==="max_tokens"?"4096":k==="language"?"zh":""}
                    className="input flex-1" />
                )}
              </div>
            ))}
          </div>
        )}
        <div className="flex justify-end gap-2 pt-3">
          <button type="button" onClick={onClose} className="btn btn-secondary">Cancel</button>
          <button type="submit" disabled={saving} className="btn btn-primary">{saving ? "..." : "Create"}</button>
        </div>
      </form>
    </div>
  );
}

/* ─── Edit Dialog ─── */
function EditDialog({ model, onClose, onSaved }: {
  model: ProviderModel; onClose: () => void; onSaved: () => void;
}) {
  const [name, setName] = useState(model.name);
  const [config, setConfig] = useState(JSON.stringify(model.config, null, 2));
  const [saving, setSaving] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setSaving(true);
    try {
      let parsed = {};
      try { parsed = JSON.parse(config); } catch { alert("Invalid JSON"); setSaving(false); return; }
      await updateModel(model.id, { name, config: parsed });
      onSaved(); onClose();
    } catch (err) { alert(err instanceof Error ? err.message : "Error"); }
    finally { setSaving(false); }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <form onClick={e => e.stopPropagation()} onSubmit={submit} className="modal-content space-y-5">
        <div>
          <h2 className="text-[16px] font-semibold" style={{ color: "var(--fg)" }}>Edit model</h2>
          <p className="text-[12px] mt-1 mono" style={{ color: "var(--fg-3)" }}>{model.provider_name} / {model.model_name}</p>
        </div>
        <div className="field">
          <label className="field-label">Display name</label>
          <input value={name} onChange={e => setName(e.target.value)} required className="input" />
        </div>
        <div className="field">
          <label className="field-label">Config (JSON)</label>
          <textarea value={config} onChange={e => setConfig(e.target.value)} className="input mono" rows={5} style={{ fontSize: 12 }} />
        </div>
        <div className="flex justify-end gap-2 pt-3">
          <button type="button" onClick={onClose} className="btn btn-secondary">Cancel</button>
          <button type="submit" disabled={saving} className="btn btn-primary">{saving ? "..." : "Save"}</button>
        </div>
      </form>
    </div>
  );
}

/* ─── Main ─── */
export default function ModelsPage() {
  const [models, setModels] = useState<ProviderModel[]>([]);
  const [options, setOptions] = useState<Record<string, ProviderOption[]>>({});
  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState<ProviderModel | null>(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<string>("all"); // "all" | "nlp" | "asr" | "tts"

  const load = useCallback(async () => {
    const [m, o] = await Promise.all([listModels(), getProviderOptions()]);
    setModels(m); setOptions(o);
  }, []);
  useEffect(() => { load(); }, [load]);

  const q = search.toLowerCase();
  const filtered = models.filter(m => {
    if (filter !== "all" && m.provider_type !== filter) return false;
    if (q && !m.name.toLowerCase().includes(q) && !m.model_name.includes(q)) return false;
    return true;
  });

  const nlp = filtered.filter(m => m.provider_type === "nlp");
  const asr = filtered.filter(m => m.provider_type === "asr");
  const tts = filtered.filter(m => m.provider_type === "tts");

  const handleDelete = (m: ProviderModel) => {
    if (confirm(`Delete "${m.name}"?`)) deleteModel(m.id).then(load);
  };

  const counts = {
    all: models.length,
    nlp: models.filter(m => m.provider_type === "nlp").length,
    asr: models.filter(m => m.provider_type === "asr").length,
    tts: models.filter(m => m.provider_type === "tts").length,
  };

  const TAGS: { key: string; label: string; color?: string }[] = [
    { key: "all", label: "All" },
    { key: "nlp", label: "NLP", color: "var(--nlp)" },
    { key: "asr", label: "ASR", color: "var(--asr)" },
    { key: "tts", label: "TTS", color: "var(--tts)" },
  ];

  const Section = ({ label, type, items }: { label: string; type: string; items: ProviderModel[] }) => {
    if (items.length === 0) return null;
    return (
      <div className="animate-in" style={{ animationDelay: type === "nlp" ? "0s" : type === "asr" ? "0.04s" : "0.08s" }}>
        <div className="flex items-center gap-2 mb-3">
          <span className={`badge badge-${type}`}>{type.toUpperCase()}</span>
          <span className="text-[13px] font-medium" style={{ color: "var(--fg-2)" }}>{label}</span>
          <span className="text-[11px]" style={{ color: "var(--fg-3)" }}>{items.length}</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 10 }}>
          {items.map(m => (
            <ModelCard key={m.id} model={m} onEdit={() => setEditing(m)} onDelete={() => handleDelete(m)} />
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="page">
      {/* Header */}
      <div className="page-header animate-in">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="page-title">Models</h1>
            <GatewayDot />
          </div>
          <p className="page-desc">ASR, TTS and NLP model instances via AIHubMix</p>
        </div>
        <button onClick={() => setShowAdd(true)} className="btn btn-primary">Add model</button>
      </div>

      {/* Search + Filter Tags */}
      <div className="flex items-center gap-4 animate-in" style={{ animationDelay: "0.02s", marginBottom: 28 }}>
        <input
          value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Search models..."
          className="input"
          style={{ background: "var(--bg-1)", maxWidth: 280, flexShrink: 0 }}
        />
        <div className="flex items-center gap-[6px]">
          {TAGS.map(t => {
            const active = filter === t.key;
            const count = counts[t.key as keyof typeof counts];
            return (
              <button
                key={t.key}
                onClick={() => setFilter(t.key)}
                style={{
                  padding: "5px 14px",
                  borderRadius: "var(--radius-full)",
                  fontSize: 12,
                  fontWeight: 500,
                  border: active ? `1.5px solid ${t.color || "var(--fg-3)"}` : "1.5px solid transparent",
                  background: active ? (t.color ? `color-mix(in srgb, ${t.color} 12%, transparent)` : "var(--bg-3)") : "var(--bg-2)",
                  color: active ? (t.color || "var(--fg)") : "var(--fg-3)",
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                }}
              >
                {t.label}
                <span style={{ marginLeft: 4, opacity: 0.5 }}>{count}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Sections */}
      <div style={{ display: "flex", flexDirection: "column", gap: 36 }}>
        {nlp.length > 0 && <Section label="Language Models" type="nlp" items={nlp} />}
        {asr.length > 0 && <Section label="Speech Recognition" type="asr" items={asr} />}
        {tts.length > 0 && <Section label="Text-to-Speech" type="tts" items={tts} />}
        {filtered.length === 0 && (
          <div className="text-center py-20 animate-in" style={{ color: "var(--fg-3)" }}>
            <p className="text-[13px]">{q ? `No models matching "${search}"` : "No models in this category"}</p>
          </div>
        )}
      </div>

      {showAdd && <AddDialog options={options} onClose={() => setShowAdd(false)} onCreated={load} />}
      {editing && <EditDialog model={editing} onClose={() => setEditing(null)} onSaved={load} />}
    </div>
  );
}
