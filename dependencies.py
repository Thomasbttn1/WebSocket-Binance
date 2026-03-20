from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from auth.service import decode_token
from auth.store import user_store

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """Returns user_id of authenticated user."""
    return decode_token(token)


async def get_current_user_verified(
    user_id: str = Depends(get_current_user),
) -> str:
    """Returns user_id after confirming the user still exists in the store."""
    user = await user_store.get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user_id


def get_aggregator(request: Request):
    return request.app.state.aggregator


def get_trading_engine(request: Request):
    return request.app.state.trading_engine


def get_broker(request: Request):
    return request.app.state.broker
