import asyncio
import logging

from config import ASSETS, TRADING_PAIRS
from market.models import BestTouch
from pubsub.broker import PubSubBroker
from trading.models import Balance, DepositRequest, Order, OrderCreate, OrderSide, OrderStatus

logger = logging.getLogger(__name__)


def _base_quote(symbol: str) -> tuple[str, str]:
    """Return (base, quote) for a symbol. Assumes quote is USDT or BTC."""
    if symbol.endswith("USDT"):
        return symbol[:-4], "USDT"
    if symbol.endswith("BTC"):
        return symbol[:-3], "BTC"
    raise ValueError(f"Unknown symbol format: {symbol}")


class PaperTradingEngine:
    def __init__(self, broker: PubSubBroker) -> None:
        self._broker = broker
        # user_id → {asset: total_balance}
        self._total: dict[str, dict[str, float]] = {}
        # user_id → {asset: reserved_balance}
        self._reserved: dict[str, dict[str, float]] = {}
        # token_id → Order
        self._orders: dict[str, Order] = {}
        self._lock = asyncio.Lock()

    def _ensure_user(self, user_id: str) -> None:
        if user_id not in self._total:
            self._total[user_id] = {asset: 0.0 for asset in ASSETS}
            self._reserved[user_id] = {asset: 0.0 for asset in ASSETS}

    async def deposit(self, user_id: str, req: DepositRequest) -> dict:
        asset = req.asset.upper()
        if asset not in ASSETS:
            raise ValueError(f"Asset '{asset}' is not supported. Available: {ASSETS}")
        async with self._lock:
            self._ensure_user(user_id)
            self._total[user_id][asset] += req.amount
        return {"asset": asset, "deposited": req.amount, "new_total": self._total[user_id][asset]}

    async def get_balance(self, user_id: str) -> Balance:
        async with self._lock:
            self._ensure_user(user_id)
            total = dict(self._total[user_id])
            reserved = dict(self._reserved[user_id])
        available = {a: total[a] - reserved.get(a, 0.0) for a in total}
        return Balance(total=total, available=available)

    async def place_order(self, user_id: str, req: OrderCreate) -> Order:
        symbol = req.symbol.upper()
        if symbol not in TRADING_PAIRS:
            raise ValueError(f"Symbol '{symbol}' is not supported. Available: {TRADING_PAIRS}")

        base, quote = _base_quote(symbol)

        async with self._lock:
            self._ensure_user(user_id)

            # Check for duplicate token_id
            if req.token_id in self._orders:
                existing = self._orders[req.token_id]
                if existing.user_id != user_id:
                    raise ValueError("token_id already used by another user")
                raise ValueError(f"Order with token_id '{req.token_id}' already exists")

            total = self._total[user_id]
            reserved = self._reserved[user_id]
            available = {a: total[a] - reserved.get(a, 0.0) for a in total}

            if req.side == OrderSide.buy:
                cost = req.price * req.quantity
                if available.get(quote, 0.0) < cost:
                    raise ValueError(
                        f"Insufficient {quote} balance. "
                        f"Need {cost:.6f}, have {available.get(quote, 0.0):.6f} available"
                    )
                reserved[quote] = reserved.get(quote, 0.0) + cost
            else:
                if available.get(base, 0.0) < req.quantity:
                    raise ValueError(
                        f"Insufficient {base} balance. "
                        f"Need {req.quantity:.6f}, have {available.get(base, 0.0):.6f} available"
                    )
                reserved[base] = reserved.get(base, 0.0) + req.quantity

            order = Order(
                token_id=req.token_id,
                user_id=user_id,
                symbol=symbol,
                side=req.side,
                price=req.price,
                quantity=req.quantity,
                status=OrderStatus.open,
            )
            self._orders[req.token_id] = order

        return order

    async def cancel_order(self, user_id: str, token_id: str) -> Order:
        async with self._lock:
            order = self._orders.get(token_id)
            if order is None:
                raise ValueError(f"Order '{token_id}' not found")
            if order.user_id != user_id:
                raise ValueError(f"Order '{token_id}' not found")
            if order.status != OrderStatus.open:
                raise ValueError(f"Order '{token_id}' is already {order.status.value}")

            order.status = OrderStatus.cancelled
            self._release_reserved(order)

        return order

    def _release_reserved(self, order: Order) -> None:
        """Release reserved funds for an order (must be called under lock)."""
        base, quote = _base_quote(order.symbol)
        reserved = self._reserved[order.user_id]
        if order.side == OrderSide.buy:
            cost = order.price * order.quantity
            reserved[quote] = max(0.0, reserved.get(quote, 0.0) - cost)
        else:
            reserved[base] = max(0.0, reserved.get(base, 0.0) - order.quantity)

    async def get_order(self, user_id: str, token_id: str) -> Order:
        order = self._orders.get(token_id)
        if order is None or order.user_id != user_id:
            raise ValueError(f"Order '{token_id}' not found")
        return order

    async def on_best_touch(self, bt: BestTouch) -> None:
        """Called whenever a best touch update is published. Tries to match open orders."""
        symbol = bt.symbol
        async with self._lock:
            for order in list(self._orders.values()):
                if order.status != OrderStatus.open or order.symbol != symbol:
                    continue
                filled = False
                if order.side == OrderSide.buy and bt.best_ask <= order.price:
                    filled = True
                    fill_price = bt.best_ask
                elif order.side == OrderSide.sell and bt.best_bid >= order.price:
                    filled = True
                    fill_price = bt.best_bid

                if filled:
                    self._fill_order(order, fill_price)

    def _fill_order(self, order: Order, fill_price: float) -> None:
        """Settle a filled order and update balances (must be called under lock)."""
        base, quote = _base_quote(order.symbol)
        user_id = order.user_id
        total = self._total[user_id]
        reserved = self._reserved[user_id]

        if order.side == OrderSide.buy:
            cost = order.price * order.quantity  # reserved amount
            actual_cost = fill_price * order.quantity
            # Deduct reserved quote, credit base, refund overpay
            reserved[quote] = max(0.0, reserved.get(quote, 0.0) - cost)
            total[quote] = max(0.0, total.get(quote, 0.0) - actual_cost)
            total[base] = total.get(base, 0.0) + order.quantity
        else:
            # Reserved base, receive quote
            reserved[base] = max(0.0, reserved.get(base, 0.0) - order.quantity)
            total[base] = max(0.0, total.get(base, 0.0) - order.quantity)
            total[quote] = total.get(quote, 0.0) + fill_price * order.quantity

        order.status = OrderStatus.filled
        order.filled_price = fill_price
        logger.info(
            "Order %s filled: %s %s %s @ %.8f (limit %.8f)",
            order.token_id,
            order.side.value,
            order.quantity,
            order.symbol,
            fill_price,
            order.price,
        )

    async def run_matcher(self, aggregator) -> None:
        """
        Subscribe to all symbol best_touch topics and drive order matching.
        Runs forever; cancel the task to stop.
        """
        queues = {}
        for symbol in TRADING_PAIRS:
            q = self._broker.subscribe(f"{symbol}.best_touch")
            queues[f"{symbol}.best_touch"] = q

        pending: dict[asyncio.Task, str] = {
            asyncio.create_task(q.get()): topic
            for topic, q in queues.items()
        }

        try:
            while True:
                done, _ = await asyncio.wait(
                    pending.keys(), return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    topic = pending.pop(task)
                    try:
                        bt = task.result()
                        await self.on_best_touch(bt)
                    except Exception:
                        logger.exception("Error in matcher for topic %s", topic)
                    # Re-schedule
                    pending[asyncio.create_task(queues[topic].get())] = topic
        except asyncio.CancelledError:
            for t in pending:
                t.cancel()
            raise
