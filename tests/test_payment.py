import pytest
from sqlalchemy.orm import selectinload
from sqlmodel import select

from deep_ice.models import (Order, OrderItem, OrderStatus, PaymentMethod,
                             PaymentStatus)


@pytest.mark.anyio
async def test_make_cash_payment(session, auth_client, cart_items, initial_data):
    response = await auth_client.post("/v1/payments", json={"method": "CASH"})
    assert response.status_code == 201
    data = response.json()

    # Cash payments are instantly triggered, since they don't wait for a confirmation.
    assert data["status"] == PaymentStatus.SUCCESS.value
    assert data["amount"] == 111.0

    # Now check if the payment successfully created the order and its status.
    order = (
        await session.exec(
            select(Order)
            .where(Order.id == data["order_id"])
            .options(selectinload(Order.items).selectinload(OrderItem.icecream))
        )
    ).one()
    assert order.amount == 111.0
    assert order.status is OrderStatus.CONFIRMED
    get_icecream = lambda flavor: [
        ice for ice in initial_data["icecream"] if ice["flavor"] == flavor
    ][0]
    for item in order.items:
        before = get_icecream(item.icecream.flavor)["stock"]
        after = item.icecream.stock
        assert after == before - item.quantity

    response = await auth_client.get("/v1/payments")
    assert response.status_code == 200
    data = response.json()
    assert data[0]["method"] == PaymentMethod.CASH.value
