from fastapi import APIRouter
from sqlmodel import select

from deep_ice.core.dependencies import SessionDep
from deep_ice.models import IceCream, RetrieveIceCream

router = APIRouter()


@router.get("", response_model=list[RetrieveIceCream])
async def get_icecream(session: SessionDep):
    results = await session.exec(select(IceCream))
    return results.all()
