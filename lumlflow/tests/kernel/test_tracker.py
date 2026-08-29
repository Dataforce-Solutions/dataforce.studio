from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from luml.experiments.tracker import ExperimentTracker
else:
    ExperimentTracker = pytest.importorskip(
        "luml.experiments.tracker"
    ).ExperimentTracker

from lumlflow_kernel.kernel import Kernel
from lumlflow_kernel.tracker import Tracker
from tests.kernel.helpers import FakeLink, make_kernel, run, stored_value

DEADLINE_S = 20.0
PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVALUATE_CELL = (
    PROJECT_ROOT / "examples" / "churn" / "churn.flow" / "cells" / "evaluate.py"
)


def test_an_experiment_run_writes_metadata_params_metrics_and_completes(
    tmp_path: Path, tracker_store: Path
) -> None:
    kernel, link = make_kernel(tmp_path)
    identity = _identity(kernel, run_id="evaluate-run")

    record = run(
        kernel,
        """
        def materialize(self, ctx):
            if ctx.tracker.record["params"] != {"folds": 5}:
                raise RuntimeError("declared params were not seeded")
            ctx.tracker.log_params({"alpha": 0.25, "optimizer": "adamw"})
            ctx.tracker.log_metrics({"rmse": 0.4, "mae": 0.3}, step=7)
            return {"metrics": ctx.tracker.record}
        """,
        slug="evaluate",
        run_id="evaluate-run",
        produces={"metrics": "experiment"},
        params={"folds": 5},
        identity=identity,
    )

    tracker = ExperimentTracker(f"sqlite://{tracker_store}")
    experiment = _only_experiment(tracker)
    data = tracker.get_experiment(experiment.id)
    assert data is not None
    assert (experiment.name, experiment.group_name, experiment.status) == (
        "evaluate",
        "churn",
        "completed",
    )
    assert experiment.tags == ["main", "evaluate"]
    assert experiment.metadata == {"lumlflow": identity}
    assert data.static_params == {
        "folds": 5,
        "alpha": 0.25,
        "optimizer": "adamw",
    }
    assert data.dynamic_metrics == {
        "rmse": [{"value": 0.4, "step": 7}],
        "mae": [{"value": 0.3, "step": 7}],
    }
    assert json.loads(stored_value(kernel, record, "metrics")) == {
        "params": {"folds": 5, "alpha": 0.25, "optimizer": "adamw"},
        "metrics": {"rmse": 0.4, "mae": 0.3},
    }
    started = link.named("experiment_started")
    assert started == [
        {
            "run_id": "evaluate-run",
            "slug": "evaluate",
            "experiment_id": experiment.id,
            "store": str(tracker_store),
        }
    ]
    assert record["experiment_id"] == experiment.id
    assert record["store"] == str(tracker_store)
    assert link.named("materialized")[-1]["experiment_id"] == experiment.id


def test_the_experiment_start_is_reported_before_materialize(
    tmp_path: Path, tracker_store: Path
) -> None:
    announced = tmp_path / "announced"
    link = _StartMarkingLink(announced)
    kernel, _ = make_kernel(tmp_path, link=link)

    record = run(
        kernel,
        f"""
        def materialize(self, ctx):
            from pathlib import Path
            if not Path({str(announced)!r}).exists():
                raise RuntimeError("materialize ran before the start event")
            return {{"metrics": ctx.tracker.record}}
        """,
        slug="evaluate",
        produces={"metrics": "experiment"},
        identity=_identity(kernel),
    )

    event = link.named("experiment_started")[0]
    assert record["state"] == "succeeded"
    assert event["experiment_id"] == record["experiment_id"]
    assert event["store"] == str(tracker_store)


def test_a_failed_run_fails_the_experiment_and_keeps_its_id(
    tmp_path: Path, tracker_store: Path
) -> None:
    kernel, link = make_kernel(tmp_path)
    record = run(
        kernel,
        """
        def materialize(self, ctx):
            ctx.tracker.log_metric("loss", 0.8, step=2)
            raise ValueError("did not converge")
        """,
        slug="train",
        produces={"run": "experiment"},
        identity=_identity(kernel, slug="train"),
    )

    tracker = ExperimentTracker(f"sqlite://{tracker_store}")
    experiment = _only_experiment(tracker)
    assert record["state"] == "failed"
    assert experiment.status == "error"
    assert (
        tracker.get_experiment_metric_history(experiment.id, "loss")[0]["value"] == 0.8
    )
    assert record["experiment_id"] == experiment.id
    assert link.named("failed")[-1]["experiment_id"] == experiment.id


