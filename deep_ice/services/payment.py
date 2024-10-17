import asyncio
import random
from dataclasses import dataclass

from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from deep_ice.models import Order, OrderItem, OrderStatus, PaymentMethod, PaymentStatus


class PaymentError(Exception):
    """Base class for immediate payment failures. (like invalid card info)"""


async def confirm_order(session: AsyncSession, order_id: int):
    order = (
        await session.exec(
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.items).selectinload(OrderItem.icecream))
        )
    ).one()
    order.status = OrderStatus.CONFIRMED
    session.add(order)

    for item in order.items:
        item.icecream.stock -= item.quantity
        item.icecream.blocked_quantity -= item.quantity
    session.add_all(order.items)


@dataclass
class PaymentServiceStub:
    """Dummy payment service which emulates IO blocking during order payment."""

    min_delay: int
    max_delay: int
    allow_failures: bool = False  # enable failures or not

    async def make_payment(
        self,
        order_id: int,
        amount: float,
        *,
        method: PaymentMethod,
        session: AsyncSession,
    ) -> PaymentStatus:
        """Simulate a simple payment service that takes some time to process a payment
        and then returns a status.
        This is blocking and the status will either be `SUCCESS` or `FAILED` when it
        finishes.

        Args:
            order_id: The ID of the order for which payment is being made.
            amount: The total amount to be charged. (in USD)
            method: The payment method to use. (CASH/CARD)
            session: The SQLAlchemy session object.

        Returns:
            A value indicating the payment status (either `SUCCESS` or `FAILED`).
        """
        print(
            f"Initiating {method.value} payment for order {order_id}"
            f" of amount ${amount}..."
        )

        if method is PaymentMethod.CASH:
            # Cash payments are considered instant since the order has to be delivered
            #  first before being paid for. (paid at delivery time)
            await confirm_order(session, order_id)
            return PaymentStatus.SUCCESS

        # Simulate payment processing times and potential for failure for card ones.
        wait_time = random.randint(self.min_delay, self.max_delay)
        print(f"Processing payment, this may take up to {wait_time} seconds...")
        await asyncio.sleep(wait_time)

        if self.allow_failures:
            # Simulate payment result: 80% chance of success, 20% chance of failure.
            payment_result = random.choices(
                [PaymentStatus.SUCCESS, PaymentStatus.FAILED], weights=[80, 20], k=1
            )[0]
        else:
            payment_result = PaymentStatus.SUCCESS

        print(f"Payment result: {payment_result}")
        if payment_result is PaymentStatus.SUCCESS:
            await confirm_order(session, order_id)
        return payment_result


payment_service = PaymentServiceStub(1, 3)
