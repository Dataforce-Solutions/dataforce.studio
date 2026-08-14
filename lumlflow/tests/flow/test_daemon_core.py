from __future__ import annotations

import asyncio
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from lumlflow.flow.daemon import api as daemon_api
from lumlflow.flow.daemon import kernel_proc
from lumlflow.flow.daemon.api import (
    DaemonClient,
    DaemonRpcError,
    DaemonRuntime,
    ExclusiveStoreLock,
    StoreOwnershipError,
    connect_or_start,
)
from lumlflow.flow.daemon.kernel_proc import KernelProcess
from lumlflow.flow.dsl.accept import accept_cell, compute_lib_tree_hash
from lumlflow.flow.ids import mint_ulid
from lumlflow.flow.store import branches
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import InputRecord, OutputRecord, RunRecordedOp


def _install_test_venv(flow_dir: Path) -> None:
    venv = flow_dir / ".venv"
    try:
        venv.symlink_to(Path(sys.prefix).resolve(), target_is_directory=True)
    except OSError:
        pytest.skip("the end-to-end daemon test requires a venv symlink")


def _wait_until_missing(path: Path, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while path.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not path.exists()


def test_store_lock_allows_only_one_daemon_owner(tmp_path: Path) -> None:
    lock_path = tmp_path / "flow" / ".lumlflow" / "daemon.lock"
    first = ExclusiveStoreLock(lock_path)
    second = ExclusiveStoreLock(lock_path)

    first.acquire()
    try:
        with pytest.raises(StoreOwnershipError, match="another daemon"):
            second.acquire()
    finally:
        first.release()

    second.acquire()
    second.release()


def test_flow_venv_is_not_part_of_the_lib_tree(tmp_path: Path) -> None:
    flow_dir = tmp_path / "flow"
    store = FlowStore.init(flow_dir)
    initial_hash = compute_lib_tree_hash(flow_dir)
    dependency = flow_dir / ".venv" / "lib" / "dependency.py"
    dependency.parent.mkdir(parents=True)
    dependency.write_text("VERSION = 1\n", encoding="utf-8")

    assert compute_lib_tree_hash(flow_dir) == initial_hash
    store.close()


def test_missing_flow_venv_is_created_with_uv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    flow_dir = tmp_path / "flow"
    flow_dir.mkdir()
    process = KernelProcess(flow_dir)
    calls: list[list[str]] = []

    def fake_run(command: list[str], *, check: bool, cwd: Path) -> None:
        assert check is True
        assert cwd == flow_dir
        calls.append(command)
        python = flow_dir / ".venv" / "bin" / "python"
        python.parent.mkdir(parents=True)
        python.write_bytes(b"test")

    monkeypatch.setattr(
        "lumlflow.flow.daemon.kernel_proc.shutil.which",
        lambda name: "/tools/uv" if name == "uv" else None,
    )
    monkeypatch.setattr("lumlflow.flow.daemon.kernel_proc.subprocess.run", fake_run)

    assert process._venv_python() == flow_dir / ".venv" / "bin" / "python"
    assert calls == [["/tools/uv", "sync", "--project", str(flow_dir)]]


def test_mode_settings_mark_only_multi_branch_inputs_for_strict_copying(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    flow_yaml = store.flow_dir / "flow.yaml"
    contents = flow_yaml.read_text(encoding="utf-8")
    flow_yaml.write_text(
        contents.replace("  paranoid: false", "  paranoid: true").replace(
            "  strict: false", "  strict: true"
        ),
        encoding="utf-8",
    )
    cell_path = store.flow_dir / "cells" / "source.py"
    cell_path.write_text(
        """class Source:
    produces = {"value": "asset"}
    def materialize(self, ctx):
        return {"value": [1, 2, 3]}
""",
        encoding="utf-8",
    )
    accepted = accept_cell(store, cell_path)
    value_ref = store.cas.put("values", b"value")
    mat_id = mint_ulid()
    content_hash = "a" * 64
    store.commit(
        actor="system:test",
        intent="record source",
        ops=[
            RunRecordedOp(
                mat_id=mat_id,
                version_id=accepted.version_id,
                memo_key="memo",
                state="succeeded",
                outputs={
                    "value": OutputRecord(
                        content_hash=content_hash,
                        kind="pickle",
                        size=5,
                        value_ref=value_ref,
                        persisted=True,
                    )
                },
            )
        ],
    )
    record = InputRecord(
        uid=accepted.uid,
        output="value",
        content_hash=content_hash,
        mat_id=mat_id,
    )

    before_fork = kernel_proc._kernel_inputs(store, {"value": record}, strict=True)
    branches.fork(store, "main", "experiment")
    after_fork = kernel_proc._kernel_inputs(store, {"value": record}, strict=True)

    assert kernel_proc._flow_mode_enabled(store.flow_dir, "paranoid") is True
    assert kernel_proc._flow_mode_enabled(store.flow_dir, "strict") is True
    before_value = before_fork["value"]
    after_value = after_fork["value"]
    assert isinstance(before_value, dict)
    assert isinstance(after_value, dict)
    assert before_value["shared"] is False
    assert after_value["shared"] is True
    store.close()


def test_sandbox_commands_cover_supported_platform_profiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executables = {
        "unshare": "/usr/bin/unshare",
        "sandbox-exec": "/usr/bin/sandbox-exec",
    }
    monkeypatch.setattr(kernel_proc.shutil, "which", lambda name: executables.get(name))
    command = ["/venv/python", "-m", "lumlflow_kernel"]

    linux = kernel_proc._sandbox_command(command, "linux-unshare-network", tmp_path)
    macos = kernel_proc._sandbox_command(command, "macos-sandbox-exec", tmp_path)
    windows = kernel_proc._sandbox_command(command, "windows-plain", tmp_path)

    assert linux == ["/usr/bin/unshare", "-n", "--", *command]
    assert macos[:2] == ["/usr/bin/sandbox-exec", "-p"]
    assert "(deny network*)" in macos[2]
    assert f'(subpath "{tmp_path.resolve()}")' in macos[2]
    assert macos[3:] == command
    assert windows == command


async def test_status_reports_active_sandbox_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(kernel_proc.platform, "system", lambda: "Windows")
    store = FlowStore.init(tmp_path / "flow")
    runtime = DaemonRuntime(store, watch_worktree=False)
    try:
        status = await runtime.dispatch("status", {})
        assert isinstance(status, dict)
        kernel = status["kernel"]
        assert isinstance(kernel, dict)
        assert kernel["sandbox_profile"] == "windows-plain"
    finally:
        await runtime.close()


async def test_tree_includes_branch_ancestry(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    trunk = branches.get_branch(store, "main")
    experiment = branches.fork(store, "main", "experiment")
    runtime = DaemonRuntime(store, watch_worktree=False)
    try:
        result = await runtime.dispatch("tree", {"branch": "experiment"})

        assert isinstance(result, dict)
        assert result["branches"] == [
            {
                "branch_id": trunk.branch_id,
                "name": "main",
                "parent_branch_id": None,
                "fork_step": 0,
                "archived": False,
                "sweep_group": None,
            },
            {
                "branch_id": experiment.branch_id,
                "name": "experiment",
                "parent_branch_id": trunk.branch_id,
                "fork_step": 1,
                "archived": False,
                "sweep_group": None,
            },
        ]
    finally:
        await runtime.close()


async def test_branch_fork_step_and_rename_rpc_are_journaled(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    runtime = DaemonRuntime(store, watch_worktree=False)
    try:
        created = await runtime.dispatch(
            "fork",
            {
                "name": "experiment",
                "parent": "main",
                "step": 1,
                "actor": "user:ui",
                "intent": "fork experiment from main",
            },
        )
        assert isinstance(created, dict)
        assert created["fork_step"] == 1
        branch_id = created["branch_id"]
        assert isinstance(branch_id, str)

        renamed = await runtime.dispatch(
            "rename",
            {
                "branch": branch_id,
                "name": "candidate",
                "actor": "user:ui",
                "intent": "rename experiment to candidate",
            },
        )

        assert renamed == {
            "branch": branch_id,
            "name": "candidate",
            "step": 3,
        }
        transaction = list(store.journal.replay())[-1]
        assert transaction.actor == "user:ui"
        assert transaction.intent == "rename experiment to candidate"
        assert transaction.ops[0].op == "branch_renamed"

        with pytest.raises(DaemonRpcError) as duplicate:
            await runtime.dispatch(
                "rename",
                {"branch": branch_id, "name": "main", "actor": "user:ui"},
            )
        assert duplicate.value.code == -32602
        assert str(duplicate.value) == "branch already exists: main"

        with pytest.raises(DaemonRpcError) as invalid_rewind:
            await runtime.dispatch(
                "preflight",
                {"branch": branch_id, "step": 99},
            )
        assert invalid_rewind.value.code == -32602
    finally:
        await runtime.close()


async def test_tcp_daemon_transport_requires_its_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    flow_dir = tmp_path / "flow"
    FlowStore.init(flow_dir).close()
    monkeypatch.setattr(daemon_api, "_use_tcp_transport", lambda: True)
    server = daemon_api.DaemonServer(flow_dir)
    await server.start()
    token_path = flow_dir / ".lumlflow" / "daemon.token"
    original_token = token_path.read_text()
    client = DaemonClient(flow_dir)
    try:
        status = await asyncio.to_thread(client.request, "status")
        assert isinstance(status, dict)
        token_path.write_text("wrong-token\n", encoding="utf-8")
        with pytest.raises(DaemonRpcError) as invalid:
            await asyncio.to_thread(client.request, "status")
        assert invalid.value.code == -32001
    finally:
        token_path.write_text(original_token, encoding="utf-8")
        await server.close()


async def test_asset_preview_is_kernel_free_and_page_starts_kernel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    cell_path = store.flow_dir / "cells" / "table.py"
    cell_path.write_text(
        """class Table:
    produces = {"rows": "asset"}
    def materialize(self, ctx):
        return {"rows": []}
""",
        encoding="utf-8",
    )
    accepted = accept_cell(store, cell_path)
    preview = {
        "schema": 1,
        "kind": "frame",
        "blocks": [{"type": "table", "columns": ["x"], "rows": [[1]]}],
    }
    preview_ref = store.cas.put("previews", json.dumps(preview, separators=(",", ":")))
    value_ref = store.cas.put("values", b"serialized-frame")
    store.commit(
        actor="system:test",
        intent="run table",
        ops=[
            RunRecordedOp(
                mat_id=mint_ulid(),
                version_id=accepted.version_id,
                memo_key="memo",
                state="succeeded",
                outputs={
                    "rows": OutputRecord(
                        content_hash="a" * 64,
                        kind="frame",
                        size=16,
                        preview_ref=preview_ref,
                        value_ref=value_ref,
                        persisted=True,
                    )
                },
            )
        ],
    )
    runtime = DaemonRuntime(store)
    started = False

    class FakeClient:
        async def request(
            self,
            method: str,
            params: dict[str, object] | None = None,
            *,
            timeout: float = 30.0,
        ) -> object:
            assert method == "page"
            assert params == {
                "value_ref": value_ref,
                "kind": "frame",
                "query": {"offset": 0, "limit": 1},
            }
            assert timeout == 30.0
            return {"columns": ["x"], "rows": [[1]], "total_rows": 1}

    async def fake_start() -> dict[str, object]:
        nonlocal started
        started = True
        monkeypatch.setattr(runtime.kernel, "client", FakeClient())
        return {"protocol": 1}

    monkeypatch.setattr(runtime.kernel, "start", fake_start)

    assert await runtime.dispatch("asset_preview", {"target": "table.rows"}) == preview
    assert started is False

    page = await runtime.dispatch(
        "asset_page",
        {
            "target": "table.rows",
            "query": {"offset": 0, "limit": 1},
        },
    )

    assert started is True
    assert page == {"columns": ["x"], "rows": [[1]], "total_rows": 1}
    store.close()


async def test_eval_proxies_active_branch_slice_and_surfaces_kernel_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    cell_path = store.flow_dir / "cells" / "prepare.py"
    cell_path.write_text(
        """class Prepare:
    produces = {"train_df": "asset"}
    def materialize(self, ctx):
        return {"train_df": [1, 2, 3]}
""",
        encoding="utf-8",
    )
    accepted = accept_cell(store, cell_path)
    value_ref = store.cas.put("values", b"serialized")
    store.commit(
        actor="system:test",
        intent="run prepare",
        ops=[
            RunRecordedOp(
                mat_id=mint_ulid(),
                version_id=accepted.version_id,
                memo_key="memo",
                state="succeeded",
                outputs={
                    "train_df": OutputRecord(
                        content_hash="a" * 64,
                        kind="pickle",
                        size=10,
                        value_ref=value_ref,
                        persisted=True,
                    )
                },
            )
        ],
    )
    runtime = DaemonRuntime(store, watch_worktree=False)
    requests: list[tuple[str, object]] = []

    async def fake_request(
        method: str,
        params: dict[str, object] | None = None,
        *,
        timeout: float = 30.0,
    ) -> object:
        requests.append((method, params))
        assert timeout == 30.0
        if params is not None and params["code"] == "missing":
            return {
                "state": "failed",
                "error_type": "NameError",
                "error": "name 'missing' is not defined",
            }
        return {
            "state": "succeeded",
            "result": "3",
            "result_type": "int",
            "stdout": "",
            "stderr": "",
            "touched": ["prepare.train_df"],
        }

    monkeypatch.setattr(runtime.kernel, "request", fake_request)
    try:
        result = await runtime.dispatch(
            "eval", {"code": "len(train_df)", "paranoid": True}
        )

        assert isinstance(result, dict)
        assert result["result"] == "3"
        method, params = requests[0]
        assert method == "eval"
        assert params == {
            "branch_slice": {
                "prepare.train_df": {
                    "value_ref": value_ref,
                    "content_hash": "a" * 64,
                    "kind": "pickle",
                }
            },
            "code": "len(train_df)",
            "paranoid": True,
        }

        with pytest.raises(DaemonRpcError, match="NameError.*missing") as error:
            await runtime.dispatch("eval", {"code": "missing"})
        assert error.value.code == -32010
    finally:
        await runtime.close()


def test_real_cell_runs_daemon_to_kernel_to_store_and_survives_restart(
    tmp_path: Path,
) -> None:
    flow_dir = tmp_path / "counter.flow"
    store = FlowStore.init(flow_dir)
    cell_path = flow_dir / "cells" / "counter.py"
    cell_path.write_text(
        """class Counter:
    produces = {"value": "asset"}
    params = {"start": 41}

    def materialize(self, ctx):
        print("running counter")
        return {"value": self.params["start"] + 1}
""",
        encoding="utf-8",
    )
    accepted = accept_cell(store, cell_path, actor="agent:test")
    slow_path = flow_dir / "cells" / "slow.py"
    slow_path.write_text(
        """class Slow:
    produces = {"value": "asset"}

    def materialize(self, ctx):
        while True:
            pass
""",
        encoding="utf-8",
    )
    slow = accept_cell(store, slow_path, actor="agent:test")
    initial_step = store.last_step
    store.close()
    _install_test_venv(flow_dir)

    client = connect_or_start(flow_dir)
    pid_path = flow_dir / ".lumlflow" / "daemon.pid"
    try:
        status = client.request("status")
        assert isinstance(status, dict)
        kernel_status = status["kernel"]
        assert isinstance(kernel_status, dict)
        assert kernel_status["running"] is False
        assert kernel_status["pid"] is None
        assert isinstance(kernel_status["sandbox_profile"], str)

        result = client.request("run", {"target": "counter"})
        assert isinstance(result, dict)
        assert result["executed"] == [accepted.uid]
        assert result["memo_hits"] == []

        running_status = client.request("status")
        assert isinstance(running_status, dict)
        kernel = running_status["kernel"]
        assert isinstance(kernel, dict)
        first_kernel_pid = kernel["pid"]
        assert kernel["running"] is True
        assert isinstance(first_kernel_pid, int)

        restarted = client.request("kernel_restart")
        assert isinstance(restarted, dict)
        after_restart = client.request("status")
        assert isinstance(after_restart, dict)
        restarted_kernel = after_restart["kernel"]
        assert isinstance(restarted_kernel, dict)
        assert restarted_kernel["running"] is True
        assert restarted_kernel["pid"] != first_kernel_pid

        with pytest.raises(DaemonRpcError) as missing_method:
            client.request("not_a_method")
        assert missing_method.value.code == -32601

        cancel_client = DaemonClient(flow_dir)
        with ThreadPoolExecutor(max_workers=1) as executor:
            slow_run = executor.submit(cancel_client.request, "run", {"target": "slow"})
            deadline = time.monotonic() + 5
            cancelled = False
            while time.monotonic() < deadline and not cancelled:
                response = client.request("cancel")
                assert isinstance(response, dict)
                cancelled = response["cancelled"] is True
                if not cancelled:
                    time.sleep(0.01)
            assert cancelled
            with pytest.raises(DaemonRpcError, match="cancelled"):
                slow_run.result(timeout=5)
    finally:
        client.request("shutdown")
        _wait_until_missing(pid_path)

    reopened = FlowStore.open(flow_dir)
    connection = reopened.index.connection
    assert connection is not None
    materialization = connection.execute(
        """
        SELECT state, outputs, log_ref FROM materializations
        WHERE version_id = ?
        """,
        (accepted.version_id,),
    ).fetchone()
    assert materialization is not None
    assert materialization["state"] == "succeeded"
    outputs = json.loads(materialization["outputs"])
    assert outputs["value"]["persisted"] is True
    assert reopened.cas.contains("values", outputs["value"]["value_ref"])
    assert reopened.cas.contains("previews", outputs["value"]["preview_ref"])
    assert reopened.cas.contains("logs", materialization["log_ref"])
    cancelled_run = connection.execute(
        """
        SELECT state FROM materializations
        WHERE version_id = ?
        """,
        (slow.version_id,),
    ).fetchone()
    assert cancelled_run is not None
    assert cancelled_run["state"] == "cancelled"
    assert reopened.last_step == initial_step + 2
    reopened.close()

    restarted_client = connect_or_start(flow_dir)
    try:
        second_result = restarted_client.request("run", {"target": "counter"})
        assert isinstance(second_result, dict)
        assert second_result["executed"] == []
        second_status = restarted_client.request("status")
        assert isinstance(second_status, dict)
        kernel_status = second_status["kernel"]
        assert isinstance(kernel_status, dict)
        assert kernel_status["running"] is False
        assert kernel_status["pid"] is None
        assert isinstance(kernel_status["sandbox_profile"], str)
    finally:
        restarted_client.request("shutdown")
        _wait_until_missing(pid_path)


def test_lib_edit_reruns_cell_with_fresh_module(tmp_path: Path) -> None:
    flow_dir = tmp_path / "lib-edit.flow"
    store = FlowStore.init(flow_dir)
    helper = flow_dir / "lib" / "helper.py"
    helper.write_text('VALUE = "first"\n', encoding="utf-8")
    cell_path = flow_dir / "cells" / "uses_lib.py"
    cell_path.write_text(
        """class UsesLib:
    produces = {"value": "asset"}

    def materialize(self, ctx):
        from lib.helper import VALUE
        return {"value": VALUE}
""",
        encoding="utf-8",
    )
    accepted = accept_cell(store, cell_path)
    store.close()
    _install_test_venv(flow_dir)
    client = connect_or_start(flow_dir)
    pid_path = flow_dir / ".lumlflow" / "daemon.pid"
    try:
        first = client.request("run", {"target": "uses_lib"})
        assert isinstance(first, dict)
        assert first["executed"] == [accepted.uid]

        helper.write_text(
            'VALUE = "fresh value with a different source size"\n',
            encoding="utf-8",
        )
        second = client.request("run", {"target": "uses_lib"})
        assert isinstance(second, dict)
        assert second["executed"] == [accepted.uid]
        preview = client.request("asset_preview", {"target": "uses_lib.value"})
        assert isinstance(preview, dict)
        assert "fresh value with a different source size" in json.dumps(preview)
    finally:
        client.request("shutdown")
        _wait_until_missing(pid_path)
