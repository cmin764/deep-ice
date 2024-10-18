import pytest
from sqlalchemy.orm import selectinload
from sqlmodel import select

from deep_ice.models import Order, OrderItem, OrderStatus, PaymentMethod, PaymentStatus


async def _check_order_creation(session, order_id, *, status, amount):
    # Check if the payment successfully created the order and its status.
    order = (
        await session.exec(
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.items).selectinload(OrderItem.icecream))
        )
    ).one()
    assert order.status is status
    assert order.amount == amount

    return order


def _check_quantities(order, initial_data):
    # For confirmed orders, ensure the stock was deducted correctly.
    get_icecream = lambda flavor: [
        ice for ice in initial_data["icecream"] if ice["flavor"] == flavor
    ][0]
    for item in order.items:
        before = get_icecream(item.icecream.flavor)["stock"]
        after = item.icecream.stock
        assert after == before - item.quantity
        assert not item.icecream.blocked_quantity


@pytest.mark.parametrize("method", list(PaymentMethod))
@pytest.mark.anyio
async def test_make_payment(session, auth_client, cart_items, initial_data, method):
    # Cash payments are instantly triggered, since they don't wait for a confirmation,
    #  while card payments are non-blocking and returning instantly with pending
    #  status (meanwhile they are processed in the background).
    response = await auth_client.post("/v1/payments", json={"method": method.value})
    assert response.status_code == 201
    data = response.json()
    expected_payment_status = (
        PaymentStatus.SUCCESS if method is PaymentMethod.CASH else PaymentStatus.PENDING
    )
    assert data["status"] == expected_payment_status.value
    assert data["amount"] == 111.0

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

    # The list of payments contain our just-made payment.
    response = await auth_client.get("/v1/payments")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["method"] == method.value
