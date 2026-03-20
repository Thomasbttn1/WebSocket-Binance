from fastapi import APIRouter, Depends, HTTPException, status

from config import ASSETS, TRADING_PAIRS
from dependencies import get_current_user_verified, get_trading_engine
from trading.engine import PaperTradingEngine
from trading.models import Balance, DepositRequest, Order, OrderCreate

router = APIRouter(tags=["trading"])


@router.get("/info")
async def get_info():
    return {"assets": ASSETS, "pairs": TRADING_PAIRS}


@router.post("/deposit")
async def deposit(
    body: DepositRequest,
    user_id: str = Depends(get_current_user_verified),
    engine: PaperTradingEngine = Depends(get_trading_engine),
):
    try:
        result = await engine.deposit(user_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return result


@router.post("/orders", response_model=Order, status_code=status.HTTP_201_CREATED)
async def place_order(
    body: OrderCreate,
    user_id: str = Depends(get_current_user_verified),
    engine: PaperTradingEngine = Depends(get_trading_engine),
):
    try:
        order = await engine.place_order(user_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return order


@router.get("/orders/{token_id}", response_model=Order)
async def get_order(
    token_id: str,
    user_id: str = Depends(get_current_user_verified),
    engine: PaperTradingEngine = Depends(get_trading_engine),
):
    try:
        return await engine.get_order(user_id, token_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/orders/{token_id}", response_model=Order)
async def cancel_order(
    token_id: str,
    user_id: str = Depends(get_current_user_verified),
    engine: PaperTradingEngine = Depends(get_trading_engine),
):
    try:
        return await engine.cancel_order(user_id, token_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/balance", response_model=Balance)
async def get_balance(
    user_id: str = Depends(get_current_user_verified),
    engine: PaperTradingEngine = Depends(get_trading_engine),
):
    return await engine.get_balance(user_id)
