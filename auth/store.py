import asyncio
import uuid

from auth.models import UserInDB


class UserStore:
    def __init__(self) -> None:
        self._users_by_id: dict[str, UserInDB] = {}
        self._users_by_name: dict[str, UserInDB] = {}
        self._lock = asyncio.Lock()

    async def create(self, username: str, hashed_password: str) -> UserInDB:
        async with self._lock:
            if username in self._users_by_name:
                return None  # already exists
            user = UserInDB(
                user_id=str(uuid.uuid4()),
                username=username,
                hashed_password=hashed_password,
            )
            self._users_by_id[user.user_id] = user
            self._users_by_name[username] = user
            return user

    async def get_by_username(self, username: str) -> UserInDB | None:
        return self._users_by_name.get(username)

    async def get_by_id(self, user_id: str) -> UserInDB | None:
        return self._users_by_id.get(user_id)


# Singleton instance
user_store = UserStore()
