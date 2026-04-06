"""Task Chain Controller — drives conversation through a task graph.

Each task has a goal, success/failure conditions, max turns, and transition targets.
The LLM judges whether the current task succeeded/failed after each turn.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TaskTransition:
    from_task: str
    to_task: str
    reason: str  # "success" | "failure" | "timeout"
    turns: int


class TaskChainController:
    """Drives conversation through a task chain."""

    def __init__(self, chain_config: dict[str, Any], skills: dict[str, Any] | None = None):
        """
        Args:
            chain_config: {tasks: [...], entry_task: "greeting"}
            skills: {skill_code: AgentSkill} mapping
        """
        self._tasks: dict[str, dict] = {t["id"]: t for t in chain_config.get("tasks", [])}
        self._skills = skills or {}
        self._entry_task = chain_config.get("entry_task", "")
        self._current_task_id: str = self._entry_task
        self._turn_count: int = 0
        self._history: list[TaskTransition] = []
        self._finished = False

        if not self._tasks:
            logger.warning("[TASK_CHAIN] Empty task chain")
        else:
            logger.info(f"[TASK_CHAIN] Initialized with {len(self._tasks)} tasks, entry={self._entry_task}")

    @property
    def current_task(self) -> dict | None:
        return self._tasks.get(self._current_task_id)

    @property
    def current_task_id(self) -> str:
        return self._current_task_id

    @property
    def is_finished(self) -> bool:
        task = self.current_task
        return self._finished or (task is not None and task.get("terminal", False))

    @property
    def history(self) -> list[TaskTransition]:
        return self._history

    @property
    def turn_count(self) -> int:
        return self._turn_count

    def current_skill_code(self) -> str | None:
        task = self.current_task
        return task.get("skill_code") if task else None

    def on_turn_complete(self, judgment: str) -> str | None:
        """Called after each turn. Returns next task_id if transitioned, None if staying.

        Args:
            judgment: "success" | "failure" | "stay" from LLM evaluation
        """
        self._turn_count += 1
        task = self.current_task
        if not task or self.is_finished:
            return None

        # Check max turns (timeout)
        max_turns = task.get("max_turns")
        if max_turns and self._turn_count >= max_turns:
            next_id = task.get("on_timeout", task.get("on_failure"))
            if next_id:
                return self._transition(next_id, "timeout")
            return None

        # LLM judgment
        if judgment == "success":
            next_id = task.get("on_success")
            if next_id:
                return self._transition(next_id, "success")
        elif judgment == "failure":
            next_id = task.get("on_failure")
            if next_id:
                return self._transition(next_id, "failure")

        return None  # stay in current task

    def _transition(self, next_task_id: str, reason: str) -> str:
        self._history.append(TaskTransition(
            from_task=self._current_task_id,
            to_task=next_task_id,
            reason=reason,
            turns=self._turn_count,
        ))
        logger.info(f"[TASK_CHAIN] {self._current_task_id} -> {next_task_id} ({reason}, {self._turn_count} turns)")

        self._current_task_id = next_task_id
        self._turn_count = 0

        # Check if new task is terminal
        new_task = self.current_task
        if new_task and new_task.get("terminal"):
            self._finished = True

        return next_task_id

    def build_task_prompt(self) -> str:
        """Build dynamic prompt section for current task."""
        task = self.current_task
        if not task:
            return ""

        parts = [
            f"## 当前任务: {task.get('name', task.get('id', 'unknown'))}",
            f"目标: {task.get('goal', 'N/A')}",
        ]

        if task.get("success_condition"):
            parts.append(f"成功条件: {task['success_condition']}")

        max_turns = task.get("max_turns")
        if max_turns:
            remaining = max_turns - self._turn_count
            parts.append(f"剩余轮次: {remaining}")

        # Include skill content if available
        skill_code = task.get("skill_code")
        if skill_code and skill_code in self._skills:
            skill = self._skills[skill_code]
            content = getattr(skill, "content", None) or (skill.get("content") if isinstance(skill, dict) else None)
            if content:
                parts.append(f"\n### 话术参考\n{content}")

            entry_prompt = getattr(skill, "entry_prompt", None) or (skill.get("entry_prompt") if isinstance(skill, dict) else None)
            if entry_prompt:
                parts.append(f"\n### 进入指令\n{entry_prompt}")

        return "\n".join(parts)

    def build_judgment_prompt(self, user_text: str, agent_text: str) -> str:
        """Build prompt for LLM to judge task progress."""
        task = self.current_task
        if not task:
            return ""

        return f"""判断当前任务是否完成。

任务: {task.get('name', '')}
目标: {task.get('goal', '')}
成功条件: {task.get('success_condition', '无特定条件')}

用户说: "{user_text}"
AI回复: "{agent_text}"

请只回复一个词: success / failure / stay
- success: 任务目标已达成
- failure: 用户明确拒绝或无法继续
- stay: 还需要继续当前任务"""

    def get_state(self) -> dict:
        """Get serializable state for tracing/debugging."""
        return {
            "current_task": self._current_task_id,
            "turn_count": self._turn_count,
            "is_finished": self.is_finished,
            "history": [
                {"from": t.from_task, "to": t.to_task, "reason": t.reason, "turns": t.turns}
                for t in self._history
            ],
        }
