import asyncio
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from sqlmodel.ext.asyncio.session import AsyncSession

from deep_ice.models import PaymentStatus, Order, PaymentMethod, Payment
from deep_ice.services.order import OrderService


class PaymentError(Exception):
    """Base class for immediate payment failures. (like invalid card info)"""


class PaymentInterface(ABC):

    @abstractmethod
    async def make_payment(
        self,
        order_id: int,
        amount: float,
        *,
        method: PaymentMethod,
    ) -> PaymentStatus:
        """Blocking method for making a payment."""

    @abstractmethod
    async def make_payment_async(
        self,
        order_id: int,
        amount: float,
        *,
        method: PaymentMethod,
    ) -> Literal[PaymentStatus.PENDING]:
        """Non-blocking method for making a payment."""


@dataclass
class PaymentStub(PaymentInterface):
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
    ) -> PaymentStatus:
        """Simulate a simple payment transaction that takes some time to process it
        and then return a status.
        This is blocking and the status will either be `SUCCESS` or `FAILED` when it
        finishes.

        Args:
            order_id: The ID of the order for which payment is being made.
            amount: The total amount to be charged. (in USD)
            method: The payment method to use. (CASH/CARD)

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
        return payment_result

    async def make_payment_async(
        self, order_id: int, amount: float, *, method: PaymentMethod
    ) -> Literal[PaymentStatus.PENDING]:
        # TODO(cmin764): Defer this to a task queue.
        await self.make_payment(order_id, amount, method=method)
        return PaymentStatus.PENDING


class PaymentService:
    """Manage payments in relation to orders."""

    def __init__(self, session: AsyncSession, payment_processor: PaymentInterface):
        self._session = session
        self._payment_processor = payment_processor

        self._order_service = OrderService(self._session)

    async def make_payment_from_order(
        self, order: Order, *, method: PaymentMethod
    ) -> Payment:
        make_payment = {
            PaymentMethod.CASH: self._payment_processor.make_payment,
            PaymentMethod.CARD: self._payment_processor.make_payment_async,
        }
        payment_status = await make_payment[method](
            order.id, order.amount, method=method
        )
        payment = Payment(
            order_id=order.id,
            user_id=order.user_id,
            amount=order.amount,
            status=payment_status,
            method=method,
        )
        self._session.add(payment)

        if payment_status is PaymentStatus.SUCCESS:
            await self._order_service.confirm_order(order.id)
        elif payment_status is PaymentStatus.FAILED:
            await self._order_service.cancel_order(order.id)

        return payment


payment_stub = PaymentStub(1, 3)
