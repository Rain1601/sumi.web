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
  opening_line: string | null;
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
  created_at?: string;
  updated_at?: string;
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

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
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

export async function publishAgent(id: string): Promise<Agent> {
  return fetchAPI(`/api/agents/${id}/publish`, { method: "POST" });
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

export type { CreateRoomResponse };
