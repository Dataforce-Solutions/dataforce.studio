from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import platform
import re
import secrets
import shutil
import socket
import subprocess
import time
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from lumlflow.flow.ids import mint_ulid
from lumlflow.flow.scheduler.planner import (
    ExecutionCancelledError,
    ExecutionResult,
    PlanNode,
)
from lumlflow.flow.store.cas import atomic_write
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import InputRecord, JsonValue, OutputRecord

KernelEventHandler = Callable[[str, dict[str, Any]], None]
SandboxProfile = Literal[
    "linux-unshare-network",
    "linux-plain",
    "macos-sandbox-exec",
    "macos-plain",
    "windows-plain",
    "plain",
]


class KernelRpcError(RuntimeError):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


class KernelExecutionError(RuntimeError):
    def __init__(self, message: str, *, log_ref: str | None = None) -> None:
        super().__init__(message)
        self.log_ref = log_ref


class KernelClient:
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *,
        token: str | None = None,
        event_handler: KernelEventHandler | None = None,
    ) -> None:
        self.reader = reader
        self.writer = writer
        self.token = token
        self.event_handler = event_handler
        self._next_id = 1
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._write_lock = asyncio.Lock()
        self._reader_task = asyncio.create_task(self._read_messages())

    @classmethod
    async def connect_unix(
        cls,
        path: Path,
        *,
        event_handler: KernelEventHandler | None = None,
    ) -> KernelClient:
        reader, writer = await asyncio.open_unix_connection(path)
        return cls(reader, writer, event_handler=event_handler)

    @classmethod
    async def connect_tcp(
        cls,
        host: str,
        port: int,
        token: str,
        *,
        event_handler: KernelEventHandler | None = None,
    ) -> KernelClient:
        reader, writer = await asyncio.open_connection(host, port)
        return cls(reader, writer, token=token, event_handler=event_handler)

    @property
    def closed(self) -> bool:
        return self.writer.is_closing() or self._reader_task.done()

    async def request(
        self,
        method: str,
        params: dict[str, JsonValue] | None = None,
        *,
        timeout: float = 30.0,
    ) -> Any:
        if self.closed:
            raise ConnectionError("kernel connection is closed")
        request_id = self._next_id
        self._next_id += 1
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        message: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }
        if self.token is not None:
            message["token"] = self.token
        try:
            await self._send(message)
            return await asyncio.wait_for(future, timeout)
        finally:
            self._pending.pop(request_id, None)

    async def close(self) -> None:
        if not self.closed:
            try:
                await self.request("shutdown", timeout=5.0)
            except (ConnectionError, KernelRpcError, TimeoutError):
                pass
        self.writer.close()
        try:
            await self.writer.wait_closed()
        except ConnectionError:
            pass
        if not self._reader_task.done():
            self._reader_task.cancel()
        await asyncio.gather(self._reader_task, return_exceptions=True)

    async def _read_messages(self) -> None:
        failure: BaseException | None = None
        try:
            while line := await self.reader.readline():
                message = json.loads(line)
                if not isinstance(message, dict):
                    continue
                request_id = message.get("id")
                if isinstance(request_id, int) and "method" not in message:
                    future = self._pending.get(request_id)
                    if future is None or future.done():
                        continue
                    error = message.get("error")
                    if isinstance(error, dict):
                        future.set_exception(
                            KernelRpcError(
                                int(error.get("code", -32603)),
                                str(error.get("message", "kernel request failed")),
                            )
                        )
                    else:
                        future.set_result(message.get("result"))
                    continue
                method = message.get("method")
                params = message.get("params", {})
                if method == "secret" and request_id is not None:
                    await self._send(
                        {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "error": {
                                "code": -32002,
                                "message": "secrets are not configured",
                            },
                        }
                    )
                elif isinstance(method, str) and isinstance(params, dict):
                    if self.event_handler is not None:
                        self.event_handler(method, params)
        except (ConnectionError, json.JSONDecodeError) as caught:
            failure = caught
        finally:
            terminal_error = failure or ConnectionError("kernel connection closed")
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(terminal_error)

    async def _send(self, message: dict[str, Any]) -> None:
        encoded = json.dumps(message, separators=(",", ":")).encode() + b"\n"
        async with self._write_lock:
            self.writer.write(encoded)
            await self.writer.drain()


