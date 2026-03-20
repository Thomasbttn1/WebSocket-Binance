import asyncio
import logging
from typing import Any

from config import QUEUE_MAX_SIZE

logger = logging.getLogger(__name__)


class PubSubBroker:
    """
    Simple topic-based asyncio fan-out broker.
    Topics are strings like "BTCUSDT.best_touch" or "BTCUSDT.klines.60".
    Messages that cannot be delivered (full queue) are dropped to avoid
    blocking the aggregator behind a slow subscriber.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = {}

    def subscribe(self, topic: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)
        self._subscribers.setdefault(topic, set()).add(q)
        return q

    def unsubscribe(self, topic: str, queue: asyncio.Queue) -> None:
        subs = self._subscribers.get(topic)
        if subs:
            subs.discard(queue)
            if not subs:
                del self._subscribers[topic]

    async def publish(self, topic: str, message: Any) -> None:
        subs = self._subscribers.get(topic)
        if not subs:
            return
        for q in list(subs):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                logger.debug("Queue full for topic %s — dropping message", topic)

    def subscriber_count(self, topic: str) -> int:
        return len(self._subscribers.get(topic, set()))
