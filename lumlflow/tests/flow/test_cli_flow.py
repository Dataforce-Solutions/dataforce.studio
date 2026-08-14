from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest
from lumlflow.cli import app
from lumlflow.flow import cli as flow_cli
from lumlflow.flow.daemon.api import DaemonRuntime
from lumlflow.flow.daemon.errors import DaemonRpcError
from lumlflow.flow.dsl.accept import accept_cell
from lumlflow.flow.errors import contains_internal_identifier
from lumlflow.flow.ids import mint_ulid
from lumlflow.flow.scheduler.planner import ExecutionResult, PlanNode, Scheduler
from lumlflow.flow.store.branches import fork
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import InputRecord, OutputRecord, RunRecordedOp
from typer.testing import CliRunner

runner = CliRunner()

FLOW_COMMANDS = (
    ("init",),
    ("status",),
    ("tree",),
    ("graph",),
    ("cells",),
    ("cells", "list"),
    ("cells", "show"),
    ("cells", "new"),
    ("cells", "edit"),
    ("cells", "params"),
    ("run",),
    ("cancel",),
    ("fork",),
    ("sweep",),
    ("switch",),
    ("rewind",),
    ("preflight",),
    ("adopt",),
    ("diff",),
    ("rename",),
    ("asset", "preview"),
    ("asset", "page"),
    ("eval",),
    ("promote",),
    ("export",),
    ("import",),
    ("env", "add"),
    ("env", "remove"),
    ("env", "status"),
    ("context",),
    ("root",),
    ("agent", "begin"),
    ("agent", "end"),
    ("agent", "exec"),
    ("daemon", "start"),
    ("daemon", "stop"),
    ("daemon", "status"),
)

MUTATING_COMMANDS = (
    ("init",),
    ("cells", "new"),
    ("cells", "edit"),
    ("cells", "params"),
    ("run",),
    ("fork",),
    ("sweep",),
    ("switch",),
    ("rewind",),
    ("adopt",),
    ("rename",),
    ("promote",),
    ("import",),
    ("env", "add"),
    ("env", "remove"),
    ("agent", "begin"),
    ("agent", "end"),
    ("agent", "exec"),
)


def _source(class_name: str, value: int = 1, *, parameter: int | None = None) -> str:
    params = "" if parameter is None else f'    params = {{"threshold": {parameter}}}\n'
    return f"""class {class_name}:
{params}    produces = {{"value": "asset"}}

    def materialize(self, ctx):
        return {{"value": {value}}}
"""


@pytest.mark.parametrize("command", FLOW_COMMANDS)
def test_every_flow_command_supports_json(command: tuple[str, ...]) -> None:
    result = runner.invoke(app, [*command, "--help"])

    assert result.exit_code == 0, result.output
    assert "--json" in result.stdout


@pytest.mark.parametrize("command", MUTATING_COMMANDS)
def test_mutating_flow_commands_support_intents(command: tuple[str, ...]) -> None:
    result = runner.invoke(app, [*command, "--help"])

    assert result.exit_code == 0, result.output
    assert "--intent" in result.stdout
    assert "-m" in result.stdout


