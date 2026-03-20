from fastapi import APIRouter, HTTPException, status

from auth.models import Token, UserCreate, UserResponse
from auth.service import create_access_token, hash_password, verify_password
from auth.store import user_store

router = APIRouter(tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate):
    hashed = hash_password(body.password)
    user = await user_store.create(body.username, hashed)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{body.username}' is already taken",
        )
    return UserResponse(user_id=user.user_id, username=user.username)


@router.post("/login", response_model=Token)
async def login(body: UserCreate):
    user = await user_store.get_by_username(body.username)
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = create_access_token(user.user_id)
    return Token(access_token=token)
