from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from lumlflow.flow.daemon import envs as env_module
from lumlflow.flow.daemon.api import DaemonRpcError, DaemonRuntime
from lumlflow.flow.daemon.envs import EnvironmentManager
from lumlflow.flow.dsl.accept import accept_cell
from lumlflow.flow.scheduler.planner import ExecutionResult
from lumlflow.flow.store.branches import fork
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import OutputRecord, RunRecordedOp


def _flow_with_environment(tmp_path: Path) -> FlowStore:
    store = FlowStore.init(tmp_path / "flow")
    (store.flow_dir / "pyproject.toml").write_text(
        '[project]\nname = "flow"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    (store.flow_dir / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    python = store.flow_dir / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_bytes(b"test interpreter")
    return store


def _accept_value_cell(
    store: FlowStore, slug: str, *, env_sensitive: bool = False
) -> tuple[str, str]:
    declaration = "    env_sensitive = True\n" if env_sensitive else ""
    path = store.flow_dir / "cells" / f"{slug}.py"
    path.write_text(
        f"""class {slug.title().replace("_", "")}:
    produces = {{"value": "asset"}}
{declaration}
    def materialize(self, ctx):
        return {{"value": 1}}
""",
        encoding="utf-8",
    )
    accepted = accept_cell(store, path)
    return accepted.uid, accepted.version_id


def _record_value(
    store: FlowStore, version_id: str, env_lock_hash: str, memo_key: str
) -> None:
    store.commit(
        actor="system:test",
        intent="run cell",
        ops=[
            RunRecordedOp(
                mat_id=f"mat-{memo_key}",
                version_id=version_id,
                memo_key=memo_key,
                state="succeeded",
                outputs={
                    "value": OutputRecord(
                        content_hash="a" * 64,
                        kind="pickle",
                        size=1,
                        persisted=False,
                    )
                },
                env_lock_hash=env_lock_hash,
            )
        ],
    )


class _RunningProcess:
    pid = 123

    def poll(self) -> None:
        return None


class _OpenClient:
    closed = False


async def test_env_add_journals_change_and_marks_loaded_kernel_for_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _flow_with_environment(tmp_path)
    sensitive_uid, sensitive_version = _accept_value_cell(
        store, "sensitive", env_sensitive=True
    )
    normal_uid, normal_version = _accept_value_cell(store, "normal")
    runtime = DaemonRuntime(store, watch_worktree=False)
    old_lock_hash = runtime.envs.live_lock_hash
    assert old_lock_hash is not None
    _record_value(store, sensitive_version, old_lock_hash, "sensitive-old")
    _record_value(store, normal_version, old_lock_hash, "normal-old")
    commands: list[list[str]] = []

    def fake_run(
        command: list[str],
        *,
        cwd: Path,
        check: bool,
        capture_output: bool = False,
        text: bool = False,
    ) -> None:
        assert cwd == store.flow_dir
        assert check is True
        assert capture_output is False
        assert text is False
        commands.append(command)
        if command[1] == "add":
            (store.flow_dir / "uv.lock").write_text(
                "version = 2\nlightgbm = 2\n", encoding="utf-8"
            )

    async def loaded_packages() -> dict[str, str]:
        return {"lightgbm": "1.0"}

    async def execute(*_args: object, **_kwargs: object) -> ExecutionResult:
        return ExecutionResult(
            outputs={
                "value": OutputRecord(
                    content_hash="a" * 64,
                    kind="pickle",
                    size=1,
                    persisted=False,
                )
            },
            cost_seconds=0.01,
        )

    monkeypatch.setattr(env_module.shutil, "which", lambda name: "/tools/uv")
    monkeypatch.setattr(env_module.subprocess, "run", fake_run)
    monkeypatch.setattr(runtime.envs, "installed_packages", lambda: {"lightgbm": "2.0"})
    runtime.kernel.process = _RunningProcess()  # type: ignore[assignment]
    runtime.kernel.client = _OpenClient()  # type: ignore[assignment]
    monkeypatch.setattr(runtime.kernel, "loaded_packages", loaded_packages)
    monkeypatch.setattr(runtime.kernel, "execute", execute)

    result = await runtime.dispatch(
        "env_add",
        {"package": "lightgbm", "actor": "user", "intent": "try lightgbm"},
    )

    assert isinstance(result, dict)
    assert result["restart_required"] is True
    assert result["restart_packages"] == ["lightgbm"]
    assert commands == [
        ["/tools/uv", "add", "lightgbm", "--project", str(store.flow_dir)],
        ["/tools/uv", "sync", "--project", str(store.flow_dir)],
    ]
    transaction = list(store.journal.replay())[-1]
    assert transaction.intent == "try lightgbm"
    assert transaction.ops[0].op == "env_changed"

    status = cast(dict[str, Any], await runtime.dispatch("status", {}))
    cells = {
        cell["uid"]: cell for cell in cast(list[dict[str, Any]], status["cell_status"])
    }
    assert cast(dict[str, Any], status["environment"])["restart_required"] is True
    assert cells[sensitive_uid]["state"] == "unsynced"
    assert cells[sensitive_uid]["causes"] == ["env-changed"]
    assert cells[normal_uid]["state"] == "synced"
    assert cells[sensitive_uid]["computed_under_older_env"] is True

    snapshot = cast(dict[str, Any], await runtime.session_snapshot())
    live_cells = {
        cell["uid"]: cell for cell in cast(list[dict[str, Any]], snapshot["cells"])
    }
    assert live_cells[sensitive_uid]["computed_under_older_env"] is True
    assert live_cells[normal_uid]["computed_under_older_env"] is True

    rerun = cast(dict[str, Any], await runtime.dispatch("run", {"target": "sensitive"}))
    unchanged = cast(
        dict[str, Any], await runtime.dispatch("run", {"target": "normal"})
    )
    assert rerun["executed"] == [sensitive_uid]
    assert unchanged["executed"] == []
    connection = store.index.connection
    assert connection is not None
    memo_keys = {
        str(row[0])
        for row in connection.execute(
            "SELECT memo_key FROM materializations WHERE version_id = ?",
            (sensitive_version,),
        )
    }
    assert len(memo_keys) == 2
    latest = connection.execute(
        """
        SELECT env_lock_hash FROM materializations
        WHERE version_id = ? ORDER BY rowid DESC LIMIT 1
        """,
        (sensitive_version,),
    ).fetchone()
    assert latest["env_lock_hash"] == runtime.envs.live_lock_hash

    runtime.kernel.process = None
    runtime.kernel.client = None
    await runtime.close()


async def test_branch_lock_mismatch_defers_run_unless_forced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _flow_with_environment(tmp_path)
    uid, version_id = _accept_value_cell(store, "train")
    branch = fork(store, "main", "branch-b")
    runtime = DaemonRuntime(store, watch_worktree=False)
    live_lock_hash = runtime.envs.live_lock_hash
    assert live_lock_hash is not None
    await runtime.dispatch("switch", {"branch": branch.name})
    (store.flow_dir / "uv.lock").write_text("version = 2\n", encoding="utf-8")

    async def execute(*_args: object, **_kwargs: object) -> ExecutionResult:
        return ExecutionResult(
            outputs={
                "value": OutputRecord(
                    content_hash="b" * 64,
                    kind="pickle",
                    size=1,
                    persisted=False,
                )
            },
            cost_seconds=0.01,
        )

    monkeypatch.setattr(runtime.kernel, "execute", execute)
    monkeypatch.setattr(runtime.envs, "installed_packages", lambda: {})

    with pytest.raises(DaemonRpcError, match="env mismatch") as mismatch:
        await runtime.dispatch("run", {"target": "train"})
    assert mismatch.value.data == {
        "branch": "branch-b",
        "force_available": True,
    }

    status = cast(dict[str, Any], await runtime.dispatch("env_status", {}))
    assert status["branch_lock_mismatch"] is True
    assert status["background_deferred"] is True

    forced = cast(
        dict[str, Any],
        await runtime.dispatch("run", {"target": "train", "force": True}),
    )
    assert forced["executed"] == [uid]
    connection = store.index.connection
    assert connection is not None
    materialization = connection.execute(
        "SELECT env_lock_hash FROM materializations WHERE version_id = ?",
        (version_id,),
    ).fetchone()
    assert materialization["env_lock_hash"] == live_lock_hash
    flow_status = cast(dict[str, Any], await runtime.dispatch("status", {}))
    cell = cast(list[dict[str, Any]], flow_status["cell_status"])[0]
    assert cell["computed_under_older_env"] is False
    assert flow_status["environment"]["branch_lock_mismatch"] is True
    await runtime.close()


@pytest.mark.parametrize(
    ("method", "uv_command"), (("add", "add"), ("remove", "remove"))
)
async def test_environment_manager_uses_uv_then_sync(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    uv_command: str,
) -> None:
    store = _flow_with_environment(tmp_path)
    manager = EnvironmentManager(store)
    calls: list[str] = []

    def fake_run(command: list[str], **_kwargs: object) -> None:
        calls.append(command[1])
        (store.flow_dir / "uv.lock").write_text(
            f"command = {command[1]}\n", encoding="utf-8"
        )

    monkeypatch.setattr(env_module.shutil, "which", lambda name: "/tools/uv")
    monkeypatch.setattr(env_module.subprocess, "run", fake_run)

    operation = manager.add if method == "add" else manager.remove
    await operation("package", actor="user", intent=None)

    assert calls == [uv_command, "sync"]
    assert list(store.journal.replay())[-1].ops[0].op == "env_changed"
    store.close()
