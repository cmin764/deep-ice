from fastapi import APIRouter

from deep_ice.core.dependencies import CurrentUserDep, SessionDep
from deep_ice.models import Order, RetrieveOrder, OrderItem

router = APIRouter()


@router.get("", response_model=list[RetrieveOrder])
async def get_orders(session: SessionDep, current_user: CurrentUserDep):
    orders = (
        (
            await Order.fetch(
                session,
                filters=[Order.user_id == current_user.id],
                joinedloads=[Order.items, OrderItem.icecream],
            )
        )
        .unique()
        .all()
    )
    return orders
