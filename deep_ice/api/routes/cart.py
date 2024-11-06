from typing import Annotated, cast

from fastapi import APIRouter, Body, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError

from deep_ice.core.dependencies import CartServiceDep, CurrentUserDep, SessionDep
from deep_ice.models import (
    Cart,
    CartItem,
    CreateCartItem,
    IceCream,
    RetrieveCart,
    RetrieveCartItem,
)

router = APIRouter()


async def obtain_icecream(session, cart_item: CartItem) -> IceCream:
    # Retrieves the icecream from the item in the cart and checks if the added stock
    #  is viable. Then returns the corresponding icecream object.
    icecream = (
        await IceCream.fetch(session, filters=[IceCream.id == cart_item.icecream_id])
    ).one_or_none()
    if not icecream:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Icecream does not exist"
        )
    if not icecream.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Inactive icecream flavor"
        )
    if cart_item.quantity > icecream.available_stock:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Not enough available stock"
        )
    return icecream


@router.get("", response_model=RetrieveCart)
async def get_cart_items(current_user: CurrentUserDep, cart_service: CartServiceDep):
    cart = await cart_service.ensure_cart(cast(int, current_user.id))
    return cart


@router.post("/items", response_model=RetrieveCartItem)
async def add_item_to_cart(
    session: SessionDep,
    current_user: CurrentUserDep,
    cart_service: CartServiceDep,
    item: Annotated[CreateCartItem, Body()],
    response: Response,
):
    cart = await cart_service.ensure_cart(cast(int, current_user.id))
    cart_item = CartItem(cart_id=cart.id, **item.model_dump())
    icecream = await obtain_icecream(session, cart_item=cart_item)

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
    cart_item: CartItem | None = (
        await CartItem.fetch(
            session,
            filters=[CartItem.id == item_id, Cart.user_id == current_user.id],
            joins=[Cart],
            joinedloads=[CartItem.icecream],
        )
    ).one_or_none()
    if not cart_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item does not exist"
        )

    if quantity:
        cart_item.quantity = quantity
        await obtain_icecream(session, cart_item=cart_item)
        session.add(cart_item)
        await session.commit()
        await session.refresh(cart_item)
        return cart_item
    else:
        await session.delete(cart_item)
        await session.commit()
        response.status_code = status.HTTP_204_NO_CONTENT
        return None
