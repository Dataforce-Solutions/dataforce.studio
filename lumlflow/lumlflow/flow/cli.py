from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import typer

from lumlflow.flow.daemon.api import (
    DaemonClient,
    DaemonRpcError,
    connect_or_start,
)
from lumlflow.flow.daemon.projections import ProjectionManager
from lumlflow.flow.demo import scaffold_demo
from lumlflow.flow.errors import clean_human_message
from lumlflow.flow.portable import import_projection
from lumlflow.flow.store.cas import atomic_write
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import JsonValue

app = typer.Typer(name="lumlflow", help="Agent-driven, non-linear ML flows")
cells_app = typer.Typer(help="Create and inspect cells", invoke_without_command=True)
asset_app = typer.Typer(help="Inspect materialized outputs")
agent_app = typer.Typer(help="Bracket agent editing sessions")
daemon_app = typer.Typer(help="Manage the flow daemon")
env_app = typer.Typer(help="Manage the flow environment")
app.add_typer(cells_app, name="cells")
app.add_typer(asset_app, name="asset")
app.add_typer(agent_app, name="agent")
app.add_typer(daemon_app, name="daemon")
app.add_typer(env_app, name="env")

DEFAULT_FLOW_UI_URL = "http://localhost:5173/flow/railroad"


def find_flow_root(start: str | Path | None = None) -> Path:
    current = Path(start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "flow.yaml").is_file():
            return candidate
    raise FileNotFoundError("not inside a lumlflow flow")


def _client() -> DaemonClient:
    return connect_or_start(find_flow_root())


def _request(
    method: str,
    params: dict[str, JsonValue] | None,
    *,
    json_output: bool,
) -> JsonValue:
    request_params = None if params is None else dict(params)
    actor = os.environ.get("LUMLFLOW_ACTOR")
    if actor:
        request_params = dict(request_params or {})
        request_params.setdefault("actor", actor)
    try:
        return _client().request(method, request_params)
    except (DaemonRpcError, FileNotFoundError, OSError, RuntimeError) as error:
        if json_output and isinstance(error, DaemonRpcError):
            _emit(
                {
                    "error": {
                        "code": error.code,
                        "message": str(error),
                        "data": error.data,
                    }
                },
                True,
            )
        else:
            typer.echo(f"Error: {clean_human_message(str(error))}", err=True)
        raise typer.Exit(code=1) from error


def _emit(value: JsonValue, json_output: bool, human: str | None = None) -> None:
    if json_output:
        typer.echo(json.dumps(value, sort_keys=True, separators=(",", ":")))
    elif human is not None:
        typer.echo(clean_human_message(human))


def _object(value: JsonValue) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise RuntimeError("daemon returned an invalid response")
    return value


