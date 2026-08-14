from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import ModuleType
from typing import Any

import lumlflow_kernel.fs as kernel_fs
import pytest
from lumlflow_kernel.executor import Executor


class _FakeDataFrame:
    columns = ["value"]

    def __init__(self, values: list[int]) -> None:
        self.values = values

    def __len__(self) -> int:
        return len(self.values)

    def head(self, limit: int) -> _FakeDataFrame:
        return _FakeDataFrame(self.values[:limit])

    def itertuples(
        self,
        *,
        index: bool,
        name: object,
    ) -> list[tuple[int]]:
        assert index is False
        assert name is None
        return [(value,) for value in self.values]


_FakeDataFrame.__module__ = "pandas"


def run_cell(
    flow_dir: Path,
    source: str,
    produces: dict[str, object],
    *,
    run_id: str = "run-1",
    params: dict[str, object] | None = None,
) -> tuple[dict[str, object], list[tuple[str, dict[str, object]]]]:
    events: list[tuple[str, dict[str, object]]] = []
    executor = Executor(
        flow_dir,
        lambda event, payload: events.append((event, payload)),
    )
    result = executor.run(
        run_id,
        {
            "slug": "test_cell",
            "bound_source": source,
            "manifest": {"produces": produces},
        },
        {},
        params or {},
        {"branch": "main", "step": 7},
    )
    return result, events


def read_log(flow_dir: Path, log_ref: str) -> str:
    path = flow_dir / ".lumlflow" / "logs" / log_ref[:2] / log_ref
    events = [json.loads(line) for line in path.read_text().splitlines()]
    return "".join(event["bytes"] for event in events)


def test_scratch_cwd_captures_declared_file_and_is_removed(tmp_path: Path) -> None:
    source = """
class CheckpointCell:
    def materialize(self, ctx):
        from pathlib import Path
        path = Path("checkpoints/epoch3.pt")
        path.parent.mkdir()
        path.write_bytes(b"weights")
        return {"checkpoint": path}
"""

    result, _ = run_cell(tmp_path, source, {"checkpoint": "asset"})

    assert result["state"] == "succeeded"
    output = result["outputs"]["checkpoint"]  # type: ignore[index]
    assert output["kind"] == "file"
    value_ref = output["value_ref"]
    value_path = tmp_path / ".lumlflow" / "values" / value_ref[:2] / value_ref
    assert value_path.read_bytes() == b"weights"
    assert hashlib.sha256(value_path.read_bytes()).hexdigest() == output["content_hash"]
    assert not (tmp_path / ".lumlflow" / "kernel" / "scratch" / "run-1").exists()

    probe = """
class ProbeCell:
    def materialize(self, ctx):
        from pathlib import Path
        return {"visible": Path("checkpoints").exists()}
"""
    second, _ = run_cell(
        tmp_path,
        probe,
        {"visible": "asset"},
        run_id="run-2",
    )
    probe_output = second["outputs"]["visible"]  # type: ignore[index]
    executor = Executor(tmp_path, lambda event, payload: None)
    assert executor.registry.deserialize(probe_output["value_ref"], "pickle") is False


def test_input_fails_fast_with_prompt_traceback_and_hint(tmp_path: Path) -> None:
    source = """
class InteractiveCell:
    def materialize(self, ctx):
        input("continue?")
        return {"value": 1}
"""

    result, events = run_cell(tmp_path, source, {"value": "asset"})

    assert result["state"] == "failed"
    assert result["error_type"] == "EOFError"
    assert result["hint"] == (
        "cells are non-interactive — take values via params, secrets via ctx"
    )
    logged = read_log(tmp_path, str(result["log_ref"]))
    assert "continue?" in logged
    assert "EOFError" in logged
    assert any(event == "failed" for event, _ in events)


def test_fd_capture_has_one_sequence_and_run_scoped_logs(tmp_path: Path) -> None:
    source = """
class NativeOutputCell:
    def materialize(self, ctx):
        import os
        os.write(2, b"\\x1b[31mprogress\\x1b[0m\\n")
        os.system("printf subprocess-out")
        return {"value": 1}
"""

    first, events = run_cell(tmp_path, source, {"value": "asset"})
    second, _ = run_cell(
        tmp_path,
        source.replace("subprocess-out", "newer-output"),
        {"value": "asset"},
        run_id="run-2",
    )

    logs = [payload for event, payload in events if event == "log"]
    assert {payload["stream"] for payload in logs} == {"stdout", "stderr"}
    assert [payload["seq"] for payload in logs] == list(range(len(logs)))
    first_log = read_log(tmp_path, str(first["log_ref"]))
    assert "\x1b[31mprogress\x1b[0m" in first_log
    assert "subprocess-out" in first_log
    assert "newer-output" not in first_log
    assert first["log_ref"] != second["log_ref"]


