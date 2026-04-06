"""Agent manager: load, cache, and switch agents per room."""

import logging

from backend.agents.definition import AgentDefinition

logger = logging.getLogger(__name__)


class AgentManager:
    """Manages active agent assignments per LiveKit room."""

    def __init__(self):
        self._room_agents: dict[str, AgentDefinition] = {}
        self._definitions: dict[str, AgentDefinition] = {}

    async def load_agent(self, agent_id: str, *, use_cache: bool = False) -> AgentDefinition:
        """Load an agent definition from the database.

        By default always reads from DB so that model/prompt changes in the UI
        take effect on the next conversation without restarting the worker.
        """
        if use_cache and agent_id in self._definitions:
            return self._definitions[agent_id]

        from backend.db.engine import async_session
        from backend.db.models import Agent
        from sqlalchemy import select

        async with async_session() as session:
            result = await session.execute(select(Agent).where(Agent.id == agent_id))
            row = result.scalar_one_or_none()
            if not row:
                raise ValueError(f"Agent not found: {agent_id}")

            definition = AgentDefinition.from_db_row(row)
            self._definitions[agent_id] = definition
            return definition

    async def get_agent_for_room(self, room_name: str) -> AgentDefinition | None:
        """Get the currently active agent for a room."""
        return self._room_agents.get(room_name)

    async def assign_agent(self, room_name: str, agent_id: str) -> AgentDefinition:
        """Assign an agent to a room."""
        definition = await self.load_agent(agent_id)
        self._room_agents[room_name] = definition
        logger.info(f"Assigned agent '{agent_id}' to room '{room_name}'")
        return definition

    def release_room(self, room_name: str):
        """Release agent assignment for a room."""
        self._room_agents.pop(room_name, None)

    def invalidate_cache(self, agent_id: str | None = None):
        """Clear cached definitions (e.g., after config update)."""
        if agent_id:
            self._definitions.pop(agent_id, None)
        else:
            self._definitions.clear()


# Global instance
agent_manager = AgentManager()
