from typing import Annotated, cast

import sentry_sdk
from fastapi import APIRouter, Body, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import SQLAlchemyError

from deep_ice.core import logger
from deep_ice.core.dependencies import CartServiceDep, CurrentUserDep, SessionDep
from deep_ice.models import PaymentMethod, PaymentStatus, RetrievePayment
from deep_ice.services.order import OrderService
from deep_ice.services.payment import PaymentError, PaymentService, payment_stub
from deep_ice.services.stats import stats_service

router = APIRouter()


@router.post("", response_model=RetrievePayment)
async def make_payment(
    session: SessionDep,
    current_user: CurrentUserDep,
    cart_service: CartServiceDep,
    method: Annotated[PaymentMethod, Body(embed=True)],
    request: Request,
    response: Response,
):
    # FIXME(cmin764): Check if we need an async Lock primitive here in order to allow
    #  only one user to submit an order at a time. (based on available stock check)
    cart = await cart_service.get_cart(cast(int, current_user.id))
    if not cart or not cart.items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="There are no items in the cart",
        )

    cart_ok = await cart_service.check_items_against_stock(cart)
    if not cart_ok:
        # Redirect back to the cart so we get aware of the new state based on the
        #  available stock. And let the user decide if it continues with a payment.
        return RedirectResponse(url=request.url_for("get_cart_items"))

    # Items are available and ready to be sold, make the order and pay for it.
    order_service = OrderService(session, stats_service=stats_service)
    payment_service = PaymentService(
        session, order_service=order_service, payment_processor=payment_stub
    )
    order = None
    try:
        order = await order_service.make_order_from_cart(cart)
        payment = await payment_service.make_payment_from_order(order, method=method)
        # With a payment triggered over a successfully created order, we can safely
        #  delete the cart and all its contents.
        await session.delete(cart)
    except (SQLAlchemyError, PaymentError) as exc:
        logger.exception("Payment error: %s", exc)
        sentry_sdk.capture_exception(exc)
        await session.rollback()
        if order:
            await session.delete(order)
            await session.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Payment failed"
        )
    else:
        await session.commit()
        response.status_code = (
            status.HTTP_202_ACCEPTED
            if payment.status == PaymentStatus.PENDING
            else status.HTTP_201_CREATED
        )
        return payment


@router.get("", response_model=list[RetrievePayment])
async def get_payments(current_user: CurrentUserDep):
    return await current_user.awaitable_attrs.payments
