from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from lumlflow.flow.daemon.api import DaemonRuntime
from lumlflow.flow.daemon.projections import EditConflictError, ProjectionManager
from lumlflow.flow.daemon.reconcile import Reconciler
from lumlflow.flow.daemon.watcher import FlowWatcher
from lumlflow.flow.dsl.accept import accept_cell, compute_lib_tree_hash
from lumlflow.flow.dsl.normalize import read_flow_cells
from lumlflow.flow.hashing import sha256_bytes
from lumlflow.flow.scheduler.memo import memo_key_for
from lumlflow.flow.store.branches import WorktreeLockedError, fork
from lumlflow.flow.store.flowstore import FlowStore


def _source(value: int, class_name: str = "Feature") -> str:
    return f"""class {class_name}:
    produces = {{"value": "asset"}}
    params = {{"value": {value}}}

    def materialize(self, ctx):
        return {{"value": self.params["value"]}}
"""


def _selected(store: FlowStore, slug: str) -> tuple[str, str, str]:
    connection = store.index.connection
    assert connection is not None
    row = connection.execute(
        """
        SELECT selections.version_id, versions.definition_hash, versions.source_hash
        FROM selections JOIN asset_versions AS versions USING(version_id)
        WHERE selections.branch_id = ? AND versions.slug = ?
        """,
        (store.branch_id, slug),
    ).fetchone()
    assert row is not None
    return str(row[0]), str(row[1]), str(row[2])


async def test_run_quiesces_a_write_before_resolving_the_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    path = store.flow_dir / "cells" / "features.py"
    path.write_text(_source(1), encoding="utf-8")
    first = accept_cell(store, path)
    runtime = DaemonRuntime(store)
    updated = path.read_text().replace('"value": 1', '"value": 2')
    path.write_text(updated, encoding="utf-8")

    async def resolved_run(target: str, branch: str | None) -> dict[str, object]:
        assert target == "features"
        assert branch is None
        version_id, _definition, source_hash = _selected(store, "features")
        assert version_id != first.version_id
        assert source_hash == sha256_bytes(path.read_bytes())
        return {"target": target}

    monkeypatch.setattr(runtime, "_run", resolved_run)
    try:
        assert await runtime.dispatch("run", {"target": "features"}) == {
            "target": "features"
        }
    finally:
        await runtime.close()


def test_quiesce_accepts_an_intentional_revert_to_a_known_source(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    path = store.flow_dir / "cells" / "features.py"
    path.write_text(_source(1), encoding="utf-8")
    accept_cell(store, path)
    original = path.read_text(encoding="utf-8")
    path.write_text(original.replace('"value": 1', '"value": 2'), encoding="utf-8")
    accept_cell(store, path)
    path.write_text(original, encoding="utf-8")

    result = Reconciler(store, ProjectionManager(store)).reconcile(
        "quiesce", actor="agent:test"
    )

    assert len(result.accepted) == 1
    assert result.accepted[0].transaction.actor == "agent:test"
    assert _selected(store, "features")[2] == sha256_bytes(path.read_bytes())


def test_cold_start_groups_offline_cell_edits_into_one_transaction(
    tmp_path: Path,
) -> None:
    flow_dir = tmp_path / "flow"
    initial_store = FlowStore.init(flow_dir)
    for index in range(3):
        path = flow_dir / "cells" / f"cell_{index}.py"
        path.write_text(
            _source(index, f"Cell{index}"), encoding="utf-8"
        )
        accept_cell(initial_store, path)
    before_step = initial_store.last_step
    initial_store.close()

    for index in range(3):
        path = flow_dir / "cells" / f"cell_{index}.py"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                f'"value": {index}', f'"value": {index + 10}'
            ),
            encoding="utf-8",
        )
    (flow_dir / "cells" / "cell_3.py").write_text(
        _source(3, "Cell3"), encoding="utf-8"
    )

    store = FlowStore.open(flow_dir)
    runtime = DaemonRuntime(store)

    assert store.last_step == before_step + 1
    transaction = list(store.journal.replay())[-1]
    assert transaction.actor == "user"
    assert transaction.offline is True
    assert transaction.intent == "offline edits: 4 cells changed"
    assert len([op for op in transaction.ops if op.op == "cell_accepted"]) == 4
    assert all(
        'uid = "' in path.read_text() for path in (flow_dir / "cells").glob("*.py")
    )
    runtime.store.close()


