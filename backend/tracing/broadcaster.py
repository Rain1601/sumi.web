"""WebSocket broadcaster for real-time trace event streaming."""

import asyncio
import logging
from collections import defaultdict
from typing import Callable

logger = logging.getLogger(__name__)

EventCallback = Callable[[dict], None]


class TraceBroadcaster:
    """Manages WebSocket subscriptions for trace events per conversation."""

    def __init__(self):
        self._subscribers: dict[str, list[EventCallback]] = defaultdict(list)

    def subscribe(self, conversation_id: str, callback: EventCallback):
        self._subscribers[conversation_id].append(callback)
        logger.debug(f"Subscriber added for conversation {conversation_id}")

    def unsubscribe(self, conversation_id: str, callback: EventCallback):
        if conversation_id in self._subscribers:
            self._subscribers[conversation_id] = [
                cb for cb in self._subscribers[conversation_id] if cb is not callback
            ]
            if not self._subscribers[conversation_id]:
                del self._subscribers[conversation_id]

    def broadcast(self, conversation_id: str, event: dict):
        """Broadcast an event to all subscribers of a conversation."""
        callbacks = self._subscribers.get(conversation_id, [])
        for callback in callbacks:
            try:
                # Schedule as async task if it's a coroutine function
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(event))
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Error broadcasting to subscriber: {e}")


# Global instance
trace_broadcaster = TraceBroadcaster()
