import os

from pydantic import BaseModel


class UserTokenConfig:
    ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    @staticmethod
    def get_secret_key():
        return os.getenv('SECRET_KEY')


class User(BaseModel):
    user_name: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None
