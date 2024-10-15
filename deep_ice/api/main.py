from fastapi import APIRouter

from deep_ice.api.routes import icecream

api_router = APIRouter()
api_router.include_router(icecream.router, prefix="/icecream", tags=["icecream"])
