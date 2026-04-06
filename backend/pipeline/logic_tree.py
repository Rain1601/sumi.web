"""Logic Tree Engine — deterministic conversation flow via decision tree.

Used by skills with skill_type="logic_tree". Each node has a fixed utterance
and keyword-based branches to route to the next node.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class LogicTreeEngine:
    """Deterministic conversation flow via decision tree."""

    def __init__(self, tree_config: dict[str, Any]):
        """
        Args:
            tree_config: {nodes: [...], entry_node: "start"}
        """
        self._nodes: dict[str, dict] = {n["id"]: n for n in tree_config.get("nodes", [])}
        self._entry_node = tree_config.get("entry_node", "")
        self._current_node_id: str = self._entry_node
        self._history: list[dict] = []

        if self._nodes:
            logger.info(f"[LOGIC_TREE] Initialized with {len(self._nodes)} nodes, entry={self._entry_node}")

    @property
    def current_node(self) -> dict | None:
        return self._nodes.get(self._current_node_id)

    @property
    def current_node_id(self) -> str:
        return self._current_node_id

    @property
    def is_terminal(self) -> bool:
        node = self.current_node
        return node is not None and (node.get("terminal", False) or not node.get("branches"))

    def get_utterance(self) -> str:
        """Get what the agent should say at current node."""
        node = self.current_node
        return node.get("say", "") if node else ""

    def process_response(self, user_text: str) -> str | None:
        """Match user response to branch, return next node id.

        Returns: next node id, or None if no match / terminal.
        """
        node = self.current_node
        if not node:
            return None

        branches = node.get("branches", [])
        default_next = None

        for branch in branches:
            if branch.get("condition") == "default":
                default_next = branch.get("next")
                continue

            keywords = branch.get("keywords", [])
            if any(kw in user_text for kw in keywords):
                next_id = branch["next"]
                self._history.append({
                    "from": self._current_node_id,
                    "to": next_id,
                    "condition": branch["condition"],
                    "user_text": user_text[:60],
                })
                self._current_node_id = next_id
                logger.info(f"[LOGIC_TREE] {self._history[-1]['from']} -> {next_id} (matched: {branch['condition']})")
                return next_id

        # Default branch
        if default_next:
            self._history.append({
                "from": self._current_node_id,
                "to": default_next,
                "condition": "default",
                "user_text": user_text[:60],
            })
            self._current_node_id = default_next
            logger.info(f"[LOGIC_TREE] {self._history[-1]['from']} -> {default_next} (default)")
            return default_next

        return None

    def build_prompt(self) -> str:
        """Build prompt injection for current logic tree node."""
        node = self.current_node
        if not node:
            return ""

        parts = [f"### 逻辑树节点: {node.get('id', '?')}"]

        say = node.get("say", "")
        if say:
            parts.append(f"请说: \"{say}\"")

        branches = node.get("branches", [])
        if branches:
            parts.append("用户可能的回答:")
            for b in branches:
                cond = b.get("condition", "")
                keywords = "、".join(b.get("keywords", []))
                if keywords:
                    parts.append(f"- {cond}: 关键词 [{keywords}]")

        return "\n".join(parts)

    def get_state(self) -> dict:
        """Get serializable state for tracing."""
        return {
            "current_node": self._current_node_id,
            "is_terminal": self.is_terminal,
            "history": self._history[-10:],  # last 10 transitions
        }