def _objects(value: JsonValue) -> list[dict[str, JsonValue]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _strings(value: JsonValue) -> list[str]:
    return (
        [item for item in value if isinstance(item, str)]
        if isinstance(value, list)
        else []
    )


def _intent_params(intent: str | None) -> dict[str, JsonValue]:
    return {"intent": intent} if intent is not None else {}


def _daemon_connect_info(flow_dir: Path, ui_url: str) -> dict[str, JsonValue]:
    store_dir = flow_dir / ".lumlflow"
    port = int((store_dir / "daemon.port").read_text(encoding="utf-8").strip())
    token = (store_dir / "daemon.token").read_text(encoding="utf-8").strip()
    http_url = f"http://127.0.0.1:{port}"
    parsed_ui_url = urlsplit(ui_url)
    query = [
        (key, value)
        for key, value in parse_qsl(parsed_ui_url.query, keep_blank_values=True)
        if key not in {"live", "token"}
    ]
    query.extend((("live", http_url), ("token", token)))
    deep_link = urlunsplit(parsed_ui_url._replace(query=urlencode(query)))
    return {"http_url": http_url, "token": token, "ui_url": deep_link}


def _daemon_running_human(result: dict[str, JsonValue]) -> str:
    return "\n".join(
        (
            "Daemon running",
            f"HTTP URL: {result['http_url']}",
            f"Token: {result['token']}",
            f"UI: {result['ui_url']}",
        )
    )


def _prepare_flow_worktree(store: FlowStore) -> None:
    pyproject = store.flow_dir / "pyproject.toml"
    if not pyproject.exists():
        atomic_write(
            pyproject,
            (
                f'[project]\nname = "{store.flow_dir.stem}"\n'
                'version = "0.1.0"\nrequires-python = ">=3.10"\n'
                'dependencies = ["cloudpickle>=3"]\n'
            ).encode(),
        )
    atomic_write(
        store.flow_dir / ".mcp.json",
        (
            json.dumps(
                {
                    "mcpServers": {
                        "lumlflow": {"command": "lumlflow", "args": ["mcp"]}
                    }
                },
                indent=2,
            )
            + "\n"
        ).encode(),
    )
    ProjectionManager(store).refresh_generated_docs()


@app.command("init")
def init_flow(
    path: Path = typer.Argument(  # noqa: B008
        Path("."), help="Directory for the flow"
    ),
    name: str | None = typer.Option(None, "--name"),
    intent: str | None = typer.Option(None, "--intent", "-m"),
    demo: bool = typer.Option(False, "--demo", help="Scaffold a runnable demo flow"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    try:
        store = FlowStore.init(path, name=name, intent=intent or "initialize flow")
        if demo:
            scaffold_demo(store)
        _prepare_flow_worktree(store)
        result: dict[str, JsonValue] = {
            "root": str(store.flow_dir.resolve()),
            "flow": store.flow_id,
            "branch": "main",
        }
        store.close()
    except (FileExistsError, OSError, ValueError) as error:
        typer.echo(f"Error: {clean_human_message(str(error))}", err=True)
        raise typer.Exit(code=1) from error
    _emit(result, json_output, f"Initialized flow at {result['root']}")


@app.command("export")
def export_flow(
    destination: Path,
    branch: str | None = typer.Option(None, "--branch"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    result = _object(
        _request("export", {"branch": branch}, json_output=json_output)
    )
    source = result.get("source")
    if not isinstance(source, str):
        typer.echo("Error: daemon returned an invalid export", err=True)
        raise typer.Exit(code=1)
    try:
        atomic_write(destination, source.encode())
    except OSError as error:
        typer.echo(f"Error: {clean_human_message(str(error))}", err=True)
        raise typer.Exit(code=1) from error
    payload: dict[str, JsonValue] = {
        "path": str(destination.resolve()),
        "branch": result.get("branch"),
        "cells": result.get("cells"),
    }
    _emit(
        payload,
        json_output,
        f"Exported {payload['cells']} cells to {payload['path']}",
    )


@app.command("import")
def import_flow(
    source: Path,
    path: Path | None = typer.Argument(  # noqa: B008
        None, help="Fresh flow directory (defaults to <source>.flow)"
    ),
    name: str | None = typer.Option(None, "--name"),
    intent: str | None = typer.Option(None, "--intent", "-m"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    destination = path or Path(f"{source.stem}.flow")
    try:
        store = import_projection(
            source,
            destination,
            name=name,
            intent=intent,
        )
        _prepare_flow_worktree(store)
        result: dict[str, JsonValue] = {
            "root": str(store.flow_dir.resolve()),
            "flow": store.flow_id,
            "branch": "main",
            "cells": len(list((store.flow_dir / "cells").glob("*.py"))),
        }
        store.close()
    except (FileExistsError, OSError, ValueError) as error:
        typer.echo(f"Error: {clean_human_message(str(error))}", err=True)
        raise typer.Exit(code=1) from error
    _emit(result, json_output, f"Imported flow at {result['root']}")


@app.command()
def status(json_output: bool = typer.Option(False, "--json")) -> None:
    result = _object(_request("status", None, json_output=json_output))
    lines = [
        f"Branch {result.get('branch')} at step {result.get('step')}",
        f"Cells: {result.get('cells')}",
    ]
    environment = result.get("environment")
    if isinstance(environment, dict):
        if environment.get("restart_required") is True:
            lines.append("Environment changed — restart kernel to apply")
        if environment.get("branch_lock_mismatch") is True:
            lines.append(
                "Environment mismatch — restart under this branch's lock to clear"
            )
    for cell in _objects(result.get("cell_status")):
        slug = cell.get("slug")
        state = cell.get("state")
        causes = _strings(cell.get("causes"))
        suffix = f" — {', '.join(str(cause) for cause in causes)}" if causes else ""
        lines.append(f"{slug}: {state}{suffix}")
        manifest = cell.get("manifest")
        if isinstance(manifest, dict):
            for issue in _strings(manifest.get("issues")):
                lines.append(f"  {issue}")
        failure = cell.get("failure")
        if isinstance(failure, dict) and isinstance(failure.get("traceback"), str):
            lines.append(str(failure["traceback"]).rstrip())
    _emit(result, json_output, "\n".join(lines))


@app.command()
def tree(
    branch: str | None = typer.Option(None, "--branch"),
    since: int | None = typer.Option(None, "--since", min=0),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    params: dict[str, JsonValue] = {"branch": branch, "since": since}
    result = _object(_request("tree", params, json_output=json_output))
    lines = [
        f"{cell.get('slug')} [{cell.get('state')}]"
        for cell in _objects(result.get("cells"))
    ]
    _emit(result, json_output, "\n".join(lines) or "No cells")


@app.command()
def graph(
    around: str | None = typer.Option(None, "--around"),
    depth: int = typer.Option(2, "--depth", min=0),
    branch: str | None = typer.Option(None, "--branch"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    result = _object(
        _request(
            "graph",
            {"around": around, "depth": depth, "branch": branch},
            json_output=json_output,
        )
    )
    lines = [
        f"{edge.get('from')}.{edge.get('output')} -> "
        f"{edge.get('to')}.{edge.get('input')}"
        for edge in _objects(result.get("edges"))
    ]
    if not lines:
        lines = [str(node.get("slug")) for node in _objects(result.get("nodes"))]
    _emit(result, json_output, "\n".join(lines) or "No cells")


def _list_cells(unsynced: bool, branch: str | None, json_output: bool) -> None:
    result = _object(
        _request(
            "cells_list",
            {"unsynced": unsynced, "branch": branch},
            json_output=json_output,
        )
    )
    lines = [
        f"{cell.get('slug')} [{cell.get('state')}]"
        for cell in _objects(result.get("cells"))
    ]
    _emit(result, json_output, "\n".join(lines) or "No cells")


@cells_app.callback()
def cells_default(
    ctx: typer.Context,
    unsynced: bool = typer.Option(False, "--unsynced"),
    branch: str | None = typer.Option(None, "--branch"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    if ctx.invoked_subcommand is None:
        _list_cells(unsynced, branch, json_output)


@cells_app.command("list")
def cells_list(
    unsynced: bool = typer.Option(False, "--unsynced"),
    branch: str | None = typer.Option(None, "--branch"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    _list_cells(unsynced, branch, json_output)


@cells_app.command("show")
def cells_show(
    slug: str,
    branch: str | None = typer.Option(None, "--branch"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    result = _object(
        _request(
            "cells_show", {"slug": slug, "branch": branch}, json_output=json_output
        )
    )
    manifest = result.get("manifest")
    issues = _strings(manifest.get("issues")) if isinstance(manifest, dict) else []
    human = f"{slug} [{result.get('state')}]\n{result.get('source', '')}"
    if issues:
        human += "\n" + "\n".join(str(issue) for issue in issues)
    _emit(result, json_output, human)


@cells_app.command("new")
def cells_new(
    slug: str,
    after: str | None = typer.Option(None, "--after"),
    intent: str | None = typer.Option(None, "--intent", "-m"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    params = {"slug": slug, "after": after, **_intent_params(intent)}
    result = _object(_request("cells_new", params, json_output=json_output))
    _emit(result, json_output, f"Created cell {result.get('slug')}")


@cells_app.command("edit")
def cells_edit(
    slug: str,
    source: str | None = typer.Option(None, "--source"),
    file: Path | None = typer.Option(None, "--file"),  # noqa: B008
    intent: str | None = typer.Option(None, "--intent", "-m"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    if (source is None) == (file is None):
        raise typer.BadParameter("provide exactly one of --source or --file")
    incoming = source if source is not None else file.read_text(encoding="utf-8")  # type: ignore[union-attr]
    current = _object(_request("cells_show", {"slug": slug}, json_output=json_output))
    params: dict[str, JsonValue] = {
        "slug": slug,
        "source": incoming,
        "base_definition_hash": current.get("definition_hash"),
        **_intent_params(intent),
    }
    result = _object(_request("cells_edit", params, json_output=json_output))
    _emit(result, json_output, f"Updated cell {slug}")


@cells_app.command("params")
def cells_params(
    slug: str,
    set_values: list[str] = typer.Option(..., "--set"),  # noqa: B008
    branch: str | None = typer.Option(None, "--branch"),
    intent: str | None = typer.Option(None, "--intent", "-m"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    current = _object(
        _request(
            "cells_show",
            {"slug": slug, "branch": branch},
            json_output=json_output,
        )
    )
    manifest = current.get("manifest")
    current_params = manifest.get("params", {}) if isinstance(manifest, dict) else {}
    if not isinstance(current_params, dict):
        current_params = {}
    updated: dict[str, JsonValue] = dict(current_params)
    for assignment in set_values:
        name, separator, raw = assignment.partition("=")
        if not separator or not name:
            raise typer.BadParameter("parameter assignments must use NAME=JSON")
        try:
            updated[name] = json.loads(raw)
        except json.JSONDecodeError as error:
            raise typer.BadParameter(
                f"parameter {name} must have a JSON value"
            ) from error
    result = _object(
        _request(
            "params_edit",
            {
                "slug": slug,
                "branch": branch,
                "params": updated,
                "base_definition_hash": current.get("definition_hash"),
                **_intent_params(intent),
            },
            json_output=json_output,
        )
    )
    _emit(result, json_output, f"Updated parameters for {slug}")


@app.command()
def run(
    target: str,
    force: bool = typer.Option(False, "--force"),
    intent: str | None = typer.Option(None, "--intent", "-m"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    params = {"target": target, "force": force, **_intent_params(intent)}
    result = _object(_request("run", params, json_output=json_output))
    executed = result.get("executed")
    hits = result.get("memo_hits")
    executed_count = len(executed) if isinstance(executed, list) else 0
    hit_count = len(hits) if isinstance(hits, list) else 0
    human = f"Ran {result.get('target')}: {executed_count} executed, {hit_count} reused"
    _emit(result, json_output, human)


@env_app.command("add")
def env_add(
    package: str,
    intent: str | None = typer.Option(None, "--intent", "-m"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    result = _object(
        _request(
            "env_add",
            {"package": package, **_intent_params(intent)},
            json_output=json_output,
        )
    )
    suffix = " — restart kernel to apply" if result.get("restart_required") else ""
    _emit(result, json_output, f"Added {package}{suffix}")


@env_app.command("remove")
def env_remove(
    package: str,
    intent: str | None = typer.Option(None, "--intent", "-m"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    result = _object(
        _request(
            "env_remove",
            {"package": package, **_intent_params(intent)},
            json_output=json_output,
        )
    )
    suffix = " — restart kernel to apply" if result.get("restart_required") else ""
    _emit(result, json_output, f"Removed {package}{suffix}")


@env_app.command("status")
def env_status(json_output: bool = typer.Option(False, "--json")) -> None:
    result = _object(_request("env_status", None, json_output=json_output))
    packages = result.get("packages")
    lines = (
        [f"{name} {version}" for name, version in sorted(packages.items())]
        if isinstance(packages, dict)
        else []
    )
    if result.get("restart_required") is True:
        lines.append("Restart kernel to apply environment changes")
    if result.get("branch_lock_mismatch") is True:
        lines.append("Environment mismatch — background work deferred")
    _emit(result, json_output, "\n".join(lines) or "Environment is empty")


@app.command()
def cancel(
    run_id: str | None = typer.Argument(None),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    result = _object(_request("cancel", {"run_id": run_id}, json_output=json_output))
    _emit(
        result,
        json_output,
        "Cancelled active run" if result.get("cancelled") else "No active run",
    )


@app.command("eval")
def evaluate(
    code: str,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    result = _object(
        _request("eval", {"code": code}, json_output=json_output)
    )
    stdout = result.get("stdout")
    rendered = stdout if isinstance(stdout, str) else ""
    expression_result = result.get("result")
    if isinstance(expression_result, str):
        rendered += expression_result
    _emit(result, json_output, rendered)


@app.command()
def fork(
    name: str,
    parent: str | None = typer.Option(None, "--from"),
    intent: str | None = typer.Option(None, "--intent", "-m"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    params = {"name": name, "parent": parent, **_intent_params(intent)}
    result = _object(_request("fork", params, json_output=json_output))
    _emit(
        result,
        json_output,
        f"Forked {result.get('branch')} from {result.get('parent')}",
    )


@app.command()
def sweep(
    slug: str,
    overrides: list[str] = typer.Option(..., "--params"),  # noqa: B008
    group: str | None = typer.Option(None, "--group"),
    parent: str | None = typer.Option(None, "--from"),
    branch_prefix: str | None = typer.Option(None, "--branch-prefix"),
    intent: str | None = typer.Option(None, "--intent", "-m"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    parsed: list[JsonValue] = []
    for raw in overrides:
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as error:
            raise typer.BadParameter("--params must be a JSON object") from error
        if not isinstance(value, dict):
            raise typer.BadParameter("--params must be a JSON object")
        parsed.append(value)
    result = _object(
        _request(
            "sweep",
            {
                "slug": slug,
                "overrides": parsed,
                "group": group,
                "parent": parent,
                "branch_prefix": branch_prefix,
                **_intent_params(intent),
            },
            json_output=json_output,
        )
    )
    variants = result.get("variants")
    count = len(variants) if isinstance(variants, list) else 0
    _emit(
        result,
        json_output,
        f"Created sweep {result.get('group')} with {count} variants",
    )


@app.command()
def switch(
    branch: str,
    force: bool = typer.Option(False, "--force"),
    intent: str | None = typer.Option(None, "--intent", "-m"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    params = {"branch": branch, "force": force, **_intent_params(intent)}
    result = _object(_request("switch", params, json_output=json_output))
    _emit(result, json_output, f"Switched to {result.get('branch')}")


@app.command()
def preflight(
    step: int = typer.Option(..., "--to", min=1),
    branch: str | None = typer.Option(None, "--branch"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    result = _object(
        _request("preflight", {"step": step, "branch": branch}, json_output=json_output)
    )
    lines = [
        f"Recompute {item.get('cell')} ({item.get('cost_seconds') or 'unknown'} s)"
        for item in _objects(result.get("recompute"))
    ]
    lines.extend(
        f"Irrecoverable: {name}" for name in _strings(result.get("irrecoverable"))
    )
    _emit(result, json_output, "\n".join(lines) or "No recomputation needed")


@app.command()
def rewind(
    step: int = typer.Option(..., "--to", min=1),
    branch: str | None = typer.Option(None, "--branch"),
    intent: str | None = typer.Option(None, "--intent", "-m"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    params = {"step": step, "branch": branch, **_intent_params(intent)}
    result = _object(_request("rewind", params, json_output=json_output))
    _emit(result, json_output, f"Rewound {result.get('branch')} to step {step}")


@app.command()
def adopt(
    slug: str,
    from_branch: str = typer.Option(..., "--from"),
    branch: str | None = typer.Option(None, "--branch"),
    resolution: str | None = typer.Option(None, "--resolution"),
    intent: str | None = typer.Option(None, "--intent", "-m"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    params = {
        "slug": slug,
        "from_branch": from_branch,
        "branch": branch,
        "resolution": resolution,
        **_intent_params(intent),
    }
    result = _object(_request("adopt", params, json_output=json_output))
    _emit(result, json_output, f"Adopted {slug} from {from_branch}")


@app.command()
def diff(
    left: str,
    right: str,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    result = _object(
        _request("diff", {"left": left, "right": right}, json_output=json_output)
    )
    lines = [
        f"{item.get('cell')}: {item.get('divergence')} divergence"
        for item in _objects(result.get("differences"))
    ]
    _emit(result, json_output, "\n".join(lines) or "No differences")


@app.command()
def rename(
    old: str,
    new: str,
    intent: str | None = typer.Option(None, "--intent", "-m"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    result = _object(
        _request(
            "rename",
            {"old": old, "new": new, **_intent_params(intent)},
            json_output=json_output,
        )
    )
    _emit(result, json_output, f"Renamed {old} to {new}")


@asset_app.command("preview")
def asset_preview(
    target: str,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    result = _request("asset_preview", {"target": target}, json_output=json_output)
    _emit(result, json_output, json.dumps(result, indent=2))


@asset_app.command("page")
def asset_page(
    target: str,
    offset: int = typer.Option(0, "--offset", min=0),
    limit: int = typer.Option(20, "--limit", min=1),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    result = _request(
        "asset_page",
        {"target": target, "query": {"offset": offset, "limit": limit}},
        json_output=json_output,
    )
    _emit(result, json_output, json.dumps(result, indent=2))


@app.command()
def context(json_output: bool = typer.Option(False, "--json")) -> None:
    result = _object(_request("context", None, json_output=json_output))
    lines = [f"Branch {result.get('branch')}, checkpoint {result.get('checkpoint')}"]
    for cell in _objects(result.get("unsynced")):
        causes = _strings(cell.get("causes")) or [str(cell.get("state"))]
        lines.append(f"{cell.get('slug')}: {', '.join(str(item) for item in causes)}")
    for failure in _objects(result.get("failures")):
        lines.append(
            f"Last failure: {failure.get('cell')} at step {failure.get('step')}"
        )
        traceback_text = failure.get("traceback")
        if isinstance(traceback_text, str):
            lines.append(traceback_text.rstrip())
    _emit(result, json_output, "\n".join(lines))


@app.command("mcp")
def mcp_server(
    actor: str = typer.Option("agent:mcp", "--actor"),
) -> None:
    from lumlflow.flow.daemon.mcp import run_stdio

    run_stdio(find_flow_root(), actor=actor)


@app.command()
def promote(
    slug: str,
    output: str,
    intent: str | None = typer.Option(None, "--intent", "-m"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    result = _object(
        _request(
            "promote",
            {"slug": slug, "output": output, **_intent_params(intent)},
            json_output=json_output,
        )
    )
    _emit(
        result,
        json_output,
        f"Queued {slug}.{output} for publication",
    )


@app.command()
def root(json_output: bool = typer.Option(False, "--json")) -> None:
    try:
        flow_root = find_flow_root()
    except FileNotFoundError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error
    result: dict[str, JsonValue] = {"root": str(flow_root)}
    _emit(result, json_output, str(flow_root))


@agent_app.command("begin")
def agent_begin(
    label: str = typer.Option(..., "--label"),
    intent: str | None = typer.Option(None, "--intent", "-m"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    params = {"label": label, **_intent_params(intent)}
    result = _object(_request("agent_begin", params, json_output=json_output))
    _emit(result, json_output, f"Agent session {label} started")


@agent_app.command("end")
def agent_end(
    label: str = typer.Option(..., "--label"),
    intent: str | None = typer.Option(None, "--intent", "-m"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    params = {"label": label, **_intent_params(intent)}
    result = _object(_request("agent_end", params, json_output=json_output))
    _emit(result, json_output, f"Agent session {label} ended")


@agent_app.command(
    "exec", context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def agent_exec(
    ctx: typer.Context,
    label: str = typer.Option("agent:cli", "--label"),
    intent: str | None = typer.Option(None, "--intent", "-m"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    command = list(ctx.args)
    if command and command[0] == "--":
        command.pop(0)
    if not command:
        raise typer.BadParameter("a command is required after --")
    _request(
        "agent_begin",
        {"label": label, **_intent_params(intent)},
        json_output=json_output,
    )
    environment = os.environ.copy()
    environment["LUMLFLOW_ACTOR"] = label
    try:
        completed = subprocess.run(command, env=environment, check=False)
    finally:
        _request(
            "agent_end",
            {"label": label, **_intent_params(intent)},
            json_output=json_output,
        )
    result: dict[str, JsonValue] = {
        "command": list(command),
        "exit_code": completed.returncode,
    }
    _emit(result, json_output, f"Command exited {completed.returncode}")
    if completed.returncode:
        raise typer.Exit(code=completed.returncode)


@daemon_app.command("start")
def daemon_start(
    json_output: bool = typer.Option(False, "--json"),
    ui_url: str = typer.Option(
        DEFAULT_FLOW_UI_URL,
        "--ui-url",
        envvar="LUMLFLOW_UI_URL",
        help="Flow UI URL used to build the live-session link",
    ),
) -> None:
    result = _object(_request("handshake", None, json_output=json_output))
    result.update(_daemon_connect_info(find_flow_root(), ui_url))
    _emit(result, json_output, _daemon_running_human(result))


@daemon_app.command("stop")
def daemon_stop(json_output: bool = typer.Option(False, "--json")) -> None:
    result = _object(_request("shutdown", None, json_output=json_output))
    _emit(result, json_output, "Daemon stopped")


@daemon_app.command("status")
def daemon_status(
    json_output: bool = typer.Option(False, "--json"),
    ui_url: str = typer.Option(
        DEFAULT_FLOW_UI_URL,
        "--ui-url",
        envvar="LUMLFLOW_UI_URL",
        help="Flow UI URL used to build the live-session link",
    ),
) -> None:
    try:
        flow_dir = find_flow_root()
        client = DaemonClient(flow_dir, timeout=0.5)
        result = _object(client.request("handshake"))
        result.update(_daemon_connect_info(flow_dir, ui_url))
        _emit(result, json_output, _daemon_running_human(result))
    except (ConnectionError, FileNotFoundError, OSError, ValueError):
        result = {"running": False}
        _emit(result, json_output, "Daemon stopped")


__all__ = ["app", "find_flow_root"]
