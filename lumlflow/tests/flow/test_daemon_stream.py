from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from lumlflow.flow.daemon.api import DaemonRpcError
from lumlflow.flow.daemon.stream import (
    DaemonStreamServer,
    StreamHub,
    create_stream_app,
)
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import FlagSetOp, JsonValue

RPC_METHODS = {
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


def _commit_flag(store: FlowStore, flag: str) -> None:
    store.commit(
        actor="agent:test",
        intent=f"set {flag}",
        ops=[FlagSetOp(flag=flag)],
    )


def test_websocket_replays_exact_transactions_after_cursor(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    _commit_flag(store, "first")
    _commit_flag(store, "second")
    hub = StreamHub(store.journal)
    app = create_stream_app(hub, "secret")

    with (
        TestClient(app) as client,
        client.websocket_connect("/ws?token=secret&cursor=1") as websocket,
    ):
        first = websocket.receive_json()
        second = websocket.receive_json()

    assert [first["cursor"], second["cursor"]] == [2, 3]
    assert [
        first["transaction"]["intent"],
        second["transaction"]["intent"],
    ] == ["set first", "set second"]
    assert client.get("/api/session?token=wrong").status_code == 401
    store.close()


def test_browser_asset_page_proxies_to_the_daemon_runtime(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    requests: list[tuple[str, dict[str, JsonValue]]] = []

    async def page(
        target: str, query: dict[str, JsonValue]
    ) -> dict[str, JsonValue]:
        requests.append((target, query))
        return {
            "columns": ["score"],
            "rows": [{"score": 0.9}],
            "offset": 0,
            "total_rows": 1,
        }

    app = create_stream_app(
        StreamHub(store.journal), "secret", asset_page_provider=page
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/assets/evaluate/results/page?token=secret",
            json={"offset": 0, "limit": 100},
        )
        unauthorized = client.post(
            "/api/assets/evaluate/results/page?token=wrong",
            json={},
        )

    assert response.json() == {
        "columns": ["score"],
        "rows": [{"score": 0.9}],
        "offset": 0,
        "total_rows": 1,
    }
    assert requests == [("evaluate.results", {"offset": 0, "limit": 100})]
    assert unauthorized.status_code == 401
    store.close()


def test_browser_param_edit_proxies_optimistic_payload(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    requests: list[tuple[str, dict[str, JsonValue]]] = []

    async def edit(
        slug: str, payload: dict[str, JsonValue]
    ) -> dict[str, JsonValue]:
        requests.append((slug, payload))
        return {"changed": True}

    app = create_stream_app(
        StreamHub(store.journal), "secret", param_edit_provider=edit
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/cells/train/params?token=secret",
            json={
                "params": {"lr": 0.2},
                "base_definition_hash": "definition-1",
            },
        )

    assert response.json() == {"changed": True}
    assert requests == [
        (
            "train",
            {
                "params": {"lr": 0.2},
                "base_definition_hash": "definition-1",
            },
        )
    ]
    store.close()


def test_browser_rpc_requires_query_or_bearer_token(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")

    async def dispatch(
        method: str, params: dict[str, JsonValue]
    ) -> dict[str, JsonValue]:
        return {"method": method, "params": params}

    app = create_stream_app(
        StreamHub(store.journal), "secret", rpc_provider=dispatch
    )

    with TestClient(app) as client:
        missing = client.post("/api/rpc", json={"method": "status", "params": {}})
        wrong = client.post(
            "/api/rpc?token=wrong", json={"method": "status", "params": {}}
        )
        query = client.post(
            "/api/rpc?token=secret", json={"method": "status", "params": {}}
        )
        bearer = client.post(
            "/api/rpc",
            headers={"Authorization": "Bearer secret"},
            json={"method": "status", "params": {}},
        )

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert query.json() == {"method": "status", "params": {}}
    assert bearer.json() == {"method": "status", "params": {}}
    store.close()


def test_browser_rpc_exposes_dispatch_vocabulary_except_shutdown(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    dispatched: list[str] = []

    async def dispatch(
        method: str, _params: dict[str, JsonValue]
    ) -> dict[str, JsonValue]:
        dispatched.append(method)
        return {"method": method}

    app = create_stream_app(
        StreamHub(store.journal), "secret", rpc_provider=dispatch
    )

    with TestClient(app) as client:
        for method in sorted(RPC_METHODS):
            response = client.post(
                "/api/rpc?token=secret", json={"method": method, "params": {}}
            )
            assert response.status_code == 200
            assert response.json() == {"method": method}
        shutdown = client.post(
            "/api/rpc?token=secret", json={"method": "shutdown", "params": {}}
        )
        unknown = client.post(
            "/api/rpc?token=secret", json={"method": "unknown", "params": {}}
        )

    assert dispatched == sorted(RPC_METHODS)
    for response, method in ((shutdown, "shutdown"), (unknown, "unknown")):
        assert response.status_code == 400
        assert response.json() == {
            "error": {
                "code": -32601,
                "message": f"method not found: {method}",
                "data": None,
            }
        }
    store.close()


def test_browser_rpc_maps_daemon_errors_to_structured_responses(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")

    async def dispatch(
        _method: str, _params: dict[str, JsonValue]
    ) -> JsonValue:
        raise DaemonRpcError(
            -32009,
            "definition changed",
            {"current_definition_hash": "definition-2"},
        )

    app = create_stream_app(
        StreamHub(store.journal), "secret", rpc_provider=dispatch
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/rpc?token=secret",
            json={"method": "cells_edit", "params": {}},
        )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": -32009,
            "message": "definition changed",
            "data": {"current_definition_hash": "definition-2"},
        }
    }
    store.close()


def test_browser_rpc_carries_mutation_actor_and_intent(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    requests: list[tuple[str, dict[str, JsonValue]]] = []

    async def dispatch(
        method: str, params: dict[str, JsonValue]
    ) -> dict[str, JsonValue]:
        requests.append((method, params))
        return {"changed": True}

    app = create_stream_app(
        StreamHub(store.journal), "secret", rpc_provider=dispatch
    )

    with TestClient(app) as client:
        explicit = client.post(
            "/api/rpc?token=secret",
            json={
                "method": "params_edit",
                "params": {
                    "slug": "train",
                    "params": {"lr": 0.2},
                    "actor": "agent:spoofed",
                    "intent": "tune learning rate",
                },
            },
        )
        default_actor = client.post(
            "/api/rpc?token=secret",
            json={"method": "fork", "params": {"branch": "experiment"}},
        )

    assert explicit.status_code == 200
    assert default_actor.status_code == 200
    assert requests == [
        (
            "params_edit",
            {
                "slug": "train",
                "params": {"lr": 0.2},
                "actor": "user:ui",
                "intent": "tune learning rate",
            },
        ),
        ("fork", {"branch": "experiment", "actor": "user:ui"}),
    ]
    store.close()


async def test_subscriber_gets_new_commits_without_replaying_duplicates(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    hub = StreamHub(store.journal)
    hub.bind_loop()
    remove_listener = store.add_commit_listener(hub.publish_transaction)
    messages = hub.subscribe("journal", cursor=store.last_step)
    pending = asyncio.ensure_future(anext(messages))

    _commit_flag(store, "live")
    message = await asyncio.wait_for(pending, 1)

    assert message["cursor"] == 2
    transaction = message["transaction"]
    assert isinstance(transaction, dict)
    assert transaction["intent"] == "set live"
    await messages.aclose()
    remove_listener()
    store.close()


async def test_late_log_subscriber_receives_only_ring_buffer_tail(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    hub = StreamHub(store.journal, log_tail_chunks=2)
    for sequence in range(4):
        hub.publish_kernel_event(
            "log",
            {
                "run_id": "run-1",
                "stream": "stdout",
                "seq": sequence,
                "bytes": str(sequence),
            },
        )

    messages = hub.subscribe("run-log", run_id="run-1")
    tail = [await anext(messages), await anext(messages)]

    sequences: list[int] = []
    for message in tail:
        chunk = message["chunk"]
        assert isinstance(chunk, dict)
        tail_sequence = chunk["seq"]
        assert isinstance(tail_sequence, int)
        sequences.append(tail_sequence)
    assert sequences == [2, 3]
    await messages.aclose()
    store.close()


async def test_stream_server_writes_loopback_port_and_token_files(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    hub = StreamHub(store.journal)

    async def snapshot() -> dict[str, JsonValue]:
        return {"step": store.last_step}

    server = DaemonStreamServer(store.store_dir, hub, snapshot, token="secret")
    await server.start()
    try:
        port = int((store.store_dir / "daemon.port").read_text())
        assert (store.store_dir / "daemon.token").read_text().strip() == "secret"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://127.0.0.1:{port}/api/session?token=secret"
            )
            async with client.stream(
                "GET",
                f"http://127.0.0.1:{port}/events?token=secret&cursor=0",
            ) as events:
                lines = events.aiter_lines()
                event = await anext(lines)
        assert response.json() == {"step": 1}
        assert '"cursor":1' in event
    finally:
        await server.close()
        store.close()

    assert not (store.store_dir / "daemon.port").exists()
    assert not (store.store_dir / "daemon.token").exists()
