import enum
from typing import Annotated

from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlmodel import Column, Enum, Field, Relationship, SQLModel, UniqueConstraint


class BaseIceCream(SQLModel):
    name: str
    flavor: str
    price: float


class IceCream(BaseIceCream, table=True):
    id: Annotated[int | None, Field(primary_key=True)] = None
    stock: int
    blocked_quantity: int = 0  # reserved for payments only
    is_active: bool = True

    cart_items: list["CartItem"] = Relationship(
        back_populates="icecream", cascade_delete=True
    )
    order_items: list["OrderItem"] = Relationship(back_populates="icecream")

    @property
    def available_stock(self) -> int:
        return self.stock - self.blocked_quantity


class RetrieveIceCream(BaseIceCream):
    id: int
    available_stock: int


class User(SQLModel, AsyncAttrs, table=True):
    __tablename__ = "users"

    id: Annotated[int | None, Field(primary_key=True)] = None
    name: str = ""
    email: Annotated[EmailStr, Field(index=True, unique=True, max_length=255)]
    hashed_password: str
    is_active: bool = True

    cart: "Cart" = Relationship(back_populates="user", cascade_delete=True)
    orders: list["Order"] = Relationship(back_populates="user", cascade_delete=True)
    payments: list["Payment"] = Relationship(back_populates="user")


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(SQLModel):
    sub: str | int


class BaseCartItem(SQLModel):
    icecream_id: Annotated[int, Field(foreign_key="icecream.id", ondelete="CASCADE")]
    quantity: Annotated[int, Field(ge=1)] = 1  # defaults to 1 when not specified


class CartItem(BaseCartItem, AsyncAttrs, table=True):
    __tablename__ = "cartitems"
    __table_args__ = (
        UniqueConstraint("cart_id", "icecream_id", name="cart_icecream_id"),
    )

    id: Annotated[int | None, Field(primary_key=True)] = None
    cart_id: Annotated[int, Field(foreign_key="cart.id", ondelete="CASCADE")]

    icecream: IceCream = Relationship(back_populates="cart_items")
    cart: "Cart" = Relationship(back_populates="items")


class RetrieveCartItem(BaseCartItem):
    id: int
    icecream: RetrieveIceCream


class CreateCartItem(BaseCartItem):
    pass


class BaseCart(SQLModel):
    user_id: Annotated[
        int, Field(foreign_key="users.id", unique=True, ondelete="CASCADE")
    ]


class Cart(BaseCart, AsyncAttrs, table=True):
    id: Annotated[int | None, Field(primary_key=True)] = None

    items: list[CartItem] = Relationship(back_populates="cart", cascade_delete=True)
    user: User = Relationship(back_populates="cart")


class RetrieveCart(BaseCart):
    id: int
    items: list[RetrieveCartItem] = []


class OrderItem(SQLModel, table=True):
    __tablename__ = "orderitems"
    __table_args__ = (
        UniqueConstraint("order_id", "icecream_id", name="order_icecream_id"),
    )

    id: Annotated[int | None, Field(primary_key=True)] = None
    icecream_id: Annotated[
        int | None, Field(foreign_key="icecream.id", ondelete="SET NULL", nullable=True)
    ]
    order_id: Annotated[int, Field(foreign_key="orders.id", ondelete="CASCADE")]
    quantity: int
    total_price: float  # to freeze the total amount at the point of sale

    icecream: IceCream | None = Relationship(back_populates="order_items")
    order: "Order" = Relationship(back_populates="items")


class OrderStatus(enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class BaseOrder(SQLModel):
    user_id: Annotated[int, Field(foreign_key="users.id", ondelete="CASCADE")]
    status: Annotated[OrderStatus, Field(sa_column=Column(Enum(OrderStatus)))]


class Order(BaseOrder, AsyncAttrs, table=True):
    __tablename__ = "orders"

    id: Annotated[int | None, Field(primary_key=True)] = None

    user: User = Relationship(back_populates="orders")
    payment: "Payment" = Relationship(back_populates="order")
    items: list[OrderItem] = Relationship(back_populates="order", cascade_delete=True)

    @property
    def amount(self) -> float:
        return sum(item.total_price for item in self.items)


class RetrieveOrder(BaseOrder):
    id: int
    amount: float


class PaymentMethod(enum.Enum):
    CASH = "CASH"
    CARD = "CARD"


class PaymentStatus(enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class BasePayment(SQLModel):
    # Do not delete payments at all cost, for audit purposes.
    order_id: Annotated[
        int | None,
        Field(foreign_key="orders.id", unique=True, ondelete="SET NULL", nullable=True),
    ]
    # Can't delete a user without backing-up the payments pre-delete first.
    user_id: Annotated[int, Field(foreign_key="users.id", ondelete="RESTRICT")]
    status: Annotated[PaymentStatus, Field(sa_column=Column(Enum(PaymentStatus)))]
    amount: float  # should match the order total
    method: Annotated[PaymentMethod, Field(sa_column=Column(Enum(PaymentMethod)))]


class Payment(BasePayment, table=True):
    __tablename__ = "payments"

    id: Annotated[int | None, Field(primary_key=True)] = None

    order: Order | None = Relationship(back_populates="payment")
    user: User = Relationship(back_populates="payments")


class RetrievePayment(BasePayment):
    id: int
