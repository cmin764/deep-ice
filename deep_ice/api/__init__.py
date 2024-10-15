from fastapi import APIRouter

from deep_ice.api.routes import auth, icecream

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(icecream.router, prefix="/icecream", tags=["icecream"])
