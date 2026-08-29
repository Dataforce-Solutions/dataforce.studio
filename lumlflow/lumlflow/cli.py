import ipaddress
import os
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from lumlflow.flow import cli as flow_cli

if TYPE_CHECKING:
    from lumlflow.flow.daemon.workspace import DaemonRecord

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
NON_LOOPBACK_WARNING = (
    "The tracker API on this port is unauthenticated on a non-loopback bind."
)

app = typer.Typer(
    name="lumlflow",
    help="Local ML experiment tracking",
)

flow_cli.register(app)


@app.command()
def ui(
    path: str | None = typer.Option(
        None,
        "--path",
        help="Backend store URI (e.g. sqlite://./experiments)",
    ),
    host: str = typer.Option(
        DEFAULT_HOST,
        "--host",
        help=f"Host to serve on. {NON_LOOPBACK_WARNING}",
    ),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="Port to serve on."),
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Do not open the browser."
    ),
) -> None:
    """Start lumlflow: Experiments, and this workspace's flows.

    It serves http://127.0.0.1:5000 by default. It keeps running until you stop
    it with Ctrl+C. Start a second one in the same workspace and it opens the
    browser on the one already serving.
    """
    from lumlflow.flow.daemon import client, workspace
    from lumlflow.flow.daemon import main as server
    from lumlflow.flow.errors import FlowError

    if path is not None:
        # Read out of the environment by the store this process is about to
        # serve; one already serving keeps the store it was started with.
        os.environ["BACKEND_STORE_URI"] = path

    root = workspace.resolve_root(Path.cwd())
    try:
        serving = client.live_record(root)
        if serving is not None and not client.stand_down(serving):
            _attach(serving, port=port, no_browser=no_browser)
            return
        code = server.serve_here(
            root,
            web_host=host,
            web_port=port,
            announce=lambda record: _serving(record, no_browser=no_browser),
        )
    except FlowError as failure:
        typer.echo(str(failure), err=True)
        raise typer.Exit(1) from failure
    if code:
        raise typer.Exit(code)


def _serving(record: "DaemonRecord", *, no_browser: bool) -> None:
    """Said once this process is answering, from inside its own event loop."""
    _warn_if_non_loopback(record.web_host)
    typer.echo(f"workspace: {record.workspace}")
    typer.echo(f"lumlflow at {_url(record)}")
    typer.echo("press Ctrl+C to stop")
    if not no_browser:
        webbrowser.open(_url(record))


def _attach(record: "DaemonRecord", *, port: int, no_browser: bool) -> None:
    """Point the browser at what is already serving this workspace.

    A port belongs to the process that bound it, so one that answers on
    another is said plainly rather than papered over — and never taken from
    a session somebody is using or a run somebody is waiting on.
    """
    if not record.web_port:
        typer.echo(
            f"lumlflow is already running for {record.workspace}. it is not "
            "serving a browser endpoint",
            err=True,
        )
        raise typer.Exit(1)
    _warn_if_non_loopback(record.web_host)
    typer.echo(f"workspace: {record.workspace}")
    typer.echo(f"lumlflow already at {_url(record)}")
    if record.web_port != port:
        typer.echo(f"it is serving port {record.web_port}, not {port}")
    if not no_browser:
        webbrowser.open(_url(record))


def _url(record: "DaemonRecord") -> str:
    """The authenticated address: the flow API asks every caller for the
    workspace's token, and the SPA is the one caller with no other way to
    have it."""
    return f"http://{record.web_host}:{record.web_port}/?token={record.token}"


def _warn_if_non_loopback(host: str) -> None:
    if not _is_loopback(host):
        typer.echo(f"warning: {NON_LOOPBACK_WARNING}")


def _is_loopback(host: str) -> bool:
    if host.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@app.command(
    context_settings={
        # The TUI accepts an optional positional script + arbitrary
        # pass-through args; we collect them via `script_args` and let
        # Typer ignore unknown options that belong to the script
        # (rather than treating `--epochs 10` as a `tui` option).
        "allow_extra_args": True,
        "ignore_unknown_options": True,
    }
)
def tui(
    ctx: typer.Context,
    script: str | None = typer.Argument(
        None,
        help=(
            "Optional training script to run; the TUI shares its SQLite "
            "store via BACKEND_STORE_URI and auto-attaches to the experiment "
            "the script creates."
        ),
    ),
    path: str | None = typer.Option(
        None,
        "--path",
        help="Backend store URI (e.g. sqlite://./experiments)",
    ),
    refresh_interval: float = typer.Option(
        2.0,
        "--refresh-interval",
        help="Live auto-refresh interval (seconds)",
        min=0.1,
    ),
    no_auto_refresh: bool = typer.Option(
        False,
        "--no-auto-refresh",
        help="Start with auto-refresh disabled",
    ),
    attach_timeout: float = typer.Option(
        60.0,
        "--attach-timeout",
        help=(
            "Max seconds to wait for the launched script to create a "
            "new experiment before giving up auto-attach."
        ),
        min=1.0,
    ),
) -> None:
    if path is not None:
        os.environ["BACKEND_STORE_URI"] = path

    from lumlflow.settings import get_config

    try:
        from lumlflow.tui import LumlflowApp
        from lumlflow.tui.run_manager import RunSpec
    except ModuleNotFoundError as exc:
        # Only translate missing optional deps into a friendly hint;
        # re-raise genuine import bugs inside lumlflow itself.
        if exc.name is None or not exc.name.startswith(("textual", "plotext")):
            raise
        typer.echo(
            "The TUI requires optional dependencies. "
            "Install them with: pip install 'lumlflow[tui]'",
            err=True,
        )
        raise typer.Exit(code=1) from exc

    # `BACKEND_STORE_URI` after `parse_uri` is a filesystem path; the child
    # process expects a fully-qualified `sqlite://...` URI so its tracker
    # reads from the same store. Always prefix here (idempotently).
    raw = get_config().BACKEND_STORE_URI
    store_uri = raw if "://" in raw else f"sqlite://{raw}"
    typer.echo(f"Using experiment store: {raw}")

    run_spec: RunSpec | None = None
    if script is not None:
        run_spec = RunSpec(script=script, args=tuple(ctx.args))

    app_instance = LumlflowApp(
        refresh_interval=refresh_interval,
        auto_refresh=not no_auto_refresh,
        run_spec=run_spec,
        store_uri=store_uri,
        attach_timeout=attach_timeout,
    )
    app_instance.run()


@app.command()
def version() -> None:
    from lumlflow import __version__

    typer.echo(f"lumlflow {__version__}")


if __name__ == "__main__":
    app()