def test_cancelling_a_run_fails_its_live_experiment(
    tmp_path: Path, tracker_store: Path
) -> None:
    kernel, _ = make_kernel(tmp_path)
    logged = tmp_path / "logged"
    finished: list[dict[str, Any]] = []
    worker = threading.Thread(
        target=lambda: finished.append(
            run(
                kernel,
                f"""
                def materialize(self, ctx):
                    from pathlib import Path
                    import time
                    ctx.tracker.log_metric("loss", 0.9, step=1)
                    Path({str(logged)!r}).write_text("ready")
                    while True:
                        time.sleep(0.01)
                """,
                slug="train",
                produces={"run": "experiment"},
                identity=_identity(kernel, slug="train"),
            )
        )
    )
    worker.start()
    try:
        _await(logged.exists)
        assert kernel.cancel({"run_id": "run1"}) == {"cancelled": True}
    finally:
        worker.join(timeout=DEADLINE_S)

    tracker = ExperimentTracker(f"sqlite://{tracker_store}")
    experiment = _only_experiment(tracker)
    assert not worker.is_alive()
    assert finished[0]["state"] == "cancelled"
    assert finished[0]["experiment_id"] == experiment.id
    assert experiment.status == "error"
    assert tracker.get_experiment_metric_history(experiment.id, "loss")[0]["step"] == 1


def test_metrics_are_in_the_tracker_in_order_while_the_cell_is_running(
    tmp_path: Path, tracker_store: Path
) -> None:
    kernel, link = make_kernel(tmp_path)
    logged, release = tmp_path / "logged", tmp_path / "release"
    finished: list[dict[str, Any]] = []
    worker = threading.Thread(
        target=lambda: finished.append(
            run(
                kernel,
                f"""
                def materialize(self, ctx):
                    from pathlib import Path
                    import time
                    ctx.tracker.log_metric("loss", 0.9, step=1)
                    ctx.tracker.log_metrics({{"loss": 0.7}}, step=2)
                    ctx.tracker.log_metric("loss", 0.5, step=3)
                    Path({str(logged)!r}).write_text("ready")
                    while not Path({str(release)!r}).exists():
                        time.sleep(0.01)
                    return {{"run": ctx.tracker.record}}
                """,
                slug="train",
                produces={"run": "experiment"},
                identity=_identity(kernel, slug="train"),
            )
        )
    )
    worker.start()
    try:
        _await(logged.exists)
        experiment_id = link.named("experiment_started")[0]["experiment_id"]
        tracker = ExperimentTracker(f"sqlite://{tracker_store}")
        history = tracker.get_experiment_metric_history(experiment_id, "loss")
        assert [(point["step"], point["value"]) for point in history] == [
            (1, 0.9),
            (2, 0.7),
            (3, 0.5),
        ]
        assert tracker.get_experiment_record(experiment_id).status == "active"
    finally:
        release.write_text("go")
        worker.join(timeout=DEADLINE_S)

    assert not worker.is_alive()
    assert finished[0]["state"] == "succeeded"


def test_a_close_failure_keeps_the_materialization_and_reaches_the_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kernel, link = make_kernel(tmp_path)
    complete = Tracker.complete

    def complete_then_report_failure(tracker: Tracker) -> None:
        complete(tracker)
        raise RuntimeError("could not close the experiment")

    monkeypatch.setattr(Tracker, "complete", complete_then_report_failure)
    record = run(
        kernel,
        """
        def materialize(self, ctx):
            return {"run": ctx.tracker.record}
        """,
        produces={"run": "experiment"},
        identity=_identity(kernel),
    )

    assert record["state"] == "succeeded"
    assert record["outputs"]["run"]["value_ref"]
    assert record["experiment_close_error"] == "could not close the experiment"
    assert link.named("materialized")[-1]["experiment_close_error"] == (
        "could not close the experiment"
    )


