import pytest


@pytest.mark.anyio
async def test_get_icecream(client, initial_data):
    response = await client.get("/v1/icecream")
    assert response.status_code == 200
    data = response.json()
    strawberry = [item for item in data if item["flavor"] == "strawberry"][0]
    assert strawberry["price"] == 4
