import asyncio
from unittest.mock import call

import pytest

from deep_ice import app
from deep_ice.models import Order, OrderItem, OrderStatus, PaymentMethod, PaymentStatus


async def _check_order_creation(session, order_id, *, status, amount):
    order = (
        (
            await Order.fetch(
                session,
                filters=[Order.id == order_id],
                joinedloads=[Order.items, OrderItem.icecream],
            )
        )
        .unique()
        .one()
    )
    assert order.status is status
    assert order.amount == amount

    return order


def _get_icecream(initial_data, flavor):
    for icecream in initial_data["icecream"]:
        if icecream["flavor"] == flavor:
            return icecream


def _check_quantities(order, initial_data):
    for item in order.items:
        before = _get_icecream(initial_data, item.icecream.flavor)["stock"]
        after = item.icecream.stock
        assert after == before - item.quantity
        assert not item.icecream.blocked_quantity


def _check_stats(redis_client):
    expected_calls = [
        call("POPULAR_ICECREAM", 10, "Vanilla:1"),
        call("POPULAR_ICECREAM", 20, "Chocolate:2"),
        call("POPULAR_ICECREAM", 5, "Strawberry:3"),
    ]
    redis_client.zincrby.assert_has_calls(expected_calls)


@pytest.mark.parametrize("method", list(PaymentMethod))
@pytest.mark.anyio
async def test_make_successful_payment(
    redis_client, session, auth_client, cart_items, initial_data, method
):
    # Cash payments are instantly triggered (201), since they don't wait for a
    #  confirmation, while card payments are non-blocking and returning instantly with
    #  pending (202) status (as they are processed in the background).
    response = await auth_client.post("/v1/payments", json={"method": method.value})
    status_code = 201 if method is PaymentMethod.CASH else 202
    assert response.status_code == status_code
    data = response.json()
    expected_payment_status = (
        PaymentStatus.SUCCESS if method is PaymentMethod.CASH else PaymentStatus.PENDING
    )
    assert data["status"] == expected_payment_status.value
    assert data["amount"] == 111.0
    if method is PaymentMethod.CARD:
        enqueue_mock = app.state.redis_pool.enqueue_job
        enqueue_mock.assert_called_once()

    # Any successful payment initiation will trigger an order creation.
    expected_order_status = (
        OrderStatus.CONFIRMED
        if expected_payment_status is PaymentStatus.SUCCESS
        else OrderStatus.PENDING
    )
    db_order = await _check_order_creation(
        session, data["order_id"], status=expected_order_status, amount=111.0
    )
    if db_order.status is OrderStatus.CONFIRMED:
        _check_quantities(db_order, initial_data)
        _check_stats(redis_client)

    # The list of payments contain our just-made payment.
    response = await auth_client.get("/v1/payments")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["method"] == method.value


@pytest.mark.anyio
async def test_payment_redirect_insufficient_stock(
    redis_client, session, auth_client, cart_items
):
    # Simulate purchase of some icecream which became unavailable in the meantime.
    first_item = cart_items[0]
    icecream = await first_item.awaitable_attrs.icecream
    initial_quantity = first_item.quantity
    max_quantity = initial_quantity - 1
    icecream.stock = max_quantity
    session.add(icecream)
    await session.commit()

    # Simulate payment and check if the redirect happened including the cart item
    #  quantity update to the new maximum available quantity for that ice cream flavor.
    response = await auth_client.post(
        "/v1/payments", json={"method": PaymentMethod.CASH.value}
    )
    assert response.status_code == 307
    redirect_url = response.headers.get("Location")
    assert redirect_url.endswith("/v1/cart")
    assert first_item.quantity != initial_quantity
    assert first_item.quantity == max_quantity


@pytest.mark.anyio
async def test_concurrent_card_payments(
    redis_client,
    session,
    auth_client,
    cart_items,
    secondary_auth_client,
    secondary_cart_items,
):
    # Two greedy customers add the whole stock at the same time to each of their carts.
    for items in (cart_items, secondary_cart_items):
        for item in items:
            item.quantity = item.icecream.available_stock
        session.add_all(items)
    await session.commit()

    # Two different customers triggering a card payment each, simultaneously and
    #  without enough stock for both.
    args, kwargs = ["/v1/payments"], {"json": {"method": PaymentMethod.CARD.value}}
    requests = [
        crt_client.post(*args, **kwargs)
        for crt_client in (auth_client, secondary_auth_client)
    ]
    responses = await asyncio.gather(*requests)
    print([resp.status_code for resp in responses])
