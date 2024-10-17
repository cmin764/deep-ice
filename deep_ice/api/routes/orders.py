from fastapi import APIRouter
from sqlalchemy.orm import selectinload
from sqlmodel import select

from deep_ice.core.dependencies import CurrentUserDep, SessionDep
from deep_ice.models import Order, RetrieveOrder

router = APIRouter()


@router.get("", response_model=list[RetrieveOrder])
async def get_orders(session: SessionDep, current_user: CurrentUserDep):
    user_orders_select = (
        select(Order)
        .where(Order.user_id == current_user.id)
        .options(selectinload(Order.items))
    )
    orders = (await session.exec(user_orders_select)).all()
    return orders