async def test_cloned_code_plane_rebuilds_identity_with_fresh_history(
    tmp_path: Path,
) -> None:
    original = FlowStore.init(tmp_path / "original")
    path = original.flow_dir / "cells" / "features.py"
    path.write_text(_source(1), encoding="utf-8")
    accepted = accept_cell(original, path)
    original_flow_id = original.flow_id
    original_memo_key = memo_key_for(
        accepted.definition_hash,
        compute_lib_tree_hash(original.flow_dir),
        {},
    )
    original.close()

    clone_dir = tmp_path / "clone"
    shutil.copytree(
        tmp_path / "original",
        clone_dir,
        ignore=shutil.ignore_patterns(".lumlflow"),
    )

    cloned = FlowStore.open(clone_dir)
    runtime = DaemonRuntime(cloned)
    try:
        _version_id, definition_hash, _source_hash = _selected(cloned, "features")
        transactions = list(cloned.journal.replay())

        assert cloned.flow_id == original_flow_id
        assert definition_hash == accepted.definition_hash
        assert read_flow_cells(clone_dir) == {"features": accepted.uid}
        assert (
            memo_key_for(definition_hash, compute_lib_tree_hash(clone_dir), {})
            == original_memo_key
        )
        assert f'uid = "{accepted.uid}"' in (
            clone_dir / "cells" / "features.py"
        ).read_text(encoding="utf-8")
        assert [operation.op for operation in transactions[0].ops] == ["flow_init"]
        assert transactions[0].intent == "initialize cloned flow"
        assert len(transactions) == 2
        assert transactions[1].offline is True
    finally:
        await runtime.close()


