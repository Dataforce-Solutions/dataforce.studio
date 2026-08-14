from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote, unquote, urlparse

import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.server.models import InitializationOptions
from pydantic import AnyUrl

from lumlflow.flow.daemon.api import connect_or_start
from lumlflow.flow.store.models import JsonValue


class DaemonRequester(Protocol):
    def request(
        self, method: str, params: dict[str, JsonValue] | None = None
    ) -> JsonValue: ...


def _object_schema(
    properties: dict[str, dict[str, Any]], required: Iterable[str] = ()
) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    required_fields = list(required)
    if required_fields:
        schema["required"] = required_fields
    return schema


_INTENT = {"type": "string", "minLength": 1, "description": "Journal intent"}
_BRANCH = {"type": "string", "minLength": 1}
_TOOLS = [
    types.Tool(
        name="new-cell",
        description="Create a cell directly in the active branch store.",
        inputSchema=_object_schema(
            {
                "slug": {"type": "string", "minLength": 1},
                "source": {"type": "string"},
                "after": {"type": "string", "minLength": 1},
                "intent": _INTENT,
            },
            ["intent"],
        ),
    ),
    types.Tool(
        name="edit-cell",
        description="Edit a cell with optimistic definition locking.",
        inputSchema=_object_schema(
            {
                "slug": {"type": "string", "minLength": 1},
                "source": {"type": "string"},
                "base_definition_hash": {"type": "string", "minLength": 1},
                "resolution": {
                    "type": "string",
                    "enum": ["overwrite", "fork-my-edit"],
                },
                "intent": _INTENT,
            },
            ["slug", "source", "base_definition_hash", "intent"],
        ),
    ),
    types.Tool(
        name="run",
        description="Materialize a cell or named output and its stale dependencies.",
        inputSchema=_object_schema(
            {
                "target": {"type": "string", "minLength": 1},
                "branch": _BRANCH,
                "force": {"type": "boolean"},
                "intent": _INTENT,
            },
            ["target", "intent"],
        ),
    ),
    types.Tool(
        name="status",
        description="Inspect branch, cell, staleness, failure, and environment status.",
        inputSchema=_object_schema({}),
    ),
    types.Tool(
        name="fork",
        description="Fork a branch from the current or named parent branch.",
        inputSchema=_object_schema(
            {"name": _BRANCH, "parent": _BRANCH, "intent": _INTENT},
            ["name", "intent"],
        ),
    ),
    types.Tool(
        name="switch",
        description="Switch the active branch without projecting files.",
        inputSchema=_object_schema(
            {
                "branch": _BRANCH,
                "force": {"type": "boolean"},
                "intent": _INTENT,
            },
            ["branch", "intent"],
        ),
    ),
    types.Tool(
        name="rewind",
        description="Rewind a branch selection to a journal step.",
        inputSchema=_object_schema(
            {
                "step": {"type": "integer", "minimum": 1},
                "branch": _BRANCH,
                "intent": _INTENT,
            },
            ["step", "intent"],
        ),
    ),
    types.Tool(
        name="adopt",
        description="Adopt one cell version from another branch.",
        inputSchema=_object_schema(
            {
                "slug": {"type": "string", "minLength": 1},
                "from_branch": _BRANCH,
                "branch": _BRANCH,
                "resolution": {"type": "string", "enum": ["incoming", "current"]},
                "intent": _INTENT,
            },
            ["slug", "from_branch", "intent"],
        ),
    ),
    types.Tool(
        name="diff",
        description=(
            "Compare definition and materialization divergence between branches."
        ),
        inputSchema=_object_schema(
            {"left": _BRANCH, "right": _BRANCH}, ["left", "right"]
        ),
    ),
    types.Tool(
        name="context",
        description="Read the token-budgeted active-session context.",
        inputSchema=_object_schema({}),
    ),
    types.Tool(
        name="asset-preview",
        description="Read a stored preview without starting the kernel.",
        inputSchema=_object_schema(
            {
                "target": {"type": "string", "pattern": r"^[^.]+\..+$"},
                "branch": _BRANCH,
            },
            ["target"],
        ),
    ),
]

_TOOL_METHODS = {
    "new-cell": "cells_new",
    "edit-cell": "cells_edit",
    "run": "run",
    "status": "status",
    "fork": "fork",
    "switch": "switch",
    "rewind": "rewind",
    "adopt": "adopt",
    "diff": "diff",
    "context": "context",
    "asset-preview": "asset_preview",
}
_ACTOR_TOOLS = {
    "new-cell",
    "edit-cell",
    "run",
    "fork",
    "switch",
    "rewind",
    "adopt",
}
_HEADLESS_TOOLS = {"new-cell", "edit-cell", "switch", "rewind", "adopt"}


