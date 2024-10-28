Here's the expected user flow and experience (with [httpie](https://httpie.io/)):

1. Authenticate
```console
http -f POST :8000/v1/auth/access-token username="cmin764@gmail.com" password="cosmin-password"
```
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3Mjk4NTQwOTQsInN1YiI6IjEiLCJlbWFpbCI6ImNtaW43NjRAZ21haWwuY29tIn0.lGuQ-dVy2Ybyu6TE2e-4sYNs7d87EOipEvNOC0g6R20",
    "token_type": "bearer"
}
```

Save the token in the terminal with `token=<access-token>` for later usage.

2. Check available ice cream
```console
http :8000/v1/icecream
```
```json
[
    {
        "available_stock": 100,
        "flavor": "vanilla",
        "id": 1,
        "name": "Vanilla",
        "price": 3.3
    },
    {
        "available_stock": 50,
        "flavor": "strawberry",
        "id": 3,
        "name": "Strawberry",
        "price": 4.0
    },
    {
        "available_stock": 104,
        "flavor": "chocolate",
        "id": 2,
        "name": "Chocolate",
        "price": 2.9
    }
]
```

> Note that ice cream is public common information that doesn't require authentication.

3. Add ice cream to cart
```console
http POST :8000/v1/cart/items icecream_id=1 quantity=10 "Authorization: Bearer $token"
```
```json
{
    "icecream": {
        "available_stock": 100,
        "flavor": "vanilla",
        "id": 1,
        "name": "Vanilla",
        "price": 3.3
    },
    "icecream_id": 1,
    "id": 52,
    "quantity": 10
}
```

4. Place order by making the payment
```console
http POST :8000/v1/payments method=CASH "Authorization: Bearer $token"
```
```json
{
    "amount": 33.0,
    "id": 9,
    "method": "CASH",
    "order_id": 20,
    "status": "SUCCESS",
    "user_id": 1
}
```

> Choosing the `CARD` method will defer the payment to a task queue so the API won't stay blocked until the payment processor validates and confirms the payment.

5. Check existing orders
```console
http :8000/v1/orders "Authorization: Bearer $token"
```
```json
[
    {
        "amount": 33.0,
        "id": 20,
        "items": [
            {
                "icecream": {
                    "available_stock": 90,
                    "flavor": "vanilla",
                    "id": 1,
                    "name": "Vanilla",
                    "price": 3.3
                },
                "icecream_id": 1,
                "id": 23,
                "order_id": 20,
                "quantity": 10,
                "total_price": 33.0
            }
        ],
        "status": "CONFIRMED",
        "user_id": 1
    }
]
```
