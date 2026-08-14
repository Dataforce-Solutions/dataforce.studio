import asyncio
from pathlib import Path
from typing import cast

import pytest
from lumlflow.flow.hashing import sha256_bytes
from lumlflow.flow.ids import mint_ulid
from lumlflow.flow.scheduler.memo import find_memo_hit, memo_key_for
from lumlflow.flow.scheduler.planner import (
    ExecutionResult,
    Planner,
    PlanNode,
    Scheduler,
)
from lumlflow.flow.scheduler.queue import SerialPriorityQueue
from lumlflow.flow.scheduler.staleness import derive_staleness
from lumlflow.flow.store.branches import baselines, fork
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import (
    CellAcceptedOp,
    InputRecord,
    JsonValue,
    OutputRecord,
    RunRecordedOp,
    SelectionSetOp,
)


def _output(value: str) -> OutputRecord:
    return OutputRecord(
        content_hash=sha256_bytes(value.encode()),
        kind="pickle",
        size=len(value),
        persisted=True,
    )


def _accept(
    store: FlowStore,
    uid: str,
    slug: str,
    *,
    definition: str,
    produces: tuple[str, ...] = ("value",),
    consumes: dict[str, tuple[str, str]] | None = None,
    branch: str | None = None,
    volatility: str = "pure",
    env_sensitive: bool = False,
) -> str:
    version_id = mint_ulid()
    bound_inputs = {
        name: f"uid:{parent_uid}.{output}"
        for name, (parent_uid, output) in (consumes or {}).items()
    }
    manifest: dict[str, JsonValue] = {
        "bound_inputs": cast(JsonValue, bound_inputs),
        "consumes": cast(JsonValue, bound_inputs),
        "produces": {name: "asset" for name in produces},
        "volatility": volatility,
        "env_sensitive": env_sensitive,
    }
    store.commit(
        actor="agent:test",
        intent=f"accept {slug}",
        branch=branch,
        ops=[
            CellAcceptedOp(
                uid=uid,
                version_id=version_id,
                slug=slug,
                source_hash="a" * 64,
                bound_hash="b" * 64,
                definition_hash=definition,
                manifest=manifest,
            ),
            SelectionSetOp(uid=uid, version_id=version_id),
        ],
    )
    return version_id


def _materialize(
    store: FlowStore,
    version_id: str,
    outputs: dict[str, str],
    *,
    inputs: dict[str, InputRecord] | None = None,
    branch: str | None = None,
    key: str = "initial",
    cost: float = 1.0,
    identity_dependent: bool = False,
) -> str:
    mat_id = mint_ulid()
    store.commit(
        actor="agent:test",
        intent="seed materialization",
        branch=branch,
        ops=[
            RunRecordedOp(
                mat_id=mat_id,
                version_id=version_id,
                memo_key=key,
                state="succeeded",
                inputs=inputs or {},
                outputs={name: _output(value) for name, value in outputs.items()},
                identity_dependent=identity_dependent,
                cost_seconds=cost,
            )
        ],
    )
    return mat_id


def _input(uid: str, output: str, value: str, mat_id: str) -> InputRecord:
    return InputRecord(
        uid=uid,
        output=output,
        content_hash=_output(value).content_hash,
        mat_id=mat_id,
    )


