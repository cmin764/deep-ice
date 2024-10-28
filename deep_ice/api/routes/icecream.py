from fastapi import APIRouter

from deep_ice.core.dependencies import SessionDep
from deep_ice.models import IceCream, RetrieveIceCream

router = APIRouter()


@router.get("", response_model=list[RetrieveIceCream])
async def get_icecream(session: SessionDep):
    return (await IceCream.fetch(session)).all()
