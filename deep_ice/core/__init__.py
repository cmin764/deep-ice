import logging

from .config import settings

LOG_LEVEL = logging.getLevelName(settings.LOG_LEVEL)
# Basic configuration, applied only if the logger has not been configured before.
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("uvicorn.error")
logger.setLevel(LOG_LEVEL)
