import asyncio
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

class AsyncBatchWriter:
    def __init__(self, flush_interval: float = 2.0, max_batch_size: int = 100):
        self._event_buffer: list[dict] = []
        self._message_buffer: list[dict] = []
        self._flush_interval = flush_interval
        self._max_batch_size = max_batch_size
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._flush_loop())
        logger.info("[BATCH WRITER] Started")

    async def _flush_loop(self):
        while self._running:
            await asyncio.sleep(self._flush_interval)
            await self._flush()

    async def _flush(self):
        if not self._event_buffer and not self._message_buffer:
            return

        events = self._event_buffer.copy()
        messages = self._message_buffer.copy()
        self._event_buffer.clear()
        self._message_buffer.clear()

        try:
            from backend.db.engine import async_session
            from backend.db.models import TraceEvent, Message

            async with async_session() as db:
                if events:
                    for e in events:
                        db.add(TraceEvent(
                            id=e["id"],
                            conversation_id=e["conversation_id"],
                            event_type=e["event_type"],
                            timestamp=e["timestamp"],
                            duration_ms=e.get("duration_ms"),
                            data=e.get("data"),
                        ))
                if messages:
                    for m in messages:
                        db.add(Message(**m))
                await db.commit()

            if events or messages:
                logger.debug(f"[BATCH WRITER] Flushed {len(events)} events, {len(messages)} messages")
        except Exception as e:
            logger.error(f"[BATCH WRITER] Flush failed: {e}")

    def enqueue_event(self, event: dict):
        self._event_buffer.append(event)
        if len(self._event_buffer) >= self._max_batch_size:
            asyncio.create_task(self._flush())

    def enqueue_message(self, message: dict):
        self._message_buffer.append(message)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._flush()  # Final flush
        logger.info("[BATCH WRITER] Stopped")

# Global instance
batch_writer = AsyncBatchWriter()
