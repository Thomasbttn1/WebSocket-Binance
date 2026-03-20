from pydantic import BaseModel, field_validator


class UserCreate(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def username_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("username cannot be empty")
        return v

    @field_validator("password")
    @classmethod
    def password_not_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("password cannot be empty")
        return v


class UserResponse(BaseModel):
    user_id: str
    username: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserInDB(BaseModel):
    user_id: str
    username: str
    hashed_password: str
