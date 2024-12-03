import asyncio
from typing import cast
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    async_scoped_session,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import insert
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.pool import StaticPool

from deep_ice import app
from deep_ice.core.database import get_async_session
from deep_ice.core.security import get_password_hash
from deep_ice.models import Cart, CartItem, IceCream, Order, SQLModel, User
from deep_ice.services.cart import CartService
from deep_ice.services.order import OrderService
from deep_ice.services.stats import stats_service


# Run tests with `asyncio` only.
@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
def redis_client(mocker):
    return mocker.patch(
        "deep_ice.services.stats.stats_service._client", new_callable=AsyncMock
    )


@pytest.fixture
async def _scoped_session():
    async_engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    session_factory = async_sessionmaker(
        bind=async_engine, class_=AsyncSession, expire_on_commit=False
    )
    scoped_session = async_scoped_session(
        session_factory, scopefunc=asyncio.current_task
    )
    yield scoped_session
    await scoped_session.remove()


@pytest.fixture
async def session(_scoped_session: async_scoped_session):
    async with _scoped_session() as session:
        yield session


@pytest.fixture
async def initial_data(session: AsyncSession) -> dict:
    icecream_dump = [
        {
            "name": "Vanilla",
            "flavor": "vanilla",
            "stock": 100,
            "price": 3.3,
        },
        {
            "name": "Chocolate",
            "flavor": "chocolate",
            "stock": 200,
            "price": 2.9,
        },
        {
            "name": "Strawberry",
            "flavor": "strawberry",
            "stock": 50,
            "price": 4,
        },
    ]
    users_dump = [
        {
            "name": "Cosmin Poieana",
            "email": "cmin764@gmail.com",
            "password": "cosmin-password",
            "hashed_password": get_password_hash("cosmin-password"),
        },
        {
            "name": "John Doe",
            "email": "john.doe@deepicecream.ai",
            "password": "john-password",
            "hashed_password": get_password_hash("john-password"),
        },
        {
            "name": "Sam Smith",
            "email": "sam.smith@deepicecream.ai",
            "password": "sam-password",
            "hashed_password": get_password_hash("sam-password"),
        },
    ]

    await session.exec(insert(IceCream).values(icecream_dump))  # type: ignore
    clean_users_dump = [
        {key: value for key, value in user_data.items() if key != "password"}
        for user_data in users_dump
    ]
    await session.exec(insert(User).values(clean_users_dump))  # type: ignore
    await session.commit()

    return {"icecream": icecream_dump, "users": users_dump}


@pytest.fixture
async def users(session: AsyncSession, initial_data: dict) -> list[User]:
    return list((await User.fetch(session)).all())


@pytest.fixture
async def user(users: list[User]) -> User:
    return [usr for usr in users if usr.email == "cmin764@gmail.com"][0]


@pytest.fixture
async def secondary_user(users: list[User], user: User) -> User:
    return [usr for usr in users if usr.email != user.email][0]


@pytest.fixture
async def _client_factory(_scoped_session: async_scoped_session, mocker):
    async def get_session_override():
        async with _scoped_session() as session:
            yield session

    async def _create_client():
        app.state.redis_pool = mocker.AsyncMock()
        app.dependency_overrides[get_async_session] = get_session_override
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            yield client
        app.dependency_overrides.clear()

    return _create_client


@pytest.fixture
async def client(_client_factory):
    async for client in _client_factory():
        yield client


@pytest.fixture
async def secondary_client(_client_factory):
    async for client in _client_factory():
        yield client


async def _get_auth_token(initial_data: dict, user: User, client: AsyncClient) -> str:
    users_dump = initial_data["users"]
    user_dump = [item for item in users_dump if item["email"] == user.email][0]

    # Authenticate and get the token.
    form_data = {"username": user.email, "password": user_dump["password"]}
    response = await client.post("/v1/auth/access-token", data=form_data)
    assert response.status_code == 200

    # Extract the token from the response and place it in the auth header.
    token_data = response.json()
    token = token_data["access_token"]
    return token


@pytest.fixture
async def auth_client(initial_data: dict, user: User, client: AsyncClient):
    token = await _get_auth_token(initial_data, user, client)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


@pytest.fixture
async def secondary_auth_client(
    initial_data: dict, secondary_user: User, secondary_client: AsyncClient
):
    token = await _get_auth_token(initial_data, secondary_user, secondary_client)
    secondary_client.headers.update({"Authorization": f"Bearer {token}"})
    return secondary_client


async def _create_cart_with_items(session: AsyncSession, user: User) -> list[CartItem]:
    cart = Cart(user_id=user.id)
    session.add(cart)
    await session.commit()
    await session.refresh(cart)

    items = []
    for icecream in (await IceCream.fetch(session)).all():
        cart_item = CartItem(
            cart_id=cart.id,
            icecream_id=icecream.id,
            quantity=icecream.available_stock // 10,
        )
        items.append(cart_item)

    session.add_all(items)
    await session.commit()

    items = list(
        (
            await CartItem.fetch(
                session,
                filters=[CartItem.id == cart.id],
                joinedloads=[CartItem.icecream],
            )
        ).all()
    )
    return items


@pytest.fixture
async def cart_items(session: AsyncSession, user: User) -> list[CartItem]:
    return await _create_cart_with_items(session, user)


@pytest.fixture
async def secondary_cart_items(
    session: AsyncSession, secondary_user: User
) -> list[CartItem]:
    return await _create_cart_with_items(session, secondary_user)


@pytest.fixture
async def order(session: AsyncSession, cart_items: list[CartItem], user: User) -> Order:
    cart_service = CartService(session)
    cart = await cart_service.ensure_cart(cast(int, user.id))
    order_service = OrderService(session, stats_service=stats_service)
    order = await order_service.make_order_from_cart(cart)
    await session.commit()
    return order
