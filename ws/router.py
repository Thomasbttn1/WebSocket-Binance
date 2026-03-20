import asyncio
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from auth.service import decode_token
from config import KLINE_INTERVALS, TRADING_PAIRS
from market.ewma import EWMACalculator
from pubsub.broker import PubSubBroker

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

VALID_STREAMS = {"best_touch", "trades", "klines", "ewma"}
VALID_EXCHANGES = {"all", "binance", "okx"}


def _resolve_topic(symbol: str, stream: str, exchange: str, interval: int | None) -> str | None:
    suffix = "" if exchange == "all" else f".{exchange}"
    if stream == "best_touch":
        return f"{symbol}.best_touch{suffix}"
    if stream == "trades":
        return f"{symbol}.trades{suffix}"
    if stream == "klines":
        if interval not in KLINE_INTERVALS:
            return None
        return f"{symbol}.klines.{interval}{suffix}"
    return None


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket, token: str = Query(...)):
    try:
        user_id = decode_token(token)
    except Exception:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    broker: PubSubBroker = websocket.app.state.broker

    # Single outbound queue — all forwarder tasks push here
    outbound: asyncio.Queue = asyncio.Queue(maxsize=500)

    # broker topic → asyncio.Queue
    broker_queues: dict[str, asyncio.Queue] = {}
    # forwarder tasks (one per subscription)
    forwarder_tasks: set[asyncio.Task] = set()

    # EWMA: key → (EWMACalculator, source_queue, forwarder_task)
    ewma_state: dict[str, tuple] = {}

    async def forwarder(topic: str, q: asyncio.Queue):
        """Read from a broker queue and push serialized messages to outbound."""
        try:
            while True:
                msg = await q.get()
                try:
                    outbound.put_nowait({"topic": topic, "data": msg.model_dump()})
                except asyncio.QueueFull:
                    pass
        except asyncio.CancelledError:
            raise

    async def ewma_forwarder(key: str, calc: EWMACalculator, src_q: asyncio.Queue):
        """Drive an EWMA calculator from trade events."""
        try:
            while True:
                trade = await src_q.get()
                update = calc.update(trade.price)
                try:
                    outbound.put_nowait({
                        "topic": f"{calc.symbol}.ewma",
                        "data": update.model_dump(),
                    })
                except asyncio.QueueFull:
                    pass
        except asyncio.CancelledError:
            raise

    def add_subscription(stream: str, symbol: str, exchange: str,
                         interval: int | None = None,
                         half_life: float | None = None):
        if stream == "ewma":
            key = f"{symbol}.ewma.{exchange}.{half_life}"
            if key in ewma_state:
                return
            calc = EWMACalculator(symbol, exchange, half_life)
            src_topic = f"{symbol}.trades" if exchange == "all" else f"{symbol}.trades.{exchange}"
            src_q = broker.subscribe(src_topic)
            t = asyncio.create_task(ewma_forwarder(key, calc, src_q))
            forwarder_tasks.add(t)
            t.add_done_callback(forwarder_tasks.discard)
            ewma_state[key] = (calc, src_q, t, src_topic)
            return

        topic = _resolve_topic(symbol, stream, exchange, interval)
        if topic is None or topic in broker_queues:
            return
        q = broker.subscribe(topic)
        broker_queues[topic] = q
        t = asyncio.create_task(forwarder(topic, q))
        forwarder_tasks.add(t)
        t.add_done_callback(forwarder_tasks.discard)

    async def reader():
        """Handle incoming subscription messages from the client."""
        try:
            while True:
                data = await websocket.receive_json()
                action = data.get("action")
                if action == "subscribe":
                    stream = data.get("stream", "")
                    symbol = data.get("symbol", "").upper()
                    exchange = data.get("exchange", "all").lower()

                    if stream not in VALID_STREAMS:
                        continue
                    if symbol not in TRADING_PAIRS:
                        continue
                    if exchange not in VALID_EXCHANGES:
                        continue

                    if stream == "klines":
                        interval_map = {"1s": 1, "10s": 10, "1m": 60, "5m": 300}
                        raw = data.get("interval", "")
                        interval = interval_map.get(str(raw))
                        if interval is None:
                            try:
                                interval = int(raw)
                            except (TypeError, ValueError):
                                continue
                        if interval not in KLINE_INTERVALS:
                            continue
                        add_subscription(stream, symbol, exchange, interval=interval)
                    elif stream == "ewma":
                        try:
                            half_life = float(data.get("half_life", 0))
                            if half_life <= 0:
                                raise ValueError
                        except (TypeError, ValueError):
                            continue
                        add_subscription(stream, symbol, exchange, half_life=half_life)
                    else:
                        add_subscription(stream, symbol, exchange)

                elif action == "unsubscribe":
                    topic = data.get("topic", "")
                    q = broker_queues.pop(topic, None)
                    if q:
                        broker.unsubscribe(topic, q)

                elif action == "ping":
                    await websocket.send_json({"action": "pong"})

        except (WebSocketDisconnect, RuntimeError):
            pass
        except asyncio.CancelledError:
            raise

    async def writer():
        """Drain the outbound queue and send to WebSocket."""
        try:
            while True:
                msg = await outbound.get()
                await websocket.send_json(msg)
        except (WebSocketDisconnect, RuntimeError):
            pass
        except asyncio.CancelledError:
            raise

    reader_task = asyncio.create_task(reader())
    writer_task = asyncio.create_task(writer())

    try:
        done, pending = await asyncio.wait(
            [reader_task, writer_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
    finally:
        # Cancel all forwarder tasks
        for t in list(forwarder_tasks):
            t.cancel()
        await asyncio.gather(*forwarder_tasks, return_exceptions=True)

        # Unsubscribe from broker
        for topic, q in broker_queues.items():
            broker.unsubscribe(topic, q)
        for key, state in ewma_state.items():
            calc, src_q, _, src_topic = state
            broker.unsubscribe(src_topic, src_q)

        logger.info("WebSocket client %s disconnected", user_id)