def test_unmaterialized_is_distinct_in_both_views(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    uid = mint_ulid()
    _accept(store, uid, "new_cell", definition="1" * 64)

    views = derive_staleness(store, "main", uid)

    assert views.direct.state == "unmaterialized"
    assert views.transitive.state == "unmaterialized"


def test_direct_and_transitive_staleness_include_named_lib_causes(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    parent_uid = mint_ulid()
    parent_v1 = _accept(store, parent_uid, "features", definition="1" * 64)
    parent_mat = _materialize(store, parent_v1, {"value": "old"})
    child_uid = mint_ulid()
    child_version = _accept(
        store,
        child_uid,
        "train",
        definition="2" * 64,
        consumes={"data": (parent_uid, "value")},
    )
    _materialize(
        store,
        child_version,
        {"value": "model"},
        inputs={"data": _input(parent_uid, "value", "old", parent_mat)},
    )
    _accept(store, parent_uid, "features", definition="3" * 64)

    parent = derive_staleness(
        store, "main", parent_uid, lib_changed_files=["lib/features.py"]
    )
    child = derive_staleness(store, "main", child_uid)

    assert parent.direct.causes == (
        "definition-changed",
        "lib-changed(lib/features.py)",
    )
    assert child.direct.state == "synced"
    assert child.transitive.state == "unsynced"
    assert child.transitive.causes == ("definition-changed",)


def test_editing_on_a_fork_marks_only_that_branch_unsynced(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    producer_uid = mint_ulid()
    producer_version = _accept(store, producer_uid, "features", definition="1" * 64)
    producer_mat = _materialize(store, producer_version, {"value": "features"})
    consumer_uid = mint_ulid()
    consumer_version = _accept(
        store,
        consumer_uid,
        "train",
        definition="2" * 64,
        consumes={"data": (producer_uid, "value")},
    )
    _materialize(
        store,
        consumer_version,
        {"value": "model"},
        inputs={"data": _input(producer_uid, "value", "features", producer_mat)},
    )
    child = fork(store, "main", "experiment")

    _accept(
        store,
        producer_uid,
        "features",
        definition="3" * 64,
        branch=child.branch_id,
    )

    assert derive_staleness(store, child.branch_id, producer_uid).direct.state == (
        "unsynced"
    )
    assert derive_staleness(store, child.branch_id, consumer_uid).transitive.state == (
        "unsynced"
    )
    assert derive_staleness(store, "main", producer_uid).direct.state == "synced"
    assert derive_staleness(store, "main", consumer_uid).transitive.state == "synced"


def test_named_memo_map_and_environment_sensitivity() -> None:
    first = memo_key_for("d", "l", {"train": "a", "test": "b"})
    swapped = memo_key_for("d", "l", {"train": "b", "test": "a"})

    assert first != swapped
    assert memo_key_for("d", "l", {"x": "a"}) == memo_key_for(
        "d", "l", {"x": "a"}, env_sensitive=False, env_lock_hash="ignored"
    )
    assert memo_key_for(
        "d", "l", {"x": "a"}, env_sensitive=True, env_lock_hash="one"
    ) != memo_key_for("d", "l", {"x": "a"}, env_sensitive=True, env_lock_hash="two")
    with pytest.raises(ValueError, match="lock hash"):
        memo_key_for("d", "l", {}, env_sensitive=True)


def test_early_cutoff_is_per_output_with_a_stub_executor(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    producer_uid = mint_ulid()
    producer_v1 = _accept(
        store,
        producer_uid,
        "train_model",
        definition="1" * 64,
        produces=("run", "checkpoint"),
    )
    producer_mat = _materialize(
        store, producer_v1, {"run": "run-old", "checkpoint": "checkpoint"}
    )
    run_uid = mint_ulid()
    run_version = _accept(
        store,
        run_uid,
        "publish_run",
        definition="2" * 64,
        consumes={"run": (producer_uid, "run")},
    )
    run_mat = _materialize(
        store,
        run_version,
        {"value": "published-old"},
        inputs={"run": _input(producer_uid, "run", "run-old", producer_mat)},
    )
    checkpoint_uid = mint_ulid()
    checkpoint_version = _accept(
        store,
        checkpoint_uid,
        "archive_checkpoint",
        definition="3" * 64,
        consumes={"checkpoint": (producer_uid, "checkpoint")},
    )
    checkpoint_mat = _materialize(
        store,
        checkpoint_version,
        {"value": "archived"},
        inputs={
            "checkpoint": _input(producer_uid, "checkpoint", "checkpoint", producer_mat)
        },
    )
    final_uid = mint_ulid()
    final_version = _accept(
        store,
        final_uid,
        "report",
        definition="4" * 64,
        consumes={
            "run": (run_uid, "value"),
            "checkpoint": (checkpoint_uid, "value"),
        },
    )
    _materialize(
        store,
        final_version,
        {"value": "report-old"},
        inputs={
            "run": _input(run_uid, "value", "published-old", run_mat),
            "checkpoint": _input(checkpoint_uid, "value", "archived", checkpoint_mat),
        },
    )
    _accept(
        store,
        producer_uid,
        "train_model",
        definition="5" * 64,
        produces=("run", "checkpoint"),
    )
    calls: list[str] = []

    async def execute(
        node: PlanNode, _inputs: dict[str, InputRecord]
    ) -> ExecutionResult:
        calls.append(node.slug)
        values = {
            "train_model": {"run": "run-new", "checkpoint": "checkpoint"},
            "publish_run": {"value": "published-new"},
            "report": {"value": "report-new"},
        }[node.slug]
        return ExecutionResult(
            outputs={name: _output(value) for name, value in values.items()},
            cost_seconds=0.1,
        )

    summary = asyncio.run(
        Scheduler(store, execute, lib_tree_hash="lib").run("main", final_uid)
    )

    assert calls == ["train_model", "publish_run", "report"]
    assert summary.pruned == (checkpoint_uid,)


def test_cross_branch_hit_is_journaled_and_identity_fact_blocks_it(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    reusable_uid = mint_ulid()
    reusable_version = _accept(store, reusable_uid, "features", definition="1" * 64)
    key = memo_key_for("1" * 64, "lib", {})
    reusable_mat = _materialize(store, reusable_version, {"value": "features"}, key=key)
    identity_uid = mint_ulid()
    identity_version = _accept(store, identity_uid, "export", definition="2" * 64)
    identity_key = memo_key_for("2" * 64, "lib", {})
    _materialize(
        store,
        identity_version,
        {"value": "main/export"},
        key=identity_key,
        identity_dependent=True,
    )
    reusable_current = _accept(store, reusable_uid, "features", definition="3" * 64)
    _materialize(
        store,
        reusable_current,
        {"value": "changed-features"},
        key=memo_key_for("3" * 64, "lib", {}),
    )
    identity_current = _accept(store, identity_uid, "export", definition="4" * 64)
    _materialize(
        store,
        identity_current,
        {"value": "main/current-export"},
        key=memo_key_for("4" * 64, "lib", {}),
        identity_dependent=True,
    )
    child = fork(store, "main", "branch-b")
    store.commit(
        actor="agent:test",
        intent="select prior definitions on branch",
        branch=child.branch_id,
        ops=[
            SelectionSetOp(uid=reusable_uid, version_id=reusable_version),
            SelectionSetOp(uid=identity_uid, version_id=identity_version),
        ],
    )
    calls: list[str] = []

    async def execute(
        node: PlanNode, _inputs: dict[str, InputRecord]
    ) -> ExecutionResult:
        calls.append(node.slug)
        return ExecutionResult(
            outputs={"value": _output("branch-b/export")},
            cost_seconds=0.1,
            identity_dependent=True,
        )

    scheduler = Scheduler(store, execute, lib_tree_hash="lib")
    reusable_summary = asyncio.run(scheduler.run(child.branch_id, reusable_uid))
    identity_summary = asyncio.run(scheduler.run(child.branch_id, identity_uid))

    assert reusable_summary.memo_hits == (reusable_uid,)
    assert identity_summary.executed == (identity_uid,)
    assert calls == ["export"]
    assert find_memo_hit(store, child.branch_id, identity_key) is not None
    assert {item.uid: item.mat_id for item in baselines(store, child.branch_id)}[
        reusable_uid
    ] == reusable_mat
    assert list(store.journal.replay())[-2].ops[0].op == "memo_hit"


def test_failed_run_is_derived_and_rebuilt_as_failed(tmp_path: Path) -> None:
    flow_dir = tmp_path / "flow"
    store = FlowStore.init(flow_dir)
    uid = mint_ulid()
    version = _accept(store, uid, "broken", definition="1" * 64)

    class FailedRun(RuntimeError):
        log_ref = "failure-log"

    async def execute(
        _node: PlanNode, _inputs: dict[str, InputRecord]
    ) -> ExecutionResult:
        raise FailedRun("boom")

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(Scheduler(store, execute, lib_tree_hash="lib").run("main", uid))

    assert derive_staleness(store, "main", uid).direct.state == "failed"
    connection = store.index.connection
    assert connection is not None
    assert (
        connection.execute(
            "SELECT log_ref FROM materializations WHERE version_id = ?", (version,)
        ).fetchone()["log_ref"]
        == "failure-log"
    )
    store.close()
    (flow_dir / ".lumlflow" / "store.sqlite").unlink()
    reopened = FlowStore.open(flow_dir)
    assert derive_staleness(reopened, "main", uid).direct.state == "failed"


def test_nondeterministic_and_external_materializations_never_hit(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    uid = mint_ulid()
    version = _accept(store, uid, "sample", definition="1" * 64)
    _materialize(store, version, {"value": "x"}, key="same")

    assert find_memo_hit(store, "main", "same", volatility="nondeterministic") is None
    assert find_memo_hit(store, "main", "same", volatility="external") is None


def test_lazy_default_and_eager_candidates_use_recorded_cost(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    features_uid = mint_ulid()
    features_version = _accept(store, features_uid, "features", definition="1" * 64)
    features_mat = _materialize(store, features_version, {"value": "features"})
    plot_uid = mint_ulid()
    plot_version = _accept(
        store,
        plot_uid,
        "plot",
        definition="2" * 64,
        consumes={"data": (features_uid, "value")},
    )
    _materialize(
        store,
        plot_version,
        {"value": "plot"},
        inputs={"data": _input(features_uid, "value", "features", features_mat)},
        cost=0.2,
    )
    train_uid = mint_ulid()
    train_version = _accept(
        store,
        train_uid,
        "train",
        definition="3" * 64,
        consumes={"data": (features_uid, "value")},
    )
    _materialize(
        store,
        train_version,
        {"value": "model"},
        inputs={"data": _input(features_uid, "value", "features", features_mat)},
        cost=600,
    )
    _accept(store, features_uid, "features", definition="4" * 64)

    candidates = Planner(store).eager_candidates("main", [features_uid])

    assert candidates == [plot_uid]
    assert derive_staleness(store, "main", train_uid).transitive.state == "unsynced"
    assert len(list(store.journal.replay())) == store.last_step


def test_in_flight_requests_coalesce_across_a_mid_run_fork(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = FlowStore.init(tmp_path / "flow")
        uid = mint_ulid()
        _accept(store, uid, "train", definition="1" * 64)
        started = asyncio.Event()
        release = asyncio.Event()
        calls = 0

        async def execute(
            _node: PlanNode, _inputs: dict[str, InputRecord]
        ) -> ExecutionResult:
            nonlocal calls
            calls += 1
            started.set()
            await release.wait()
            return ExecutionResult(outputs={"value": _output("model")}, cost_seconds=1)

        scheduler = Scheduler(store, execute, lib_tree_hash="lib")
        main_run = asyncio.create_task(scheduler.run("main", uid))
        await started.wait()
        child = fork(store, "main", "branch-b")
        child_run = asyncio.create_task(scheduler.run(child.branch_id, uid))
        await asyncio.sleep(0)
        release.set()
        main_summary, child_summary = await asyncio.gather(main_run, child_run)

        assert calls == 1
        assert main_summary.executed == (uid,)
        assert child_summary.memo_hits == (uid,)
        assert {item.uid for item in baselines(store, child.branch_id)} == {uid}

    asyncio.run(scenario())


def test_serial_queue_prioritizes_active_branch_and_protects_awaited_work() -> None:
    async def scenario() -> None:
        queue: SerialPriorityQueue[str] = SerialPriorityQueue(active_branch="main")
        release = asyncio.Event()
        order: list[str] = []

        async def work(name: str, wait: bool = False) -> str:
            order.append(name)
            if wait:
                await release.wait()
            return name

        first = asyncio.create_task(
            queue.run("first", "other", lambda: work("first", True))
        )
        await asyncio.sleep(0)
        other = asyncio.create_task(queue.run("other", "other", lambda: work("other")))
        active = asyncio.create_task(
            queue.run("active", "main", lambda: work("active"))
        )
        await asyncio.sleep(0)
        assert queue.request_preemption("first") is False
        release.set()
        assert await asyncio.gather(first, other, active) == [
            "first",
            "other",
            "active",
        ]
        assert order == ["first", "active", "other"]

    asyncio.run(scenario())
