# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

See [README.md](README.md) for the full run/dev/test/format/lint command reference. Key shortcuts:

```bash
inv check-all                        # test + format-check + lint + type-check (fast-fail)
inv format-check -f                  # format in-place (black + ruff + isort)
uv run pytest tests/test_orders.py   # single test file
uv run pytest -k "test_name"         # single test by name
```

Tests use SQLite in-memory and mock Redis -- no external services needed. Copy `.env.template` to `.env` before running the server or migrations.

## Architecture

**Stack:** FastAPI + SQLModel (SQLAlchemy async) + PostgreSQL + Redis/ARQ

**Entry point:** `deep_ice/__init__.py` creates the `FastAPI` app and the `TaskQueue` class (ARQ worker config). The lifespan opens/closes the Redis connection pool stored on `app.state.redis_pool`.

**Layers:**
- `deep_ice/api/routes/` -- thin HTTP handlers; dependencies injected via FastAPI `Depends`
- `deep_ice/services/` -- business logic (`CartService`, `OrderService`, `PaymentService`, `StatsService`)
- `deep_ice/models.py` -- all SQLModel table and schema models; `FetchMixin` adds a shared `fetch()` classmethod used instead of raw `select()` everywhere
- `deep_ice/core/` -- config (pydantic-settings), async DB engine/session, FastAPI dependency providers, JWT security

## Payment flow

This is the most non-obvious part of the codebase. See [docs/use-case.md](docs/use-case.md) for the end-to-end user flow.

`POST /v1/payments` creates an order from the cart then delegates to `PaymentService`:

- **CASH** -- synchronous; returns `201 Created` with `SUCCESS` status immediately
- **CARD** -- enqueues `make_payment_task` to ARQ and returns `202 Accepted` with `PENDING` status; the worker later calls `OrderService.confirm_order` or `cancel_order`
- **Insufficient stock** -- returns `307 Redirect` to `GET /v1/cart` after adjusting cart item quantities down to the current available stock

Stock reservation: when an order is created, `IceCream.blocked_quantity` is incremented to hold the units. `available_stock` is a computed property (`stock - blocked_quantity`). On `confirm_order`, both `stock` and `blocked_quantity` are decremented together. On `cancel_order`, only `blocked_quantity` is decremented.

**Concurrency:** the payments route acquires a Redis distributed lock per ice cream SKU (`ice-lock:<icecream_id>`) via `aioredlock` before checking stock and creating the order. This prevents overselling under concurrent requests. Tests replace `get_lock_manager` with a local `asyncio.Lock` stub.

**Stats:** `StatsService` maintains a Redis sorted set (`POPULAR_ICECREAM`) updated in `OrderService.confirm_order` via `zincrby`. Only called on confirmed orders, not pending/cancelled ones.

## Testing patterns

Tests use `httpx.AsyncClient` with `ASGITransport` against the live app. The DB is SQLite in-memory with `async_scoped_session` scoped per asyncio task. `app.state.redis_pool` and `StatsService._client` are mocked with `pytest-mock`. See `tests/conftest.py` for fixture setup.
