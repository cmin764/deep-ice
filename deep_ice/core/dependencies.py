from typing import Annotated

import jwt
import sentry_sdk
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from deep_ice.core import security, logger
from deep_ice.core.config import settings
from deep_ice.core.database import get_async_session
from deep_ice.models import TokenPayload, User
from deep_ice.services.cart import CartService

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/access-token"
)

SessionDep = Annotated[AsyncSession, Depends(get_async_session)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


async def get_current_user(session: SessionDep, token: TokenDep) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload.model_validate(payload)
    except (InvalidTokenError, ValidationError) as exc:
        logger.exception("Invalid token: %s", exc)
        sentry_sdk.capture_exception(exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Couldn't validate credentials",
        )
    user: User | None = await session.get(User, int(token_data.sub))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
        )
    return user


async def get_cart_service(session: SessionDep) -> CartService:
    return CartService(session)


CurrentUserDep = Annotated[User, Depends(get_current_user)]
CartServiceDep = Annotated[CartService, Depends(get_cart_service)]
