from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, status, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from deep_ice.core.dependencies import CurrentUserDep, SessionDep
from deep_ice.models import (
    Cart,
    CartItem,
    RetrieveCart,
    CreateCartItem,
    RetrieveCartItem,
    IceCream,
)

router = APIRouter()


async def _ensure_cart(session: AsyncSession, *, user_id: int) -> Cart:
    statement = (
        select(Cart)
        .where(Cart.user_id == user_id)
        .options(selectinload(Cart.items).selectinload(CartItem.icecream))
    )
    cart = (await session.exec(statement)).one_or_none()
    if not cart:
        cart = Cart(user_id=user_id)
        session.add(cart)
        await session.commit()

    return cart


async def _check_stock(session: AsyncSession, *, cart_item) -> IceCream:
    # Retrieves the icecream from the item in the cart and checks if the added stock
    #  is viable. Then returns the corresponding icecream object.
    query_icecream = select(IceCream).where(IceCream.id == cart_item.icecream_id)
    icecream = (await session.exec(query_icecream)).one_or_none()
    if not icecream:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Icecream does not exist"
        )
    if cart_item.quantity > icecream.available_stock:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Not enough available stock"
        )
    return icecream


@router.get("", response_model=RetrieveCart)
async def get_cart_items(session: SessionDep, current_user: CurrentUserDep):
    cart = await _ensure_cart(session, user_id=current_user.id)
    return cart


@router.post("/items", response_model=RetrieveCartItem)
async def add_item_to_cart(
    session: SessionDep,
    current_user: CurrentUserDep,
    item: Annotated[CreateCartItem, Body()],
    response: Response,
):
    cart = await _ensure_cart(session, user_id=current_user.id)
    cart_item = CartItem(cart_id=cart.id, **item.model_dump())
    icecream = await _check_stock(session, cart_item=cart_item)

    try:
        session.add(cart_item)
        await session.commit()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Item already exists"
        )
    else:
        cart_item.icecream = icecream

    response.status_code = status.HTTP_201_CREATED
    return cart_item


@router.put("/items/{item_id:int}", response_model=RetrieveCartItem | None)
async def update_cart_item(
    session: SessionDep,
    current_user: CurrentUserDep,
    item_id: int,
    quantity: Annotated[int, Body(ge=0, embed=True)],
    response: Response,
):
    query_cart_item = (
        select(CartItem)
        .where(CartItem.id == item_id)
        .join(Cart)
        .where(Cart.user_id == current_user.id)
        .options(selectinload(CartItem.icecream))
    )
    cart_item: CartItem = (await session.exec(query_cart_item)).one_or_none()
    if not cart_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item does not exist"
        )

    if quantity:
        cart_item.quantity = quantity
        await _check_stock(session, cart_item=cart_item)
        session.add(cart_item)
        await session.commit()
        await session.refresh(cart_item)
        return cart_item
    else:
        await session.delete(cart_item)
        await session.commit()
        response.status_code = status.HTTP_204_NO_CONTENT
        return None
