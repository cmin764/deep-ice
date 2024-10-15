from typing import Annotated

from sqlmodel import SQLModel, Field


class IceCream(SQLModel, table=True):
    id: Annotated[int | None, Field(primary_key=True)] = None
    name: str
    flavor: str
    stock: int
    price: float
    blocked_quantity: int = 0
    is_active: bool = True
