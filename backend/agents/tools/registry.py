"""Tool registry for discovering and invoking agent tools."""

import logging

from backend.agents.tools.base import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for agent tools."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        """Register a tool by its name."""
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def get_tools_for_agent(self, tool_names: list[str]) -> list[BaseTool]:
        """Resolve tool names to BaseTool instances."""
        tools = []
        for name in tool_names:
            tool = self._tools.get(name)
            if tool:
                tools.append(tool)
            else:
                logger.warning(f"Tool not found: {name}")
        return tools

    def to_provider_format(
        self, tool_names: list[str], provider: str
    ) -> list[dict]:
        """Convert named tools to provider-specific format."""
        tools = self.get_tools_for_agent(tool_names)
        return [t.to_provider_format(provider) for t in tools]

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())


# Global instance
tool_registry = ToolRegistry()
