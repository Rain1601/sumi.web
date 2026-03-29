"""Base tool interface for agent tools."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolContext:
    """Context passed to tool execution."""
    user_id: str
    conversation_id: str
    agent_id: str
    language: str = "auto"


@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    output: str
    data: dict[str, Any] = field(default_factory=dict)


class BaseTool(ABC):
    """Abstract base for all agent tools."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema

    @abstractmethod
    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        """Execute the tool with given parameters and context."""
        ...

    def to_provider_format(self, provider: str) -> dict[str, Any]:
        """Convert tool definition to provider-specific function calling format."""
        if provider in ("anthropic", "claude"):
            return {
                "name": self.name,
                "description": self.description,
                "input_schema": self.parameters,
            }
        # OpenAI / compatible format (default)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
