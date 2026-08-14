from __future__ import annotations

import importlib
import json
import random
import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path


class LocalTracker:
    def __init__(
        self,
        run_id: str,
        emit: Callable[[str, dict[str, object]], None],
    ) -> None:
        self.run_id = run_id
        self.emit = emit
        self.current_experiment_id: str | None = None
        self.records: list[dict[str, object]] = []

    def start_experiment(
        self,
        name: str | None = None,
        group: str = "default",
        experiment_id: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        identifier = experiment_id or str(uuid.uuid4())
        self.current_experiment_id = identifier
        self._record(
            "start_experiment",
            {
                "experiment_id": identifier,
                "name": name,
                "group": group,
                "tags": tags or [],
            },
        )
        return identifier

    def end_experiment(self, experiment_id: str | None = None) -> None:
        identifier = self._experiment_id(experiment_id)
        self._record("end_experiment", {"experiment_id": identifier})
        if identifier == self.current_experiment_id:
            self.current_experiment_id = None

    def fail_experiment(self, experiment_id: str | None = None) -> None:
        identifier = self._experiment_id(experiment_id)
        self._record("fail_experiment", {"experiment_id": identifier})
        if identifier == self.current_experiment_id:
            self.current_experiment_id = None

    def log_static(
        self,
        key: str,
        value: object,
        experiment_id: str | None = None,
    ) -> None:
        self._record(
            "log_static",
            {
                "experiment_id": self._experiment_id(experiment_id),
                "key": key,
                "value": value,
            },
        )

    def log_dynamic(
        self,
        key: str,
        value: int | float,
        step: int | None = None,
        experiment_id: str | None = None,
    ) -> None:
        self._record(
            "log_dynamic",
            {
                "experiment_id": self._experiment_id(experiment_id),
                "key": key,
                "value": value,
                "step": step,
            },
        )

    def log_params(
        self,
        values: dict[str, object],
        experiment_id: str | None = None,
    ) -> None:
        for key, value in values.items():
            self.log_static(key, value, experiment_id)

    def log_metrics(
        self,
        values: dict[str, int | float],
        step: int | None = None,
        experiment_id: str | None = None,
    ) -> None:
        for key, value in values.items():
            self.log_dynamic(key, value, step, experiment_id)

    def _record(self, method: str, data: dict[str, object]) -> None:
        try:
            normalized = json.loads(json.dumps(data, allow_nan=False))
        except (TypeError, ValueError) as error:
            raise TypeError("ctx.tracker records must be JSON-serializable") from error
        record: dict[str, object] = {
            "seq": len(self.records),
            "method": method,
            "data": normalized,
        }
        self.records.append(record)
        self.emit("tracker_record", {"run_id": self.run_id, "record": record})

    def _experiment_id(self, value: str | None) -> str:
        identifier = value or self.current_experiment_id
        if identifier is None:
            raise ValueError("no active experiment; call start_experiment() first")
        return identifier


class RunContext:
    def __init__(
        self,
        *,
        run_id: str,
        scratch_dir: Path,
        flow_dir: Path,
        branch: str,
        step: int,
        params: dict[str, object],
        emit: Callable[[str, dict[str, object]], None],
        secret_request: Callable[[str], str],
    ) -> None:
        self.run_id = run_id
        self.scratch_dir = scratch_dir
        self._flow_dir = flow_dir
        self._branch = branch
        self._step = step
        self.params = params
        self.emit = emit
        self.secret_request = secret_request
        self.tracker = LocalTracker(run_id, emit)

    def seed(self) -> int:
        value = self.params.get("seed")
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("ctx.seed() requires an integer params['seed']")
        random.seed(value)
        self._seed_optional_libraries(value)
        return value

    def tempdir(self) -> Path:
        return Path(tempfile.mkdtemp(prefix="ctx-", dir=self.scratch_dir))

    @property
    def flow_dir(self) -> Path:
        self._record_identity("flow_dir")
        return self._flow_dir

    @property
    def branch(self) -> str:
        self._record_identity("branch")
        return self._branch

    @property
    def step(self) -> int:
        self._record_identity("step")
        return self._step

    def secret(self, name: str) -> str:
        if not name:
            raise ValueError("secret name cannot be empty")
        return self.secret_request(name)

    def progress(self, value: float, message: str | None = None) -> None:
        if not 0 <= value <= 1:
            raise ValueError("progress must be between 0 and 1")
        self.emit(
            "progress",
            {"run_id": self.run_id, "value": value, "message": message},
        )

    def _record_identity(self, attribute: str) -> None:
        self.emit(
            "identity_access",
            {"run_id": self.run_id, "attr": attribute},
        )

    @staticmethod
    def _seed_optional_libraries(value: int) -> None:
        try:
            numpy = importlib.import_module("numpy")
        except ImportError:
            pass
        else:
            numpy.random.seed(value)
        try:
            torch = importlib.import_module("torch")
        except ImportError:
            return
        torch.manual_seed(value)
