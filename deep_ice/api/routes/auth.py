from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from deep_ice.core import security
from deep_ice.core.dependencies import SessionDep
from deep_ice.models import Token
from deep_ice.services import user as user_service

router = APIRouter()


@router.post("/access-token")
async def get_access_token(
    session: SessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    """Generates an access token after logging in the user."""
    user = await user_service.authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    elif not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
        )
    return Token(access_token=security.create_access_token(user))
