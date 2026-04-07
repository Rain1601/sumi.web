import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


# ═══════════════════════════════════════════════════════════════
# Multi-tenancy: Organization + User
# ═══════════════════════════════════════════════════════════════

class Tenant(Base):
    """Organization / workspace — shared resource boundary."""
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)  # URL-safe identifier
    plan: Mapped[str] = mapped_column(String, default="free")               # "free" | "pro" | "enterprise"
    settings: Mapped[dict | None] = mapped_column(JSON)                     # Org-level settings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class TenantMember(Base):
    """User ↔ Tenant membership with role."""
    __tablename__ = "tenant_members"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_tenant_member"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String, default="member")  # "owner" | "admin" | "member" | "viewer"
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class ProviderModel(Base):
    """A configured model instance (e.g., 'Deepgram Nova-2 中文', 'Claude Sonnet')."""
    __tablename__ = "provider_models"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False, default="")
    name: Mapped[str] = mapped_column(String, nullable=False)           # Display name
    provider_type: Mapped[str] = mapped_column(String, nullable=False)  # "asr" | "tts" | "nlp"
    provider_name: Mapped[str] = mapped_column(String, nullable=False)  # "deepgram" | "openai" | "anthropic" | etc.
    api_key: Mapped[str] = mapped_column(String, default="")            # Encrypted in prod
    model_name: Mapped[str] = mapped_column(String, default="")         # e.g., "nova-2", "claude-sonnet-4-20250514"
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # Provider-specific params
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # Firebase / Supabase UID
    display_name: Mapped[str | None] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)
    avatar_url: Mapped[str | None] = mapped_column(String)
    preferred_language: Mapped[str] = mapped_column(String, default="zh")
    voiceprint_enrolled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False, default="")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))  # Creator user
    name_zh: Mapped[str] = mapped_column(String, nullable=False)
    name_en: Mapped[str] = mapped_column(String, nullable=False)
    description_zh: Mapped[str | None] = mapped_column(Text)
    description_en: Mapped[str | None] = mapped_column(Text)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    goal: Mapped[str | None] = mapped_column(Text)               # Agent task objective
    # Provider references (link to provider_models)
    asr_model_id: Mapped[str | None] = mapped_column(ForeignKey("provider_models.id"))
    tts_model_id: Mapped[str | None] = mapped_column(ForeignKey("provider_models.id"))
    nlp_model_id: Mapped[str | None] = mapped_column(ForeignKey("provider_models.id"))
    # Legacy direct config (fallback if model_id not set)
    asr_provider: Mapped[str] = mapped_column(String, nullable=False, default="")
    asr_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    tts_provider: Mapped[str] = mapped_column(String, nullable=False, default="")
    tts_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    nlp_provider: Mapped[str] = mapped_column(String, nullable=False, default="")
    nlp_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    vad_mode: Mapped[str] = mapped_column(String, default="backend")
    vad_config: Mapped[dict | None] = mapped_column(JSON)
    tools: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    interruption_policy: Mapped[str] = mapped_column(String, default="always")
    voiceprint_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str] = mapped_column(String, default="auto")
    opening_line: Mapped[str | None] = mapped_column(Text)           # 开场白
    test_scenario: Mapped[str | None] = mapped_column(Text)          # 对抗测试默认场景描述
    user_prompt: Mapped[str | None] = mapped_column(Text)            # User prompt template with ${vars}
    version: Mapped[int] = mapped_column(Integer, default=1)         # Version number
    status: Mapped[str] = mapped_column(String, default="draft")     # "draft" | "published"
    folder_id: Mapped[str | None] = mapped_column(String)            # Folder grouping
    call_control: Mapped[dict | None] = mapped_column(JSON)          # {noise_detection, interruption_modes, ...}
    cloned_from: Mapped[str | None] = mapped_column(String)          # Source agent ID if duplicated
    # --- Task Chain architecture fields ---
    role: Mapped[str | None] = mapped_column(Text)                   # Role definition (persona, tone, boundaries)
    task_chain: Mapped[dict | None] = mapped_column(JSON)            # Task chain definition {tasks: [...], entry_task: "..."}
    rules: Mapped[list | None] = mapped_column(JSON)                 # Rule list [{type, content, priority}, ...]
    optimization: Mapped[dict | None] = mapped_column(JSON)          # Optimization config (EQ/IQ tuning)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentVersion(Base):
    """Snapshot of agent config at each published version."""
    __tablename__ = "agent_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)   # Full agent config snapshot
    change_summary: Mapped[str | None] = mapped_column(Text)       # Optional description of changes
    published_by: Mapped[str | None] = mapped_column(String)       # User who published
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class AgentVariable(Base):
    __tablename__ = "agent_variables"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)        # Display name
    code: Mapped[str] = mapped_column(String, nullable=False)        # Variable code for ${code} substitution
    var_type: Mapped[str] = mapped_column(String, default="string")  # "string" | "number" | "boolean" | "list"
    default_value: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class AgentSkill(Base):
    __tablename__ = "agent_skills"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[str] = mapped_column(String, nullable=False)        # Unique code identifier
    description: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)                # Markdown conversation script
    # --- Task Chain architecture fields ---
    skill_type: Mapped[str] = mapped_column(String, default="free")  # "free" | "qa" | "logic_tree"
    qa_pairs: Mapped[dict | None] = mapped_column(JSON)              # QA pair mode {pairs: [...], fallback: "free"}
    logic_tree: Mapped[dict | None] = mapped_column(JSON)            # Logic tree mode {nodes: [...], entry_node: "..."}
    entry_prompt: Mapped[str | None] = mapped_column(Text)           # Instruction when entering this skill
    exit_conditions: Mapped[dict | None] = mapped_column(JSON)       # Exit conditions config
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class AgentTool(Base):
    __tablename__ = "agent_tools"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    tool_id: Mapped[str] = mapped_column(String, nullable=False)     # Internal tool identifier
    description: Mapped[str | None] = mapped_column(Text)
    parameters_schema: Mapped[dict | None] = mapped_column(JSON)     # JSON Schema for params
    execution_type: Mapped[str] = mapped_column(String, default="sync_round")  # "sync_round" | "async_round"
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False, default="")
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    room_name: Mapped[str | None] = mapped_column(String)
    language: Mapped[str | None] = mapped_column(String)
    started_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column()
    summary: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # user | assistant | system | tool
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String)
    tool_input: Mapped[dict | None] = mapped_column(JSON)
    tool_output: Mapped[dict | None] = mapped_column(JSON)
    is_truncated: Mapped[bool] = mapped_column(Boolean, default=False)
    turn_index: Mapped[int | None] = mapped_column(Integer, default=None)
    started_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column()
    audio_url: Mapped[str | None] = mapped_column(String)


