from __future__ import annotations

import asyncio
import contextlib
import json
import os
import secrets
import socket
from collections import defaultdict, deque
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any, Literal, cast

import uvicorn
from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from lumlflow.flow.daemon.errors import DaemonRpcError
from lumlflow.flow.store.cas import atomic_write
from lumlflow.flow.store.journal import Journal
from lumlflow.flow.store.models import JsonValue, Transaction

StreamChannel = Literal["journal", "run-log"]
StreamMessage = dict[str, JsonValue]
SessionProvider = Callable[[], Awaitable[JsonValue]]
AssetPageProvider = Callable[[str, dict[str, JsonValue]], Awaitable[JsonValue]]
ParamEditProvider = Callable[[str, dict[str, JsonValue]], Awaitable[JsonValue]]
RpcProvider = Callable[[str, dict[str, JsonValue]], Awaitable[JsonValue]]

BROWSER_RPC_METHODS = frozenset(
    {
        "adopt",
        "agent_begin",
        "agent_end",
        "asset_page",
        "asset_preview",
        "cancel",
        "cells_edit",
        "cells_list",
        "cells_new",
        "cells_show",
        "context",
        "diff",
        "env_add",
        "env_remove",
        "env_status",
        "eval",
        "evict_lib",
        "export",
        "fork",
        "graph",
        "handshake",
        "kernel_restart",
        "params_edit",
        "preflight",
        "promote",
        "rename",
        "rewind",
        "root",
        "run",
        "status",
        "sweep",
        "sweep_compare",
        "switch",
        "tree",
    }
)

_MUTATING_BROWSER_RPC_METHODS = frozenset(
    {
        "adopt",
        "cells_edit",
        "cells_new",
        "env_add",
        "env_remove",
        "fork",
        "params_edit",
        "promote",
        "rename",
        "rewind",
        "run",
        "sweep",
        "switch",
    }
)


class StreamHub:
    def __init__(self, journal: Journal, *, log_tail_chunks: int = 200) -> None:
        if log_tail_chunks < 1:
            raise ValueError("log_tail_chunks must be positive")
        self.journal = journal
        self.log_tail_chunks = log_tail_chunks
        self._log_tails: dict[str, deque[StreamMessage]] = defaultdict(
            lambda: deque(maxlen=self.log_tail_chunks)
        )
        self._subscribers: set[asyncio.Queue[StreamMessage]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._loop = loop or asyncio.get_running_loop()

    def replay(self, cursor: int) -> list[StreamMessage]:
        if cursor < 0:
            raise ValueError("cursor must not be negative")
        return [
            self._transaction_message(transaction)
            for transaction in self.journal.replay()
            if transaction.step > cursor
        ]

    def log_tail(self, run_id: str) -> list[StreamMessage]:
        return list(self._log_tails.get(run_id, ()))

    def publish_transaction(self, transaction: Transaction) -> None:
        self._publish_threadsafe(self._transaction_message(transaction))

    def publish_kernel_event(self, event: str, payload: dict[str, Any]) -> None:
        run_id = payload.get("run_id")
        normalized = cast(JsonValue, _json_value(payload))
        if event == "log" and isinstance(run_id, str):
            message: StreamMessage = {
                "channel": "run-log",
                "kind": "chunk",
                "run_id": run_id,
                "chunk": normalized,
            }
            self._log_tails[run_id].append(message)
        else:
            message = {
                "channel": "journal",
                "kind": "kernel",
                "event": event,
                "run_id": run_id if isinstance(run_id, str) else None,
                "payload": normalized,
            }
        self._publish_threadsafe(message)

    async def subscribe(
        self,
        channel: StreamChannel,
        *,
        cursor: int = 0,
        run_id: str | None = None,
    ) -> AsyncGenerator[StreamMessage, None]:
        if channel == "run-log" and not run_id:
            raise ValueError("run_id is required for the run-log channel")
        queue: asyncio.Queue[StreamMessage] = asyncio.Queue()
        self._subscribers.add(queue)
        last_step = cursor
        last_sequence = -1
        try:
            initial = (
                self.replay(cursor)
                if channel == "journal"
                else self.log_tail(run_id or "")
            )
            for message in initial:
                if channel == "journal":
                    message_cursor = message.get("cursor")
                    if isinstance(message_cursor, int):
                        last_step = max(last_step, message_cursor)
                else:
                    last_sequence = max(last_sequence, _log_sequence(message))
                yield message
            while True:
                message = await queue.get()
                if message.get("channel") != channel:
                    continue
                if channel == "journal":
                    message_cursor = message.get("cursor")
                    if isinstance(message_cursor, int):
                        if message_cursor <= last_step:
                            continue
                        last_step = message_cursor
                else:
                    if message.get("run_id") != run_id:
                        continue
                    sequence = _log_sequence(message)
                    if sequence <= last_sequence:
                        continue
                    last_sequence = sequence
                yield message
        finally:
            self._subscribers.discard(queue)

    def _publish_threadsafe(self, message: StreamMessage) -> None:
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._publish, message)

    def _publish(self, message: StreamMessage) -> None:
        for queue in tuple(self._subscribers):
            queue.put_nowait(message)

    @staticmethod
    def _transaction_message(transaction: Transaction) -> StreamMessage:
        return {
            "channel": "journal",
            "kind": "transaction",
            "cursor": transaction.step,
            "transaction": cast(JsonValue, transaction.model_dump(mode="json")),
        }


