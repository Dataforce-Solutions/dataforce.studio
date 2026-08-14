from __future__ import annotations

import ctypes
import importlib
import importlib.metadata
import inspect
import logging
import os
import shutil
import sys
import threading
import traceback
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .capture import FDCapture
from .ctxobj import RunContext
from .kinds import KindRegistry
from .repl import ScratchEvaluator, ValueDescriptor

EventEmitter = Callable[[str, dict[str, object]], None]
SecretRequester = Callable[[str], str]


class Executor:
    def __init__(
        self,
        flow_dir: Path,
        emit: EventEmitter,
        *,
        secret_request: SecretRequester | None = None,
        log_limit_bytes: int = 4 * 1024 * 1024,
    ) -> None:
        self.flow_dir = flow_dir.resolve()
        if str(self.flow_dir) not in sys.path:
            sys.path.insert(0, str(self.flow_dir))
        self.store_dir = self.flow_dir / ".lumlflow"
        self.scratch_root = self.store_dir / "kernel" / "scratch"
        self.scratch_root.mkdir(parents=True, exist_ok=True)
        self.emit = emit
        self.secret_request = secret_request or self._secret_unavailable
        self.log_limit_bytes = log_limit_bytes
        self.registry = KindRegistry(
            self.flow_dir,
            self.store_dir / "values",
            self.store_dir / "previews",
        )
        self._run_threads: dict[str, int] = {}
        self._run_lock = threading.Lock()
        self._hot_values: OrderedDict[tuple[str, str], Any] = OrderedDict()
        self._enable_pandas_copy_on_write()

    def handshake(self) -> dict[str, object]:
        return {
            "protocol": 1,
            "python": ".".join(str(part) for part in sys.version_info[:3]),
            "capabilities": [
                "run",
                "cancel",
                "load_slice",
                "page",
                "diff",
                "eval",
                "fd_capture",
                "identity_access",
                "loaded_packages",
            ],
            "kinds": self.registry.report(),
        }

    def load_slice(self, values: dict[str, dict[str, str]]) -> dict[str, int]:
        loaded = 0
        for item in values.values():
            value_ref = item["value_ref"]
            kind = item["kind"]
            if kind == "file":
                continue
            self._get_cached(value_ref, kind)
            loaded += 1
        return {"loaded": loaded}

    def run(
        self,
        run_id: str,
        version: dict[str, Any],
        inputs: dict[str, dict[str, Any]],
        params: dict[str, object],
        ctx_info: dict[str, object],
    ) -> dict[str, object]:
        if not run_id or any(character in run_id for character in "/\\"):
            raise ValueError("run_id must be a non-empty path-safe identifier")
        with self._run_lock:
            return self._run_serial(run_id, version, inputs, params, ctx_info)

    def cancel(self, run_id: str) -> dict[str, bool]:
        thread_id = self._run_threads.get(run_id)
        if thread_id is None:
            return {"cancelled": False}
        result = ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(thread_id),
            ctypes.py_object(KeyboardInterrupt),
        )
        if result > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_ulong(thread_id),
                ctypes.c_void_p(),
            )
            raise RuntimeError("could not target the running cell thread")
        return {"cancelled": result == 1}

    def page(self, value_ref: str, kind: str, query: dict[str, Any]) -> Any:
        return self.registry.page(value_ref, kind, query)

    def diff(self, ref_a: str, ref_b: str, kind: str) -> Any:
        return self.registry.diff(ref_a, ref_b, kind)

    def evaluate(
        self,
        branch_slice: dict[str, ValueDescriptor],
        code: str,
        *,
        paranoid: bool = False,
    ) -> dict[str, object]:
        if not isinstance(code, str):
            raise TypeError("eval code must be a string")

        def load_copy(descriptor: ValueDescriptor) -> Any:
            value_ref = descriptor["value_ref"]
            kind = descriptor["kind"]
            self._get_cached(value_ref, kind)
            return self.registry.deserialize(value_ref, kind)

        evaluator = ScratchEvaluator(branch_slice, load_copy)
        with self._run_lock:
            result: dict[str, object] | None = None
            evaluation_error: Exception | None = None
            try:
                result = evaluator.execute(code, self.registry.preview)
            except Exception as error:
                evaluation_error = error
            if paranoid:
                try:
                    evaluator.check_integrity(self._check_eval_value_integrity)
                except Exception as error:
                    evaluation_error = error
            if evaluation_error is not None:
                return {
                    "state": "failed",
                    "error_type": type(evaluation_error).__name__,
                    "error": str(evaluation_error),
                }
            assert result is not None
            return result

    def evict_lib(self) -> dict[str, int]:
        names = [
            name for name in sys.modules if name == "lib" or name.startswith("lib.")
        ]
        for name in names:
            del sys.modules[name]
        return {"evicted": len(names)}

    def loaded_packages(self) -> dict[str, str]:
        package_distributions = importlib.metadata.packages_distributions()
        loaded: dict[str, str] = {}
        for module_name, module in tuple(sys.modules.items()):
            if "." in module_name or module is None:
                continue
            version = getattr(module, "__version__", None)
            if not isinstance(version, str):
                continue
            for distribution in package_distributions.get(module_name, ()):
                normalized = distribution.casefold().replace("_", "-").replace(".", "-")
                loaded[normalized] = version
        return loaded

    def _run_serial(
        self,
        run_id: str,
        version: dict[str, Any],
        inputs: dict[str, dict[str, Any]],
        params: dict[str, object],
        ctx_info: dict[str, object],
    ) -> dict[str, object]:
        self._enable_pandas_copy_on_write()
        source = version.get("bound_source")
        if not isinstance(source, str):
            raise ValueError("version.bound_source must be source text")
        slug = str(version.get("slug", "cell"))
        manifest = version.get("manifest", {})
        if not isinstance(manifest, dict):
            raise ValueError("version.manifest must be an object")
        produces = manifest.get("produces", version.get("produces", {}))
        if not isinstance(produces, dict):
            raise ValueError("version produces declaration must be an object")
        scratch_dir = self.scratch_root / run_id
        if scratch_dir.exists():
            shutil.rmtree(scratch_dir)
        scratch_dir.mkdir(parents=True)
        original_cwd = Path.cwd()
        original_environment = os.environ.copy()
        root_logger = logging.getLogger()
        original_handlers = list(root_logger.handlers)
        original_level = root_logger.level
        logger_states = self._snapshot_loggers()
        capture = FDCapture(
            run_id,
            self.emit,
            self.store_dir / "logs",
            limit_bytes=self.log_limit_bytes,
        )
        self._run_threads[run_id] = threading.get_ident()
        self.emit("started", {"run_id": run_id})
        try:
            with capture, _NullStdin():
                os.chdir(scratch_dir)
                resolved_inputs = self._resolve_inputs(
                    inputs,
                    scratch_dir,
                    strict=ctx_info.get("strict", False) is True,
                )
                context = RunContext(
                    run_id=run_id,
                    scratch_dir=scratch_dir,
                    flow_dir=self.flow_dir,
                    branch=str(ctx_info.get("branch", "")),
                    step=self._ctx_step(ctx_info.get("step", 0)),
                    params=params,
                    emit=self.emit,
                    secret_request=self.secret_request,
                )
                cell = self._instantiate_cell(source, slug)
                cell.params = dict(params)
                try:
                    returned = cell.materialize(context, **resolved_inputs)
                finally:
                    if ctx_info.get("paranoid", False) is True:
                        self._check_input_integrity(slug, inputs, resolved_inputs)
                if not isinstance(returned, dict):
                    raise TypeError(
                        "materialize() must return a dict of declared outputs"
                    )
                missing = sorted(set(produces) - set(returned))
                extra = sorted(set(returned) - set(produces))
                if missing or extra:
                    raise ValueError(
                        "returned outputs do not match declaration; "
                        f"missing={missing}, extra={extra}"
                    )
                outputs = self._capture_outputs(
                    run_id,
                    returned,
                    produces,
                    context.tracker.records,
                )
            log_ref, log_size = capture.persist()
            result: dict[str, object] = {
                "run_id": run_id,
                "state": "succeeded",
                "outputs": outputs,
                "log_ref": log_ref,
                "log_size": log_size,
                "log_truncated": capture.truncated,
            }
            self.emit("materialized", result)
            return result
        except BaseException as error:
            capture.record("stderr", traceback.format_exc().encode())
            log_ref, log_size = capture.persist()
            cancelled = isinstance(error, KeyboardInterrupt)
            failure: dict[str, object] = {
                "run_id": run_id,
                "state": "cancelled" if cancelled else "failed",
                "error_type": type(error).__name__,
                "error": str(error),
                "log_ref": log_ref,
                "log_size": log_size,
                "log_truncated": capture.truncated,
            }
            if isinstance(error, EOFError):
                failure["hint"] = (
                    "cells are non-interactive — take values via params, "
                    "secrets via ctx"
                )
            self.emit("failed", failure)
            return failure
        finally:
            os.chdir(original_cwd)
            os.environ.clear()
            os.environ.update(original_environment)
            root_logger.handlers[:] = original_handlers
            root_logger.setLevel(original_level)
            self._restore_loggers(logger_states)
            self._close_figures()
            self._run_threads.pop(run_id, None)
            shutil.rmtree(scratch_dir, ignore_errors=True)

    def _resolve_inputs(
        self,
        inputs: dict[str, dict[str, Any]],
        scratch_dir: Path,
        *,
        strict: bool,
    ) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        for name, item in inputs.items():
            value_ref = item["value_ref"]
            kind = item["kind"]
            if kind == "file":
                filename = Path(item.get("name", name)).name
                destination = scratch_dir / "inputs" / name / filename
                destination.parent.mkdir(parents=True, exist_ok=True)
                source = self.registry.values_root / value_ref[:2] / value_ref
                shutil.copyfile(source, destination)
                resolved[name] = destination
            else:
                defensive_copy = strict and item.get("shared", False) is True
                value = (
                    self.registry.deserialize(value_ref, kind)
                    if defensive_copy
                    else self._get_cached(value_ref, kind)
                )
                resolved[name] = self._protect_input(value)
        return resolved

    def _get_cached(self, value_ref: str, kind: str) -> Any:
        key = (value_ref, kind)
        if key in self._hot_values:
            value = self._hot_values.pop(key)
            self._hot_values[key] = value
            return value
        value = self.registry.deserialize(value_ref, kind)
        self._hot_values[key] = value
        while len(self._hot_values) > 32:
            self._hot_values.popitem(last=False)
        return value

    def _check_input_integrity(
        self,
        slug: str,
        inputs: dict[str, dict[str, Any]],
        resolved_inputs: dict[str, Any],
    ) -> None:
        mutated: list[str] = []
        for name, item in inputs.items():
            value_ref = item["value_ref"]
            kind = item["kind"]
            expected_hash = item.get("content_hash", value_ref)
            actual_hash = self.registry.content_hash(resolved_inputs[name], kind)
            if actual_hash == expected_hash:
                continue
            mutated.append(name)
            self._hot_values.pop((value_ref, kind), None)
        if mutated:
            names = ", ".join(mutated)
            raise RuntimeError(
                f"cell {slug!r} mutated consumed input(s): {names}; "
                "values were restored from the store"
            )

    def _check_eval_value_integrity(self, descriptor: ValueDescriptor) -> None:
        value_ref = descriptor["value_ref"]
        kind = descriptor["kind"]
        expected_hash = descriptor.get("content_hash", value_ref)
        cached = self._get_cached(value_ref, kind)
        if self.registry.content_hash(cached, kind) == expected_hash:
            return
        self._hot_values.pop((value_ref, kind), None)
        raise RuntimeError("evaluation mutated a cached asset; value was restored")

    def _capture_outputs(
        self,
        run_id: str,
        returned: dict[str, Any],
        produces: dict[str, Any],
        tracker_records: list[dict[str, object]],
    ) -> dict[str, dict[str, object]]:
        outputs: dict[str, dict[str, object]] = {}
        for name, value in returned.items():
            declaration = produces[name]
            override = (
                declaration.get("kind") if isinstance(declaration, dict) else None
            )
            output_type = (
                declaration.get("type")
                if isinstance(declaration, dict)
                else declaration
            )
            native_type = (
                output_type
                if output_type in {"model", "dataset", "experiment"}
                else None
            )
            serialized = self.registry.serialize(
                value,
                override,
                preview_kind=native_type,
            )
            output = serialized.as_dict()
            if native_type is not None:
                output["native_type"] = native_type
            if native_type == "experiment" and tracker_records:
                output["metadata"] = {"tracker_records": tracker_records}
            outputs[name] = output
            self.emit(
                "kind_inferred",
                {
                    "run_id": run_id,
                    "output": name,
                    "kind": serialized.kind,
                    "provenance": serialized.provenance,
                    "override": override is not None,
                },
            )
            self.emit(
                "preview",
                {
                    "run_id": run_id,
                    "output": name,
                    "kind": serialized.kind,
                    "preview_ref": serialized.preview_ref,
                },
            )
        return outputs

    @staticmethod
    def _instantiate_cell(source: str, slug: str) -> Any:
        namespace: dict[str, Any] = {
            "__name__": "__lumlflow_cell__",
            "__file__": f"cells/{slug}.py",
        }
        exec(compile(source, namespace["__file__"], "exec"), namespace)
        candidates = [
            value
            for value in namespace.values()
            if inspect.isclass(value)
            and value.__module__ == "__lumlflow_cell__"
            and callable(getattr(value, "materialize", None))
        ]
        if len(candidates) != 1:
            raise ValueError(
                "bound source must define exactly one materialize cell class"
            )
        return candidates[0]()

    @staticmethod
    def _protect_input(value: Any) -> Any:
        if type(value).__module__.split(".", maxsplit=1)[0] != "numpy":
            return value
        try:
            protected = value.view()
            protected.flags.writeable = False
        except (AttributeError, TypeError, ValueError):
            return value
        return protected

    @staticmethod
    def _close_figures() -> None:
        pyplot = sys.modules.get("matplotlib.pyplot")
        if pyplot is not None:
            pyplot.close("all")

    @staticmethod
    def _enable_pandas_copy_on_write() -> None:
        try:
            pandas = importlib.import_module("pandas")
        except ImportError:
            return
        try:
            pandas.options.mode.copy_on_write = True
        except (AttributeError, ValueError):
            pass

    @staticmethod
    def _snapshot_loggers() -> dict[
        str,
        tuple[list[logging.Handler], int, bool, bool],
    ]:
        states: dict[str, tuple[list[logging.Handler], int, bool, bool]] = {}
        for name, candidate in logging.Logger.manager.loggerDict.items():
            if isinstance(candidate, logging.Logger):
                states[name] = (
                    list(candidate.handlers),
                    candidate.level,
                    candidate.propagate,
                    candidate.disabled,
                )
        return states

    @staticmethod
    def _restore_loggers(
        states: dict[str, tuple[list[logging.Handler], int, bool, bool]],
    ) -> None:
        for name, candidate in logging.Logger.manager.loggerDict.items():
            if not isinstance(candidate, logging.Logger):
                continue
            state = states.get(name)
            if state is None:
                candidate.handlers.clear()
                continue
            handlers, level, propagate, disabled = state
            candidate.handlers[:] = handlers
            candidate.setLevel(level)
            candidate.propagate = propagate
            candidate.disabled = disabled

    @staticmethod
    def _ctx_step(value: object) -> int:
        if not isinstance(value, (int, str, bytes, bytearray)):
            raise ValueError("ctx_info.step must be an integer")
        return int(value)

    @staticmethod
    def _secret_unavailable(name: str) -> str:
        raise RuntimeError(f"secret RPC is unavailable for {name!r}")


class _NullStdin:
    def __init__(self) -> None:
        self._saved_fd: int | None = None
        self._null_fd: int | None = None
        self._saved_stream: Any = None
        self._null_stream: Any = None

    def __enter__(self) -> _NullStdin:
        self._saved_fd = os.dup(0)
        self._null_fd = os.open(os.devnull, os.O_RDONLY)
        os.dup2(self._null_fd, 0)
        self._saved_stream = sys.stdin
        self._null_stream = open(os.devnull, encoding="utf-8")
        sys.stdin = self._null_stream
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback_object: object | None,
    ) -> None:
        sys.stdin = self._saved_stream
        if self._null_stream is not None:
            self._null_stream.close()
        if self._saved_fd is not None:
            os.dup2(self._saved_fd, 0)
            os.close(self._saved_fd)
        if self._null_fd is not None:
            os.close(self._null_fd)