class MemoryFact(Base):
    __tablename__ = "memory_facts"
    __table_args__ = (
        UniqueConstraint("user_id", "category", "key", name="uq_memory_user_cat_key"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    key: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    source_conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id"))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentRule(Base):
    """Rules that constrain agent behavior (forbidden phrases, required actions, format rules)."""
    __tablename__ = "agent_rules"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    rule_type: Mapped[str] = mapped_column(String, nullable=False)  # "forbidden" | "required" | "format"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class Annotation(Base):
    """Human annotations on conversation messages for quality evaluation."""
    __tablename__ = "annotations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False)
    message_id: Mapped[str | None] = mapped_column(String)
    turn_index: Mapped[int | None] = mapped_column(Integer)
    annotation_type: Mapped[str] = mapped_column(String, nullable=False)  # "asr" | "response" | "skill" | "overall"
    rating: Mapped[int | None] = mapped_column(Integer)              # 1-5
    labels: Mapped[list | None] = mapped_column(JSON)                # ["asr_error", "off_topic", ...]
    corrected_text: Mapped[str | None] = mapped_column(Text)
    expected_response: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    annotator: Mapped[str] = mapped_column(String, default="human")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class TraceEvent(Base):
    __tablename__ = "trace_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    duration_ms: Mapped[float | None] = mapped_column(Float)
    data: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
