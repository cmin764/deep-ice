from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from fastapi.routing import APIRoute

from deep_ice.api import api_router
from deep_ice.core.config import settings
from deep_ice.services import payment as payment_service


redis_settings = RedisSettings(host=settings.REDIS_HOST)


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


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)

app.include_router(api_router, prefix=settings.API_V1_STR)
