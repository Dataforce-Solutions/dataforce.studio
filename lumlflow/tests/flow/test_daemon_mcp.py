from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from anyio import create_memory_object_stream
from lumlflow.flow.daemon.api import DaemonClient, DaemonServer
from lumlflow.flow.daemon.mcp import LumlflowMcpServer
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import JsonValue
from mcp import ClientSession
from mcp.shared.message import SessionMessage
from mcp.types import CallToolResult, ReadResourceResult
from pydantic import AnyUrl


def _install_test_venv(flow_dir: Path) -> None:
    try:
        (flow_dir / ".venv").symlink_to(
            Path(sys.prefix).resolve(), target_is_directory=True
        )
    except OSError:
        pytest.skip("the MCP run test requires a venv symlink")


def _source(value: int) -> str:
    return f"""class TrainModel:
    produces = {{"model": "asset"}}

    def materialize(self, ctx):
        return {{"model": {{"score": {value}}}}}
"""


def _structured(result: CallToolResult) -> dict[str, Any]:
    assert result.isError is False
    assert isinstance(result.structuredContent, dict)
    return result.structuredContent


def _resource_text(result: ReadResourceResult) -> str:
    assert len(result.contents) == 1
    content = result.contents[0]
    assert hasattr(content, "text")
    return str(content.text)


class RecordingDaemon:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, JsonValue]]] = []

    def request(
        self, method: str, params: dict[str, JsonValue] | None = None
    ) -> JsonValue:
        self.calls.append((method, params or {}))
        return {"method": method}


@pytest.mark.parametrize(
    ("tool", "method", "has_actor", "headless"),
    [
        ("new-cell", "cells_new", True, True),
        ("edit-cell", "cells_edit", True, True),
        ("run", "run", True, False),
        ("status", "status", False, False),
        ("fork", "fork", True, False),
        ("switch", "switch", True, True),
        ("rewind", "rewind", True, True),
        ("adopt", "adopt", True, True),
        ("diff", "diff", False, False),
        ("context", "context", False, False),
        ("asset-preview", "asset_preview", False, False),
    ],
)
async def test_mcp_tools_delegate_to_daemon_api(
    tool: str, method: str, has_actor: bool, headless: bool
) -> None:
    daemon = RecordingDaemon()
    mcp = LumlflowMcpServer(daemon, actor="agent:mcp:test")

    result = await mcp.call_tool(tool, {})

    assert _structured(result) == {"method": method}
    assert daemon.calls[0][0] == method
    params = daemon.calls[0][1]
    assert (params.get("actor") == "agent:mcp:test") is has_actor
    assert (params.get("project") is False) is headless


async def test_mcp_only_edit_run_inspect_loop_stays_worktree_less(
    tmp_path: Path,
) -> None:
    flow_dir = tmp_path / "flow"
    FlowStore.init(flow_dir).close()
    _install_test_venv(flow_dir)
    daemon = DaemonServer(flow_dir, watch_worktree=False)
    await daemon.start()
    assert daemon.runtime is not None
    assert daemon.runtime.watcher is None

    actor = "agent:mcp:test"
    mcp = LumlflowMcpServer(DaemonClient(flow_dir), actor=actor)
    client_send, server_receive = create_memory_object_stream[
        SessionMessage | Exception
    ](10)
    server_send, client_receive = create_memory_object_stream[
        SessionMessage | Exception
    ](10)
    server_task = asyncio.create_task(
        mcp.server.run(server_receive, server_send, mcp._initialization())
    )
    try:
        async with ClientSession(client_receive, client_send) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert {tool.name for tool in tools.tools} == {
                "new-cell",
                "edit-cell",
                "run",
                "status",
                "fork",
                "switch",
                "rewind",
                "adopt",
                "diff",
                "context",
                "asset-preview",
            }

            created = _structured(
                await session.call_tool(
                    "new-cell",
                    {
                        "slug": "train_model",
                        "source": _source(1),
                        "intent": "create model cell",
                    },
                )
            )
            edited_source = _source(2)
            edited = _structured(
                await session.call_tool(
                    "edit-cell",
                    {
                        "slug": "train_model",
                        "source": edited_source,
                        "base_definition_hash": created["definition_hash"],
                        "intent": "raise model score",
                    },
                )
            )
            assert edited["selected"] is True

            run = _structured(
                await session.call_tool(
                    "run",
                    {"target": "train_model", "intent": "materialize model"},
                )
            )
            assert run["executed"]
            status = _structured(await session.call_tool("status", {}))
            assert status["branch"] == "main"
            assert status["cell_status"][0]["state"] == "synced"

            resources = await session.list_resources()
            uris = {str(resource.uri) for resource in resources.resources}
            assert "flow://manifest" in uris
            assert "session://focus" in uris
            assert "cell://train_model/source" in uris
            assert "asset://train_model.model/preview" in uris

            source = await session.read_resource(AnyUrl("cell://train_model/source"))
            source_text = _resource_text(source)
            assert '    uid = "' in source_text
            assert '"score": 2' in source_text
            manifest = json.loads(
                _resource_text(await session.read_resource(AnyUrl("flow://manifest")))
            )
            assert manifest["cells"][0]["slug"] == "train_model"
            focus = json.loads(
                _resource_text(await session.read_resource(AnyUrl("session://focus")))
            )
            assert focus["branch"] == "main"
            preview = json.loads(
                _resource_text(
                    await session.read_resource(
                        AnyUrl("asset://train_model.model/preview")
                    )
                )
            )
            assert preview["kind"] == "metric"

        assert not list((flow_dir / "cells").glob("*.py"))
        transactions = list(daemon.runtime.store.journal.replay())
        attributed_ops = {
            "cell_accepted",
            "run_recorded",
            "memo_hit",
        }
        attributed = [
            transaction
            for transaction in transactions
            if any(operation.op in attributed_ops for operation in transaction.ops)
        ]
        assert attributed
        assert all(transaction.actor == actor for transaction in attributed)
    finally:
        server_task.cancel()
        await asyncio.gather(server_task, return_exceptions=True)
        await daemon.close()
