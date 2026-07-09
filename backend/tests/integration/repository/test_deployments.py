import uuid

import pytest
from luml.repositories.deployments import DeploymentRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.satellites import SatelliteRepository
from luml.schemas.deployment import (
    Deployment,
    DeploymentCreate,
    DeploymentDetailsUpdate,
    DeploymentStatus,
    DeploymentUpdate,
    MonitoringMode,
)
from luml.schemas.orbit import OrbitCreateIn, OrbitDetails
from luml.schemas.satellite import (
    Satellite,
    SatelliteCreate,
    SatelliteTaskStatus,
    SatelliteTaskType,
)

from tests.conftest import SatelliteFixtureData


async def _create_sibling_orbit(data: SatelliteFixtureData) -> OrbitDetails:
    orbit = await OrbitRepository(data.engine).create_orbit(
        data.organization.id,
        OrbitCreateIn(name="sibling orbit", bucket_secret_id=data.bucket_secret.id),
    )
    assert orbit is not None
    return orbit


async def _create_satellite_in(
    data: SatelliteFixtureData, orbit: OrbitDetails
) -> Satellite:
    return await SatelliteRepository(data.engine).create_satellite(
        SatelliteCreate(
            orbit_id=orbit.id, api_key_hash=str(uuid.uuid4()), name="sibling satellite"
        )
    )


async def _create_deployment(data: SatelliteFixtureData) -> Deployment:
    deployment, _ = await DeploymentRepository(data.engine).create_deployment(
        DeploymentCreate(
            name="my-deployment",
            orbit_id=data.orbit.id,
            satellite_id=data.satellite.id,
            artifact_id=data.model.id,
            status=DeploymentStatus.DELETION_PENDING,
        )
    )
    return deployment


@pytest.mark.asyncio
async def test_create_deployment(create_satellite: SatelliteFixtureData) -> None:
    data = create_satellite
    engine, orbit, model, satellite = (
        data.engine,
        data.orbit,
        data.model,
        data.satellite,
    )
    repo = DeploymentRepository(engine)

    deployment_data = DeploymentCreate(
        name="my-deployment",
        orbit_id=orbit.id,
        satellite_id=satellite.id,
        artifact_id=model.id,
        status=DeploymentStatus.PENDING,
        created_by_user="test_user",
        tags=["test", "deployment"],
    )
    deployment, task = await repo.create_deployment(deployment_data)

    assert deployment
    assert deployment.orbit_id == deployment_data.orbit_id
    assert deployment.satellite_id == deployment_data.satellite_id
    assert deployment.artifact_id == deployment_data.artifact_id
    assert deployment.collection_id == model.collection_id
    assert deployment.status == DeploymentStatus.PENDING

    assert task
    assert task.satellite_id == deployment_data.satellite_id
    assert task.orbit_id == deployment_data.orbit_id
    assert task.type == SatelliteTaskType.DEPLOY
    assert task.payload["deployment_id"] == str(deployment.id)


@pytest.mark.asyncio
async def test_get_deployment(create_satellite: SatelliteFixtureData) -> None:
    data = create_satellite
    engine, orbit, model, satellite = (
        data.engine,
        data.orbit,
        data.model,
        data.satellite,
    )
    repo = DeploymentRepository(engine)

    deployment_data = DeploymentCreate(
        name="my-deployment",
        orbit_id=orbit.id,
        satellite_id=satellite.id,
        artifact_id=model.id,
        status=DeploymentStatus.PENDING,
        created_by_user="test_user",
        tags=["test", "deployment"],
    )
    deployment, _ = await repo.create_deployment(deployment_data)

    fetched_deployment = await repo.get_deployment(deployment.id, orbit.id)

    assert fetched_deployment
    assert fetched_deployment.id == deployment.id
    assert fetched_deployment.orbit_id == deployment_data.orbit_id
    assert fetched_deployment.satellite_id == deployment_data.satellite_id
    assert fetched_deployment.collection_id == model.collection_id


@pytest.mark.asyncio
async def test_list_deployments(create_satellite: SatelliteFixtureData) -> None:
    data = create_satellite
    engine, orbit, model, satellite = (
        data.engine,
        data.orbit,
        data.model,
        data.satellite,
    )
    repo = DeploymentRepository(engine)

    deployment_data = DeploymentCreate(
        name="my-deployment",
        orbit_id=orbit.id,
        satellite_id=satellite.id,
        artifact_id=model.id,
        status=DeploymentStatus.PENDING,
        created_by_user="test_user",
        tags=["test", "deployment"],
    )

    created_dep1, _ = await repo.create_deployment(deployment_data)

    deployment_data.status = DeploymentStatus.ACTIVE
    created_dep2, _ = await repo.create_deployment(deployment_data)

    deployments = await repo.list_deployments(orbit.id)

    assert len(deployments) == 2
    deployment_ids = [d.id for d in deployments]
    assert created_dep1.id in deployment_ids
    assert created_dep2.id in deployment_ids
    for d in deployments:
        assert d.collection_id == model.collection_id


