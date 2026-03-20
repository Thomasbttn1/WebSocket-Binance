import time

from market.models import BestTouch, OrderBookUpdate


class OrderBook:
    """Maintains sorted bid/ask levels for a single (symbol, exchange) pair."""

    def __init__(self, symbol: str, exchange: str) -> None:
        self.symbol = symbol
        self.exchange = exchange
        self.bids: dict[float, float] = {}  # price -> qty
        self.asks: dict[float, float] = {}
        self._last_update: float = 0.0

    def apply_snapshot(self, update: OrderBookUpdate) -> None:
        self.bids = {p: q for p, q in update.bids if q > 0}
        self.asks = {p: q for p, q in update.asks if q > 0}
        self._last_update = update.timestamp

    def apply_delta(self, update: OrderBookUpdate) -> None:
        for price, qty in update.bids:
            if qty == 0:
                self.bids.pop(price, None)
            else:
                self.bids[price] = qty
        for price, qty in update.asks:
            if qty == 0:
                self.asks.pop(price, None)
            else:
                self.asks[price] = qty
        self._last_update = update.timestamp

    @property
    def best_bid(self) -> tuple[float, float] | None:
        """Returns (price, qty) or None."""
        if not self.bids:
            return None
        price = max(self.bids)
        return (price, self.bids[price])

    @property
    def best_ask(self) -> tuple[float, float] | None:
        """Returns (price, qty) or None."""
        if not self.asks:
            return None
        price = min(self.asks)
        return (price, self.asks[price])

    @property
    def mid_price(self) -> float | None:
        bid = self.best_bid
        ask = self.best_ask
        if bid and ask:
            return (bid[0] + ask[0]) / 2
        return None

    def to_best_touch(self) -> BestTouch | None:
        bid = self.best_bid
        ask = self.best_ask
        if not bid or not ask:
            return None
        return BestTouch(
            symbol=self.symbol,
            best_bid=bid[0],
            best_bid_qty=bid[1],
            best_bid_exchange=self.exchange,
            best_ask=ask[0],
            best_ask_qty=ask[1],
            best_ask_exchange=self.exchange,
            timestamp=self._last_update,
        )


def merge_best_touch(books: list["OrderBook"]) -> BestTouch | None:
    """Return merged best touch across multiple order books."""
    best_bid_price = -1.0
    best_bid_qty = 0.0
    best_bid_exchange = ""
    best_ask_price = float("inf")
    best_ask_qty = 0.0
    best_ask_exchange = ""
    latest_ts = 0.0

    for book in books:
        bid = book.best_bid
        ask = book.best_ask
        if bid and bid[0] > best_bid_price:
            best_bid_price, best_bid_qty = bid
            best_bid_exchange = book.exchange
        if ask and ask[0] < best_ask_price:
            best_ask_price, best_ask_qty = ask
            best_ask_exchange = book.exchange
        if book._last_update > latest_ts:
            latest_ts = book._last_update

    if best_bid_price < 0 or best_ask_price == float("inf"):
        return None

    return BestTouch(
        symbol=books[0].symbol,
        best_bid=best_bid_price,
        best_bid_qty=best_bid_qty,
        best_bid_exchange=best_bid_exchange,
        best_ask=best_ask_price,
        best_ask_qty=best_ask_qty,
        best_ask_exchange=best_ask_exchange,
        timestamp=latest_ts,
    )
