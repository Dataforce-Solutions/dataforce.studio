from typing import Any

from fastapi import FastAPI

from agent.agent_api import OpenAPISchemaBuilder
from agent.clients import PlatformClient
from agent.monitoring import MetricRegistry, default_registry
from agent.settings import config

_UNIVERSAL_MONITORING_FEATURES = ["runtime", "traces", "alerts"]
_PROFILE_FEATURE_BY_METRIC = (
    ("data_quality", "data_quality"),
    ("feature_drift", "feature_drift"),
    ("output_drift", "output_drift"),
    ("multivariate", "multivariate_drift"),
)


class SatelliteManager:
    def __init__(
        self,
        platform: PlatformClient,
        app: FastAPI,
        monitoring_registry: MetricRegistry,
    ) -> None:
        self.platform = platform
        self.app = app
        self.monitoring_registry = monitoring_registry
        self.slug = "docker-2026.01-v2-debian12"

    async def pair(self) -> None:
        capabilities = self.get_capabilities(self.monitoring_registry)
        facets = {facet for declaration in capabilities.values() for facet in declaration["facets"]}
        openapi = OpenAPISchemaBuilder.generate_static_schema(self.app, facets)
        await self.platform.pair_satellite(
            base_url=config.BASE_URL.rstrip("/"),
            capabilities=capabilities,
            slug=self.slug,
            openapi=openapi,
        )

    @staticmethod
    def get_capabilities(
        monitoring_registry: MetricRegistry | None = None,
    ) -> dict[str, dict[str, Any]]:
        capabilities: dict[str, dict[str, Any]] = {
            "deploy": {
                "version": 1,
                "api_versions": [1],
                "facets": ["satellite", "deployment"],
                "supported_variants": ["pyfunc", "pipeline"],
                "supported_tags_combinations": None,
                "extra_fields_form_spec": [],
            }
        }
        if not config.MONITORING_ENABLED:
            return capabilities

        registry = monitoring_registry or default_registry(
            latency_p95_threshold_ms=config.MONITORING_LATENCY_P95_THRESHOLD_MS
        )
        registered_metrics = {metric.metric for metric in registry.metrics()}
        profile_features = [
            feature
            for metric, feature in _PROFILE_FEATURE_BY_METRIC
            if metric in registered_metrics
        ]
        capabilities["monitoring"] = {
            "version": 1,
            "api_versions": [1],
            "facets": ["deployment:monitoring"],
            "features": [*_UNIVERSAL_MONITORING_FEATURES, *profile_features],
        }
        return capabilities

    @staticmethod
    def _generate_form_spec() -> list[dict[str, Any]]:
        return [
            {
                "name": "custom_inference_url",
                "type": "text",
                "values": None,
                "required": False,
                "validators": [
                    {
                        "type": "regex",
                        "value": r"^https?://.*",
                        "message": "Your deployment custom base url. ",
                    }
                ],
                "conditions": [],
            },
            {
                "name": "use_gpu",
                "type": "boolean",
                "values": None,
                "required": False,
                "validators": [],
                "conditions": [],
            },
            {
                "name": "memory_limit",
                "type": "dropdown",
                "values": [
                    {"label": "512 MB", "value": "512m"},
                    {"label": "1 GB", "value": "1g"},
                    {"label": "2 GB", "value": "2g"},
                    {"label": "4 GB", "value": "4g"},
                    {"label": "8 GB", "value": "8g"},
                    {"label": "16 GB", "value": "16g"},
                ],
                "required": False,
                "validators": [],
                "conditions": [],
            },
            {
                "name": "cpu_limit",
                "type": "number",
                "values": None,
                "required": False,
                "validators": [
                    {"type": "min", "value": 0.1},
                    {"type": "max", "value": 16},
                ],
                "conditions": [
                    {
                        "type": "field",
                        "body": {
                            "field": "use_gpu",
                            "operator": "equal",
                            "value": False,
                        },
                    }
                ],
            },
            {
                "name": "gpu_count",
                "type": "number",
                "values": None,
                "required": False,
                "validators": [
                    {"type": "min", "value": 1},
                    {"type": "max", "value": 8},
                ],
                "conditions": [
                    {
                        "type": "field",
                        "body": {
                            "field": "use_gpu",
                            "operator": "equal",
                            "value": True,
                        },
                    }
                ],
            },
            {
                "name": "restart_policy",
                "type": "dropdown",
                "values": [
                    {"label": "Always restart", "value": "always"},
                    {"label": "On failure only", "value": "on-failure"},
                    {"label": "Unless stopped", "value": "unless-stopped"},
                    {"label": "Never restart", "value": "no"},
                ],
                "required": False,
                "validators": [],
                "conditions": [],
            },
            {
                "name": "health_check_timeout",
                "type": "number",
                "values": None,
                "required": False,
                "validators": [
                    {"type": "min", "value": 60},
                    {"type": "max", "value": 360},
                ],
                "conditions": [],
            },
            {
                "name": "log_level",
                "type": "dropdown",
                "values": [
                    {"label": "Debug", "value": "DEBUG"},
                    {"label": "Info", "value": "INFO"},
                    {"label": "Warning", "value": "WARNING"},
                    {"label": "Error", "value": "ERROR"},
                ],
                "required": False,
                "validators": [],
                "conditions": [],
            },
        ]
