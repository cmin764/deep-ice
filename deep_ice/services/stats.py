from abc import ABC, abstractmethod
from collections import OrderedDict

import redis.asyncio as redis

from deep_ice.core.config import redis_settings


class StatsInterface(ABC):

    @abstractmethod
    async def acknowledge_icecream_demand(
        self, icecream_id: int, *, name: str, quantity: int
    ):
        """Count the number of successful ordered items of a given product."""

    @abstractmethod
    async def get_top_icecream(self, size: int = 1) -> OrderedDict[str, int]:
        """Retrieve an ordered dictionary with the top ordered icecream brands."""


class StatsService(StatsInterface):

    POPULARITY_KEY = "POPULAR_ICECREAM"

    def __init__(self):
        self._client = redis.Redis(host=redis_settings.host)

    @staticmethod
    def _get_product_key(*args: int | str) -> str:
        return ":".join(map(str, args))

    async def acknowledge_icecream_demand(
        self, icecream_id: int, *, name: str, quantity: int
    ):
        key = self._get_product_key(name, icecream_id)
        await self._client.zincrby(self.POPULARITY_KEY, quantity, key)

    async def get_top_icecream(self, size: int = 1) -> OrderedDict[str, int]:
        top_ice = await self._client.zrevrange(
            self.POPULARITY_KEY, 0, size - 1, withscores=True
        )
        popular_ice = OrderedDict()
        for name, score in top_ice:
            brand = name.decode().split(":")[0]
            popular_ice[brand] = score
        return popular_ice


stats_service = StatsService()
