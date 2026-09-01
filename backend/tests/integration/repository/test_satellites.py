import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from luml.repositories.satellites import SatelliteRepository
from luml.schemas.satellite import (
    SatelliteCreate,
    SatellitePair,
    SatelliteRegenerateApiKey,
)
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import OrbitFixtureData


@pytest.mark.asyncio
async def test_create_satellite(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = SatelliteRepository(engine)

    satellite_data = SatelliteCreate(
        orbit_id=orbit.id, api_key_hash=str(uuid.uuid4()), name="test"
    )
    satellite = await repo.create_satellite(satellite_data)

    assert satellite
    assert satellite.orbit_id == orbit.id


@pytest.mark.asyncio
async def test_get_satellite(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = SatelliteRepository(engine)

    satellite_data = SatelliteCreate(
        orbit_id=orbit.id, api_key_hash=str(uuid.uuid4()), name="test"
    )
    satellite = await repo.create_satellite(satellite_data)

    fetched_satellite = await repo.get_satellite(satellite.id)

    assert fetched_satellite
    assert fetched_satellite.id == satellite.id


@pytest.mark.asyncio
async def test_get_satellite_not_found(
    create_database_and_apply_migrations: str,
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = SatelliteRepository(engine)

    fetched_satellite = await repo.get_satellite(uuid.uuid7())

    assert fetched_satellite is None


@pytest.mark.asyncio
async def test_get_satellite_get_satellite_by_hash(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = SatelliteRepository(engine)

    satellite_data = SatelliteCreate(
        orbit_id=orbit.id, api_key_hash=str(uuid.uuid4()), name="test"
    )
    satellite = await repo.create_satellite(satellite_data)

    fetched_satellite = await repo.get_satellite_by_hash(satellite_data.api_key_hash)

    assert fetched_satellite
    assert fetched_satellite.id == satellite.id


@pytest.mark.asyncio
async def test_regenerate_api_key_stops_the_old_key_authenticating(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = SatelliteRepository(engine)

    old_hash = str(uuid.uuid4())
    satellite = await repo.create_satellite(
        SatelliteCreate(orbit_id=orbit.id, api_key_hash=old_hash, name="test")
    )

    new_hash = str(uuid.uuid4())
    updated = await repo.update_satellite(
        SatelliteRegenerateApiKey(id=satellite.id, api_key_hash=new_hash)
    )

    assert updated
    assert await repo.get_satellite_by_hash(old_hash) is None
    reauthenticated = await repo.get_satellite_by_hash(new_hash)
    assert reauthenticated
    assert reauthenticated.id == satellite.id


@pytest.mark.asyncio
async def test_list_satellites(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = SatelliteRepository(engine)

    satellite_data = SatelliteCreate(
        orbit_id=orbit.id, api_key_hash=str(uuid.uuid4()), name="test"
    )
    satellite = await repo.create_satellite(satellite_data)

    fetched_satellites = await repo.list_satellites(orbit.id)

    assert len(fetched_satellites) == 1
    assert fetched_satellites[0].id == satellite.id


@pytest.mark.asyncio
async def test_pair_satellite(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = SatelliteRepository(engine)

    satellite_data = SatelliteCreate(
        orbit_id=orbit.id, api_key_hash=str(uuid.uuid4()), name="test"
    )
    satellite = await repo.create_satellite(satellite_data)

    base_url = "https://test-satellite.com"
    capabilities: dict[str, dict[str, Any]] = {
        "deploy": {"version": 1, "config": "value"}
    }
    openapi = {
        "openapi": "3.1.0",
        "paths": {"/health": {"get": {"summary": "Health"}}},
    }

    satellite_pair = SatellitePair(
        id=satellite.id,
        base_url=str(base_url),
        capabilities=capabilities,
        openapi=openapi,
        paired=True,
        last_seen_at=datetime.now(UTC),
    )

    paired_satellite = await repo.pair_satellite(satellite_pair)

    assert paired_satellite
    assert paired_satellite.id == satellite.id
    assert paired_satellite.paired is True
    assert paired_satellite.base_url == base_url
    assert paired_satellite.capabilities == capabilities
    assert paired_satellite.last_seen_at is not None
    assert await repo.get_satellite_openapi(satellite.id) == openapi
    assert "openapi" not in paired_satellite.model_dump()

    listed_satellites = await repo.list_satellites(orbit.id)
    fetched_satellite = await repo.get_satellite(satellite.id)

    assert "openapi" not in listed_satellites[0].model_dump()
    assert fetched_satellite is not None
    assert "openapi" not in fetched_satellite.model_dump()

    await repo.pair_satellite(
        SatellitePair(
            id=satellite.id,
            base_url=str(base_url),
            capabilities=capabilities,
            openapi=None,
            paired=True,
            last_seen_at=datetime.now(UTC),
        )
    )

    assert await repo.get_satellite_openapi(satellite.id) is None


@pytest.mark.asyncio
async def test_list_tasks_empty(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = SatelliteRepository(engine)

    tasks = await repo.list_tasks(uuid.uuid7())

    assert len(tasks) == 0


@pytest.mark.asyncio
async def test_touch_last_seen(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit

    repo = SatelliteRepository(engine)
    satellite_data = SatelliteCreate(
        orbit_id=orbit.id, api_key_hash=str(uuid.uuid4()), name="test"
    )
    satellite = await repo.create_satellite(satellite_data)

    original_last_seen = satellite.last_seen_at
    assert original_last_seen is None

    await repo.touch_last_seen(satellite.id)
    seen_satellite = await repo.get_satellite(satellite.id)

    assert seen_satellite
    assert seen_satellite.last_seen_at is not None
    assert seen_satellite.last_seen_at != original_last_seen
