from __future__ import annotations

from pathlib import Path
from typing import Any, BinaryIO, Protocol, runtime_checkable


@runtime_checkable
class AssetType(Protocol):
    kind: str
    python_types: tuple[type[Any], ...]

    def serialize(self, value: Any, sink: BinaryIO) -> str | None: ...

    def deserialize(self, source: BinaryIO) -> Any: ...

    def preview(self, value: Any) -> dict[str, Any]: ...

    def page(self, source: BinaryIO, query: dict[str, Any]) -> Any: ...


class Ctx(Protocol):
    tracker: Tracker

    def seed(self) -> int: ...

    def tempdir(self) -> Path: ...

    @property
    def flow_dir(self) -> Path: ...

    @property
    def branch(self) -> str: ...

    @property
    def step(self) -> int: ...

    def secret(self, name: str) -> str: ...


class Tracker(Protocol):
    def start_experiment(
        self,
        name: str | None = None,
        group: str = "default",
        experiment_id: str | None = None,
        tags: list[str] | None = None,
    ) -> str: ...

    def end_experiment(self, experiment_id: str | None = None) -> None: ...

    def fail_experiment(self, experiment_id: str | None = None) -> None: ...

    def log_static(
        self,
        key: str,
        value: object,
        experiment_id: str | None = None,
    ) -> None: ...

    def log_dynamic(
        self,
        key: str,
        value: int | float,
        step: int | None = None,
        experiment_id: str | None = None,
    ) -> None: ...


class CellProtocol(Protocol):
    def materialize(self, ctx: Ctx, **inputs: Any) -> dict[str, Any]: ...


__all__ = ["AssetType", "CellProtocol", "Ctx", "Tracker"]