@pytest.mark.asyncio
async def test_list_satellite_deployments(
    create_satellite: SatelliteFixtureData,
) -> None:
    data = create_satellite
    engine, orbit, model, satellite = (
        data.engine,
        data.orbit,
        data.model,
        data.satellite,
    )
    repo = DeploymentRepository(engine)
    deployments_num = 4
    deployments = []

    for _ in range(deployments_num):
        deployment, _ = await repo.create_deployment(
            DeploymentCreate(
                name="my-deployment",
                orbit_id=orbit.id,
                satellite_id=satellite.id,
                artifact_id=model.id,
                status=DeploymentStatus.PENDING,
            )
        )
        deployments.append(deployment)

    all_deployments = await repo.list_satellite_deployments(satellite.id)
    ids = [d.id for d in all_deployments]
    assert len(all_deployments) == deployments_num
    assert all(dep.id in ids for dep in deployments)
    assert all(d.collection_id == model.collection_id for d in all_deployments)


@pytest.mark.asyncio
async def test_update_deployment(create_satellite: SatelliteFixtureData) -> None:
    data = create_satellite
    engine, orbit, model, satellite = (
        data.engine,
        data.orbit,
        data.model,
        data.satellite,
    )
    repo = DeploymentRepository(engine)

    deployment_data = DeploymentCreate(
        name="my-deployment",
        orbit_id=orbit.id,
        satellite_id=satellite.id,
        artifact_id=model.id,
        status=DeploymentStatus.PENDING,
        tags=["original"],
    )
    created_deployment, _ = await repo.create_deployment(deployment_data)

    update_data = DeploymentUpdate(
        id=created_deployment.id,
        inference_url=f"https://test-inference{uuid.uuid4()}.com/api",
        status=DeploymentStatus.ACTIVE,
        tags=["updated", "active"],
    )
    updated_deployment = await repo.update_deployment(
        created_deployment.id, satellite.id, update_data
    )

    assert updated_deployment
    assert updated_deployment.id == created_deployment.id
    assert updated_deployment.inference_url == update_data.inference_url
    assert updated_deployment.status == update_data.status
    assert updated_deployment.tags == update_data.tags
    assert updated_deployment.collection_id == model.collection_id


@pytest.mark.asyncio
async def test_update_deployment_details(
    create_satellite: SatelliteFixtureData,
) -> None:
    data = create_satellite
    engine, orbit, model, satellite = (
        data.engine,
        data.orbit,
        data.model,
        data.satellite,
    )
    repo = DeploymentRepository(engine)

    created_deployment, _ = await repo.create_deployment(
        DeploymentCreate(
            name="my-deployment",
            orbit_id=orbit.id,
            satellite_id=satellite.id,
            artifact_id=model.id,
            status=DeploymentStatus.PENDING,
            tags=["original"],
        )
    )

    details = DeploymentDetailsUpdate(
        name="my-deployment",
        description="some desc",
        dynamic_attributes_secrets={"token": str(uuid.uuid7())},
        tags=["one", "two"],
    )

    updated = await repo.update_deployment_details(
        orbit.id, created_deployment.id, details
    )

    assert updated is not None
    assert updated.id == created_deployment.id
    assert updated.name == details.name
    assert updated.description == details.description
    assert updated.dynamic_attributes_secrets == details.dynamic_attributes_secrets
    assert updated.tags == details.tags
    assert updated.collection_id == model.collection_id


@pytest.mark.asyncio
async def test_update_monitoring_mode_enqueues_reconcile(
    create_satellite: SatelliteFixtureData,
) -> None:
    data = create_satellite
    engine, orbit, model, satellite = (
        data.engine,
        data.orbit,
        data.model,
        data.satellite,
    )
    repo = DeploymentRepository(engine)
    sat_repo = SatelliteRepository(engine)

    created, _ = await repo.create_deployment(
        DeploymentCreate(
            name="my-deployment",
            orbit_id=orbit.id,
            satellite_id=satellite.id,
            artifact_id=model.id,
            monitoring_mode=MonitoringMode.OFF,
        )
    )

    updated = await repo.update_deployment_details(
        orbit.id,
        created.id,
        DeploymentDetailsUpdate(monitoring_mode=MonitoringMode.FULL),
    )

    assert updated is not None
    assert updated.monitoring_mode == MonitoringMode.FULL

    tasks = await sat_repo.list_tasks(satellite.id)
    reconcile_tasks = [t for t in tasks if t.type == SatelliteTaskType.RECONCILE]
    assert len(reconcile_tasks) == 1
    assert reconcile_tasks[0].payload["deployment_id"] == str(created.id)


