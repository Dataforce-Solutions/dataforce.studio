import asyncio
from contextlib import suppress
from uuid import UUID

import httpx
import uvicorn

from agent.agent_api import ResolveArtifactFn, create_agent_app
from agent.agent_manager import SatelliteManager
from agent.clients import DockerService, PlatformClient
from agent.controllers import PeriodicController
from agent.handlers.artifact_urls import presigned_expiry
from agent.handlers.handler_instances import ms_handler
from agent.handlers.tasks import TaskHandler
from agent.monitoring import (
    GreptimeMonitoringStore,
    MetricRegistry,
    MonitoringWorker,
    default_registry,
    monitored_deployments,
)
from agent.monitoring.health import worker_health
from agent.schemas import ArtifactDownload
from agent.settings import config


def _build_monitoring_worker(
    registry: MetricRegistry,
) -> tuple[MonitoringWorker, GreptimeMonitoringStore]:
    store = GreptimeMonitoringStore(
        host=config.GREPTIMEDB_HOST,
        port=config.GREPTIMEDB_HTTP_PORT,
        database=config.GREPTIMEDB_DATABASE,
        events_ttl=config.MONITORING_EVENTS_TTL,
        results_ttl=config.MONITORING_RESULTS_TTL,
        alerts_ttl=config.MONITORING_ALERTS_TTL,
        traces_ttl=config.MONITORING_TRACES_TTL,
        metrics_ttl=config.MONITORING_METRICS_TTL,
    )
    worker = MonitoringWorker(
        store=store,
        registry=registry,
        provider=lambda: monitored_deployments(ms_handler.deployments.values()),
        window_seconds=config.MONITORING_WINDOW_SEC,
        interval_seconds=config.MONITORING_INTERVAL_SEC,
        health=worker_health,
        max_backfill_windows=config.MONITORING_BACKFILL_MAX_WINDOWS,
    )
    return worker, store


def _artifact_resolver(platform: PlatformClient) -> ResolveArtifactFn:
    """Answer a model container's request for its artifact with a URL signed right now.

    Deliberately not checked against the Agent's local registry: a deployment is
    registered there only after its health check, and the container asks well before
    that. Scoping comes from the Platform's satellite-scoped endpoint.
    """

    async def resolve(deployment_id: UUID) -> ArtifactDownload:
        try:
            deployment = await platform.get_deployment(deployment_id)
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                raise KeyError(deployment_id) from error
            raise
        if deployment is None:
            raise KeyError(deployment_id)
        url = await platform.get_artifact_download_url(UUID(deployment.artifact_id))
        return ArtifactDownload(
            url=url,
            artifact_id=str(deployment.artifact_id),
            expires_at=presigned_expiry(url),
        )

    return resolve


async def run_async() -> None:
    async with PlatformClient(str(config.PLATFORM_URL), config.SATELLITE_TOKEN) as platform:
        agent_app = create_agent_app(
            platform.authorize_inference_access,
            platform.introspect_monitoring_token,
            _artifact_resolver(platform),
        )

        uv_config = uvicorn.Config(
            agent_app,
            host="0.0.0.0",
            port=config.AGENT_PORT,
            log_level="warning",
        )
        uv_server = uvicorn.Server(uv_config)
        uv_task = asyncio.create_task(uv_server.serve())
        async with DockerService() as docker:
            handler = TaskHandler(platform=platform, docker=docker)
            controller = PeriodicController(
                handler=handler, poll_interval_s=float(config.POLL_INTERVAL_SEC)
            )
            monitoring_registry = default_registry(
                latency_p95_threshold_ms=config.MONITORING_LATENCY_P95_THRESHOLD_MS
            )
            satellite_manager = SatelliteManager(platform, agent_app, monitoring_registry)

            monitoring_worker = None
            monitoring_store = None
            monitoring_task = None
            if config.MONITORING_ENABLED:
                monitoring_worker, monitoring_store = _build_monitoring_worker(monitoring_registry)
                monitoring_task = asyncio.create_task(monitoring_worker.run_forever())

            try:
                await asyncio.sleep(0.1)

                await satellite_manager.pair()

                await controller.run_forever()
            finally:
                if monitoring_worker is not None:
                    monitoring_worker.stop()
                if monitoring_task is not None:
                    monitoring_task.cancel()
                    with suppress(asyncio.CancelledError, Exception):
                        await monitoring_task
                if monitoring_store is not None:
                    with suppress(Exception):
                        await monitoring_store.aclose()
                uv_server.should_exit = True
                with suppress(Exception):
                    await asyncio.wait_for(uv_task, timeout=2.0)


def run() -> None:
    asyncio.run(run_async())


if __name__ == "__main__":
    run()
