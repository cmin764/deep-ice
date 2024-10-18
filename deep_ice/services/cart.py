from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from deep_ice.models import Cart, CartItem


class CartService:
    """Manage the cart and its content."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_cart(self, user_id: int) -> Cart:
        query_cart = (
            select(Cart)
            .where(Cart.user_id == user_id)
            .options(selectinload(Cart.items).selectinload(CartItem.icecream))
        )
        cart: Cart = (await self._session.exec(query_cart)).one_or_none()
        return cart

    async def ensure_cart(self, user_id: int) -> Cart:
        cart = await self.get_cart(user_id)
        if not cart:
            cart = Cart(user_id=user_id)
            self._session.add(cart)
            await self._session.commit()
            await self._session.refresh(cart)
            cart.items = await cart.awaitable_attrs.items

        return cart

    async def check_items_against_stock(self, cart: Cart) -> bool:
        # Ensure once again that we still have on stock the items we intend to buy.
        cart_ok = True
        for item in cart.items:
            if item.quantity > item.icecream.available_stock:
                item.quantity = item.icecream.available_stock
                self._session.add(item)
                cart_ok = False
        if not cart_ok:
            await self._session.commit()

        return cart_ok
