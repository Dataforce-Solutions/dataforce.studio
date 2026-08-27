from typing import TYPE_CHECKING

from luml_api._types import AsyncSatellite, Satellite

if TYPE_CHECKING:
    from luml_api._client import AsyncLumlClient, LumlClient


class SatelliteResource:
    def __init__(self, client: "LumlClient") -> None:
        self._client = client

    def _path(self, satellite_id: str) -> str:
        return (
            f"/v1/organizations/{self._client.organization}"
            f"/orbits/{self._client.orbit}/satellites/{satellite_id}"
        )

    def get(self, satellite_id: str) -> Satellite:
        path = self._path(satellite_id)
        satellite = Satellite.model_validate(self._client.get(path))
        satellite._bind(self._client, f"{path}/openapi")
        return satellite


class AsyncSatelliteResource:
    def __init__(self, client: "AsyncLumlClient") -> None:
        self._client = client

    def _path(self, satellite_id: str) -> str:
        return (
            f"/v1/organizations/{self._client.organization}"
            f"/orbits/{self._client.orbit}/satellites/{satellite_id}"
        )

    async def get(self, satellite_id: str) -> AsyncSatellite:
        path = self._path(satellite_id)
        satellite = AsyncSatellite.model_validate(await self._client.get(path))
        satellite._bind(self._client, f"{path}/openapi")
        return satellite
