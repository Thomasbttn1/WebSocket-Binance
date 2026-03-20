import json
import logging
import time

from config import BINANCE_WS_URL, TRADING_PAIRS
from market.connectors.base import BaseConnector
from market.models import OrderBookUpdate, Trade

logger = logging.getLogger(__name__)


def _build_binance_url() -> str:
    streams = []
    for pair in TRADING_PAIRS:
        sym = pair.lower()
        streams.append(f"{sym}@depth20@100ms")
        streams.append(f"{sym}@aggTrade")
    return f"{BINANCE_WS_URL}?streams={'/'.join(streams)}"


class BinanceConnector(BaseConnector):
    def __init__(self, aggregator) -> None:
        super().__init__("binance")
        self._aggregator = aggregator
        self._url = _build_binance_url()

    def get_url(self) -> str:
        return self._url

    async def subscribe(self, ws) -> None:
        # Binance combined stream: subscriptions are embedded in the URL
        pass

    async def on_message(self, raw: str) -> None:
        data = json.loads(raw)
        # Combined stream wrapper: {"stream": "...", "data": {...}}
        stream = data.get("stream", "")
        payload = data.get("data", data)

        if "@aggTrade" in stream:
            await self._handle_trade(payload)
        elif "@depth" in stream:
            await self._handle_depth(payload)

    async def _handle_trade(self, d: dict) -> None:
        symbol = d.get("s", "").upper()
        if symbol not in TRADING_PAIRS:
            return
        trade = Trade(
            exchange="binance",
            symbol=symbol,
            trade_id=str(d.get("a", d.get("t", ""))),
            price=float(d["p"]),
            quantity=float(d["q"]),
            timestamp=float(d.get("T", time.time() * 1000)),
        )
        await self._aggregator.on_trade("binance", trade)

    async def _handle_depth(self, d: dict) -> None:
        symbol = d.get("s", "").upper()
        if symbol not in TRADING_PAIRS:
            return
        bids = [(float(p), float(q)) for p, q in d.get("bids", [])]
        asks = [(float(p), float(q)) for p, q in d.get("asks", [])]
        update = OrderBookUpdate(
            exchange="binance",
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=float(d.get("T", time.time() * 1000)),
        )
        await self._aggregator.on_order_book("binance", update)
