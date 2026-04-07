"""Hangup detector — LLM-based async goodbye detection.

After each agent turn completes, asynchronously asks an LLM whether the
conversation has reached a natural ending (both sides said goodbye).
When 2 consecutive turns are judged as "goodbye", triggers disconnect.

This runs in the background and does NOT block the main conversation loop.
"""

import asyncio
import logging

import openai

from backend.config import settings

logger = logging.getLogger("kodama.hangup")

_HANGUP_CHECK_PROMPT = """\
你是一个通话结束检测器。根据对话的最近几轮内容，判断双方是否已经在告别/结束通话。

判断标准：
- 一方说了"再见""拜拜""bye"等明确告别语
- 一方表达了结束意图，如"就这样吧""没别的事了""挂了""先这样"
- 对话已自然结束，双方都没有新话题

只回答一个字：是 或 否
- "是" = 这轮对话是告别/结束
- "否" = 对话还在进行中"""


class HangupDetector:
    """LLM-based async hangup detection.

    After each complete agent turn (agent finishes speaking), submits recent
    conversation context to a lightweight LLM for goodbye detection.
    When `threshold` consecutive turns are judged as goodbye, sets the
    hangup flag.

    Usage in worker:
        hangup = HangupDetector()
        # After each turn:
        hangup.feed_turn("user", transcript)
        hangup.feed_turn("agent", agent_text)
        # Check:
        if hangup.should_hangup: ctx.shutdown()
    """

    def __init__(self, threshold: int = 2, model: str = ""):
        self._threshold = threshold
        self._model = model or "qwen-turbo"  # Fast, cheap model for binary classification
        self._consecutive_goodbyes = 0
        self._should_hangup = False
        self._recent_turns: list[dict[str, str]] = []
        self._pending_check: asyncio.Task | None = None
        self._client: openai.AsyncOpenAI | None = None

    @property
    def should_hangup(self) -> bool:
        return self._should_hangup

    def _get_client(self) -> openai.AsyncOpenAI:
        if not self._client:
            self._client = openai.AsyncOpenAI(
                api_key=settings.aihubmix_api_key,
                base_url=settings.aihubmix_base_url,
            )
        return self._client

    def feed_turn(self, role: str, text: str):
        """Record a turn and trigger async hangup check.

        Call this after each user ASR final or agent speech complete.
        """
        if self._should_hangup:
            return

        self._recent_turns.append({"role": role, "text": text})
        # Keep only last 4 turns for context
        if len(self._recent_turns) > 4:
            self._recent_turns = self._recent_turns[-4:]

        # Only check after agent turn (= complete exchange)
        if role == "agent":
            # Cancel previous pending check if still running
            if self._pending_check and not self._pending_check.done():
                self._pending_check.cancel()
            self._pending_check = asyncio.create_task(self._async_check())

    async def _async_check(self):
        """Ask LLM if conversation is ending."""
        try:
            recent_text = "\n".join(
                f"{'用户' if t['role'] == 'user' else 'Agent'}: {t['text']}"
                for t in self._recent_turns
            )

            client = self._get_client()
            resp = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _HANGUP_CHECK_PROMPT},
                    {"role": "user", "content": f"最近对话：\n{recent_text}\n\n这轮对话是否在告别/结束？"},
                ],
                temperature=0,
                max_tokens=4,
            )
            answer = (resp.choices[0].message.content or "").strip()
            is_goodbye = answer.startswith("是")

            if is_goodbye:
                self._consecutive_goodbyes += 1
                logger.info(
                    f"[HANGUP] LLM判定为告别: count={self._consecutive_goodbyes}/{self._threshold}"
                )
                if self._consecutive_goodbyes >= self._threshold:
                    logger.info("[HANGUP] 达到阈值 — 触发挂断")
                    self._should_hangup = True
            else:
                if self._consecutive_goodbyes > 0:
                    logger.debug(f"[HANGUP] LLM判定未告别, 重置计数器 (was {self._consecutive_goodbyes})")
                self._consecutive_goodbyes = 0

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"[HANGUP] LLM check failed: {e}")

    def reset(self):
        """Reset detector state."""
        self._consecutive_goodbyes = 0
        self._should_hangup = False
        self._recent_turns.clear()
