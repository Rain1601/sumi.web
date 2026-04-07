-- Sumi.web PostgreSQL Schema (Multi-tenant)
-- Run on Cloud SQL PostgreSQL instance to initialize database
-- This mirrors backend/db/models.py ORM definitions

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ═══════════════════════════════════════════════════════════════
-- Tenants (Organizations / Workspaces)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS tenants (
    id          TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL UNIQUE,
    plan        TEXT DEFAULT 'free',
    settings    JSONB,
    is_active   BOOLEAN DEFAULT true,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════
-- Users
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS users (
    id                  TEXT PRIMARY KEY,  -- Firebase UID
    display_name        TEXT,
    email               TEXT,
    avatar_url          TEXT,
    preferred_language  TEXT DEFAULT 'zh',
    voiceprint_enrolled BOOLEAN DEFAULT false,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════
-- Tenant Members (User ↔ Tenant with role)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS tenant_members (
    id          TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    tenant_id   TEXT NOT NULL REFERENCES tenants(id),
    user_id     TEXT NOT NULL REFERENCES users(id),
    role        TEXT DEFAULT 'member',  -- 'owner' | 'admin' | 'member' | 'viewer'
    created_at  TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_tenant_member UNIQUE (tenant_id, user_id)
);

-- ═══════════════════════════════════════════════════════════════
-- Provider Models (ASR/TTS/NLP — tenant-scoped)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS provider_models (
    id          TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    tenant_id   TEXT NOT NULL REFERENCES tenants(id),
    name        TEXT NOT NULL,
    provider_type TEXT NOT NULL,
    provider_name TEXT NOT NULL,
    api_key     TEXT DEFAULT '',
    model_name  TEXT DEFAULT '',
    config      JSONB NOT NULL DEFAULT '{}',
    is_active   BOOLEAN DEFAULT true,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════
-- Agents (tenant-scoped)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS agents (
    id                  TEXT PRIMARY KEY,
    tenant_id           TEXT NOT NULL REFERENCES tenants(id),
    created_by          TEXT REFERENCES users(id),
    name_zh             TEXT NOT NULL,
    name_en             TEXT NOT NULL,
    description_zh      TEXT,
    description_en      TEXT,
    system_prompt       TEXT NOT NULL,
    goal                TEXT,
    asr_model_id        TEXT REFERENCES provider_models(id),
    tts_model_id        TEXT REFERENCES provider_models(id),
    nlp_model_id        TEXT REFERENCES provider_models(id),
    asr_provider        TEXT NOT NULL DEFAULT '',
    asr_config          JSONB NOT NULL DEFAULT '{}',
    tts_provider        TEXT NOT NULL DEFAULT '',
    tts_config          JSONB NOT NULL DEFAULT '{}',
    nlp_provider        TEXT NOT NULL DEFAULT '',
    nlp_config          JSONB NOT NULL DEFAULT '{}',
    vad_mode            TEXT DEFAULT 'backend',
    vad_config          JSONB,
    tools               JSONB NOT NULL DEFAULT '[]',
    interruption_policy TEXT DEFAULT 'always',
    voiceprint_enabled  BOOLEAN DEFAULT false,
    language            TEXT DEFAULT 'auto',
    opening_line        TEXT,
    test_scenario       TEXT,
    user_prompt         TEXT,
    version             INTEGER DEFAULT 1,
    status              TEXT DEFAULT 'draft',
    folder_id           TEXT,
    call_control        JSONB,
    cloned_from         TEXT,
    role                TEXT,
    task_chain          JSONB,
    rules               JSONB,
    optimization        JSONB,
    is_active           BOOLEAN DEFAULT true,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════
-- Agent Versions (published snapshots)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS agent_versions (
    id              TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    agent_id        TEXT NOT NULL REFERENCES agents(id),
    version         INTEGER NOT NULL,
    snapshot        JSONB NOT NULL,
    change_summary  TEXT,
    published_by    TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════
-- Agent Variables (template variables)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS agent_variables (
    id              TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    agent_id        TEXT NOT NULL REFERENCES agents(id),
    name            TEXT NOT NULL,
    code            TEXT NOT NULL,
    var_type        TEXT DEFAULT 'string',
    default_value   TEXT,
    description     TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════
-- Agent Skills
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS agent_skills (
    id              TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    agent_id        TEXT NOT NULL REFERENCES agents(id),
    name            TEXT NOT NULL,
    code            TEXT NOT NULL,
    description     TEXT,
    content         TEXT,
    skill_type      TEXT DEFAULT 'free',
    qa_pairs        JSONB,
    logic_tree      JSONB,
    entry_prompt    TEXT,
    exit_conditions JSONB,
    sort_order      INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════
-- Agent Tools
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS agent_tools (
    id                  TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    agent_id            TEXT NOT NULL REFERENCES agents(id),
    name                TEXT NOT NULL,
    tool_id             TEXT NOT NULL,
    description         TEXT,
    parameters_schema   JSONB,
    execution_type      TEXT DEFAULT 'sync_round',
    created_at          TIMESTAMP DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════
-- Conversations (tenant + user scoped)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    tenant_id   TEXT NOT NULL REFERENCES tenants(id),
    user_id     TEXT NOT NULL REFERENCES users(id),
    agent_id    TEXT NOT NULL REFERENCES agents(id),
    room_name   TEXT,
    language    TEXT,
    started_at  TIMESTAMP DEFAULT NOW(),
    ended_at    TIMESTAMP,
    summary     TEXT,
    metadata    JSONB
);

-- ═══════════════════════════════════════════════════════════════
-- Messages
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS messages (
    id                  TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    conversation_id     TEXT NOT NULL REFERENCES conversations(id),
    role                TEXT NOT NULL,
    content             TEXT NOT NULL,
    tool_name           TEXT,
    tool_input          JSONB,
    tool_output         JSONB,
    is_truncated        BOOLEAN DEFAULT false,
    turn_index          INTEGER,
    started_at          TIMESTAMP DEFAULT NOW(),
    ended_at            TIMESTAMP,
    audio_url           TEXT
);

-- ═══════════════════════════════════════════════════════════════
-- Memory Facts (user-scoped)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS memory_facts (
    id                      TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    user_id                 TEXT NOT NULL REFERENCES users(id),
    category                TEXT NOT NULL,
    key                     TEXT NOT NULL,
    value                   TEXT NOT NULL,
    source_conversation_id  TEXT REFERENCES conversations(id),
    confidence              REAL DEFAULT 1.0,
    created_at              TIMESTAMP DEFAULT NOW(),
    updated_at              TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_memory_user_cat_key UNIQUE (user_id, category, key)
);

-- ═══════════════════════════════════════════════════════════════
-- Agent Rules (behavioral constraints)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS agent_rules (
    id          TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    agent_id    TEXT NOT NULL REFERENCES agents(id),
    rule_type   TEXT NOT NULL,
    content     TEXT NOT NULL,
    priority    INTEGER DEFAULT 0,
    is_active   BOOLEAN DEFAULT true,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════
-- Annotations (quality evaluation)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS annotations (
    id                  TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    conversation_id     TEXT NOT NULL REFERENCES conversations(id),
    message_id          TEXT,
    turn_index          INTEGER,
    annotation_type     TEXT NOT NULL,
    rating              INTEGER,
    labels              JSONB,
    corrected_text      TEXT,
    expected_response   TEXT,
    notes               TEXT,
    annotator           TEXT DEFAULT 'human',
    created_at          TIMESTAMP DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════
-- Trace Events (pipeline performance/debug)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS trace_events (
    id                  TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    conversation_id     TEXT NOT NULL REFERENCES conversations(id),
    event_type          TEXT NOT NULL,
    timestamp           DOUBLE PRECISION NOT NULL,
    duration_ms         DOUBLE PRECISION,
    data                JSONB,
    created_at          TIMESTAMP DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════
-- Indexes
-- ═══════════════════════════════════════════════════════════════
-- Tenant scoping
CREATE INDEX IF NOT EXISTS idx_provider_models_tenant ON provider_models(tenant_id);
CREATE INDEX IF NOT EXISTS idx_agents_tenant ON agents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_conversations_tenant ON conversations(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_members_tenant ON tenant_members(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_members_user ON tenant_members(user_id);

-- Common queries
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_agent_id ON conversations(agent_id);
CREATE INDEX IF NOT EXISTS idx_conversations_started_at ON conversations(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_started_at ON messages(started_at);
CREATE INDEX IF NOT EXISTS idx_trace_events_conversation_id ON trace_events(conversation_id);
CREATE INDEX IF NOT EXISTS idx_trace_events_event_type ON trace_events(event_type);
CREATE INDEX IF NOT EXISTS idx_memory_facts_user_id ON memory_facts(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_versions_agent_id ON agent_versions(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_skills_agent_id ON agent_skills(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_tools_agent_id ON agent_tools(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_variables_agent_id ON agent_variables(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_rules_agent_id ON agent_rules(agent_id);
CREATE INDEX IF NOT EXISTS idx_annotations_conversation_id ON annotations(conversation_id);
