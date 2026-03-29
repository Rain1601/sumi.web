"""Memory data models."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemoryFact:
    """A structured fact about a user."""
    user_id: str
    category: str       # "preference", "fact", "goal", "context"
    key: str
    value: str
    confidence: float = 1.0
    source_conversation_id: str | None = None


@dataclass
class MemoryContext:
    """Combined memory context for injection into system prompt."""
    facts: list[MemoryFact] = field(default_factory=list)
    relevant_history: list[dict[str, Any]] = field(default_factory=list)

    def to_prompt_text(self) -> str:
        parts = []
        if self.facts:
            parts.append("## User Profile:")
            for f in self.facts:
                parts.append(f"- {f.key}: {f.value}")
        if self.relevant_history:
            parts.append("\n## Relevant Context:")
            for h in self.relevant_history:
                parts.append(f"- {h.get('content', '')}")
        return "\n".join(parts)