@pytest.mark.asyncio
async def test_update_details_without_mode_change_no_reconcile(
    create_satellite: SatelliteFixtureData,
) -> None:
    data = create_satellite
    engine, orbit, model, satellite = (
        data.engine,
        data.orbit,
        data.model,
        data.satellite,
    )
    repo = DeploymentRepository(engine)
    sat_repo = SatelliteRepository(engine)

    created, _ = await repo.create_deployment(
        DeploymentCreate(
            name="my-deployment",
            orbit_id=orbit.id,
            satellite_id=satellite.id,
            artifact_id=model.id,
            monitoring_mode=MonitoringMode.FULL,
        )
    )

    # Same mode + unrelated field change must not enqueue a reconcile task.
    await repo.update_deployment_details(
        orbit.id,
        created.id,
        DeploymentDetailsUpdate(description="new", monitoring_mode=MonitoringMode.FULL),
    )

    tasks = await sat_repo.list_tasks(satellite.id)
    assert [t for t in tasks if t.type == SatelliteTaskType.RECONCILE] == []


@pytest.mark.asyncio
async def test_request_deployment_deletion(
    create_satellite: SatelliteFixtureData,
) -> None:
    data = create_satellite
    engine, orbit, model, satellite = (
        data.engine,
        data.orbit,
        data.model,
        data.satellite,
    )
    repo = DeploymentRepository(engine)

    created, _ = await repo.create_deployment(
        DeploymentCreate(
            name="my-deployment",
            orbit_id=orbit.id,
            satellite_id=satellite.id,
            artifact_id=model.id,
            status=DeploymentStatus.PENDING,
        )
    )

    result = await repo.request_deployment_deletion(orbit.id, created.id)
    assert result is not None
    dep, task = result
    assert dep.status == DeploymentStatus.DELETION_PENDING
    assert dep.collection_id == model.collection_id
    assert task is not None
    assert task.type == SatelliteTaskType.UNDEPLOY
    assert task.payload["deployment_id"] == str(created.id)

    result2 = await repo.request_deployment_deletion(orbit.id, created.id)
    assert result2 is not None
    dep2, task2 = result2
    assert dep2.status == DeploymentStatus.DELETION_PENDING
    assert task2 is None


@pytest.mark.asyncio
async def test_enqueue_undeploy_task(create_satellite: SatelliteFixtureData) -> None:
    data = create_satellite
    engine, orbit, model, satellite = (
        data.engine,
        data.orbit,
        data.model,
        data.satellite,
    )
    repo = DeploymentRepository(engine)

    deployment, _ = await repo.create_deployment(
        DeploymentCreate(
            name="my-deployment",
            orbit_id=orbit.id,
            satellite_id=satellite.id,
            artifact_id=model.id,
            status=DeploymentStatus.ACTIVE,
        )
    )

    task = await repo.enqueue_undeploy_task(deployment.id)
    assert task is not None
    assert task.type == SatelliteTaskType.UNDEPLOY
    assert task.payload["deployment_id"] == str(deployment.id)
    assert task.status == SatelliteTaskStatus.PENDING

    duplicate_task = await repo.enqueue_undeploy_task(deployment.id)
    assert duplicate_task is not None
    assert duplicate_task.id == task.id


@pytest.mark.asyncio
async def test_get_deployment_from_another_orbit(
    create_satellite: SatelliteFixtureData,
) -> None:
    data = create_satellite
    repo = DeploymentRepository(data.engine)
    deployment = await _create_deployment(data)
    sibling_orbit = await _create_sibling_orbit(data)

    assert await repo.get_deployment(deployment.id, sibling_orbit.id) is None
    assert await repo.get_deployment(deployment.id, data.orbit.id) is not None


@pytest.mark.asyncio
async def test_delete_deployment_from_another_orbit(
    create_satellite: SatelliteFixtureData,
) -> None:
    data = create_satellite
    repo = DeploymentRepository(data.engine)
    deployment = await _create_deployment(data)
    sibling_orbit = await _create_sibling_orbit(data)

    await repo.delete_deployment(deployment.id, sibling_orbit.id)

    assert await repo.get_deployment(deployment.id, data.orbit.id) is not None

    await repo.delete_deployment(deployment.id, data.orbit.id)

    assert await repo.get_deployment(deployment.id, data.orbit.id) is None


@pytest.mark.asyncio
async def test_delete_satellite_deployment_from_another_satellite(
    create_satellite: SatelliteFixtureData,
) -> None:
    data = create_satellite
    repo = DeploymentRepository(data.engine)
    deployment = await _create_deployment(data)
    foreign_satellite = await _create_satellite_in(
        data, await _create_sibling_orbit(data)
    )

    await repo.delete_satellite_deployment(deployment.id, foreign_satellite.id)

    assert await repo.get_deployment(deployment.id, data.orbit.id) is not None

    await repo.delete_satellite_deployment(deployment.id, data.satellite.id)

    assert await repo.get_deployment(deployment.id, data.orbit.id) is None
