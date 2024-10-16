import pytest
from sqlmodel import select

from deep_ice.models import IceCream


@pytest.mark.anyio
async def test_get_cart(auth_client, initial_data):
    response = await auth_client.get("/v1/cart")
    assert response.status_code == 200
    data = response.json()
    assert data["id"]
    assert not data["items"]


async def _add_cart_item(session, auth_client, active=True):
    query_icecream = select(IceCream).where(IceCream.flavor == "chocolate")
    icecream = (await session.exec(query_icecream)).one_or_none()
    icecream.is_active = active
    session.add(icecream)
    await session.commit()

    response = await auth_client.post(
        "/v1/cart/items", json={"icecream_id": icecream.id, "quantity": 1}
    )
    return response


@pytest.mark.anyio
async def test_add_to_cart(session, auth_client, initial_data):
    response = await _add_cart_item(session, auth_client)
    assert response.status_code == 201
    data = response.json()
    choco = [
        item for item in initial_data["icecream"] if item["flavor"] == "chocolate"
    ][0]
    assert data["icecream"]["available_stock"] == choco["stock"]


@pytest.mark.anyio
async def test_put_to_cart(session, auth_client, initial_data):
    response = await _add_cart_item(session, auth_client)
    data = response.json()
    assert data["quantity"] == 1

    response = await auth_client.put(
        f"/v1/cart/items/{data["id"]}", json={"quantity": 10}
    )
    data = response.json()
    assert data["quantity"] == 10

    response = await auth_client.put(
        f"/v1/cart/items/{data["id"]}", json={"quantity": 0}
    )
    assert response.status_code == 204


@pytest.mark.anyio
async def test_add_inactive_icecream(session, auth_client, initial_data):
    response = await _add_cart_item(session, auth_client, active=False)
    assert response.status_code == 409
