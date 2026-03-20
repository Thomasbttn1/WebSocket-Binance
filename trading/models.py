from enum import Enum
from typing import Literal

from pydantic import BaseModel, field_validator


class OrderSide(str, Enum):
    buy = "buy"
    sell = "sell"


class OrderStatus(str, Enum):
    open = "open"
    filled = "filled"
    cancelled = "cancelled"


class OrderCreate(BaseModel):
    token_id: str
    symbol: str
    side: OrderSide
    price: float
    quantity: float

    @field_validator("price", "quantity")
    @classmethod
    def must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("must be positive")
        return v

    @field_validator("token_id")
    @classmethod
    def token_id_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("token_id cannot be empty")
        return v.strip()


class Order(BaseModel):
    token_id: str
    user_id: str
    symbol: str
    side: OrderSide
    price: float
    quantity: float
    status: OrderStatus = OrderStatus.open
    filled_price: float | None = None


class DepositRequest(BaseModel):
    asset: str
    amount: float

    @field_validator("amount")
    @classmethod
    def must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("amount must be positive")
        return v


class Balance(BaseModel):
    total: dict[str, float]
    available: dict[str, float]
