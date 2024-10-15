from typing import Annotated

from pydantic import EmailStr
from sqlmodel import SQLModel, Field


class IceCream(SQLModel, table=True):
    id: Annotated[int | None, Field(primary_key=True)] = None
    name: str
    flavor: str
    stock: int
    price: float
    blocked_quantity: int = 0
    is_active: bool = True


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Annotated[int | None, Field(primary_key=True)] = None
    name: str = ""
    email: Annotated[EmailStr, Field(index=True, unique=True)]
    hashed_password: str
    is_active: bool = True


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(SQLModel):
    sub: str | int
