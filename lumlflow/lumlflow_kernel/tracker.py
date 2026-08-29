"""The kernel-side experiment recorder, backed by the workspace's SDK."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DEFAULT_STORE = "~/.luml/experiments"


@dataclass(frozen=True)
class ExperimentRef:
    """The stored identity and final snapshot of a tracked experiment."""

    experiment_id: str
    group: str
    store: Path
    snapshot: dict[str, dict[str, Any]]


def tracker_store() -> Path:
    raw = os.environ.get("BACKEND_STORE_URI") or os.environ.get(
        "LUML_BACKEND_STORE_URI", _DEFAULT_STORE
    )
    if "://" in raw:
        _, raw = raw.split("://", 1)
    return Path(raw).expanduser().resolve()


def open_sdk_tracker(store: Path) -> Any:
    from luml.experiments.tracker import ExperimentTracker

    return ExperimentTracker(f"sqlite://{store}")


class Tracker:
    def __init__(
        self,
        client: Any,
        *,
        experiment_id: str,
        group: str,
        store: Path,
        params: Mapping[str, Any],
    ) -> None:
        self._client = client
        self.experiment_id = experiment_id
        self.group = group
        self.store = store
        self._params = dict(params)
        self._metrics: dict[str, float] = {}

    @classmethod
    def start(
        cls,
        client: Any,
        *,
        name: str,
        group: str,
        tags: list[str],
        store: Path,
        params: Mapping[str, Any],
    ) -> Tracker:
        experiment_id = str(client.start_experiment(name=name, group=group, tags=tags))
        return cls(
            client,
            experiment_id=experiment_id,
            group=group,
            store=store,
            params=params,
        )

    @property
    def event_fields(self) -> dict[str, str]:
        return {"experiment_id": self.experiment_id, "store": str(self.store)}

    def initialize(self, metadata: dict[str, Any]) -> None:
        self._client.set_experiment_metadata(self.experiment_id, metadata)
        for name, value in self._params.items():
            self._client.log_static(name, value, experiment_id=self.experiment_id)

    def log_param(self, name: str, value: Any) -> None:
        key = str(name)
        self._client.log_static(key, value, experiment_id=self.experiment_id)
        self._params[key] = value

    def log_params(self, values: Mapping[str, Any]) -> None:
        for name, value in values.items():
            self.log_param(name, value)

    def log_metric(self, name: str, value: float, step: int | None = None) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(
                f"`{name}` is a metric, so it takes a number — "
                "anything else belongs in a param"
            )
        key = str(name)
        self._client.log_dynamic(
            key, value, step=step, experiment_id=self.experiment_id
        )
        self._metrics[key] = value

    def log_metrics(self, values: Mapping[str, float], step: int | None = None) -> None:
        for name, value in values.items():
            self.log_metric(name, value, step=step)

    @property
    def record(self) -> ExperimentRef:
        return ExperimentRef(
            experiment_id=self.experiment_id,
            group=self.group,
            store=self.store,
            snapshot={
                "params": dict(self._params),
                "metrics": dict(self._metrics),
            },
        )

    def complete(self) -> None:
        self._client.end_experiment(self.experiment_id)

    def fail(self) -> None:
        self._client.fail_experiment(self.experiment_id)
