import enum
from typing import Annotated, Any, Type, TypeVar

from pydantic import EmailStr
from sqlalchemy.engine.result import ScalarResult
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession
from sqlalchemy.orm import joinedload
from sqlmodel import (
    Column,
    Enum,
    Field,
    Relationship,
    SQLModel,
    UniqueConstraint,
    select,
)

T = TypeVar("T", bound=SQLModel)


class FetchMixin:
    """Mixin class for `SQLModel` models with helper methods for common queries."""

    @classmethod
    async def fetch(  # type: ignore
        cls: Type[T],
        session: AsyncSession,
        filters: list[Any] | None = None,
        joins: list[Any] | None = None,
        joinedloads: list[Any] | None = None,
    ) -> ScalarResult:
        """Rows fetching helper as a result object supporting filtering and joins.

        Args:
            session: The database session for executing the query.
            filters: A list of filter conditions.
            joins: List of models to join in the query.
            joinedloads: List of models to eagerly load via `joinedload`.

        Returns:
            The result of the executed query as scalars.
        """
        query = select(cls)

        if filters:
            for condition in filters:
                query = query.where(condition)

        if joins:
            for join_model in joins:
                query = query.join(join_model)

        if joinedloads:
            eager_load = joinedload(joinedloads[0])
            for load_relation in joinedloads[1:]:
                eager_load = eager_load.joinedload(load_relation)
            query = query.options(eager_load)

        return await session.exec(query)  # type: ignore


class BaseIceCream(SQLModel):
    name: str
    flavor: str
    price: float


class IceCream(BaseIceCream, FetchMixin, table=True):
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


class User(SQLModel, FetchMixin, AsyncAttrs, table=True):
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


class CartItem(BaseCartItem, FetchMixin, AsyncAttrs, table=True):
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


class Cart(BaseCart, FetchMixin, AsyncAttrs, table=True):
    id: Annotated[int | None, Field(primary_key=True)] = None

    items: list[CartItem] = Relationship(back_populates="cart", cascade_delete=True)
    user: User = Relationship(back_populates="cart")


class RetrieveCart(BaseCart):
    id: int
    items: list[RetrieveCartItem] = []


class BaseOrderItem(SQLModel):
    icecream_id: Annotated[
        int | None, Field(foreign_key="icecream.id", ondelete="SET NULL", nullable=True)
    ]
    order_id: Annotated[int, Field(foreign_key="orders.id", ondelete="CASCADE")]
    quantity: int
    total_price: float  # to freeze the total amount at the point of sale


class OrderItem(BaseOrderItem, FetchMixin, table=True):
    __tablename__ = "orderitems"
    __table_args__ = (
        UniqueConstraint("order_id", "icecream_id", name="order_icecream_id"),
    )

    id: Annotated[int | None, Field(primary_key=True)] = None

    icecream: IceCream | None = Relationship(back_populates="order_items")
    order: "Order" = Relationship(back_populates="items")


class RetrieveOrderItem(BaseOrderItem):
    id: int
    icecream: RetrieveIceCream


class OrderStatus(enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class BaseOrder(SQLModel):
    user_id: Annotated[int, Field(foreign_key="users.id", ondelete="CASCADE")]
    status: Annotated[OrderStatus, Field(sa_column=Column(Enum(OrderStatus)))]


class Order(BaseOrder, FetchMixin, AsyncAttrs, table=True):
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
    items: list[RetrieveOrderItem]


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


class Payment(BasePayment, FetchMixin, table=True):
    __tablename__ = "payments"

    id: Annotated[int | None, Field(primary_key=True)] = None

    order: Order | None = Relationship(back_populates="payment")
    user: User = Relationship(back_populates="payments")


class RetrievePayment(BasePayment):
    id: int