def test_context_records_identity_access_and_applies_seed(tmp_path: Path) -> None:
    source = """
class ContextCell:
    def materialize(self, ctx):
        import random
        ctx.seed()
        return {
            "facts": [ctx.branch, ctx.step, ctx.flow_dir.name, random.random()]
        }
"""

    first, events = run_cell(
        tmp_path,
        source,
        {"facts": "asset"},
        params={"seed": 42},
    )
    second, _ = run_cell(
        tmp_path,
        source,
        {"facts": "asset"},
        run_id="run-2",
        params={"seed": 42},
    )

    accesses = [
        payload["attr"] for event, payload in events if event == "identity_access"
    ]
    assert accesses == ["branch", "step", "flow_dir"]
    assert (
        first["outputs"]["facts"]["content_hash"]  # type: ignore[index]
        == second["outputs"]["facts"]["content_hash"]  # type: ignore[index]
    )


def test_context_secret_uses_rpc_callback_and_reset_hooks_restore_env(
    tmp_path: Path,
) -> None:
    events: list[tuple[str, dict[str, object]]] = []
    executor = Executor(
        tmp_path,
        lambda event, payload: events.append((event, payload)),
        secret_request=lambda name: f"secret:{name}",
    )
    source = """
class SecretCell:
    def materialize(self, ctx):
        import os
        os.environ["LUMLFLOW_TEST_DELTA"] = "changed"
        return {"secret": ctx.secret("token")}
"""

    result = executor.run(
        "secret-run",
        {
            "slug": "secret_cell",
            "bound_source": source,
            "manifest": {"produces": {"secret": "asset"}},
        },
        {},
        {},
        {"branch": "main", "step": 1},
    )

    assert result["state"] == "succeeded"
    assert "LUMLFLOW_TEST_DELTA" not in os.environ
    output = result["outputs"]["secret"]  # type: ignore[index]
    assert executor.registry.deserialize(output["value_ref"], "pickle") == (
        "secret:token"
    )


def test_paranoid_mode_rejects_mutation_and_restores_cached_input(
    tmp_path: Path,
) -> None:
    executor = Executor(tmp_path, lambda event, payload: None)
    serialized = executor.registry.serialize([1, 2, 3], "pickle")
    mutating_source = """
class MutatingCell:
    def materialize(self, ctx, values):
        values.clear()
        return {"count": len(values)}
"""
    inputs = {
        "values": {
            "value_ref": serialized.value_ref,
            "content_hash": serialized.content_hash,
            "kind": "pickle",
        }
    }

    failed = executor.run(
        "mutating-run",
        {
            "slug": "mutating_cell",
            "bound_source": mutating_source,
            "manifest": {"produces": {"count": "asset"}},
        },
        inputs,
        {},
        {"branch": "main", "step": 1, "paranoid": True},
    )

    assert failed["state"] == "failed"
    assert "mutating_cell" in str(failed["error"])
    assert "values" in str(failed["error"])

    probe_source = """
class ProbeCell:
    def materialize(self, ctx, values):
        return {"count": len(values)}
"""
    restored = executor.run(
        "probe-run",
        {
            "slug": "probe_cell",
            "bound_source": probe_source,
            "manifest": {"produces": {"count": "asset"}},
        },
        inputs,
        {},
        {"branch": "main", "step": 2},
    )

    assert restored["state"] == "succeeded"
    count = restored["outputs"]["count"]  # type: ignore[index]
    assert executor.registry.deserialize(count["value_ref"], "pickle") == 3


