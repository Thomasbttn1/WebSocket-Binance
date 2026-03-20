import asyncio
import logging
from abc import ABC, abstractmethod

import websockets
from websockets.exceptions import ConnectionClosed

from config import RECONNECT_MAX_WAIT

logger = logging.getLogger(__name__)


class BaseConnector(ABC):
    """
    Abstract base for exchange WebSocket connectors.
    Implements an infinite reconnect loop with exponential backoff.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._running = True

    @abstractmethod
    def get_url(self) -> str:
        ...

    @abstractmethod
    async def subscribe(self, ws) -> None:
        """Send subscription frames after connecting."""
        ...

    @abstractmethod
    async def on_message(self, raw: str) -> None:
        """Parse raw JSON and dispatch to aggregator."""
        ...

    async def connect(self) -> None:
        """Start the WebSocket loop. Runs forever until self._running = False."""
        attempt = 0
        while self._running:
            url = self.get_url()
            try:
                logger.info("[%s] Connecting to %s (attempt %d)", self.name, url, attempt)
                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=10,
                ) as ws:
                    await self.subscribe(ws)
                    logger.info("[%s] Connected and subscribed", self.name)
                    attempt = 0  # reset on success
                    async for raw in ws:
                        if not self._running:
                            return
                        try:
                            await self.on_message(raw)
                        except Exception:
                            logger.exception("[%s] Error processing message", self.name)
            except ConnectionClosed as exc:
                logger.warning("[%s] Connection closed: %s", self.name, exc)
            except OSError as exc:
                logger.warning("[%s] OS error: %s", self.name, exc)
            except asyncio.CancelledError:
                logger.info("[%s] Connector task cancelled", self.name)
                return
            except Exception:
                logger.exception("[%s] Unexpected error", self.name)

            if not self._running:
                return

            wait = min(2 ** attempt, RECONNECT_MAX_WAIT)
            logger.info("[%s] Reconnecting in %ds", self.name, wait)
            await asyncio.sleep(wait)
            attempt += 1

    def stop(self) -> None:
        self._running = False
