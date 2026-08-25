from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.routing import APIRouter

from agent.monitoring.query import (
    TRACES_DEFAULT_LIMIT,
    TRACES_MAX_LIMIT,
    MonitoringQueryService,
    QueryDimensions,
)
from agent.monitoring.session import (
    MonitoringSession,
    require_monitoring_session,
    require_monitoring_write,
)
from agent.schemas.monitoring_query import (
    AcknowledgeAlertRequest,
    AlertsResponse,
    Compare,
    DataQualityResponse,
    FeatureDriftResponse,
    Granularity,
    HeaderResponse,
    OutputDriftResponse,
    OverviewResponse,
    ReferenceProfileResponse,
    RuntimeResponse,
    SectionState,
    SeverityFilter,
    TraceDetailResponse,
    TracesResponse,
    Window,
    WorkerHealthResponse,
)

MONITORING_API_PREFIX = "/monitoring/api"


def get_query_service(request: Request) -> MonitoringQueryService:
    return request.app.state.monitoring_query


# Retention keeps 30 days of data; a touch of slack spares clients that compute
# "30 days ago" a hair differently from a pointless 422.
_MAX_RANGE_SECONDS = 31 * 24 * 3600


def _dimensions(
    window: Window = Window.H24,
    compare: Compare = Compare.REFERENCE,
    severity: SeverityFilter = SeverityFilter.ALL,
    granularity: Granularity = Granularity.AUTO,
    feature: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    compare_start: datetime | None = None,
    compare_end: datetime | None = None,
) -> QueryDimensions:
    if (start is None) != (end is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start and end come together: pass both for a custom range, or neither",
        )
    if start is not None and end is not None:
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        if end <= start:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="end must be after start",
            )
        if (end - start).total_seconds() > _MAX_RANGE_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="range too wide: monitoring data is retained for 30 days",
            )
    if compare is Compare.CUSTOM:
        if compare_start is None or compare_end is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="compare=custom needs compare_start and compare_end",
            )
        if compare_start.tzinfo is None:
            compare_start = compare_start.replace(tzinfo=UTC)
        if compare_end.tzinfo is None:
            compare_end = compare_end.replace(tzinfo=UTC)
        if compare_end <= compare_start:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="compare_end must be after compare_start",
            )
        if (compare_end - compare_start).total_seconds() > _MAX_RANGE_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="comparison range too wide: monitoring data is retained for 30 days",
            )
    return QueryDimensions(
        window=window,
        compare=compare,
        severity=severity,
        granularity=granularity,
        feature=feature,
        start=start,
        end=end,
        compare_start=compare_start if compare is Compare.CUSTOM else None,
        compare_end=compare_end if compare is Compare.CUSTOM else None,
    )


