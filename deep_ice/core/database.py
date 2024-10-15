from sqlmodel import create_engine

from deep_ice.core.config import settings

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI), echo=True, future=True)
