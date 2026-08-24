from typing import Any

from luml_api._exceptions import LumlAPIError

_WINDOWS = ("24h", "7d", "30d")


def _dims(
    window: str,
    compare: str,
    severity: str,
    granularity: str,
    feature: str | None,
) -> dict[str, str]:
    if window not in _WINDOWS:
        raise LumlAPIError(f"window must be one of {_WINDOWS}, got {window!r}")
    params = {
        "window": window,
        "compare": compare,
        "severity": severity,
        "granularity": granularity,
    }
    if feature is not None:
        params["feature"] = feature
    return params


class _MonitoringBase:
    """Monitoring sections of one deployment, read from its Satellite.

    Requests go straight to the Satellite that hosts the deployment — monitoring data
    never passes through the Platform — authenticated with the same API key the client
    already holds. Every method returns the chart-ready payload the dashboard renders,
    exactly as the Satellite's OpenAPI schema describes it.
    """

    def __init__(self, client: Any, satellite_url: str, deployment_id: str) -> None:  # noqa: ANN401
        self._client = client
        self._base = satellite_url.rstrip("/")
        self.deployment_id = deployment_id

    def _url(self, section: str) -> str:
        return f"{self._base}/deployments/{self.deployment_id}/monitoring/{section}"


class DeploymentMonitoring(_MonitoringBase):
    def header(self) -> dict:
        """
        Identity of the deployment as the dashboard header shows it.

        Returns:
            dict with the deployment's name, status, task type, model name, and the
            timestamps of the last prediction and the last materialized
            monitoring window.

        Raises:
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        monitoring = luml.deployments.monitoring("insurance regression")
        header = monitoring.header()
        ```

        Example response:
        ```python
        {
            "state": "ok",
            "deployment_id": "01a033db-bb07-728a-9b5a-628c4cc6df94",
            "name": "insurance regression",
            "status": "active",
            "task_type": "regression",
            "model_name": "insurance_regression_v2",
            "satellite": "satellite",
            "last_prediction_at": "2026-08-24T16:19:32.140034Z",
            "last_monitored_at": "2026-08-24T16:20:00Z",
            "profile_status": "ready",
        }
        ```
        """
        return self._client.get(self._url("header"))

    def overview(
        self,
        window: str = "24h",
        compare: str = "reference",
        severity: str = "all",
        granularity: str = "auto",
        feature: str | None = None,
    ) -> dict:
        """
        Status summary of the deployment: what changed and where to look first.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            compare: What deltas are computed against: "reference" (the
                training profile) or "previous" (the preceding period).
            severity: Alert severity filter: "all", "warning" or "critical".
            granularity: Series bucketing: "auto", "hour" or "day".
            feature: Optional feature name to scope the section to.

        Returns:
            dict with status cards, alert banners, runtime series and the top drifted
            features — the chart-ready payload the dashboard's Overview tab renders.

        Raises:
            LumlAPIError: If ``window`` is not one the dashboard offers.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        monitoring = luml.deployments.monitoring("insurance regression")
        overview = monitoring.overview(window="7d", severity="critical")
        ```
        """
        return self._client.get(
            self._url("overview"),
            params=_dims(window, compare, severity, granularity, feature),
        )

    def runtime(
        self,
        window: str = "24h",
        compare: str = "reference",
        severity: str = "all",
        granularity: str = "auto",
    ) -> dict:
        """
        Whether the deployed endpoint is technically healthy.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            compare: What deltas are computed against: "reference" (the
                training profile) or "previous" (the preceding period).
            severity: Alert severity filter: "all", "warning" or "critical".
            granularity: Series bucketing: "auto", "hour" or "day".

        Returns:
            dict with request/success/error counts, error rate, latency percentiles,
            timeout and failed-inference counts, the outcome breakdown by HTTP status,
            time series, and the runtime alerts.

        Raises:
            LumlAPIError: If ``window`` is not one the dashboard offers.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        monitoring = luml.deployments.monitoring("insurance regression")
        runtime = monitoring.runtime(window="24h")
        ```
        """
        return self._client.get(
            self._url("runtime"),
            params=_dims(window, compare, severity, granularity, None),
        )

    def data_quality(
        self,
        window: str = "24h",
        severity: str = "all",
        feature: str | None = None,
    ) -> dict:
        """
        Whether live inputs still conform to the model contract.

        Without ``feature`` the payload covers every feature; with it, the named
        feature's trends are included as well.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            severity: Alert severity filter: "all", "warning" or "critical".
            feature: Optional feature name to scope the section to.

        Returns:
            dict with per-feature rates of missing values, type mismatches, range
            violations and unseen categories, plus summaries of the invalid values seen.

        Raises:
            LumlAPIError: If ``window`` is not one the dashboard offers.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        monitoring = luml.deployments.monitoring("insurance regression")
        data_quality = monitoring.data_quality(feature="age")
        ```
        """
        return self._client.get(
            self._url("data-quality"),
            params=_dims(window, "reference", severity, "auto", feature),
        )

    def feature_drift(
        self,
        window: str = "24h",
        severity: str = "all",
        feature: str | None = None,
    ) -> dict:
        """
        Which inputs changed compared with the training reference.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            severity: Alert severity filter: "all", "warning" or "critical".
            feature: Optional feature name to scope the section to.

        Returns:
            dict with the PSI ranking of all features, the selected feature's
            distributions and PSI history, and the multivariate (PCA) panel.

        Raises:
            LumlAPIError: If ``window`` is not one the dashboard offers.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        monitoring = luml.deployments.monitoring("insurance regression")
        feature_drift = monitoring.feature_drift(severity="critical")
        ```
        """
        return self._client.get(
            self._url("feature-drift"),
            params=_dims(window, "reference", severity, "auto", feature),
        )

    def reference_profile(self, feature: str | None = None) -> dict:
        """
        The profile the deployment is compared against.

        This is the reference profile shipped inside the model artifact: schemas,
        baseline distributions and threshold rules.

        Args:
            feature: Optional feature name to scope the section to.

        Returns:
            dict with the profile document, or one feature's entry when ``feature``
            is passed.

        Raises:
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        monitoring = luml.deployments.monitoring("insurance regression")
        reference_profile = monitoring.reference_profile()
        ```
        """
        return self._client.get(
            self._url("reference-profile"),
            params=_dims("24h", "reference", "all", "auto", feature),
        )

    def alerts(self, window: str = "24h", severity: str = "all") -> dict:
        """
        Open and acknowledged alerts, grouped by metric family.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            severity: Alert severity filter: "all", "warning" or "critical".

        Returns:
            dict with alert groups (runtime, data quality, feature drift, output drift,
            multivariate); every alert carries its current value, threshold, state and
            metric history.

        Raises:
            LumlAPIError: If ``window`` is not one the dashboard offers.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        monitoring = luml.deployments.monitoring("insurance regression")
        alerts = monitoring.alerts(window="7d", severity="critical")
        ```
        """
        return self._client.get(
            self._url("alerts"),
            params=_dims(window, "reference", severity, "auto", None),
        )

    def traces(self, window: str = "24h", limit: int = 50, offset: int = 0) -> dict:
        """
        The local request log: one row per inference call.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            limit: Maximum rows per page (up to 200).
            offset: Rows to skip, for paging.

        Returns:
            dict with the page's rows (event id, timestamp, feature summary, prediction,
            latency, status) and the total count.

        Raises:
            LumlAPIError: If ``window`` is not one the dashboard offers.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        monitoring = luml.deployments.monitoring("insurance regression")
        traces = monitoring.traces(limit=20)
        ```
        """
        params = _dims(window, "reference", "all", "auto", None)
        params.update({"limit": str(limit), "offset": str(offset)})
        return self._client.get(self._url("traces"), params=params)

    def trace(self, event_id: str, window: str = "24h") -> dict:
        """
        One call with its full payloads and span tree.

        The window must cover the call: the Satellite looks the event up inside it.

        Args:
            event_id: Event ID of the call, from a ``traces()`` row.
            window: Time range the section covers: "24h", "7d" or "30d".

        Returns:
            dict with the call's inputs, output, latency, status and
            OpenTelemetry spans.

        Raises:
            NotFoundError: If the event is not found in the window, or the
                Satellite does not host this deployment.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        monitoring = luml.deployments.monitoring("insurance regression")
        trace = monitoring.trace("01a03491-e699-7244-ba1f-84ddc4cde2a1")
        ```
        """
        return self._client.get(
            self._url(f"traces/{event_id}"),
            params=_dims(window, "reference", "all", "auto", None),
        )

    def worker(self) -> dict:
        """
        Whether monitoring itself is keeping up — not a metric about the model.

        Returns:
            dict with the worker's liveness, processed-window counters, lag behind the
            last closed window, and the history of metric failures.

        Raises:
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        monitoring = luml.deployments.monitoring("insurance regression")
        worker = monitoring.worker()
        ```
        """
        return self._client.get(self._url("worker"))