@pytest.mark.parametrize("command", ["start", "status"])
def test_daemon_connect_coordinates_are_printed_for_humans(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    flow_dir = tmp_path / "flow"
    store_dir = flow_dir / ".lumlflow"
    store_dir.mkdir(parents=True)
    (flow_dir / "flow.yaml").write_text("flow: test\n", encoding="utf-8")
    (store_dir / "daemon.port").write_text("43125\n", encoding="utf-8")
    (store_dir / "daemon.token").write_text("secret token\n", encoding="utf-8")

    class FakeClient:
        def request(self, method: str, params: object = None) -> object:
            assert method == "handshake"
            return {"protocol": 1, "flow": "test"}

    monkeypatch.chdir(flow_dir)
    monkeypatch.setattr("lumlflow.flow.cli._client", lambda: FakeClient())
    monkeypatch.setattr(
        "lumlflow.flow.cli.DaemonClient", lambda *_args, **_kwargs: FakeClient()
    )

    result = runner.invoke(app, ["daemon", command])

    assert result.exit_code == 0, result.output
    assert "Daemon running" in result.stdout
    assert "HTTP URL: http://127.0.0.1:43125" in result.stdout
    assert "Token: secret token" in result.stdout
    assert (
        "UI: http://localhost:5173/flow/railroad?"
        "live=http%3A%2F%2F127.0.0.1%3A43125&token=secret+token"
    ) in result.stdout


@pytest.mark.parametrize("command", ["start", "status"])
def test_daemon_connect_coordinates_are_in_json_with_ui_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    flow_dir = tmp_path / "flow"
    store_dir = flow_dir / ".lumlflow"
    store_dir.mkdir(parents=True)
    (flow_dir / "flow.yaml").write_text("flow: test\n", encoding="utf-8")
    (store_dir / "daemon.port").write_text("43125\n", encoding="utf-8")
    (store_dir / "daemon.token").write_text("secret\n", encoding="utf-8")

    class FakeClient:
        def request(self, method: str, params: object = None) -> object:
            assert method == "handshake"
            return {"protocol": 1, "flow": "test"}

    monkeypatch.chdir(flow_dir)
    monkeypatch.setattr("lumlflow.flow.cli._client", lambda: FakeClient())
    monkeypatch.setattr(
        "lumlflow.flow.cli.DaemonClient", lambda *_args, **_kwargs: FakeClient()
    )

    result = runner.invoke(
        app,
        [
            "daemon",
            command,
            "--ui-url",
            "https://ui.example/flow/railroad?theme=dark",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "flow": "test",
        "http_url": "http://127.0.0.1:43125",
        "protocol": 1,
        "token": "secret",
        "ui_url": (
            "https://ui.example/flow/railroad?theme=dark&"
            "live=http%3A%2F%2F127.0.0.1%3A43125&token=secret"
        ),
    }


def test_agent_end_forwards_its_intent(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[tuple[str, object]] = []

    class FakeClient:
        def request(self, method: str, params: object = None) -> object:
            requests.append((method, params))
            return {"actor": "agent:test", "locked": False}

    monkeypatch.setattr("lumlflow.flow.cli._client", lambda: FakeClient())

    result = runner.invoke(
        app,
        ["agent", "end", "--label", "agent:test", "-m", "finish edit", "--json"],
    )

    assert result.exit_code == 0, result.output
    assert requests == [("agent_end", {"label": "agent:test", "intent": "finish edit"})]


def test_eval_prints_expression_result_and_supports_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "flow.yaml").write_text("flow: placeholder\n", encoding="utf-8")
    requests: list[tuple[str, object]] = []

    class FakeClient:
        def request(self, method: str, params: object = None) -> object:
            requests.append((method, params))
            return {
                "state": "succeeded",
                "result": "3",
                "result_type": "int",
                "stdout": "loaded\n",
                "stderr": "",
                "touched": ["prepare.train_df"],
            }

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("lumlflow.flow.cli._client", lambda: FakeClient())

    human = runner.invoke(app, ["eval", "len(train_df)"])
    structured = runner.invoke(app, ["eval", "len(train_df)", "--json"])

    assert human.exit_code == 0, human.output
    assert human.stdout == "loaded\n3\n"
    assert json.loads(structured.stdout)["result"] == "3"
    assert requests == [
        ("eval", {"code": "len(train_df)"}),
        ("eval", {"code": "len(train_df)"}),
    ]


def test_promote_forwards_named_output_and_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[tuple[str, object]] = []

    class FakeClient:
        def request(self, method: str, params: object = None) -> object:
            requests.append((method, params))
            return {"cell": "train", "output": "model", "state": "queued"}

    monkeypatch.setattr("lumlflow.flow.cli._client", lambda: FakeClient())

    result = runner.invoke(
        app,
        ["promote", "train", "model", "-m", "publish winner", "--json"],
    )

    assert result.exit_code == 0, result.output
    assert requests == [
        (
            "promote",
            {
                "slug": "train",
                "output": "model",
                "intent": "publish winner",
            },
        )
    ]


def test_param_edit_and_sweep_forward_structured_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[tuple[str, object]] = []

    class FakeClient:
        def request(self, method: str, params: object = None) -> object:
            requests.append((method, params))
            if method == "cells_show":
                return {
                    "definition_hash": "definition-1",
                    "manifest": {"params": {"epochs": 10, "lr": 0.1}},
                }
            if method == "params_edit":
                return {"changed": True}
            return {"group": "learning-rate", "variants": [{"branch": "sweep/1"}]}

    monkeypatch.setattr("lumlflow.flow.cli._client", lambda: FakeClient())

    edit = runner.invoke(
        app,
        [
            "cells",
            "params",
            "train",
            "--set",
            "lr=0.2",
            "--set",
            'schedule={"warmup":2}',
            "-m",
            "tune training",
            "--json",
        ],
    )
    sweep_result = runner.invoke(
        app,
        [
            "sweep",
            "train",
            "--params",
            '{"lr":0.2}',
            "--params",
            '{"lr":0.3}',
            "--group",
            "learning-rate",
            "--from",
            "main",
            "--branch-prefix",
            "sweep/lr",
            "-m",
            "compare learning rates",
            "--json",
        ],
    )

    assert edit.exit_code == 0, edit.output
    assert sweep_result.exit_code == 0, sweep_result.output
    assert requests == [
        ("cells_show", {"slug": "train", "branch": None}),
        (
            "params_edit",
            {
                "slug": "train",
                "branch": None,
                "params": {
                    "epochs": 10,
                    "lr": 0.2,
                    "schedule": {"warmup": 2},
                },
                "base_definition_hash": "definition-1",
                "intent": "tune training",
            },
        ),
        (
            "sweep",
            {
                "slug": "train",
                "overrides": [{"lr": 0.2}, {"lr": 0.3}],
                "group": "learning-rate",
                "parent": "main",
                "branch_prefix": "sweep/lr",
                "intent": "compare learning rates",
            },
        ),
    ]


def test_init_generates_compact_agent_and_checkout_guides(tmp_path: Path) -> None:
    flow_dir = tmp_path / "demo.flow"

    result = runner.invoke(app, ["init", str(flow_dir), "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["branch"] == "main"
    guide = (flow_dir / "AGENTS.md").read_text(encoding="utf-8")
    checkout = (flow_dir / ".lumlflow" / "CHECKOUT.md").read_text(encoding="utf-8")
    assert len(guide.splitlines()) <= 20
    assert "lumlflow context" in guide
    assert "always name" in guide
    assert "`asset`, `model`, `dataset`, and `experiment`" in guide
    assert "ctx.flow_dir" in guide
    assert "failures include a traceback" in guide
    assert "rerun it until status reports `synced`" in guide
    assert "Branch: main" in checkout
    assert "Checkpoint: step 1" in checkout
    assert (flow_dir / "pyproject.toml").is_file()
    assert json.loads((flow_dir / ".mcp.json").read_text(encoding="utf-8")) == {
        "mcpServers": {
            "lumlflow": {"command": "lumlflow", "args": ["mcp"]},
        }
    }


def test_agent_exec_attributes_child_cli_transactions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    runtime = DaemonRuntime(store, watch_worktree=False)

    class RuntimeClient:
        def request(self, method: str, params: object = None) -> object:
            assert params is None or isinstance(params, dict)
            return asyncio.run(runtime.dispatch(method, params or {}))

    def run_child(
        command: list[str], *, env: dict[str, str], check: bool
    ) -> subprocess.CompletedProcess[str]:
        assert check is False
        assert env["LUMLFLOW_ACTOR"] == "agent:cli:test"
        previous_actor = os.environ.get("LUMLFLOW_ACTOR")
        os.environ["LUMLFLOW_ACTOR"] = env["LUMLFLOW_ACTOR"]
        try:
            created = flow_cli._request(
                "cells_new",
                {"slug": "agent_cell", "intent": "create agent cell"},
                json_output=False,
            )
        finally:
            if previous_actor is None:
                os.environ.pop("LUMLFLOW_ACTOR", None)
            else:
                os.environ["LUMLFLOW_ACTOR"] = previous_actor
        assert isinstance(created, dict)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("lumlflow.flow.cli._client", RuntimeClient)
    monkeypatch.setattr("lumlflow.flow.cli.subprocess.run", run_child)
    try:
        result = runner.invoke(
            app,
            [
                "agent",
                "exec",
                "--label",
                "agent:cli:test",
                "--intent",
                "build agent cell",
                "--",
                "agent-command",
            ],
        )

        assert result.exit_code == 0, result.output
        transactions = list(runtime.store.journal.replay())
        accepted = [
            transaction
            for transaction in transactions
            if any(operation.op == "cell_accepted" for operation in transaction.ops)
        ]
        assert len(accepted) == 1
        assert accepted[0].actor == "agent:cli:test"
        assert accepted[0].intent == "create agent cell"
        assert transactions[-1].actor == "agent:cli:test"
        assert transactions[-1].intent == "build agent cell"
    finally:
        asyncio.run(runtime.close())


async def test_cells_new_after_scaffolds_wiring_and_graph_slice(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    producer = store.flow_dir / "cells" / "features.py"
    producer.write_text(_source("Features"), encoding="utf-8")
    accept_cell(store, producer)
    runtime = DaemonRuntime(store)
    try:
        created = await runtime.dispatch(
            "cells_new", {"slug": "train_model", "after": "features"}
        )
        assert isinstance(created, dict)
        source = (store.flow_dir / "cells" / "train_model.py").read_text(
            encoding="utf-8"
        )
        assert source.startswith("from __future__ import annotations")
        assert "'value': 'features.value'" in source
        assert "def materialize(self, ctx, value):" in source
        assert "_check: CellProtocol = TrainModel()" in source

        graph = await runtime.dispatch("graph", {"around": "train_model", "depth": 1})
        assert isinstance(graph, dict)
        nodes_value = graph["nodes"]
        assert isinstance(nodes_value, list)
        assert all(isinstance(item, dict) for item in nodes_value)
        nodes = cast(list[dict[str, object]], nodes_value)
        assert graph["edges"] == [
            {
                "from_uid": next(
                    item["uid"] for item in nodes if item["slug"] == "features"
                ),
                "from": "features",
                "output": "value",
                "to_uid": next(
                    item["uid"] for item in nodes if item["slug"] == "train_model"
                ),
                "to": "train_model",
                "input": "value",
            }
        ]
    finally:
        await runtime.close()


async def test_diff_separates_definition_divergence(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    path = store.flow_dir / "cells" / "features.py"
    path.write_text(_source("Features", parameter=1), encoding="utf-8")
    accepted = accept_cell(store, path)
    child = fork(store, "main", "experiment")
    path.write_text(_source("Features", 2, parameter=2), encoding="utf-8")
    accept_cell(store, path, branch=child.branch_id)

    async def execute(
        node: PlanNode, _inputs: dict[str, InputRecord]
    ) -> ExecutionResult:
        params = node.manifest["params"]
        assert isinstance(params, dict)
        threshold = params["threshold"]
        assert isinstance(threshold, int)
        return ExecutionResult(
            outputs={
                "value": OutputRecord(
                    content_hash=f"{threshold:064d}",
                    kind="pickle",
                    size=1,
                    persisted=True,
                )
            },
            cost_seconds=0.1,
        )

    await Scheduler(store, execute, lib_tree_hash="lib").run(
        store.branch_id, accepted.uid
    )
    await Scheduler(store, execute, lib_tree_hash="lib").run(
        child.branch_id, accepted.uid
    )
    runtime = DaemonRuntime(store, watch_worktree=False)
    try:
        result = await runtime.dispatch("diff", {"left": "main", "right": "experiment"})
        assert isinstance(result, dict)
        differences = result["differences"]
        assert isinstance(differences, list)
        assert all(isinstance(item, dict) for item in differences)
        typed_differences = cast(list[dict[str, object]], differences)
        assert typed_differences[0]["cell"] == "features"
        assert typed_differences[0]["divergence"] == "definition"
        assert typed_differences[0]["left_params"] == {"threshold": 1}
        assert typed_differences[0]["right_params"] == {"threshold": 2}
        assert typed_differences[0]["left_outputs"] == {"value": f"{1:064d}"}
        assert typed_differences[0]["right_outputs"] == {"value": f"{2:064d}"}
    finally:
        await runtime.close()


async def test_adopt_maps_three_way_conflicts_to_structured_rpc_errors(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    path = store.flow_dir / "cells" / "features.py"
    path.write_text(_source("Features"), encoding="utf-8")
    accept_cell(store, path)
    child = fork(store, "main", "experiment")
    path.write_text(_source("Features", 2), encoding="utf-8")
    accept_cell(store, path, branch=child.branch_id)
    path.write_text(_source("Features", 3), encoding="utf-8")
    accept_cell(store, path, branch=store.branch_id)
    runtime = DaemonRuntime(store, watch_worktree=False)
    try:
        with pytest.raises(DaemonRpcError) as captured:
            await runtime.dispatch(
                "adopt",
                {
                    "slug": "features",
                    "from_branch": child.branch_id,
                    "branch": store.branch_id,
                },
            )

        assert captured.value.code == -32009
        assert str(captured.value) == (
            "adopt conflict for features: both branches edited it "
            "since their fork point"
        )
        data = captured.value.data
        assert isinstance(data, dict)
        assert data["kind"] == "definition"
        assert data["cell"] == "features"
        assert isinstance(data["base_definition_hash"], str)
        assert isinstance(data["current_definition_hash"], str)
        assert isinstance(data["incoming_definition_hash"], str)
    finally:
        await runtime.close()


def test_human_status_and_errors_hide_internal_identifiers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    uid = "01JABCDEF0123456789ABCDEFA"
    content_hash = "a" * 64
    (tmp_path / "flow.yaml").write_text("flow: placeholder\n", encoding="utf-8")

    class FakeClient:
        def request(self, method: str, params: object = None) -> object:
            assert method == "status"
            return {
                "branch": "main",
                "step": 4,
                "cells": 1,
                "cell_status": [
                    {
                        "slug": "train_model",
                        "state": "failed",
                        "causes": [f"uid {uid}", f"content_hash {content_hash}"],
                        "manifest": {"issues": [f"memo_key {content_hash}"]},
                    }
                ],
            }

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("lumlflow.flow.cli._client", lambda: FakeClient())

    human = runner.invoke(app, ["status"])
    structured = runner.invoke(app, ["status", "--json"])

    assert human.exit_code == 0
    assert not contains_internal_identifier(human.stdout)
    assert "content_hash" not in human.stdout
    assert "memo_key" not in human.stdout
    assert uid in structured.stdout
    assert content_hash in structured.stdout


async def test_failed_status_explains_the_runtime_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    path = store.flow_dir / "cells" / "train_model.py"
    path.write_text(_source("TrainModel"), encoding="utf-8")
    accepted = accept_cell(store, path)
    log = (
        json.dumps(
            {
                "run_id": mint_ulid(),
                "stream": "stderr",
                "seq": 0,
                "bytes": (
                    "Traceback (most recent call last):\n"
                    '  File "train_model.py", line 5, in materialize\n'
                    "RuntimeError: gate failure\n"
                ),
            },
            separators=(",", ":"),
        ).encode()
        + b"\n"
    )
    log_ref = store.cas.put("logs", log)
    store.commit(
        actor="system:scheduler",
        intent="run train_model",
        ops=[
            RunRecordedOp(
                mat_id=mint_ulid(),
                version_id=accepted.version_id,
                memo_key="failed-run",
                state="failed",
                log_ref=log_ref,
            )
        ],
    )
    runtime = DaemonRuntime(store, watch_worktree=False)
    try:
        status = await runtime.dispatch("status", {})
        assert isinstance(status, dict)

        class FakeClient:
            def request(self, method: str, params: object = None) -> object:
                assert method == "status"
                return status

        monkeypatch.chdir(store.flow_dir)
        monkeypatch.setattr("lumlflow.flow.cli._client", lambda: FakeClient())
        human = runner.invoke(app, ["status"])

        assert human.exit_code == 0
        assert "train_model: failed" in human.stdout
        assert "Traceback (most recent call last)" in human.stdout
        assert "RuntimeError: gate failure" in human.stdout
        assert not contains_internal_identifier(human.stdout)
    finally:
        await runtime.close()


def test_tier0_gate_runs_name_only_edit_inspect_fix_loop(tmp_path: Path) -> None:
    module = _load_gate_module()
    flow_dir = tmp_path / "flow"
    (flow_dir / "cells").mkdir(parents=True)
    cell = flow_dir / "cells" / "train_model.py"
    cell.write_text(_source("TrainModel"), encoding="utf-8")
    commands: list[tuple[str, ...]] = []

    def invoke(command: Sequence[str]) -> object:
        commands.append(tuple(command))
        broken = "gate failure" in cell.read_text(encoding="utf-8")
        exit_code = 1 if command[0] == "run" and broken else 0
        return module.CommandResult(exit_code, "train_model failed" if broken else "ok")

    results = module.run_gate(flow_dir, invoke)

    assert commands == [("run", "train_model"), ("status",), ("run", "train_model")]
    assert [result.exit_code for result in results] == [1, 0, 0]
    assert all(not contains_internal_identifier(result.output) for result in results)


def _load_gate_module() -> ModuleType:
    path = Path(__file__).parents[3] / "dev" / "tier0_gate" / "run.py"
    spec = importlib.util.spec_from_file_location("tier0_gate", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
