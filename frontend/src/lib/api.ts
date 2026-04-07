const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

// ─── Types ──────────────────────────────────────────

export interface ProviderModel {
  id: string;
  name: string;
  provider_type: "asr" | "tts" | "nlp";
  provider_name: string;
  model_name: string;
  config: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProviderOption {
  name: string;
  label: string;
  models: string[];
  config_schema: Record<string, string>;
  voices?: string[];
}

export interface Agent {
  id: string;
  name_zh: string;
  name_en: string;
  description_zh: string | null;
  description_en: string | null;
  system_prompt: string;
  goal: string | null;
  opening_line: string | null;
  test_scenario: string | null;
  user_prompt: string | null;
  version: number;
  status: string; // "draft" | "published"
  folder_id: string | null;
  call_control: Record<string, unknown> | null;
  cloned_from: string | null;
  asr_model_id: string | null;
  tts_model_id: string | null;
  nlp_model_id: string | null;
  asr_model_name: string | null;
  tts_model_name: string | null;
  nlp_model_name: string | null;
  vad_mode: string;
  vad_config: Record<string, unknown> | null;
  tools: string[];
  interruption_policy: string;
  voiceprint_enabled: boolean;
  language: string;
  is_active: boolean;
  // Task Chain architecture fields
  role: string | null;
  task_chain: TaskChainConfig | null;
  rules: RuleInline[] | null;
  optimization: Record<string, unknown> | null;
  created_at?: string;
  updated_at?: string;
}

export interface TaskDef {
  id: string;
  name: string;
  skill_code?: string;
  goal: string;
  success_condition?: string;
  max_turns?: number;
  on_success?: string;
  on_failure?: string;
  on_timeout?: string;
  terminal?: boolean;
}

export interface TaskChainConfig {
  tasks: TaskDef[];
  entry_task: string;
}

export interface RuleInline {
  rule_type: "forbidden" | "required" | "format";
  content: string;
  priority?: number;
  is_active?: boolean;
}

export interface AgentRule {
  id: string;
  agent_id: string;
  rule_type: "forbidden" | "required" | "format";
  content: string;
  priority: number;
  is_active: boolean;
}

export interface AgentVariable {
  id: string;
  agent_id: string;
  name: string;
  code: string;
  type: string; // "string" | "number" | "boolean" | "enum"
  default_value: string;
  description: string;
  created_at?: string;
  updated_at?: string;
}

export interface AgentSkill {
  id: string;
  agent_id: string;
  name: string;
  code: string;
  description: string;
  content: string;
  skill_type?: "free" | "qa" | "logic_tree";
  qa_pairs?: Record<string, unknown>;
  logic_tree?: Record<string, unknown>;
  entry_prompt?: string;
  exit_conditions?: Record<string, unknown>;
  sort_order: number;
  created_at?: string;
  updated_at?: string;
}

export interface AgentTool {
  id: string;
  agent_id: string;
  name: string;
  tool_id: string;
  type: string; // "sync" | "async"
  description: string;
  parameters_schema: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}

interface CreateRoomResponse {
  room_name: string;
  token: string;
  livekit_url: string;
}

// ─── Fetch helper ───────────────────────────────────

import { useAuthStore } from "@/stores/auth";

function getAuthToken(): string | null {
  // Read token from Zustand auth store (non-reactive, direct state access)
  try {
    return useAuthStore.getState().token;
  } catch {
    return null;
  }
}

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...headers,
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API error: ${res.status} ${text || res.statusText}`);
  }
  return res.json();
}

// ─── Rooms ──────────────────────────────────────────

export async function createRoom(agentId: string, token: string): Promise<CreateRoomResponse> {
  return fetchAPI("/api/rooms/create", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ agent_id: agentId }),
  });
}

export interface WorkerStatus {
  available: boolean;
  agent_count: number;
  message: string;
}

export async function checkWorkerStatus(): Promise<WorkerStatus> {
  return fetchAPI("/api/rooms/worker-status");
}

export async function restartWorker(): Promise<{ ok: boolean; message: string }> {
  return fetchAPI("/api/rooms/worker-restart", { method: "POST" });
}

// ─── Models ─────────────────────────────────────────

export async function listModels(providerType?: string): Promise<ProviderModel[]> {
  const params = providerType ? `?provider_type=${providerType}` : "";
  return fetchAPI(`/api/models/${params}`);
}

export async function getProviderOptions(): Promise<Record<string, ProviderOption[]>> {
  return fetchAPI("/api/models/options");
}

export async function createModel(data: {
  name: string;
  provider_type: string;
  provider_name: string;
  model_name?: string;
  config?: Record<string, unknown>;
}): Promise<ProviderModel> {
  return fetchAPI("/api/models/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateModel(id: string, data: Partial<{
  name: string;
  api_key: string;
  model_name: string;
  config: Record<string, unknown>;
  is_active: boolean;
}>): Promise<ProviderModel> {
  return fetchAPI(`/api/models/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteModel(id: string): Promise<void> {
  return fetchAPI(`/api/models/${id}`, { method: "DELETE" });
}

// ─── Agents ─────────────────────────────────────────

export async function listAgents(): Promise<Agent[]> {
  return fetchAPI("/api/agents/");
}

export async function getAgent(id: string): Promise<Agent> {
  return fetchAPI(`/api/agents/${id}`);
}

export async function createAgent(data: {
  name_zh: string;
  name_en: string;
  description_zh?: string;
  description_en?: string;
  system_prompt?: string;
  asr_model_id?: string;
  tts_model_id?: string;
  nlp_model_id?: string;
  tools?: string[];
  language?: string;
  interruption_policy?: string;
}): Promise<Agent> {
  return fetchAPI("/api/agents/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAgent(id: string, data: Partial<Agent>): Promise<Agent> {
  return fetchAPI(`/api/agents/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteAgent(id: string): Promise<void> {
  return fetchAPI(`/api/agents/${id}`, { method: "DELETE" });
}

export async function duplicateAgent(id: string): Promise<Agent> {
  return fetchAPI(`/api/agents/${id}/duplicate`, { method: "POST" });
}

export async function publishAgent(id: string, changeSummary?: string): Promise<Agent> {
  return fetchAPI(`/api/agents/${id}/publish`, {
    method: "POST",
    body: JSON.stringify({ change_summary: changeSummary || null }),
  });
}

// ─── Agent Versions ────────────────────────────────

export interface AgentVersionSummary {
  id: string;
  agent_id: string;
  version: number;
  change_summary: string | null;
  published_by: string | null;
  created_at: string | null;
}

export interface AgentVersionDetail extends AgentVersionSummary {
  snapshot: Record<string, unknown>;
}

export async function listAgentVersions(agentId: string): Promise<AgentVersionSummary[]> {
  return fetchAPI(`/api/agents/${agentId}/versions`);
}

export async function getAgentVersion(agentId: string, versionId: string): Promise<AgentVersionDetail> {
  return fetchAPI(`/api/agents/${agentId}/versions/${versionId}`);
}

export async function rollbackAgentVersion(agentId: string, versionId: string): Promise<Agent> {
  return fetchAPI(`/api/agents/${agentId}/versions/${versionId}/rollback`, { method: "POST" });
}

// ─── Agent Variables ────────────────────────────────

export async function listAgentVariables(agentId: string): Promise<AgentVariable[]> {
  return fetchAPI(`/api/agents/${agentId}/variables`);
}

export async function createAgentVariable(agentId: string, data: Omit<AgentVariable, "id" | "agent_id" | "created_at" | "updated_at">): Promise<AgentVariable> {
  return fetchAPI(`/api/agents/${agentId}/variables`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAgentVariable(agentId: string, varId: string, data: Partial<AgentVariable>): Promise<AgentVariable> {
  return fetchAPI(`/api/agents/${agentId}/variables/${varId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteAgentVariable(agentId: string, varId: string): Promise<void> {
  return fetchAPI(`/api/agents/${agentId}/variables/${varId}`, { method: "DELETE" });
}

// ─── Agent Skills ───────────────────────────────────

export async function listAgentSkills(agentId: string): Promise<AgentSkill[]> {
  return fetchAPI(`/api/agents/${agentId}/skills`);
}

export async function createAgentSkill(agentId: string, data: Omit<AgentSkill, "id" | "agent_id" | "created_at" | "updated_at">): Promise<AgentSkill> {
  return fetchAPI(`/api/agents/${agentId}/skills`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAgentSkill(agentId: string, skillId: string, data: Partial<AgentSkill>): Promise<AgentSkill> {
  return fetchAPI(`/api/agents/${agentId}/skills/${skillId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteAgentSkill(agentId: string, skillId: string): Promise<void> {
  return fetchAPI(`/api/agents/${agentId}/skills/${skillId}`, { method: "DELETE" });
}

// ─── Agent Tools ────────────────────────────────────

export async function listAgentTools(agentId: string): Promise<AgentTool[]> {
  return fetchAPI(`/api/agents/${agentId}/tools`);
}

export async function createAgentTool(agentId: string, data: Omit<AgentTool, "id" | "agent_id" | "created_at" | "updated_at">): Promise<AgentTool> {
  return fetchAPI(`/api/agents/${agentId}/tools`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAgentTool(agentId: string, toolId: string, data: Partial<AgentTool>): Promise<AgentTool> {
  return fetchAPI(`/api/agents/${agentId}/tools/${toolId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteAgentTool(agentId: string, toolId: string): Promise<void> {
  return fetchAPI(`/api/agents/${agentId}/tools/${toolId}`, { method: "DELETE" });
}

export interface ToolRunResult {
  success: boolean;
  output: string;
  data: Record<string, unknown>;
  duration_ms: number;
}

export async function runTool(toolId: string, params: Record<string, unknown> = {}): Promise<ToolRunResult> {
  return fetchAPI(`/api/agents/run/${toolId}`, {
    method: "POST",
    body: JSON.stringify({ params }),
  });
}

// ─── Agent Rules ───────────────────────────────────

export async function listAgentRules(agentId: string): Promise<AgentRule[]> {
  return fetchAPI(`/api/agents/${agentId}/rules`);
}

export async function createAgentRule(agentId: string, data: { rule_type: string; content: string; priority?: number }): Promise<AgentRule> {
  return fetchAPI(`/api/agents/${agentId}/rules`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAgentRule(agentId: string, ruleId: string, data: Partial<AgentRule>): Promise<AgentRule> {
  return fetchAPI(`/api/agents/${agentId}/rules/${ruleId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteAgentRule(agentId: string, ruleId: string): Promise<void> {
  return fetchAPI(`/api/agents/${agentId}/rules/${ruleId}`, { method: "DELETE" });
}

// ─── Annotations ───────────────────────────────────

export interface Annotation {
  id: string;
  conversation_id: string;
  message_id: string | null;
  turn_index: number | null;
  annotation_type: string;
  rating: number | null;
  labels: string[] | null;
  corrected_text: string | null;
  expected_response: string | null;
  notes: string | null;
  annotator: string;
}

export async function listAnnotations(conversationId?: string): Promise<Annotation[]> {
  const params = conversationId ? `?conversation_id=${conversationId}` : "";
  return fetchAPI(`/api/annotations/${params}`);
}

export async function createAnnotation(data: Omit<Annotation, "id">): Promise<Annotation> {
  return fetchAPI("/api/annotations/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAnnotation(id: string, data: Partial<Annotation>): Promise<Annotation> {
  return fetchAPI(`/api/annotations/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteAnnotation(id: string): Promise<void> {
  return fetchAPI(`/api/annotations/${id}`, { method: "DELETE" });
}

// ─── Agent Audio Init (SSE) ────────────────────────

export interface AudioInitEvent {
  type: "progress" | "transcript" | "result" | "done" | "error";
  data: Record<string, unknown>;
}

export async function initAgentFromAudio(
  agentId: string,
  file: File,
  onEvent: (event: AudioInitEvent) => void,
): Promise<void> {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${API_BASE}/api/agents/${agentId}/init-from-audio`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Upload failed: ${res.status} ${text || res.statusText}`);
  }

  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Parse SSE events from buffer
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      if (!part.trim()) continue;
      let eventType = "message";
      let data = "";
      for (const line of part.split("\n")) {
        if (line.startsWith("event: ")) eventType = line.slice(7).trim();
        else if (line.startsWith("data: ")) data = line.slice(6);
      }
      if (data) {
        try {
          onEvent({ type: eventType as AudioInitEvent["type"], data: JSON.parse(data) });
        } catch {
          // ignore parse errors
        }
      }
    }
  }
}

// ─── Conversation Test ────────────────────────────────────

export interface ConversationTestEvent {
  type: "config" | "turn" | "progress" | "evaluation" | "done" | "error";
  data: Record<string, unknown>;
}

export interface ConversationTestConfig {
  scenario: string;
  persona?: string;
  max_turns?: number;
  evaluate?: boolean;
  model?: string;
}

export async function runConversationTest(
  agentId: string,
  config: ConversationTestConfig,
  onEvent: (event: ConversationTestEvent) => void,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/agents/${agentId}/conversation-test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Test failed: ${res.status} ${text || res.statusText}`);
  }

  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      if (!part.trim()) continue;
      let eventType = "message";
      let data = "";
      for (const line of part.split("\n")) {
        if (line.startsWith("event: ")) eventType = line.slice(7).trim();
        else if (line.startsWith("data: ")) data = line.slice(6);
      }
      if (data) {
        try {
          onEvent({ type: eventType as ConversationTestEvent["type"], data: JSON.parse(data) });
        } catch {
          // ignore parse errors
        }
      }
    }
  }
}

// ─── Voice Test ───────────────────────────────────────────

export interface VoiceTestEvent {
  type: "config" | "voice_turn" | "audio_status" | "progress" | "evaluation" | "done" | "error";
  data: Record<string, unknown>;
}

export interface VoiceTestConfig {
  scenario: string;
  persona?: string;
  max_turns?: number;
  evaluate?: boolean;
  model?: string;
  audio_enabled?: boolean;
  agent_tts_model_id?: string;
  tester_tts_model_id?: string;
}

export async function runVoiceTest(
  agentId: string,
  config: VoiceTestConfig,
  onEvent: (event: VoiceTestEvent) => void,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/agents/${agentId}/voice-test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Voice test failed: ${res.status} ${text || res.statusText}`);
  }

  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      if (!part.trim()) continue;
      let eventType = "message";
      let data = "";
      for (const line of part.split("\n")) {
        if (line.startsWith("event: ")) eventType = line.slice(7).trim();
        else if (line.startsWith("data: ")) data = line.slice(6);
      }
      if (data) {
        try {
          onEvent({ type: eventType as VoiceTestEvent["type"], data: JSON.parse(data) });
        } catch {
          // ignore parse errors
        }
      }
    }
  }
}

export type { CreateRoomResponse };
