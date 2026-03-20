import json
import logging
import time

from config import OKX_WS_URL, TRADING_PAIRS
from market.connectors.base import BaseConnector
from market.models import OrderBookUpdate, Trade

logger = logging.getLogger(__name__)

# OKX uses "BTC-USDT" format
def _to_okx_inst(symbol: str) -> str:
    if symbol.endswith("USDT"):
        return symbol[:-4] + "-USDT"
    if symbol.endswith("BTC"):
        return symbol[:-3] + "-BTC"
    return symbol


def _from_okx_inst(inst_id: str) -> str:
    return inst_id.replace("-", "")


class OKXConnector(BaseConnector):
    def __init__(self, aggregator) -> None:
        super().__init__("okx")
        self._aggregator = aggregator

    def get_url(self) -> str:
        return OKX_WS_URL

    async def subscribe(self, ws) -> None:
        args = []
        for pair in TRADING_PAIRS:
            inst = _to_okx_inst(pair)
            args.append({"channel": "books5", "instId": inst})
            args.append({"channel": "trades", "instId": inst})
        msg = json.dumps({"op": "subscribe", "args": args})
        await ws.send(msg)

    async def on_message(self, raw: str) -> None:
        data = json.loads(raw)

        # Handle ping/pong
        if data.get("event") == "subscribe":
            return
        if data.get("op") == "ping" or raw == "ping":
            return

        channel = data.get("arg", {}).get("channel", "")
        inst_id = data.get("arg", {}).get("instId", "")
        symbol = _from_okx_inst(inst_id)
        payload_list = data.get("data", [])

        if not payload_list:
            return

        if channel == "books5":
            await self._handle_depth(symbol, payload_list[0])
        elif channel == "trades":
            for item in payload_list:
                await self._handle_trade(symbol, item)

    async def _handle_trade(self, symbol: str, d: dict) -> None:
        if symbol not in TRADING_PAIRS:
            return
        trade = Trade(
            exchange="okx",
            symbol=symbol,
            trade_id=str(d.get("tradeId", "")),
            price=float(d["px"]),
            quantity=float(d["sz"]),
            timestamp=float(d.get("ts", time.time() * 1000)),
        )
        await self._aggregator.on_trade("okx", trade)

    async def _handle_depth(self, symbol: str, d: dict) -> None:
        if symbol not in TRADING_PAIRS:
            return
        bids = [(float(b[0]), float(b[1])) for b in d.get("bids", [])]
        asks = [(float(a[0]), float(a[1])) for a in d.get("asks", [])]
        update = OrderBookUpdate(
            exchange="okx",
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=float(d.get("ts", time.time() * 1000)),
        )
        await self._aggregator.on_order_book("okx", update)