class KernelProcess:
    def __init__(
        self,
        flow_dir: Path,
        *,
        start_timeout: float = 30.0,
        event_handler: KernelEventHandler | None = None,
    ) -> None:
        self.flow_dir = flow_dir.resolve()
        self.kernel_dir = self.flow_dir / ".lumlflow" / "kernel"
        self.socket_path = self.kernel_dir / "kernel.sock"
        self.port_path = self.kernel_dir / "port"
        self.token_path = self.kernel_dir / "token"
        self.pid_path = self.kernel_dir / "pid"
        self.start_timeout = start_timeout
        self.event_handler = event_handler
        self.process: subprocess.Popen[bytes] | None = None
        self.client: KernelClient | None = None
        self.handshake: dict[str, Any] | None = None
        self.active_runs: set[str] = set()
        self._events: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        self._run_slugs: dict[str, str] = {}
        self._lifecycle_lock = asyncio.Lock()
        self.sandbox_profile = _select_sandbox_profile()

    @property
    def running(self) -> bool:
        return (
            self.process is not None
            and self.process.poll() is None
            and self.client is not None
            and not self.client.closed
        )

    def run_for_slug(self, slug: str) -> str | None:
        return next(
            (
                run_id
                for run_id, active_slug in self._run_slugs.items()
                if active_slug == slug
            ),
            None,
        )

    async def start(self) -> dict[str, Any]:
        async with self._lifecycle_lock:
            if self.running:
                assert self.handshake is not None
                return self.handshake
            await self._stop_unlocked()
            python = await asyncio.to_thread(self._venv_python)
            self.kernel_dir.mkdir(parents=True, exist_ok=True)
            command, token = self._command(python)
            environment = os.environ.copy()
            environment["PYTHONPATH"] = os.fspath(_kernel_import_root())
            self.process = subprocess.Popen(
                command,
                cwd=self.flow_dir,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            atomic_write(self.pid_path, f"{self.process.pid}\n".encode())
            try:
                self.client = await self._connect(token)
                result = await self.client.request("handshake", timeout=5.0)
                if not isinstance(result, dict) or result.get("protocol") != 1:
                    raise RuntimeError("kernel protocol handshake failed")
                self.handshake = result
                return result
            except BaseException:
                await self._stop_unlocked()
                raise

    async def stop(self) -> None:
        async with self._lifecycle_lock:
            await self._stop_unlocked()

    async def restart(self) -> dict[str, Any]:
        async with self._lifecycle_lock:
            await self._stop_unlocked()
        return await self.start()

    async def request(
        self,
        method: str,
        params: dict[str, JsonValue] | None = None,
        *,
        timeout: float = 30.0,
    ) -> Any:
        await self.start()
        assert self.client is not None
        return await self.client.request(method, params, timeout=timeout)

    async def execute(
        self,
        store: FlowStore,
        node: PlanNode,
        inputs: dict[str, InputRecord],
        *,
        branch_id: str,
    ) -> ExecutionResult:
        run_id = mint_ulid()
        version = _kernel_version(store, node)
        paranoid = _flow_mode_enabled(store.flow_dir, "paranoid")
        strict = _flow_mode_enabled(store.flow_dir, "strict")
        kernel_inputs = _kernel_inputs(store, inputs, strict=strict)
        params = node.manifest.get("params", {})
        if not isinstance(params, dict):
            params = {}
        self.active_runs.add(run_id)
        self._run_slugs[run_id] = node.slug
        self._events[run_id] = []
        started = time.monotonic()
        events: list[tuple[str, dict[str, Any]]]
        try:
            raw = await self.request(
                "run",
                {
                    "run_id": run_id,
                    "version": version,
                    "inputs": kernel_inputs,
                    "params": params,
                    "ctx_info": {
                        "branch": branch_id,
                        "step": store.last_step,
                        "paranoid": paranoid,
                        "strict": strict,
                    },
                },
                timeout=24 * 60 * 60,
            )
        finally:
            self.active_runs.discard(run_id)
            self._run_slugs.pop(run_id, None)
            events = self._events.pop(run_id, [])
        if not isinstance(raw, dict):
            raise RuntimeError("kernel returned an invalid run response")
        state = raw.get("state")
        if state == "cancelled":
            raise ExecutionCancelledError(f"cell run cancelled: {node.slug}")
        if state != "succeeded":
            error_type = raw.get("error_type")
            message = str(raw.get("error", f"kernel run {state}"))
            if isinstance(error_type, str):
                message = f"{error_type}: {message}"
            hint = raw.get("hint")
            if hint:
                message = f"{message}: {hint}"
            log_ref = raw.get("log_ref")
            raise KernelExecutionError(
                message,
                log_ref=log_ref if isinstance(log_ref, str) else None,
            )
        raw_outputs = raw.get("outputs")
        if not isinstance(raw_outputs, dict):
            raise RuntimeError("kernel response has no outputs")
        outputs: dict[str, OutputRecord] = {}
        for name, value in raw_outputs.items():
            if not isinstance(value, dict):
                raise RuntimeError(f"kernel output {name} is invalid")
            outputs[str(name)] = _output_record(value)
        identity_dependent = any(name == "identity_access" for name, _ in events)
        log_ref = raw.get("log_ref")
        return ExecutionResult(
            outputs=outputs,
            cost_seconds=time.monotonic() - started,
            identity_dependent=identity_dependent,
            log_ref=log_ref if isinstance(log_ref, str) else None,
        )

    async def cancel(self, run_id: str | None = None) -> dict[str, bool]:
        target = run_id
        if target is None:
            target = next(iter(self.active_runs), None)
        if target is None:
            return {"cancelled": False}
        result = await self.request("cancel", {"run_id": target}, timeout=5.0)
        return result if isinstance(result, dict) else {"cancelled": False}

    async def evict_lib(self) -> int:
        result = await self.request("evict_lib", timeout=5.0)
        return int(result.get("evicted", 0)) if isinstance(result, dict) else 0

    async def loaded_packages(self) -> dict[str, str]:
        if not self.running:
            return {}
        result = await self.request("loaded_packages", timeout=5.0)
        if not isinstance(result, dict):
            raise RuntimeError("kernel returned invalid loaded-package metadata")
        return {
            str(name): str(version)
            for name, version in result.items()
            if isinstance(name, str) and isinstance(version, str)
        }

    def _command(self, python: Path) -> tuple[list[str], str | None]:
        if _use_tcp_transport():
            port = _available_port()
            token = secrets.token_urlsafe(32)
            atomic_write(self.port_path, f"{port}\n".encode())
            atomic_write(self.token_path, f"{token}\n".encode())
            if os.name == "posix":
                self.token_path.chmod(0o600)
            command = [
                os.fspath(python),
                "-m",
                "lumlflow_kernel",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--token",
                token,
                "--flow-dir",
                os.fspath(self.flow_dir),
            ]
            return _sandbox_command(command, self.sandbox_profile, self.flow_dir), token
        self.socket_path.unlink(missing_ok=True)
        command = [
            os.fspath(python),
            "-m",
            "lumlflow_kernel",
            "--socket",
            os.fspath(self.socket_path),
            "--flow-dir",
            os.fspath(self.flow_dir),
        ]
        return _sandbox_command(command, self.sandbox_profile, self.flow_dir), None

    async def _connect(self, token: str | None) -> KernelClient:
        deadline = time.monotonic() + self.start_timeout
        last_error: OSError | None = None
        while time.monotonic() < deadline:
            if self.process is not None and self.process.poll() is not None:
                raise RuntimeError(
                    f"kernel exited during startup with code {self.process.returncode}"
                )
            try:
                if token is not None:
                    port = int(self.port_path.read_text().strip())
                    return await KernelClient.connect_tcp(
                        "127.0.0.1",
                        port,
                        token,
                        event_handler=self._record_event,
                    )
                return await KernelClient.connect_unix(
                    self.socket_path,
                    event_handler=self._record_event,
                )
            except (ConnectionRefusedError, FileNotFoundError, OSError) as error:
                last_error = error
                await asyncio.sleep(0.02)
        raise TimeoutError("kernel socket did not become ready") from last_error

    async def _stop_unlocked(self) -> None:
        if self.client is not None:
            await self.client.close()
        self.client = None
        if self.process is not None:
            try:
                await asyncio.to_thread(self.process.wait, 5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    await asyncio.to_thread(self.process.wait, 5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    await asyncio.to_thread(self.process.wait)
        self.process = None
        self.handshake = None
        self.active_runs.clear()
        self._events.clear()
        self._run_slugs.clear()
        for path in (self.socket_path, self.port_path, self.token_path, self.pid_path):
            path.unlink(missing_ok=True)

    def _venv_python(self) -> Path:
        candidates = (
            self.flow_dir / ".venv" / "Scripts" / "python.exe",
            self.flow_dir / ".venv" / "bin" / "python",
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        uv = shutil.which("uv")
        if uv is None:
            raise RuntimeError("uv is required to create the flow environment")
        subprocess.run(
            [uv, "sync", "--project", os.fspath(self.flow_dir)],
            check=True,
            cwd=self.flow_dir,
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        raise RuntimeError("uv sync did not create .venv")

    def _record_event(self, name: str, params: dict[str, Any]) -> None:
        run_id = params.get("run_id")
        if isinstance(run_id, str):
            slug = self._run_slugs.get(run_id)
            if slug is not None and "slug" not in params:
                params = {**params, "slug": slug}
            self._events.setdefault(run_id, []).append((name, params))
        if self.event_handler is not None:
            self.event_handler(name, params)


def _kernel_import_root() -> Path:
    specification = importlib.util.find_spec("lumlflow_kernel")
    if specification is None:
        raise RuntimeError("lumlflow_kernel is not installed")
    if specification.submodule_search_locations:
        package_dir = Path(next(iter(specification.submodule_search_locations)))
    elif specification.origin is not None:
        package_dir = Path(specification.origin).parent
    else:
        raise RuntimeError("cannot locate lumlflow_kernel")
    return package_dir.parent.resolve()


def _kernel_version(store: FlowStore, node: PlanNode) -> dict[str, JsonValue]:
    connection = store.index.connection
    if connection is None:
        raise RuntimeError("store index is closed")
    row = connection.execute(
        "SELECT bound_hash FROM asset_versions WHERE version_id = ?",
        (node.version_id,),
    ).fetchone()
    if row is None:
        raise LookupError(f"version {node.version_id} does not exist")
    bound_source = store.cas.get("objects", str(row["bound_hash"])).decode("utf-8")
    return {
        "slug": node.slug,
        "bound_source": bound_source,
        "manifest": node.manifest,
    }


def _kernel_inputs(
    store: FlowStore,
    inputs: dict[str, InputRecord],
    *,
    strict: bool = False,
) -> dict[str, JsonValue]:
    connection = store.index.connection
    if connection is None:
        raise RuntimeError("store index is closed")
    shared_hashes = _multi_branch_content_hashes(store, inputs) if strict else set()
    resolved: dict[str, JsonValue] = {}
    for name, record in inputs.items():
        row = connection.execute(
            "SELECT outputs FROM materializations WHERE mat_id = ?",
            (record.mat_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"materialization {record.mat_id} is missing")
        outputs = json.loads(str(row["outputs"]))
        output = outputs.get(record.output)
        if not isinstance(output, dict):
            raise RuntimeError(f"materialization output {record.output} is missing")
        value_ref = output.get("value_ref")
        kind = output.get("kind")
        if not isinstance(value_ref, str) or not isinstance(kind, str):
            raise RuntimeError(f"input {name} has no persisted value")
        resolved[name] = {
            "value_ref": value_ref,
            "kind": kind,
            "content_hash": record.content_hash,
            "name": record.output,
            "shared": record.content_hash in shared_hashes,
        }
    return resolved


def _multi_branch_content_hashes(
    store: FlowStore, inputs: dict[str, InputRecord]
) -> set[str]:
    sought = {record.content_hash for record in inputs.values()}
    if not sought:
        return set()
    connection = store.index.connection
    if connection is None:
        raise RuntimeError("store index is closed")
    branches_by_hash: dict[str, set[str]] = {
        content_hash: set() for content_hash in sought
    }
    rows = connection.execute(
        """
        SELECT baselines.branch_id, materializations.outputs
        FROM baselines
        JOIN materializations USING(mat_id)
        WHERE materializations.state = 'succeeded'
        """
    ).fetchall()
    for row in rows:
        outputs = json.loads(str(row["outputs"]))
        if not isinstance(outputs, dict):
            continue
        for output in outputs.values():
            if not isinstance(output, dict):
                continue
            content_hash = output.get("content_hash")
            if isinstance(content_hash, str) and content_hash in branches_by_hash:
                branches_by_hash[content_hash].add(str(row["branch_id"]))
    return {
        content_hash
        for content_hash, branch_ids in branches_by_hash.items()
        if len(branch_ids) > 1
    }


def _output_record(raw: dict[str, Any]) -> OutputRecord:
    return OutputRecord(
        content_hash=str(raw["content_hash"]),
        kind=str(raw["kind"]),
        size=int(raw["size"]),
        preview_ref=(
            str(raw["preview_ref"]) if raw.get("preview_ref") is not None else None
        ),
        value_ref=(str(raw["value_ref"]) if raw.get("value_ref") is not None else None),
        native_type=raw.get("native_type"),
        metadata=raw.get("metadata", {}),
        persisted=raw.get("persisted", False) is True,
    )


def _use_tcp_transport() -> bool:
    return os.name == "nt" or not hasattr(socket, "AF_UNIX")


def _flow_mode_enabled(flow_dir: Path, name: Literal["paranoid", "strict"]) -> bool:
    contents = (flow_dir / "flow.yaml").read_text(encoding="utf-8")
    return bool(
        re.search(
            rf"^\s{{2}}{name}:\s*(?:true|yes|on)\s*$",
            contents,
            re.MULTILINE | re.IGNORECASE,
        )
    )


def _select_sandbox_profile() -> SandboxProfile:
    system = platform.system()
    if system == "Windows":
        return "windows-plain"
    if system == "Darwin":
        return "macos-sandbox-exec" if shutil.which("sandbox-exec") else "macos-plain"
    if system == "Linux":
        if not _use_tcp_transport() and _can_unshare_network():
            return "linux-unshare-network"
        return "linux-plain"
    return "plain"


@lru_cache(maxsize=1)
def _can_unshare_network() -> bool:
    executable = shutil.which("unshare")
    if executable is None:
        return False
    try:
        result = subprocess.run(
            [executable, "-n", "--", "true"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _sandbox_command(
    command: list[str], profile: SandboxProfile, flow_dir: Path
) -> list[str]:
    if profile == "linux-unshare-network":
        executable = shutil.which("unshare")
        if executable is None:
            raise RuntimeError("unshare sandbox profile is unavailable")
        return [executable, "-n", "--", *command]
    if profile == "macos-sandbox-exec":
        executable = shutil.which("sandbox-exec")
        if executable is None:
            raise RuntimeError("sandbox-exec profile is unavailable")
        path = os.fspath(flow_dir.resolve()).replace("\\", "\\\\").replace('"', '\\"')
        policy = (
            "(version 1) (allow default) (deny network*) (deny file-write*) "
            f'(allow file-write* (subpath "{path}") (literal "/dev/null"))'
        )
        return [executable, "-p", policy, *command]
    return command


def _available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])