def test_a_run_without_an_experiment_never_imports_the_sdk(tmp_path: Path) -> None:
    probe = textwrap.dedent(
        f"""
        import sys
        from pathlib import Path
        from lumlflow_kernel.kernel import Kernel

        class Link:
            def notify(self, method, params):
                pass
            def stop(self):
                pass

        root = Path({str(tmp_path)!r}) / "project"
        flow = root / "churn.flow"
        (flow / "cells").mkdir(parents=True)
        kernel = Kernel(flow_dir=flow, workspace_dir=root, link=Link())
        source = (
            "class Plain:\\n"
            "    def materialize(self, ctx):\\n"
            "        return {{}}\\n"
        )
        kernel.run({{
            "run_id": "plain",
            "version": {{
                "slug": "plain",
                "source": source,
                "produces": {{}},
            }},
            "inputs": {{}},
            "params": {{}},
            "ctx_info": {{"branch": "main", "step": 1}},
        }})
        print(sorted(name for name in sys.modules if name.split('.')[0] == "luml"))
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=PROJECT_ROOT,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        capture_output=True,
        check=True,
        text=True,
    )

    assert result.stdout.strip() == "[]"


def test_the_churn_evaluate_cell_runs_unchanged_and_logs_alpha(
    tmp_path: Path, tracker_store: Path
) -> None:
    pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    pytest.importorskip("sklearn")
    kernel, _ = make_kernel(tmp_path)
    fixture = run(
        kernel,
        """
        def materialize(self, ctx):
            import pandas

            class Model:
                alpha = 0.25

                def predict(self, rows):
                    return rows["feature"].to_numpy() * 2

            test = pandas.DataFrame({
                "feature": [1.0, 2.0, 3.0],
                "target": [2.0, 4.0, 6.0],
            })
            return {"model": Model(), "test": test}
        """,
        run_id="fixture",
        produces={"model": "asset", "test": "asset"},
    )
    model = fixture["outputs"]["model"]
    test = fixture["outputs"]["test"]

    record = kernel.run(
        {
            "run_id": "evaluate-run",
            "version": {
                "slug": "evaluate",
                "source": EVALUATE_CELL.read_text("utf-8"),
                "produces": {"metrics": "experiment"},
            },
            "inputs": {
                "model": {"value_ref": model["value_ref"], "kind": model["kind"]},
                "test": {"value_ref": test["value_ref"], "kind": test["kind"]},
            },
            "params": {},
            "ctx_info": {"branch": "main", "step": 7},
            "identity": _identity(kernel, slug="evaluate", run_id="evaluate-run"),
        }
    )

    tracker = ExperimentTracker(f"sqlite://{tracker_store}")
    experiment = _only_experiment(tracker)
    assert record["state"] == "succeeded"
    assert experiment.static_params["alpha"] == 0.25
    assert set(experiment.dynamic_params) == {"rmse", "mae", "r2"}


class _StartMarkingLink(FakeLink):
    def __init__(self, marker: Path) -> None:
        super().__init__()
        self._marker = marker

    def notify(self, method: str, params: dict[str, Any]) -> None:
        super().notify(method, params)
        if method == "experiment_started":
            self._marker.write_text("ready")


def _identity(
    kernel: Kernel, *, slug: str = "evaluate", run_id: str = "run1"
) -> dict[str, str]:
    return {
        "flow": "churn",
        "flow_id": "01M00FLOW00000000000000000",
        "path": str(kernel.flow_dir.resolve()),
        "slug": slug,
        "uid": "01M00CELL00000000000000000",
        "lane": "main",
        "version_id": "01M00VERSION0000000000000",
        "run_id": run_id,
    }


def _only_experiment(tracker: ExperimentTracker) -> Any:
    experiments = tracker.list_experiments()
    assert len(experiments) == 1
    experiment = tracker.get_experiment_record(experiments[0].id)
    assert experiment is not None
    return experiment


def _await(condition: Callable[[], bool]) -> None:
    deadline = time.monotonic() + DEADLINE_S
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("the run never reached the expected point")