class AsyncDeploymentMonitoring(_MonitoringBase):
    async def header(self) -> dict:
        """
        Identity of the deployment as the dashboard header shows it.

        Returns:
            dict with the deployment's name, status, task type, model name, and the
            timestamps of the last prediction and the last materialized
            monitoring window.

        Raises:
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            )
            monitoring = await luml.deployments.monitoring(
                "insurance regression"
            )
            header = await monitoring.header()
        ```

        Example response:
        ```python
        {
            "state": "ok",
            "deployment_id": "01a033db-bb07-728a-9b5a-628c4cc6df94",
            "name": "insurance regression",
            "status": "active",
            "task_type": "regression",
            "model_name": "insurance_regression_v2",
            "satellite": "satellite",
            "last_prediction_at": "2026-08-24T16:19:32.140034Z",
            "last_monitored_at": "2026-08-24T16:20:00Z",
            "profile_status": "ready",
        }
        ```
        """
        return await self._client.get(self._url("header"))

    async def overview(
        self,
        window: str = "24h",
        compare: str = "reference",
        severity: str = "all",
        granularity: str = "auto",
        feature: str | None = None,
    ) -> dict:
        """
        Status summary of the deployment: what changed and where to look first.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            compare: What deltas are computed against: "reference" (the
                training profile) or "previous" (the preceding period).
            severity: Alert severity filter: "all", "warning" or "critical".
            granularity: Series bucketing: "auto", "hour" or "day".
            feature: Optional feature name to scope the section to.

        Returns:
            dict with status cards, alert banners, runtime series and the top drifted
            features — the chart-ready payload the dashboard's Overview tab renders.

        Raises:
            LumlAPIError: If ``window`` is not one the dashboard offers.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            )
            monitoring = await luml.deployments.monitoring(
                "insurance regression"
            )
            overview = await monitoring.overview(window="7d", severity="critical")
        ```
        """
        return await self._client.get(
            self._url("overview"),
            params=_dims(window, compare, severity, granularity, feature),
        )

    async def runtime(
        self,
        window: str = "24h",
        compare: str = "reference",
        severity: str = "all",
        granularity: str = "auto",
    ) -> dict:
        """
        Whether the deployed endpoint is technically healthy.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            compare: What deltas are computed against: "reference" (the
                training profile) or "previous" (the preceding period).
            severity: Alert severity filter: "all", "warning" or "critical".
            granularity: Series bucketing: "auto", "hour" or "day".

        Returns:
            dict with request/success/error counts, error rate, latency percentiles,
            timeout and failed-inference counts, the outcome breakdown by HTTP status,
            time series, and the runtime alerts.

        Raises:
            LumlAPIError: If ``window`` is not one the dashboard offers.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            )
            monitoring = await luml.deployments.monitoring(
                "insurance regression"
            )
            runtime = await monitoring.runtime(window="24h")
        ```
        """
        return await self._client.get(
            self._url("runtime"),
            params=_dims(window, compare, severity, granularity, None),
        )

    async def data_quality(
        self, window: str = "24h", severity: str = "all", feature: str | None = None
    ) -> dict:
        """
        Whether live inputs still conform to the model contract.

        Without ``feature`` the payload covers every feature; with it, the named
        feature's trends are included as well.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            severity: Alert severity filter: "all", "warning" or "critical".
            feature: Optional feature name to scope the section to.

        Returns:
            dict with per-feature rates of missing values, type mismatches, range
            violations and unseen categories, plus summaries of the invalid values seen.

        Raises:
            LumlAPIError: If ``window`` is not one the dashboard offers.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            )
            monitoring = await luml.deployments.monitoring(
                "insurance regression"
            )
            data_quality = await monitoring.data_quality(feature="age")
        ```
        """
        return await self._client.get(
            self._url("data-quality"),
            params=_dims(window, "reference", severity, "auto", feature),
        )

    async def feature_drift(
        self, window: str = "24h", severity: str = "all", feature: str | None = None
    ) -> dict:
        """
        Which inputs changed compared with the training reference.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            severity: Alert severity filter: "all", "warning" or "critical".
            feature: Optional feature name to scope the section to.

        Returns:
            dict with the PSI ranking of all features, the selected feature's
            distributions and PSI history, and the multivariate (PCA) panel.

        Raises:
            LumlAPIError: If ``window`` is not one the dashboard offers.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            )
            monitoring = await luml.deployments.monitoring(
                "insurance regression"
            )
            feature_drift = await monitoring.feature_drift(severity="critical")
        ```
        """
        return await self._client.get(
            self._url("feature-drift"),
            params=_dims(window, "reference", severity, "auto", feature),
        )

    async def reference_profile(self, feature: str | None = None) -> dict:
        """
        The profile the deployment is compared against.

        This is the reference profile shipped inside the model artifact: schemas,
        baseline distributions and threshold rules.

        Args:
            feature: Optional feature name to scope the section to.

        Returns:
            dict with the profile document, or one feature's entry when ``feature``
            is passed.

        Raises:
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            )
            monitoring = await luml.deployments.monitoring(
                "insurance regression"
            )
            reference_profile = await monitoring.reference_profile()
        ```
        """
        return await self._client.get(
            self._url("reference-profile"),
            params=_dims("24h", "reference", "all", "auto", feature),
        )

    async def alerts(self, window: str = "24h", severity: str = "all") -> dict:
        """
        Open and acknowledged alerts, grouped by metric family.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            severity: Alert severity filter: "all", "warning" or "critical".

        Returns:
            dict with alert groups (runtime, data quality, feature drift, output drift,
            multivariate); every alert carries its current value, threshold, state and
            metric history.

        Raises:
            LumlAPIError: If ``window`` is not one the dashboard offers.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            )
            monitoring = await luml.deployments.monitoring(
                "insurance regression"
            )
            alerts = await monitoring.alerts(window="7d", severity="critical")
        ```
        """
        return await self._client.get(
            self._url("alerts"),
            params=_dims(window, "reference", severity, "auto", None),
        )

    async def traces(
        self, window: str = "24h", limit: int = 50, offset: int = 0
    ) -> dict:
        """
        The local request log: one row per inference call.

        Args:
            window: Time range the section covers: "24h", "7d" or "30d".
            limit: Maximum rows per page (up to 200).
            offset: Rows to skip, for paging.

        Returns:
            dict with the page's rows (event id, timestamp, feature summary, prediction,
            latency, status) and the total count.

        Raises:
            LumlAPIError: If ``window`` is not one the dashboard offers.
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            )
            monitoring = await luml.deployments.monitoring(
                "insurance regression"
            )
            traces = await monitoring.traces(limit=20)
        ```
        """
        params = _dims(window, "reference", "all", "auto", None)
        params.update({"limit": str(limit), "offset": str(offset)})
        return await self._client.get(self._url("traces"), params=params)

    async def trace(self, event_id: str, window: str = "24h") -> dict:
        """
        One call with its full payloads and span tree.

        The window must cover the call: the Satellite looks the event up inside it.

        Args:
            event_id: Event ID of the call, from a ``traces()`` row.
            window: Time range the section covers: "24h", "7d" or "30d".

        Returns:
            dict with the call's inputs, output, latency, status and
            OpenTelemetry spans.

        Raises:
            NotFoundError: If the event is not found in the window, or the
                Satellite does not host this deployment.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            )
            monitoring = await luml.deployments.monitoring(
                "insurance regression"
            )
            trace = await monitoring.trace("01a03491-e699-7244-ba1f-84ddc4cde2a1")
        ```
        """
        return await self._client.get(
            self._url(f"traces/{event_id}"),
            params=_dims(window, "reference", "all", "auto", None),
        )

    async def worker(self) -> dict:
        """
        Whether monitoring itself is keeping up — not a metric about the model.

        Returns:
            dict with the worker's liveness, processed-window counters, lag behind the
            last closed window, and the history of metric failures.

        Raises:
            NotFoundError: If the Satellite does not host this deployment.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )

        async def main():
            await luml.setup_config(
                organization="0199c455-21ec-7c74-8efe-41470e29bae5",
                orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            )
            monitoring = await luml.deployments.monitoring(
                "insurance regression"
            )
            worker = await monitoring.worker()
        ```
        """
        return await self._client.get(self._url("worker"))
