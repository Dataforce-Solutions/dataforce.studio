from __future__ import annotations

import itertools
import json
import os
import socket
import threading
from pathlib import Path
from typing import Any

from .executor import Executor


class RpcError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class _PendingResponse:
    def __init__(self) -> None:
        self.event = threading.Event()
        self.result: Any = None
        self.error: dict[str, Any] | None = None


class _ConnectionBridge:
    def __init__(self) -> None:
        self.connection: KernelConnection | None = None

    def emit(self, event: str, payload: dict[str, object]) -> None:
        if self.connection is None:
            raise RuntimeError("kernel connection is not ready")
        self.connection.emit(event, payload)

    def request_secret(self, name: str) -> str:
        if self.connection is None:
            raise RuntimeError("kernel connection is not ready")
        return self.connection.request_secret(name)


class KernelConnection:
    def __init__(
        self,
        connection: socket.socket,
        executor: Executor,
        *,
        token: str | None = None,
    ) -> None:
        self.connection = connection
        self.executor = executor
        self._writer = connection.makefile("wb")
        self._write_lock = threading.Lock()
        self._pending: dict[str, _PendingResponse] = {}
        self._request_ids = itertools.count(1)
        self.closed = threading.Event()
        self.token = token

    def serve(self) -> None:
        with self.connection, self.connection.makefile("rb") as reader, self._writer:
            for raw_line in reader:
                try:
                    message = json.loads(raw_line)
                    if not isinstance(message, dict):
                        raise ValueError("message must be an object")
                    self._receive(message)
                except (json.JSONDecodeError, ValueError) as error:
                    self._send_error(None, -32700, str(error))
                if self.closed.is_set():
                    break

    def emit(self, event: str, payload: dict[str, object]) -> None:
        self._send({"jsonrpc": "2.0", "method": event, "params": payload})

    def request_secret(self, name: str) -> str:
        request_id = f"kernel-{next(self._request_ids)}"
        pending = _PendingResponse()
        self._pending[request_id] = pending
        self._send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "secret",
                "params": {"name": name},
            }
        )
        if not pending.event.wait(timeout=30):
            self._pending.pop(request_id, None)
            raise TimeoutError(f"secret request timed out for {name!r}")
        if pending.error is not None:
            message = pending.error.get("message", "secret request failed")
            raise RuntimeError(str(message))
        result = pending.result
        if isinstance(result, dict):
            result = result.get("value")
        if not isinstance(result, str):
            raise RuntimeError("secret response must contain a string value")
        return result

    def _receive(self, message: dict[str, Any]) -> None:
        request_id = message.get("id")
        if "method" not in message and request_id is not None:
            pending = self._pending.pop(str(request_id), None)
            if pending is not None:
                pending.result = message.get("result")
                error = message.get("error")
                pending.error = error if isinstance(error, dict) else None
                pending.event.set()
            return
        if message.get("jsonrpc") != "2.0":
            self._send_error(request_id, -32600, "jsonrpc must be '2.0'")
            return
        if self.token is not None and message.get("token") != self.token:
            self._send_error(request_id, -32001, "invalid kernel token")
            return
        method = message.get("method")
        params = message.get("params", {})
        if not isinstance(method, str) or not isinstance(params, dict):
            self._send_error(request_id, -32600, "invalid request")
            return
        if method == "run":
            threading.Thread(
                target=self._dispatch_and_respond,
                args=(request_id, method, params),
                daemon=True,
            ).start()
            return
        self._dispatch_and_respond(request_id, method, params)

    def _dispatch_and_respond(
        self,
        request_id: object,
        method: str,
        params: dict[str, Any],
    ) -> None:
        try:
            result = self._dispatch(method, params)
        except RpcError as error:
            self._send_error(request_id, error.code, error.message)
        except (KeyError, TypeError, ValueError) as error:
            self._send_error(request_id, -32602, str(error))
        except Exception as error:
            self._send_error(request_id, -32603, str(error))
        else:
            if request_id is not None:
                self._send({"jsonrpc": "2.0", "id": request_id, "result": result})

    def _dispatch(self, method: str, params: dict[str, Any]) -> Any:
        if method == "handshake":
            return self.executor.handshake()
        if method == "load_slice":
            return self.executor.load_slice(params["values"])
        if method == "run":
            return self.executor.run(
                params["run_id"],
                params["version"],
                params.get("inputs", {}),
                params.get("params", {}),
                params.get("ctx_info", {}),
            )
        if method == "cancel":
            return self.executor.cancel(params["run_id"])
        if method == "page":
            return self.executor.page(
                params["value_ref"],
                params["kind"],
                params.get("query", {}),
            )
        if method == "diff":
            return self.executor.diff(params["ref_a"], params["ref_b"], params["kind"])
        if method == "eval":
            return self.executor.evaluate(
                params["branch_slice"],
                params["code"],
                paranoid=params.get("paranoid", False) is True,
            )
        if method == "evict_lib":
            return self.executor.evict_lib()
        if method == "loaded_packages":
            return self.executor.loaded_packages()
        if method == "shutdown":
            self.closed.set()
            return {"shutdown": True}
        raise RpcError(-32601, f"method not found: {method}")

    def _send_error(self, request_id: object, code: int, message: str) -> None:
        self._send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": code, "message": message},
            }
        )

    def _send(self, message: dict[str, Any]) -> None:
        encoded = (
            json.dumps(
                message,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode()
            + b"\n"
        )
        with self._write_lock:
            self._writer.write(encoded)
            self._writer.flush()


class KernelServer:
    def __init__(
        self,
        flow_dir: Path,
        *,
        socket_path: Path | None = None,
        host: str = "127.0.0.1",
        port: int | None = None,
        token: str | None = None,
    ) -> None:
        if socket_path is None and port is None:
            raise ValueError("either socket_path or port is required")
        self.flow_dir = flow_dir
        self.socket_path = socket_path
        self.host = host
        self.port = port
        self.token = token
        self._server: socket.socket | None = None

    def serve_forever(self) -> None:
        server = self._bind()
        self._server = server
        try:
            while True:
                connection, _ = server.accept()
                bridge = _ConnectionBridge()
                executor = Executor(
                    self.flow_dir,
                    bridge.emit,
                    secret_request=bridge.request_secret,
                )
                kernel_connection = KernelConnection(
                    connection,
                    executor,
                    token=self.token,
                )
                bridge.connection = kernel_connection
                kernel_connection.serve()
                if kernel_connection.closed.is_set():
                    return
        finally:
            server.close()
            if self.socket_path is not None:
                self.socket_path.unlink(missing_ok=True)

    def _bind(self) -> socket.socket:
        if self.socket_path is not None:
            if not hasattr(socket, "AF_UNIX"):
                raise RuntimeError("unix sockets are unavailable; use loopback TCP")
            self.socket_path.parent.mkdir(parents=True, exist_ok=True)
            self.socket_path.unlink(missing_ok=True)
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(os.fspath(self.socket_path))
        else:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.host, int(self.port or 0)))
        server.listen(1)
        return server