class LumlflowMcpServer:
    def __init__(self, client: DaemonRequester, *, actor: str = "agent:mcp") -> None:
        if not actor:
            raise ValueError("MCP actor must not be empty")
        self.client = client
        self.actor = actor
        self.server = Server("lumlflow")
        self._register_handlers()

    def _register_handlers(self) -> None:
        @self.server.list_tools()
        async def list_tools() -> list[types.Tool]:
            return _TOOLS

        @self.server.call_tool()
        async def call_tool(
            name: str, arguments: dict[str, Any]
        ) -> types.CallToolResult:
            return await self.call_tool(name, arguments)

        @self.server.list_resources()
        async def list_resources() -> list[types.Resource]:
            return await self.list_resources()

        @self.server.read_resource()
        async def read_resource(uri: AnyUrl) -> list[ReadResourceContents]:
            return await self.read_resource(str(uri))

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> types.CallToolResult:
        method = _TOOL_METHODS.get(name)
        if method is None:
            raise ValueError(f"unknown tool: {name}")
        params = {str(key): _json_value(value) for key, value in arguments.items()}
        if name in _ACTOR_TOOLS:
            params["actor"] = self.actor
        if name in _HEADLESS_TOOLS:
            params["project"] = False
        result = await asyncio.to_thread(self.client.request, method, params)
        structured = result if isinstance(result, dict) else {"value": result}
        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text", text=json.dumps(result, indent=2, sort_keys=True)
                )
            ],
            structuredContent=structured,
        )

    async def list_resources(self) -> list[types.Resource]:
        cells = await self._cells()
        resources = [
            types.Resource(
                uri=AnyUrl("flow://manifest"),
                name="manifest",
                description="Active branch cell manifest",
                mimeType="application/json",
            ),
            types.Resource(
                uri=AnyUrl("session://focus"),
                name="focus",
                description="Token-budgeted active-session context",
                mimeType="application/json",
            ),
        ]
        for cell in cells:
            slug = cell.get("slug")
            if not isinstance(slug, str):
                continue
            encoded_slug = quote(slug, safe="")
            resources.append(
                types.Resource(
                    uri=AnyUrl(f"cell://{encoded_slug}/source"),
                    name=f"{slug} source",
                    mimeType="text/x-python",
                )
            )
            manifest = cell.get("manifest")
            produces = manifest.get("produces") if isinstance(manifest, dict) else None
            if not isinstance(produces, dict):
                continue
            for output in produces:
                if not isinstance(output, str):
                    continue
                target = quote(f"{slug}.{output}", safe="")
                resources.append(
                    types.Resource(
                        uri=AnyUrl(f"asset://{target}/preview"),
                        name=f"{slug}.{output} preview",
                        mimeType="application/json",
                    )
                )
        return resources

    async def read_resource(self, uri: str) -> list[ReadResourceContents]:
        parsed = urlparse(uri)
        if parsed.scheme == "flow" and parsed.netloc == "manifest":
            payload = await self._request("cells_list", {})
            return [self._json_resource(payload)]
        if parsed.scheme == "session" and parsed.netloc == "focus":
            payload = await self._request("context", {})
            return [self._json_resource(payload)]
        if parsed.scheme == "cell" and parsed.path == "/source":
            slug = unquote(parsed.netloc)
            payload = await self._request("cells_show", {"slug": slug})
            if not isinstance(payload, dict) or not isinstance(
                payload.get("source"), str
            ):
                raise ValueError(f"cell source not found: {slug}")
            source = payload["source"]
            assert isinstance(source, str)
            return [ReadResourceContents(source, "text/x-python")]
        if parsed.scheme == "asset" and parsed.path == "/preview":
            target = unquote(parsed.netloc)
            payload = await self._request("asset_preview", {"target": target})
            return [self._json_resource(payload)]
        raise ValueError(f"resource not found: {uri}")

    async def run(self) -> None:
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, self._initialization())

    def _initialization(self) -> InitializationOptions:
        return InitializationOptions(
            server_name="lumlflow",
            server_version="0.1.0",
            capabilities=self.server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={},
            ),
        )

    async def _cells(self) -> list[dict[str, JsonValue]]:
        payload = await self._request("cells_list", {})
        if not isinstance(payload, dict):
            raise RuntimeError("daemon returned an invalid cell manifest")
        cells = payload.get("cells")
        if not isinstance(cells, list):
            raise RuntimeError("daemon returned an invalid cell manifest")
        return [cell for cell in cells if isinstance(cell, dict)]

    async def _request(self, method: str, params: dict[str, JsonValue]) -> JsonValue:
        return await asyncio.to_thread(self.client.request, method, params)

    @staticmethod
    def _json_resource(value: JsonValue) -> ReadResourceContents:
        return ReadResourceContents(
            json.dumps(value, indent=2, sort_keys=True), "application/json"
        )


def run_stdio(flow_dir: str | Path, *, actor: str = "agent:mcp") -> None:
    client = connect_or_start(flow_dir, watch_worktree=False)
    asyncio.run(LumlflowMcpServer(client, actor=actor).run())


def _json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    raise TypeError(f"MCP argument is not JSON serializable: {type(value).__name__}")


__all__ = ["LumlflowMcpServer", "run_stdio"]
