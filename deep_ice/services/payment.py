import asyncio
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, cast

import sentry_sdk
from arq import Retry
from sqlmodel.ext.asyncio.session import AsyncSession

from deep_ice.core import logger
from deep_ice.core.config import settings
from deep_ice.core.database import get_async_session
from deep_ice.models import Order, Payment, PaymentMethod, PaymentStatus
from deep_ice.services.order import OrderService
from deep_ice.services.stats import stats_service


async def make_payment_task(
    ctx, order_id: int, amount: float, *, method: PaymentMethod, _stub_dict: dict
) -> str:
    from deep_ice import TaskQueue

    stub = PaymentStub(**_stub_dict)
    status = await stub.make_payment(order_id, amount, method=method)
    if status is PaymentStatus.FAILED:
        attempts = ctx["job_try"]
        if attempts >= TaskQueue.max_tries:
            msg = f"Gave up on {method.value} payment for order #{order_id}!"
            logger.error(msg)
            sentry_sdk.capture_message(msg, level="error")
        else:
            msg = f"{method.value} payment for order #{order_id} failed, retrying..."
            logger.warning(msg)
            sentry_sdk.capture_message(msg, level="warning")
            raise Retry(defer=attempts * settings.TASK_BACKOFF_FACTOR)

    async for session in get_async_session():
        order_service = OrderService(session, stats_service=stats_service)
        payment_service = PaymentService(
            session, order_service=order_service, payment_processor=stub
        )
        await payment_service.set_order_payment_status(order_id, status)
        if status is PaymentStatus.SUCCESS:
            await order_service.confirm_order(order_id)
        elif status is PaymentStatus.FAILED:
            await order_service.cancel_order(order_id)
        await session.commit()

    return status.value


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
    # Enable failures (or not) and at what rate.
    allow_failures: bool = False
    failure_rate: float = 0.2

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
        logger.info(
            "Initiating %s payment for order %d of amount $%f...",
            method.value,
            order_id,
            amount,
        )

        if method is PaymentMethod.CASH:
            # Cash payments are considered instant since the order has to be delivered
            #  first before being paid for. (paid at delivery time)
            return PaymentStatus.SUCCESS

        # Simulate payment processing times and potential for failure for card ones.
        wait_time = random.randint(self.min_delay, self.max_delay)
        logger.info("Processing payment, this may take up to %d seconds...", wait_time)
        await asyncio.sleep(wait_time)

        if self.allow_failures:
            # Simulate payment result: 80% chance of success, 20% chance of failure.
            payment_result = random.choices(
                [PaymentStatus.SUCCESS, PaymentStatus.FAILED],
                weights=[1 - self.failure_rate, self.failure_rate],
                k=1,
            )[0]
        else:
            payment_result = PaymentStatus.SUCCESS

        logger.info("Payment result: %s", payment_result.value)
        return payment_result

    async def make_payment_async(
        self, order_id: int, amount: float, *, method: PaymentMethod
    ) -> Literal[PaymentStatus.PENDING]:
        from deep_ice import app

        with sentry_sdk.start_transaction(name="payment-tasks"):
            await app.state.redis_pool.enqueue_job(
                make_payment_task.__name__,
                order_id,
                amount,
                method=method,
                _stub_dict=self.__dict__,
            )
        return PaymentStatus.PENDING


class PaymentService:
    """Manage payments in relation to orders."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        order_service: OrderService,
        payment_processor: PaymentInterface,
    ):
        self._session = session
        self._order_service = order_service
        self._payment_processor = payment_processor

    async def make_payment_from_order(
        self, order: Order, *, method: PaymentMethod
    ) -> Payment:
        make_payment = {
            PaymentMethod.CASH: self._payment_processor.make_payment,
            PaymentMethod.CARD: self._payment_processor.make_payment_async,
        }
        payment_status = await make_payment[method](
            cast(int, order.id), order.amount, method=method
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
            await self._order_service.confirm_order(cast(int, order.id))
        elif payment_status is PaymentStatus.FAILED:
            await self._order_service.cancel_order(cast(int, order.id))

        return payment

    async def set_order_payment_status(self, order_id: int, status: PaymentStatus):
        payment: Payment = (
            await Payment.fetch(self._session, filters=[Payment.order_id == order_id])
        ).one()
        payment.status = status
        self._session.add(payment)


payment_stub = PaymentStub(1, 3, allow_failures=True, failure_rate=0.2)