def create_stream_app(
    hub: StreamHub,
    token: str,
    *,
    session_provider: SessionProvider | None = None,
    asset_page_provider: AssetPageProvider | None = None,
    param_edit_provider: ParamEditProvider | None = None,
    rpc_provider: RpcProvider | None = None,
) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["authorization", "content-type"],
    )

    def authorize(request: Request) -> None:
        supplied = request.query_params.get("token")
        authorization = request.headers.get("authorization")
        if supplied is None and authorization is not None:
            scheme, _, credential = authorization.partition(" ")
            if scheme.casefold() == "bearer":
                supplied = credential
        if not secrets.compare_digest(supplied or "", token):
            raise HTTPException(status_code=401, detail="invalid daemon token")

    @app.get("/api/session")
    async def session(request: Request) -> JsonValue:
        authorize(request)
        if session_provider is None:
            raise HTTPException(status_code=404, detail="session snapshot unavailable")
        return await session_provider()

    @app.post("/api/assets/{slug}/{output}/page")
    async def asset_page(
        request: Request,
        slug: str,
        output: str,
        query: dict[str, JsonValue],
    ) -> JsonValue:
        authorize(request)
        if asset_page_provider is None:
            raise HTTPException(status_code=404, detail="asset paging unavailable")
        return await asset_page_provider(f"{slug}.{output}", query)

    @app.post("/api/cells/{slug}/params")
    async def edit_params(
        request: Request,
        slug: str,
        payload: dict[str, JsonValue],
    ) -> JsonValue:
        authorize(request)
        if param_edit_provider is None:
            raise HTTPException(status_code=404, detail="parameter editing unavailable")
        return await param_edit_provider(slug, payload)

    @app.post("/api/rpc")
    async def rpc(
        request: Request, payload: dict[str, JsonValue]
    ) -> JSONResponse:
        authorize(request)
        method = payload.get("method")
        params = payload.get("params")
        try:
            if not isinstance(method, str) or not isinstance(params, dict):
                raise DaemonRpcError(-32600, "invalid request")
            if method not in BROWSER_RPC_METHODS or rpc_provider is None:
                raise DaemonRpcError(-32601, f"method not found: {method}")
            if method in _MUTATING_BROWSER_RPC_METHODS:
                params = {**params, "actor": "user:ui"}
            result = await rpc_provider(method, params)
        except DaemonRpcError as error:
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "code": error.code,
                        "message": str(error),
                        "data": error.data,
                    }
                },
            )
        return JSONResponse(content=result)

    @app.get("/events")
    async def events(
        request: Request, cursor: int = Query(default=0, ge=0)
    ) -> StreamingResponse:
        authorize(request)
        return _sse_response(hub.subscribe("journal", cursor=cursor))

    @app.get("/logs/{run_id}")
    async def logs(request: Request, run_id: str) -> StreamingResponse:
        authorize(request)
        return _sse_response(hub.subscribe("run-log", run_id=run_id))

    @app.websocket("/ws")
    async def websocket(websocket: WebSocket) -> None:
        supplied = websocket.query_params.get("token", "")
        if not secrets.compare_digest(supplied, token):
            await websocket.close(code=1008)
            return
        raw_channel = websocket.query_params.get("channel", "journal")
        if raw_channel not in {"journal", "run-log"}:
            await websocket.close(code=1008)
            return
        channel = cast(StreamChannel, raw_channel)
        try:
            cursor = int(websocket.query_params.get("cursor", "0"))
        except ValueError:
            await websocket.close(code=1008)
            return
        if cursor < 0:
            await websocket.close(code=1008)
            return
        run_id = websocket.query_params.get("run_id")
        if channel == "run-log" and not run_id:
            await websocket.close(code=1008)
            return
        await websocket.accept()
        try:
            async for message in hub.subscribe(channel, cursor=cursor, run_id=run_id):
                await websocket.send_json(message)
        except WebSocketDisconnect:
            pass

    return app