def test_strict_mode_hands_consumers_defensive_input_copies(tmp_path: Path) -> None:
    executor = Executor(tmp_path, lambda event, payload: None)
    serialized = executor.registry.serialize([1, 2, 3], "pickle")
    inputs = {
        "values": {
            "value_ref": serialized.value_ref,
            "content_hash": serialized.content_hash,
            "kind": "pickle",
            "shared": True,
        }
    }
    mutating_source = """
class MutatingCell:
    def materialize(self, ctx, values):
        values.clear()
        return {"count": len(values)}
"""

    result = executor.run(
        "strict-run",
        {
            "slug": "mutating_cell",
            "bound_source": mutating_source,
            "manifest": {"produces": {"count": "asset"}},
        },
        inputs,
        {},
        {"branch": "main", "step": 1, "strict": True},
    )

    assert result["state"] == "succeeded"
    probe_source = """
class ProbeCell:
    def materialize(self, ctx, values):
        return {"count": len(values)}
"""
    probe = executor.run(
        "strict-probe",
        {
            "slug": "probe_cell",
            "bound_source": probe_source,
            "manifest": {"produces": {"count": "asset"}},
        },
        inputs,
        {},
        {"branch": "main", "step": 2},
    )

    assert probe["state"] == "succeeded"
    count = probe["outputs"]["count"]  # type: ignore[index]
    assert executor.registry.deserialize(count["value_ref"], "pickle") == 3


def test_atomic_replace_retries_sharing_violations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.write_bytes(b"complete")
    real_replace = os.replace
    attempts = 0

    def flaky_replace(source_path: Path, destination_path: Path) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("sharing violation")
        real_replace(source_path, destination_path)

    monkeypatch.setattr(kernel_fs.os, "replace", flaky_replace)

    kernel_fs.replace_with_retry(source, destination)

    assert destination.read_bytes() == b"complete"
    assert attempts == 3


def test_persisted_log_artifact_respects_configured_byte_cap(tmp_path: Path) -> None:
    source = """
class LoudCell:
    def materialize(self, ctx):
        print("x" * 1000)
        return {"value": 1}
"""
    events: list[tuple[str, dict[str, object]]] = []
    executor = Executor(
        tmp_path,
        lambda event, payload: events.append((event, payload)),
        log_limit_bytes=128,
    )

    result = executor.run(
        "loud-run",
        {
            "slug": "loud_cell",
            "bound_source": source,
            "manifest": {"produces": {"value": "asset"}},
        },
        {},
        {},
        {"branch": "main", "step": 1},
    )

    log_ref = str(result["log_ref"])
    log_path = tmp_path / ".lumlflow" / "logs" / log_ref[:2] / log_ref
    assert log_path.stat().st_size <= 128
    assert result["log_truncated"] is True
    assert any(event == "log" for event, _payload in events)


def test_cancel_interrupts_the_running_cell(tmp_path: Path) -> None:
    started = threading.Event()
    executor = Executor(
        tmp_path,
        lambda event, payload: started.set() if event == "started" else None,
    )
    source = """
class BusyCell:
    def materialize(self, ctx):
        while True:
            pass
"""
    result: dict[str, object] = {}

    def execute() -> None:
        result.update(
            executor.run(
                "busy-run",
                {
                    "slug": "busy_cell",
                    "bound_source": source,
                    "manifest": {"produces": {}},
                },
                {},
                {},
                {"branch": "main", "step": 1},
            )
        )

    thread = threading.Thread(target=execute)
    thread.start()
    assert started.wait(timeout=2)
    deadline = time.monotonic() + 2
    cancelled = False
    while not cancelled and time.monotonic() < deadline:
        cancelled = executor.cancel("busy-run")["cancelled"]
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert result["state"] == "cancelled"


