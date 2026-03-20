from typing import Literal

from pydantic import BaseModel


class Trade(BaseModel):
    exchange: str       # "binance" or "okx"
    symbol: str         # e.g. "BTCUSDT"
    trade_id: str
    price: float
    quantity: float
    timestamp: float    # unix ms


class OrderBookUpdate(BaseModel):
    exchange: str
    symbol: str
    bids: list[tuple[float, float]]   # [(price, qty), ...]
    asks: list[tuple[float, float]]
    timestamp: float


class BestTouch(BaseModel):
    symbol: str
    best_bid: float
    best_bid_qty: float
    best_bid_exchange: str
    best_ask: float
    best_ask_qty: float
    best_ask_exchange: str
    timestamp: float


class Kline(BaseModel):
    symbol: str
    interval: int       # seconds
    open: float
    high: float
    low: float
    close: float
    volume: float
    open_time: float    # unix seconds (interval start)
    close_time: float   # unix seconds (interval end)
    is_closed: bool
    exchange: str       # "binance", "okx", or "all"


class EWMAUpdate(BaseModel):
    symbol: str
    exchange: str
    half_life: float
    value: float
    timestamp: float
