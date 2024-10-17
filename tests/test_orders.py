import pytest

from deep_ice.models import OrderStatus


@pytest.mark.anyio
async def test_get_orders(auth_client, order):
    response = await auth_client.get("/v1/orders")
    assert response.status_code == 200
    order_data = response.json()[0]
    assert order_data["status"] == OrderStatus.PENDING.value
    assert order_data["amount"] == 111.0
