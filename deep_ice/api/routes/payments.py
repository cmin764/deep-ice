from typing import Annotated

from fastapi import APIRouter, Body, Response, Request, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from deep_ice.core.dependencies import CurrentUserDep, SessionDep
from deep_ice.models import (
    RetrievePayment,
    PaymentMethod,
    Cart,
    CartItem,
    Payment,
    Order,
    OrderItem,
    OrderStatus,
)
from deep_ice.services.payment import payment_service

router = APIRouter()


async def _make_order_from_cart(
    session: AsyncSession, cart: Cart, *, user_id: int
) -> Order:
    # Create and save an order out of the current cart and return it for later usage.
    order = Order(user_id=user_id, status=OrderStatus.PENDING)
    session.add(order)
    await session.commit()
    await session.refresh(order)

    try:
        for cart_item in cart.items:
            icecream = cart_item.icecream
            icecream.blocked_quantity += cart_item.quantity
            session.add(icecream)

            order_item = OrderItem(
                icecream_id=icecream.id,
                order_id=order.id,
                quantity=cart_item.quantity,
                total_price=cart_item.quantity * icecream.price,
            )
            order.items.append(order_item)

        session.add_all(order.items)
    except SQLAlchemyError:
        await session.rollback()
        await session.delete(order)
        await session.commit()
        raise

    return order


@router.post("", response_model=RetrievePayment)
async def make_payment(
    session: SessionDep,
    current_user: CurrentUserDep,
    method: Annotated[PaymentMethod, Body(embed=True)],
    request: Request,
    response: Response,
):
    statement = (
        select(Cart)
        .where(Cart.user_id == current_user.id)
        .options(selectinload(Cart.items).selectinload(CartItem.icecream))
    )
    cart: Cart = (await session.exec(statement)).one_or_none()
    if not cart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item does not exist"
        )

    # Ensure once again that we still have on stock the items we intend to buy.
    reduced = False
    for item in cart.items:
        if item.quantity > item.icecream.available_stock:
            item.quantity = item.icecream.available_stock
            session.add(item)
            reduced = True
    if reduced:
        # Redirect back to the cart so we get aware of the new state based on the
        #  available stock. And let the user decide if it continues with a payment.
        await session.commit()
        return RedirectResponse(url=request.url_for("get_cart_items"))

    # Items are available and ready to be sold, make the order and pay for it.
    try:
        order = await _make_order_from_cart(session, cart, user_id=current_user.id)
        payment_status = payment_service.make_payment(
            order.id, order.amount, method=method
        )
        payment = Payment(
            order_id=order.id,
            user_id=current_user.id,
            amount=order.amount,
            status=payment_status,
            method=method,
        )
        session.add(payment)
    except SQLAlchemyError as exc:
        # TODO(cmin764): Add proper logging and capture exception in Sentry.
        print("Payment error: ", exc)
        await session.rollback()
    else:
        await session.commit()
