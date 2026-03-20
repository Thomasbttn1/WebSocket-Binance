import logging

from config import KLINE_INTERVALS, TRADING_PAIRS
from market.ewma import EWMACalculator
from market.kline_builder import KlineBuilder
from market.models import OrderBookUpdate, Trade
from market.order_book import OrderBook, merge_best_touch
from pubsub.broker import PubSubBroker

logger = logging.getLogger(__name__)

EXCHANGES = ["binance", "okx"]


class MarketAggregator:
    """
    Central hub that owns all market state and routes updates to
    OrderBook, KlineBuilder, and publishes derived events to the broker.

    Topics published:
    - "{symbol}.best_touch"              (BestTouch, exchange filter "all")
    - "{symbol}.best_touch.binance"      (BestTouch from binance only)
    - "{symbol}.best_touch.okx"          (BestTouch from okx only)
    - "{symbol}.trades"                  (Trade, exchange "all")
    - "{symbol}.trades.binance"
    - "{symbol}.trades.okx"
    - "{symbol}.klines.{interval}"       (Kline, all exchanges merged)
    - "{symbol}.klines.{interval}.binance"
    - "{symbol}.klines.{interval}.okx"
    """

    def __init__(self, broker: PubSubBroker) -> None:
        self.broker = broker

        # Order books keyed by (symbol, exchange)
        self._books: dict[tuple[str, str], OrderBook] = {
            (sym, ex): OrderBook(sym, ex)
            for sym in TRADING_PAIRS
            for ex in EXCHANGES
        }

        # Kline builders keyed by (symbol, exchange, interval)
        self._kline_builders: dict[tuple[str, str, int], KlineBuilder] = {
            (sym, ex, iv): KlineBuilder(sym, ex, iv)
            for sym in TRADING_PAIRS
            for ex in EXCHANGES
            for iv in KLINE_INTERVALS
        }

        # Per-symbol set of seen trade IDs to deduplicate across exchanges
        self._seen_trades: dict[str, set] = {sym: set() for sym in TRADING_PAIRS}

    async def on_order_book(self, exchange: str, update: OrderBookUpdate) -> None:
        key = (update.symbol, exchange)
        book = self._books.get(key)
        if book is None:
            return
        book.apply_snapshot(update)

        # Publish exchange-specific best touch
        bt = book.to_best_touch()
        if bt:
            await self.broker.publish(f"{update.symbol}.best_touch.{exchange}", bt)

        # Publish merged best touch
        all_books = [self._books[(update.symbol, ex)] for ex in EXCHANGES]
        merged = merge_best_touch(all_books)
        if merged:
            await self.broker.publish(f"{update.symbol}.best_touch", merged)

    async def on_trade(self, exchange: str, trade: Trade) -> None:
        # Publish raw trade events
        await self.broker.publish(f"{trade.symbol}.trades.{exchange}", trade)
        await self.broker.publish(f"{trade.symbol}.trades", trade)

        # Update kline builders for this exchange
        for iv in KLINE_INTERVALS:
            key = (trade.symbol, exchange, iv)
            builder = self._kline_builders.get(key)
            if builder is None:
                continue
            klines = builder.on_trade(trade)
            for kline in klines:
                await self.broker.publish(
                    f"{trade.symbol}.klines.{iv}.{exchange}", kline
                )
                # Also publish to "all" topic
                await self.broker.publish(f"{trade.symbol}.klines.{iv}", kline)

    def get_books_for_symbol(self, symbol: str) -> list[OrderBook]:
        return [self._books.get((symbol, ex)) for ex in EXCHANGES if (symbol, ex) in self._books]

    def get_kline_builder(self, symbol: str, exchange: str, interval: int) -> KlineBuilder | None:
        return self._kline_builders.get((symbol, exchange, interval))
