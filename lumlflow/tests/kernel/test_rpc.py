from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol


class SocketFile(Protocol):
    def write(self, data: bytes) -> int | None: ...

    def flush(self) -> None: ...

    def readline(self, size: int = -1) -> bytes: ...


def send(file: SocketFile, message: dict[str, Any]) -> None:
    file.write(json.dumps(message, separators=(",", ":")).encode() + b"\n")
    file.flush()


def receive(file: SocketFile) -> dict[str, Any]:
    return json.loads(file.readline())


def response_for(
    file: SocketFile,
    request_id: int,
    secret_provider: Callable[[str], str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    while True:
        message = receive(file)
        if message.get("id") == request_id:
            return message, events
        if message.get("method") == "secret" and secret_provider is not None:
            secret_name = message["params"]["name"]
            send(
                file,
                {
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "result": {"value": secret_provider(secret_name)},
                },
            )
            continue
        events.append(message)


def test_kernel_json_rpc_runs_standalone_against_fake_daemon(tmp_path: Path) -> None:
    socket_path = tmp_path / "kernel.sock"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "lumlflow_kernel",
            "--socket",
            str(socket_path),
            "--flow-dir",
            str(tmp_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 10
        while not socket_path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert socket_path.exists()
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(str(socket_path))
        with client, client.makefile("rwb", buffering=0) as file:
            send(file, {"jsonrpc": "2.0", "id": 1, "method": "handshake"})
            handshake, _ = response_for(file, 1)
            assert handshake["result"]["protocol"] == 1
            assert "fd_capture" in handshake["result"]["capabilities"]
            assert any(
                kind["name"] == "pickle" for kind in handshake["result"]["kinds"]
            )

            send(file, {"jsonrpc": "2.0", "id": 4, "method": "loaded_packages"})
            loaded_packages, _ = response_for(file, 4)
            assert isinstance(loaded_packages["result"], dict)

            source = """
class SocketCell:
    def materialize(self, ctx):
        print("from socket")
        return {"value": ctx.secret("api-key")}
"""
            send(
                file,
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "run",
                    "params": {
                        "run_id": "socket-run",
                        "version": {
                            "slug": "socket_cell",
                            "bound_source": source,
                            "manifest": {"produces": {"value": "asset"}},
                        },
                        "inputs": {},
                        "params": {},
                        "ctx_info": {"branch": "main", "step": 1},
                    },
                },
            )
            run_response, events = response_for(
                file,
                2,
                secret_provider=lambda name: f"resolved:{name}",
            )
            assert run_response["result"]["state"] == "succeeded"
            assert any(event.get("method") == "log" for event in events)
            assert any(event.get("method") == "materialized" for event in events)

            send(file, {"jsonrpc": "2.0", "id": 3, "method": "shutdown"})
            shutdown, _ = response_for(file, 3)
            assert shutdown["result"] == {"shutdown": True}
    finally:
        process.terminate()
        process.wait(timeout=5)
