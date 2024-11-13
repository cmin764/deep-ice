from contextlib import asynccontextmanager

import sentry_sdk
from arq import create_pool
from fastapi import FastAPI
from fastapi.routing import APIRoute
from sentry_sdk.integrations.asyncio import AsyncioIntegration

from deep_ice.api import api_router
from deep_ice.core.config import redis_settings, settings
from deep_ice.services import payment as payment_service


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


@asynccontextmanager
async def lifespan(fast_app: FastAPI):
    redis_pool = await create_pool(redis_settings)
    fast_app.state.redis_pool = redis_pool
    yield
    await redis_pool.close()


class TaskQueue:
    functions = [payment_service.make_payment_task]
    redis_settings = redis_settings
    max_tries = settings.TASK_MAX_RETRIES
    retry_delay = settings.TASK_RETRY_DELAY


if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        # Set traces_sample_rate to 1.0 to capture 100%
        #  of transactions for tracing. (or lower in production)
        traces_sample_rate=settings.SENTRY_SAMPLE_RATE,
        _experiments={
            # Set this to True to automatically start the profiler when possible.
            "continuous_profiling_auto_start": True,
        },
        integrations=[
            # ARQ and FastAPI integrations are automatically added.
            AsyncioIntegration(),
        ],
    )

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)
app.include_router(api_router, prefix=settings.API_V1_STR)
