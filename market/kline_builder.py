import math
import time

from market.models import Kline, Trade


class _Candle:
    __slots__ = ("open", "high", "low", "close", "volume", "open_time")

    def __init__(self, open_time: float, price: float, qty: float) -> None:
        self.open_time = open_time
        self.open = price
        self.high = price
        self.low = price
        self.close = price
        self.volume = qty

    def update(self, price: float, qty: float) -> None:
        if price > self.high:
            self.high = price
        if price < self.low:
            self.low = price
        self.close = price
        self.volume += qty


class KlineBuilder:
    """
    Builds OHLCV candles from incoming trades for a single (symbol, exchange) pair.
    Interval boundaries are aligned to wall-clock epoch (floor(t / interval) * interval).
    """

    def __init__(self, symbol: str, exchange: str, interval: int) -> None:
        self.symbol = symbol
        self.exchange = exchange
        self.interval = interval
        self._candle: _Candle | None = None

    def _bucket(self, ts_seconds: float) -> float:
        return math.floor(ts_seconds / self.interval) * self.interval

    def on_trade(self, trade: Trade) -> list[Kline]:
        """
        Process a trade and return a list of Kline messages to publish.
        Returns a closed kline (is_closed=True) whenever a candle finalizes,
        plus always a live kline (is_closed=False) for the current candle.
        """
        ts = trade.timestamp / 1000.0  # ms → seconds
        bucket = self._bucket(ts)
        results: list[Kline] = []

        if self._candle is None:
            self._candle = _Candle(bucket, trade.price, trade.quantity)
        elif bucket > self._candle.open_time:
            # Finalize the previous candle
            c = self._candle
            results.append(
                Kline(
                    symbol=self.symbol,
                    interval=self.interval,
                    open=c.open,
                    high=c.high,
                    low=c.low,
                    close=c.close,
                    volume=c.volume,
                    open_time=c.open_time,
                    close_time=c.open_time + self.interval,
                    is_closed=True,
                    exchange=self.exchange,
                )
            )
            self._candle = _Candle(bucket, trade.price, trade.quantity)
        else:
            self._candle.update(trade.price, trade.quantity)

        # Always emit live candle
        c = self._candle
        results.append(
            Kline(
                symbol=self.symbol,
                interval=self.interval,
                open=c.open,
                high=c.high,
                low=c.low,
                close=c.close,
                volume=c.volume,
                open_time=c.open_time,
                close_time=c.open_time + self.interval,
                is_closed=False,
                exchange=self.exchange,
            )
        )
        return results

    @property
    def current_kline(self) -> Kline | None:
        if self._candle is None:
            return None
        c = self._candle
        return Kline(
            symbol=self.symbol,
            interval=self.interval,
            open=c.open,
            high=c.high,
            low=c.low,
            close=c.close,
            volume=c.volume,
            open_time=c.open_time,
            close_time=c.open_time + self.interval,
            is_closed=False,
            exchange=self.exchange,
        )