def test_kind_inference_override_plugin_and_bounded_previews(tmp_path: Path) -> None:
    library = tmp_path / "lib"
    library.mkdir()
    (library / "emb_kind.py").write_text(
        """
import pickle

class EmbKind:
    kind = "embedding"
    priority = 950
    provenance = "flow:lib/emb_kind.py"
    def matches(self, value):
        return type(value).__name__ == "EmbTable"
    def serialize(self, value, sink):
        pickle.dump(value.values, sink)
        return "pickle"
    def deserialize(self, source):
        return pickle.load(source)
    def preview(self, value):
        return {"schema": 1, "kind": self.kind, "blocks": [{"type": "kv", "items": []}]}

LUMLFLOW_KINDS = [EmbKind()]
"""
    )
    source = """
class EmbTable:
    def __init__(self):
        self.values = [1, 2, 3]

class KindsCell:
    def materialize(self, ctx):
        return {
            "metric": {"accuracy": 0.9, "loss": 0.2},
            "plugin": EmbTable(),
            "fallback": object(),
            "forced": {"value": 2.0},
            "large": "x" * 100000,
        }
"""
    produces: dict[str, object] = {
        "metric": "asset",
        "plugin": "asset",
        "fallback": "asset",
        "forced": {"type": "asset", "kind": "pickle"},
        "large": "asset",
    }

    result, events = run_cell(tmp_path, source, produces)

    outputs: dict[str, dict[str, Any]] = result["outputs"]  # type: ignore[assignment]
    assert outputs["metric"]["kind"] == "metric"
    assert outputs["plugin"]["kind"] == "embedding"
    assert outputs["fallback"]["kind"] == "pickle"
    assert outputs["forced"]["kind"] == "pickle"
    facts = {
        payload["output"]: payload
        for event, payload in events
        if event == "kind_inferred"
    }
    assert facts["plugin"]["provenance"] == "flow:lib/emb_kind.py"
    assert facts["forced"]["override"] is True
    for output in outputs.values():
        preview_ref = output["preview_ref"]
        preview_path = (
            tmp_path
            / ".lumlflow"
            / "previews"
            / preview_ref[:2]
            / f"{preview_ref}.json"
        )
        assert preview_path.stat().st_size <= 64 * 1024
        assert json.loads(preview_path.read_text())["schema"] == 1


def test_native_experiment_is_staged_with_rich_preview_and_tracker_records(
    tmp_path: Path,
) -> None:
    source = """
class ExperimentCell:
    def materialize(self, ctx):
        experiment_id = ctx.tracker.start_experiment(name="trial")
        ctx.tracker.log_static("lr", 0.01)
        ctx.tracker.log_dynamic("loss", 0.8, step=0)
        ctx.tracker.end_experiment(experiment_id)
        return {
            "run": {
                "name": "trial",
                "metrics": {"accuracy": 0.9},
                "history": {"loss": [0.8, 0.4]},
            }
        }
"""

    result, events = run_cell(tmp_path, source, {"run": "experiment"})

    assert result["state"] == "succeeded"
    output = result["outputs"]["run"]  # type: ignore[index]
    assert output["native_type"] == "experiment"
    value_ref = str(output["value_ref"])
    assert (tmp_path / ".lumlflow" / "values" / value_ref[:2] / value_ref).is_file()
    preview_ref = str(output["preview_ref"])
    preview_path = (
        tmp_path / ".lumlflow" / "previews" / preview_ref[:2] / f"{preview_ref}.json"
    )
    preview = json.loads(preview_path.read_text())
    assert preview["kind"] == "experiment"
    assert any(block["type"] == "series" for block in preview["blocks"])
    records = output["metadata"]["tracker_records"]
    assert [record["method"] for record in records] == [
        "start_experiment",
        "log_static",
        "log_dynamic",
        "end_experiment",
    ]
    assert len([event for event, _payload in events if event == "tracker_record"]) == 4


def test_frame_kind_inference_serializes_and_builds_bounded_table_preview(
    tmp_path: Path,
) -> None:
    pandas_module = ModuleType("pandas")
    pandas_module._FakeDataFrame = _FakeDataFrame  # type: ignore[attr-defined]
    previous_pandas = sys.modules.get("pandas")
    sys.modules["pandas"] = pandas_module
    try:
        executor = Executor(tmp_path, lambda event, payload: None)

        serialized = executor.registry.serialize(_FakeDataFrame(list(range(25))))
        preview_path = (
            tmp_path
            / ".lumlflow"
            / "previews"
            / serialized.preview_ref[:2]
            / f"{serialized.preview_ref}.json"
        )
        preview = json.loads(preview_path.read_text())

        assert serialized.kind == "frame"
        assert preview["blocks"][0]["total_rows"] == 25
        assert len(preview["blocks"][0]["rows"]) == 20
    finally:
        if previous_pandas is None:
            sys.modules.pop("pandas", None)
        else:
            sys.modules["pandas"] = previous_pandas


def test_kernel_modules_do_not_import_third_party_packages_at_module_load() -> None:
    code = """
import sys
import lumlflow_kernel
print(any(name in sys.modules for name in ("pandas", "pydantic", "cloudpickle")))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == "False"
