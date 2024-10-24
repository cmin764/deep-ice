from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from deep_ice.models import Order, OrderItem, OrderStatus, Cart
from deep_ice.services.stats import StatsInterface


class OrderService:
    """Manage orders, their status and ice cream stock implications."""

    def __init__(self, session: AsyncSession, *, stats_service: StatsInterface):
        self._session = session
        self._stats_service = stats_service

    async def _get_order(self, order_id: int) -> Order:
        order = (
            await self._session.exec(
                select(Order)
                .where(Order.id == order_id)
                .options(selectinload(Order.items).selectinload(OrderItem.icecream))
            )
        ).one()
        return order

    async def confirm_order(self, order_id: int):
        order = await self._get_order(order_id)
        order.status = OrderStatus.CONFIRMED
        self._session.add(order)

        for item in order.items:
            item.icecream.stock -= item.quantity
            item.icecream.blocked_quantity -= item.quantity
            await self._stats_service.acknowledge_icecream_demand(
                item.icecream_id, name=item.icecream.name, quantity=item.quantity
            )

        self._session.add_all(order.items)

    async def cancel_order(self, order_id: int):
        order = await self._get_order(order_id)
        order.status = OrderStatus.CANCELLED
        self._session.add(order)

        for item in order.items:
            item.icecream.blocked_quantity -= item.quantity
        self._session.add_all(order.items)

    async def make_order_from_cart(self, cart: Cart) -> Order:
        # Create and save an order out of the current cart and return it for later usage.
        order = Order(user_id=cart.user_id, status=OrderStatus.PENDING)
        self._session.add(order)
        await self._session.commit()
        await self._session.refresh(order)

        try:
            order_items = await order.awaitable_attrs.items
            for cart_item in cart.items:
                icecream = cart_item.icecream
                # NOTE(cmin764): Make sure to deduct this blocked amount from the main
                #  stock once the order gets confirmed.
                icecream.blocked_quantity += cart_item.quantity
                self._session.add(icecream)

                order_item = OrderItem(
                    icecream_id=icecream.id,
                    order_id=order.id,
                    quantity=cart_item.quantity,
                    total_price=cart_item.quantity * icecream.price,
                )
                order_items.append(order_item)

            self._session.add_all(order_items)
        except SQLAlchemyError:
            await self._session.rollback()
            await self._session.delete(order)
            await self._session.commit()
            raise

        return order
