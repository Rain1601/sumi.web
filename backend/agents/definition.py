"""Agent definition and configuration."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentDefinition:
    """Complete definition of a voice agent."""

    id: str
    name: dict[str, str]                    # {"zh": "默认助手", "en": "Default Assistant"}
    description: dict[str, str] = field(default_factory=dict)
    system_prompt: str = ""
    goal: str = ""

    # Model references (ProviderModel IDs)
    asr_model_id: str | None = None
    tts_model_id: str | None = None
    nlp_model_id: str | None = None

    # Legacy provider configuration (fallback)
    asr_provider: str = ""
    asr_config: dict[str, Any] = field(default_factory=dict)
    tts_provider: str = ""
    tts_config: dict[str, Any] = field(default_factory=dict)
    nlp_provider: str = ""
    nlp_config: dict[str, Any] = field(default_factory=dict)

    # VAD
    vad_mode: str = "backend"               # "backend" | "frontend"
    vad_config: dict[str, Any] = field(default_factory=lambda: {
        "threshold": 0.5,
        "min_speech_duration": 0.1,
        "min_silence_duration": 0.5,
        "padding_duration": 0.3,
    })

    # Tools
    tools: list[str] = field(default_factory=list)

    # Behavior
    interruption_policy: str = "always"     # "always" | "sentence_boundary" | "never"
    voiceprint_enabled: bool = False
    language: str = "auto"                  # "zh" | "en" | "auto"

    # New fields
    opening_line: str = ""
    user_prompt: str = ""
    version: int = 1
    status: str = "draft"

    # Task Chain architecture
    role: str = ""                                          # Role definition (persona, tone, boundaries)
    task_chain: dict[str, Any] | None = None                # Task chain {tasks: [...], entry_task: "..."}
    rules: list[dict[str, Any]] = field(default_factory=list)  # Agent rules [{type, content, priority}, ...]
    optimization: dict[str, Any] | None = None              # EQ/IQ optimization config

    call_control: dict[str, Any] = field(default_factory=lambda: {
        "noise_detection": True,
        "interruption_mode": "always",  # always | sentence_boundary | never | multimodal
        "voiceprint_model": "resemblyzer",
        "voiceprint_threshold": 0.65,
        "multi_speaker": False,
        "subtitle_alignment": False,
    })

    @classmethod
    def from_db_row(cls, row) -> "AgentDefinition":
        """Create from a database Agent model instance."""
        return cls(
            id=row.id,
            name={"zh": row.name_zh, "en": row.name_en},
            description={"zh": row.description_zh or "", "en": row.description_en or ""},
            system_prompt=row.system_prompt,
            goal=getattr(row, "goal", None) or "",
            asr_model_id=getattr(row, "asr_model_id", None),
            tts_model_id=getattr(row, "tts_model_id", None),
            nlp_model_id=getattr(row, "nlp_model_id", None),
            asr_provider=row.asr_provider or "",
            asr_config=row.asr_config or {},
            tts_provider=row.tts_provider or "",
            tts_config=row.tts_config or {},
            nlp_provider=row.nlp_provider or "",
            nlp_config=row.nlp_config or {},
            vad_mode=row.vad_mode or "backend",
            vad_config=row.vad_config or {},
            tools=row.tools or [],
            interruption_policy=row.interruption_policy or "always",
            voiceprint_enabled=row.voiceprint_enabled or False,
            language=row.language or "auto",
            opening_line=getattr(row, "opening_line", None) or "",
            user_prompt=getattr(row, "user_prompt", None) or "",
            version=getattr(row, "version", 1) or 1,
            status=getattr(row, "status", "draft") or "draft",
            role=getattr(row, "role", None) or "",
            task_chain=getattr(row, "task_chain", None),
            rules=getattr(row, "rules", None) or [],
            optimization=getattr(row, "optimization", None),
            call_control=getattr(row, "call_control", None) or {},
        )
