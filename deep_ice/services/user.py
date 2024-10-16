from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from deep_ice.core.security import verify_password
from deep_ice.models import User


async def _get_user_by_email(*, session: AsyncSession, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = (await session.exec(statement)).one_or_none()
    return session_user


async def authenticate(
    *, session: AsyncSession, email: str, password: str
) -> User | None:
    db_user = await _get_user_by_email(session=session, email=email)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user
