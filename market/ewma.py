import math
import time

from market.models import EWMAUpdate


class EWMACalculator:
    """
    Per-subscription EWMA calculator.
    alpha = 1 - exp(-ln(2) / half_life)  so that after half_life seconds the weight halves.
    """

    def __init__(self, symbol: str, exchange: str, half_life: float) -> None:
        self.symbol = symbol
        self.exchange = exchange
        self.half_life = half_life
        self._alpha = 1.0 - math.exp(-math.log(2) / half_life)
        self._value: float | None = None

    def update(self, price: float) -> EWMAUpdate:
        if self._value is None:
            self._value = price
        else:
            self._value = self._alpha * price + (1.0 - self._alpha) * self._value
        return EWMAUpdate(
            symbol=self.symbol,
            exchange=self.exchange,
            half_life=self.half_life,
            value=self._value,
            timestamp=time.time(),
        )

    @property
    def value(self) -> float | None:
        return self._value