def test_deferred_projection_completes_or_preserves_a_stale_agent_edit(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    path = store.flow_dir / "cells" / "features.py"
    path.write_text(_source(1), encoding="utf-8")
    first = accept_cell(store, path)
    projections = ProjectionManager(store)
    reconciler = Reconciler(store, projections)
    original = path.read_text()

    projections.agent_begin("agent:test")
    ui = projections.edit_cell(
        "features",
        _source(2),
        base_definition_hash=first.definition_hash,
        actor="user:ui",
    )
    assert path.read_text() == original
    assert projections.pending_for_slug("features") is not None

    path.write_text(original.replace('"value": 1', '"value": 3'), encoding="utf-8")
    result = reconciler.reconcile("quiesce", actor="agent:test")

    assert len(result.accepted) == 1
    assert result.accepted[0].selected is False
    assert "divergent" in result.accepted[0].flags
    assert _selected(store, "features")[0] == ui.version_id
    projections.agent_end("agent:test")
    assert projections.flush_pending() == []
    assert '"value": 3' in path.read_text()

    second_store = FlowStore.init(tmp_path / "flow-completes")
    second_path = second_store.flow_dir / "cells" / "features.py"
    second_path.write_text(_source(1), encoding="utf-8")
    base = accept_cell(second_store, second_path)
    second_projections = ProjectionManager(second_store)
    second_projections.agent_begin("agent:test")
    accepted = second_projections.edit_cell(
        "features",
        _source(2),
        base_definition_hash=base.definition_hash,
        actor="user:ui",
    )
    second_projections.agent_end("agent:test")

    assert second_projections.flush_pending() == ["features"]
    assert second_path.read_bytes() == second_store.cas.get(
        "objects", _selected(second_store, "features")[2]
    )
    assert _selected(second_store, "features")[0] == accepted.version_id


def test_daemon_restart_completes_a_pending_projection_without_reaccepting(
    tmp_path: Path,
) -> None:
    flow_dir = tmp_path / "flow"
    store = FlowStore.init(flow_dir)
    path = flow_dir / "cells" / "features.py"
    path.write_text(_source(1), encoding="utf-8")
    base = accept_cell(store, path)
    projections = ProjectionManager(store)
    projections.agent_begin("agent:test")
    accepted = projections.edit_cell(
        "features",
        _source(2),
        base_definition_hash=base.definition_hash,
        actor="user:ui",
    )
    connection = store.index.connection
    assert connection is not None
    version_count = int(
        connection.execute("SELECT COUNT(*) FROM asset_versions").fetchone()[0]
    )
    store.close()

    runtime = DaemonRuntime(FlowStore.open(flow_dir))
    reopened_connection = runtime.store.index.connection
    assert reopened_connection is not None

    assert runtime.projections.lock_holder is None
    assert runtime.projections.pending() == []
    assert _selected(runtime.store, "features")[0] == accepted.version_id
    assert path.read_bytes() == runtime.store.cas.get(
        "objects", _selected(runtime.store, "features")[2]
    )
    assert (
        reopened_connection.execute("SELECT COUNT(*) FROM asset_versions").fetchone()[0]
        == version_count
    )
    runtime.store.close()


def test_daemon_edit_uses_optimistic_locking_without_writing_a_version(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    path = store.flow_dir / "cells" / "features.py"
    path.write_text(_source(1), encoding="utf-8")
    first = accept_cell(store, path)
    path.write_text(path.read_text().replace('"value": 1', '"value": 2'))
    second = accept_cell(store, path)
    projections = ProjectionManager(store)
    connection = store.index.connection
    assert connection is not None
    before = int(
        connection.execute("SELECT COUNT(*) FROM asset_versions").fetchone()[0]
    )

    with pytest.raises(EditConflictError) as conflict:
        projections.edit_cell(
            "features",
            _source(3),
            base_definition_hash=first.definition_hash,
        )

    assert conflict.value.current_definition_hash == second.definition_hash
    assert conflict.value.menu[0] == {
        "action": "fork-my-edit",
        "suggested": True,
    }
    count = connection.execute("SELECT COUNT(*) FROM asset_versions").fetchone()[0]
    assert count == before


async def test_headless_cell_edits_do_not_materialize_a_worktree(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    runtime = DaemonRuntime(store, watch_worktree=False)
    try:
        created = await runtime.dispatch(
            "cells_new",
            {"source": _source(1, "TrainModel"), "actor": "agent:mcp"},
        )
        assert isinstance(created, dict)
        assert created["slug"] == "untitled_1"
        assert created["suggested_slug"] == "train_model"
        assert not list((store.flow_dir / "cells").glob("*.py"))

        edited = await runtime.dispatch(
            "cells_edit",
            {
                "slug": "untitled_1",
                "source": _source(2, "TrainModel"),
                "base_definition_hash": created["definition_hash"],
                "actor": "agent:mcp",
            },
        )
        assert isinstance(edited, dict)
        assert edited["selected"] is True
        assert not list((store.flow_dir / "cells").glob("*.py"))
        assert all(
            transaction.actor == "agent:mcp"
            for transaction in list(store.journal.replay())[1:]
        )
    finally:
        await runtime.close()


def test_watcher_ignores_workspace_files_and_flags_mixed_editing(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    projections = ProjectionManager(store)
    watcher = FlowWatcher(Reconciler(store, projections))
    workspace = store.flow_dir / "data.csv"
    workspace.write_text("ignored", encoding="utf-8")
    first = store.flow_dir / "cells" / "first.py"
    second = store.flow_dir / "cells" / "second.py"
    first.write_text(_source(1, "First"), encoding="utf-8")
    second.write_text(_source(2, "Second"), encoding="utf-8")

    watcher.notify(workspace, "agent:a")
    watcher.notify(first, "agent:a")
    watcher.notify(second, "agent:b")
    result = watcher.flush()

    assert len(result.accepted) == 2
    assert all("mixed_editing" in accepted.flags for accepted in result.accepted)
    transaction = list(store.journal.replay())[-1]
    assert transaction.actor == "user"
    manifests = (
        [
            json.loads(row[0])
            for row in store.index.connection.execute(
                "SELECT manifest FROM asset_versions"
            )
        ]
        if store.index.connection is not None
        else []
    )
    assert all("mixed_editing" in manifest["flags"] for manifest in manifests)


def test_switch_projects_only_the_branch_slice_and_honors_the_worktree_lock(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    path = store.flow_dir / "cells" / "features.py"
    workspace = store.flow_dir / "notes.txt"
    path.write_text(_source(1), encoding="utf-8")
    main = accept_cell(store, path)
    child = fork(store, "main", "child")
    path.write_text(path.read_text().replace('"value": 1', '"value": 2'))
    child_version = accept_cell(store, path, branch=child.branch_id)
    projections = ProjectionManager(store)

    projections.switch("child")
    workspace.write_text("keep me", encoding="utf-8")
    projections.agent_begin("agent:test")
    with pytest.raises(WorktreeLockedError):
        projections.switch("main")
    projections.agent_end("agent:test")
    projections.switch("main")

    assert _selected(store, "features")[0] == main.version_id
    assert path.read_bytes() == store.cas.get(
        "objects", _selected(store, "features")[2]
    )
    assert workspace.read_text() == "keep me"
    assert child_version.version_id != main.version_id


def test_agent_bracket_groups_observed_edits_into_one_transaction(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    projections = ProjectionManager(store)
    watcher = FlowWatcher(Reconciler(store, projections))
    first = store.flow_dir / "cells" / "first.py"
    second = store.flow_dir / "cells" / "second.py"
    first.write_text(_source(1, "First"), encoding="utf-8")
    second.write_text(_source(2, "Second"), encoding="utf-8")

    projections.agent_begin("agent:test")
    watcher.begin("agent:test", intent="build two cells")
    watcher.notify(first)
    watcher.notify(second)
    result = watcher.end("agent:test")
    projections.agent_end("agent:test")

    assert len(result.accepted) == 2
    assert {item.transaction.step for item in result.accepted} == {
        result.accepted[0].transaction.step
    }
    assert result.accepted[0].transaction.actor == "agent:test"
    assert result.accepted[0].transaction.intent == "build two cells"