class _UvicornServer(uvicorn.Server):
    @contextlib.contextmanager
    def capture_signals(self) -> Any:
        yield


class DaemonStreamServer:
    def __init__(
        self,
        store_dir: Path,
        hub: StreamHub,
        session_provider: SessionProvider,
        *,
        asset_page_provider: AssetPageProvider | None = None,
        param_edit_provider: ParamEditProvider | None = None,
        rpc_provider: RpcProvider | None = None,
        token: str | None = None,
    ) -> None:
        self.store_dir = store_dir
        self.hub = hub
        self.session_provider = session_provider
        self.asset_page_provider = asset_page_provider
        self.param_edit_provider = param_edit_provider
        self.rpc_provider = rpc_provider
        self.token = token or secrets.token_urlsafe(32)
        self.port_path = store_dir / "daemon.port"
        self.token_path = store_dir / "daemon.token"
        self._socket: socket.socket | None = None
        self._server: _UvicornServer | None = None
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self.hub.bind_loop()
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        listener.setblocking(False)
        self._socket = listener
        port = int(listener.getsockname()[1])
        app = create_stream_app(
            self.hub,
            self.token,
            session_provider=self.session_provider,
            asset_page_provider=self.asset_page_provider,
            param_edit_provider=self.param_edit_provider,
            rpc_provider=self.rpc_provider,
        )
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            lifespan="off",
            timeout_graceful_shutdown=1,
        )
        self._server = _UvicornServer(config)
        self._task = asyncio.create_task(self._server.serve(sockets=[listener]))
        while not self._server.started:
            if self._task.done():
                await self._task
            await asyncio.sleep(0)
        atomic_write(self.port_path, f"{port}\n".encode())
        atomic_write(self.token_path, f"{self.token}\n".encode())
        if os.name == "posix":
            self.token_path.chmod(0o600)

    async def close(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._task is not None:
            await self._task
        if self._socket is not None:
            self._socket.close()
        self.port_path.unlink(missing_ok=True)
        self.token_path.unlink(missing_ok=True)


def _sse_response(messages: AsyncIterator[StreamMessage]) -> StreamingResponse:
    async def encoded() -> AsyncIterator[bytes]:
        async for message in messages:
            payload = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
            yield f"data:{payload}\n\n".encode()

    return StreamingResponse(
        encoded(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _log_sequence(message: StreamMessage) -> int:
    chunk = message.get("chunk")
    if isinstance(chunk, dict):
        sequence = chunk.get("seq")
        if isinstance(sequence, int):
            return sequence
    return -1


def _json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return str(value)