def build_query_router() -> APIRouter:
    router = APIRouter(prefix=MONITORING_API_PREFIX, tags=["Monitoring Dashboard"])

    @router.get("/header", response_model=HeaderResponse)
    async def header(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> HeaderResponse:
        return await service.header(session.deployment_id)

    @router.get("/overview", response_model=OverviewResponse)
    async def overview(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> OverviewResponse:
        return await service.overview(session.deployment_id, dims)

    @router.get("/runtime", response_model=RuntimeResponse)
    async def runtime(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> RuntimeResponse:
        return await service.runtime(session.deployment_id, dims)

    @router.get("/data-quality", response_model=DataQualityResponse)
    async def data_quality(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> DataQualityResponse:
        return await service.data_quality(session.deployment_id, dims)

    @router.get("/feature-drift", response_model=FeatureDriftResponse)
    async def feature_drift(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> FeatureDriftResponse:
        return await service.feature_drift(session.deployment_id, dims)

    @router.get("/output-drift", response_model=OutputDriftResponse)
    async def output_drift(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> OutputDriftResponse:
        return await service.output_drift(session.deployment_id, dims)

    @router.get("/reference-profile", response_model=ReferenceProfileResponse)
    async def reference_profile(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> ReferenceProfileResponse:
        return await service.reference_profile(session.deployment_id, dims)

    @router.get("/alerts", response_model=AlertsResponse)
    async def alerts(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> AlertsResponse:
        return await service.alerts(session.deployment_id, dims)

    @router.post("/alerts/acknowledge", response_model=AlertsResponse)
    async def acknowledge_alert(
        body: AcknowledgeAlertRequest,
        session: MonitoringSession = Depends(require_monitoring_write),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> AlertsResponse:
        """Mark an alert as seen. The metric comes from the body: its key contains ':'."""
        return await service.acknowledge_alert(session.deployment_id, body.metric, dims)

    @router.get("/worker", response_model=WorkerHealthResponse)
    async def worker_health(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> WorkerHealthResponse:
        """Whether monitoring itself is keeping up — not a metric about the model."""
        return await service.worker_health(session.deployment_id)

    @router.get("/traces", response_model=TracesResponse)
    async def traces(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        limit: int = Query(TRACES_DEFAULT_LIMIT, ge=1, le=TRACES_MAX_LIMIT),
        offset: int = Query(0, ge=0),
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> TracesResponse:
        return await service.traces(session.deployment_id, dims, limit=limit, offset=offset)

    @router.get("/traces/{event_id}", response_model=TraceDetailResponse)
    async def trace_detail(
        event_id: str,
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> TraceDetailResponse:
        detail = await service.trace_detail(session.deployment_id, dims, event_id)
        if detail.state is SectionState.EMPTY:
            raise HTTPException(status_code=404, detail="trace not found in this window")
        return detail

    return router


# Whether this Satellite hosts the deployment. The machine surface answers 404 for
# anything else, revealing nothing about other Satellites.
HostedFn = Callable[[UUID], bool]


def build_machine_router(hosted: HostedFn) -> APIRouter:
    """Monitoring as a facet of the deployment tree — the machine surface.

    Addressed by deployment because the caller's credential does not carry one: a bearer
    key is valid for a whole orbit, so the request itself must say which deployment it is
    about. Authentication is attached where the router is included, alongside the rest of
    the deployment tree, so this surface and inference share one credential story.

    Read-only by construction: acknowledging alerts stays on the session surface — the
    machines watch, a person decides.
    """
    router = APIRouter(prefix="/deployments/{deployment_id}/monitoring", tags=["API"])

    def _hosted_deployment(deployment_id: UUID) -> UUID:
        if not hosted(deployment_id):
            raise HTTPException(status_code=404, detail="Deployment not found on this Satellite")
        return deployment_id

    @router.get("/header", response_model=HeaderResponse)
    async def header(
        deployment_id: UUID = Depends(_hosted_deployment),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> HeaderResponse:
        return await service.header(deployment_id)

    @router.get("/overview", response_model=OverviewResponse)
    async def overview(
        deployment_id: UUID = Depends(_hosted_deployment),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> OverviewResponse:
        return await service.overview(deployment_id, dims)

    @router.get("/runtime", response_model=RuntimeResponse)
    async def runtime(
        deployment_id: UUID = Depends(_hosted_deployment),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> RuntimeResponse:
        return await service.runtime(deployment_id, dims)

    @router.get("/data-quality", response_model=DataQualityResponse)
    async def data_quality(
        deployment_id: UUID = Depends(_hosted_deployment),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> DataQualityResponse:
        return await service.data_quality(deployment_id, dims)

    @router.get("/feature-drift", response_model=FeatureDriftResponse)
    async def feature_drift(
        deployment_id: UUID = Depends(_hosted_deployment),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> FeatureDriftResponse:
        return await service.feature_drift(deployment_id, dims)

    @router.get("/output-drift", response_model=OutputDriftResponse)
    async def output_drift(
        deployment_id: UUID = Depends(_hosted_deployment),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> OutputDriftResponse:
        return await service.output_drift(deployment_id, dims)

    @router.get("/reference-profile", response_model=ReferenceProfileResponse)
    async def reference_profile(
        deployment_id: UUID = Depends(_hosted_deployment),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> ReferenceProfileResponse:
        return await service.reference_profile(deployment_id, dims)

    @router.get("/alerts", response_model=AlertsResponse)
    async def alerts(
        deployment_id: UUID = Depends(_hosted_deployment),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> AlertsResponse:
        return await service.alerts(deployment_id, dims)

    @router.get("/traces", response_model=TracesResponse)
    async def traces(
        deployment_id: UUID = Depends(_hosted_deployment),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        limit: int = Query(TRACES_DEFAULT_LIMIT, ge=1, le=TRACES_MAX_LIMIT),
        offset: int = Query(0, ge=0),
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> TracesResponse:
        return await service.traces(deployment_id, dims, limit=limit, offset=offset)

    @router.get("/traces/{event_id}", response_model=TraceDetailResponse)
    async def trace_detail(
        event_id: str,
        deployment_id: UUID = Depends(_hosted_deployment),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> TraceDetailResponse:
        detail = await service.trace_detail(deployment_id, dims, event_id)
        if detail.state is SectionState.EMPTY:
            raise HTTPException(status_code=404, detail="trace not found in this window")
        return detail

    @router.get("/worker", response_model=WorkerHealthResponse)
    async def worker(
        deployment_id: UUID = Depends(_hosted_deployment),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> WorkerHealthResponse:
        """Whether monitoring itself is keeping up — not a metric about the model."""
        return await service.worker_health(deployment_id)

    return router
