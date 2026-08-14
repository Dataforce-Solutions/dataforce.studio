from pathlib import Path
from typing import cast

import pytest
from lumlflow.flow.hashing import sha256_bytes
from lumlflow.flow.ids import mint_ulid
from lumlflow.flow.store.branches import (
    AdoptConflictError,
    NamespaceConflictError,
    adopt,
    archive,
    baselines,
    fork,
    get_branch,
    preflight,
    rename_branch,
    rewind,
    selections,
    switch,
)
from lumlflow.flow.store.flowstore import CASWrite, FlowStore
from lumlflow.flow.store.models import (
    CellAcceptedOp,
    InputRecord,
    JsonValue,
    OutputRecord,
    RunRecordedOp,
    SelectionSetOp,
)


def _accept(
    store: FlowStore,
    uid: str,
    slug: str,
    definition: str,
    *,
    branch: str | None = None,
    volatility: str = "pure",
    bindings: dict[str, str] | None = None,
) -> str:
    version_id = mint_ulid()
    source = f"class {slug.title()}: pass\n".encode()
    manifest: dict[str, JsonValue] = {
        "consumes": {},
        "produces": {"value": "asset"},
        "volatility": volatility,
    }
    if bindings is not None:
        manifest["bindings"] = cast(JsonValue, bindings)
    store.commit(
        actor="agent:test",
        intent=f"accept {slug}",
        branch=branch,
        ops=[
            CellAcceptedOp(
                uid=uid,
                version_id=version_id,
                slug=slug,
                source_hash=sha256_bytes(source),
                bound_hash="b" * 64,
                definition_hash=definition,
                manifest=manifest,
            ),
            SelectionSetOp(uid=uid, version_id=version_id),
        ],
        blobs=[CASWrite("objects", source)],
    )
    return version_id


def _materialize(
    store: FlowStore,
    version_id: str,
    payload: bytes,
    *,
    branch: str | None = None,
    cost: float = 1.0,
    inputs: dict[str, InputRecord] | None = None,
) -> tuple[str, str]:
    mat_id = mint_ulid()
    content_hash = sha256_bytes(payload)
    store.commit(
        actor="agent:test",
        intent="run cell",
        branch=branch,
        ops=[
            RunRecordedOp(
                mat_id=mat_id,
                version_id=version_id,
                memo_key="memo",
                state="succeeded",
                inputs=inputs or {},
                outputs={
                    "value": OutputRecord(
                        content_hash=content_hash,
                        value_ref=content_hash,
                        kind="pickle",
                        size=len(payload),
                        persisted=True,
                    )
                },
                cost_seconds=cost,
            )
        ],
        blobs=[CASWrite("values", payload)],
    )
    return mat_id, content_hash


def test_fork_dense_copies_rows_without_copying_values(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    expected_baselines: dict[str, str] = {}
    for index in range(4):
        uid = mint_ulid()
        version = _accept(store, uid, f"cell_{index}", str(index) * 64)
        mat_id, _content_hash = _materialize(store, version, f"value-{index}".encode())
        expected_baselines[uid] = mat_id
    values_size = sum(
        path.stat().st_size for path in (store.store_dir / "values").glob("*/*")
    )

    child = fork(store, "main", "sweep/lr3")

    child_selections = selections(store, child.branch_id)
    assert len(child_selections) == 4
    assert all(selection.pinned for selection in child_selections)
    assert {item.uid: item.mat_id for item in baselines(store, child.branch_id)} == (
        expected_baselines
    )
    assert (
        sum(path.stat().st_size for path in (store.store_dir / "values").glob("*/*"))
        == values_size
    )


def test_fork_from_historical_step_and_branch_rename_survive_rebuild(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    uid = mint_ulid()
    first_version = _accept(store, uid, "features", "1" * 64)
    fork_step = store.last_step
    _accept(store, uid, "features", "2" * 64)

    child = fork(store, "main", "experiment", fork_step=fork_step)
    rename_branch(
        store,
        child.branch_id,
        "candidate",
        actor="user:ui",
        intent="rename experiment to candidate",
    )

    assert selections(store, child.branch_id)[0].version_id == first_version
    assert get_branch(store, "candidate").branch_id == child.branch_id
    rename_transaction = list(store.journal.replay())[-1]
    assert rename_transaction.actor == "user:ui"
    assert rename_transaction.ops[0].op == "branch_renamed"

    store.close()
    (tmp_path / "flow" / ".lumlflow" / "store.sqlite").unlink()
    reopened = FlowStore.open(tmp_path / "flow")

    assert selections(reopened, "candidate")[0].version_id == first_version
    assert get_branch(reopened, "candidate").branch_id == child.branch_id


def test_selection_change_on_fork_does_not_touch_parent(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    uid = mint_ulid()
    parent_version = _accept(store, uid, "features", "1" * 64)
    child = fork(store, "main", "experiment")

    child_version = _accept(store, uid, "features", "2" * 64, branch=child.branch_id)

    assert selections(store, "main")[0].version_id == parent_version
    assert selections(store, child.branch_id)[0].version_id == child_version


def test_switch_only_rebinds_worktree_and_archive_keeps_branch(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    child = fork(store, "main", "experiment")
    cells_before = list((store.flow_dir / "cells").iterdir())

    switch(store, child.name)
    archive(store, child.name)

    connection = store.index.connection
    assert connection is not None
    bound = connection.execute(
        "SELECT branch_id FROM worktrees WHERE path = ?",
        (str(store.flow_dir.resolve()),),
    ).fetchone()
    assert bound[0] == child.branch_id
    assert list((store.flow_dir / "cells").iterdir()) == cells_before
    assert get_branch(store, child.name).archived
    store.close()
    assert FlowStore.open(tmp_path / "flow").branch_id == child.branch_id


def test_rewind_restores_selection_and_baseline_and_survives_rebuild(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    uid = mint_ulid()
    first_version = _accept(store, uid, "train", "1" * 64)
    first_mat, first_hash = _materialize(store, first_version, b"first", cost=2.5)
    leaf_uid = mint_ulid()
    first_leaf_version = _accept(store, leaf_uid, "evaluate", "a" * 64)
    first_leaf_mat, _first_leaf_hash = _materialize(
        store, first_leaf_version, b"metrics", cost=600
    )
    unmaterialized_leaf = _accept(store, leaf_uid, "evaluate", "b" * 64)
    target_step = store.last_step
    assert list(store.journal.replay())[-1].settled is False
    second_version = _accept(store, uid, "train", "2" * 64)
    second_mat, _second_hash = _materialize(store, second_version, b"second")
    current_baselines = {item.uid: item.mat_id for item in baselines(store, "main")}
    assert current_baselines[uid] == second_mat

    store.cas.path_for("values", first_hash).unlink()
    report = preflight(store, "main", target_step)
    assert report.recompute == [("train", 2.5), ("evaluate", 600.0)]
    assert report.irrecoverable == []
    rewind(store, "main", target_step)

    rewound_selections = {
        item.uid: item.version_id for item in selections(store, "main")
    }
    rewound_baselines = {item.uid: item.mat_id for item in baselines(store, "main")}
    assert rewound_selections == {
        uid: first_version,
        leaf_uid: unmaterialized_leaf,
    }
    assert rewound_baselines == {uid: first_mat, leaf_uid: first_leaf_mat}
    store.close()
    (tmp_path / "flow" / ".lumlflow" / "store.sqlite").unlink()
    reopened = FlowStore.open(tmp_path / "flow")
    assert {item.uid: item.version_id for item in selections(reopened, "main")} == {
        uid: first_version,
        leaf_uid: unmaterialized_leaf,
    }
    assert {item.uid: item.mat_id for item in baselines(reopened, "main")} == {
        uid: first_mat,
        leaf_uid: first_leaf_mat,
    }


def test_preflight_recomputes_when_baseline_consumed_an_old_input(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    producer_uid = mint_ulid()
    producer_version = _accept(store, producer_uid, "features", "f" * 64)
    first_producer_mat, first_hash = _materialize(
        store, producer_version, b"first features"
    )
    consumer_uid = mint_ulid()
    consumer_version = _accept(store, consumer_uid, "train", "t" * 64)
    _consumer_mat, _consumer_hash = _materialize(
        store,
        consumer_version,
        b"model",
        cost=42,
        inputs={
            "data": InputRecord(
                uid=producer_uid,
                output="value",
                content_hash=first_hash,
                mat_id=first_producer_mat,
            )
        },
    )
    _second_producer_mat, _second_hash = _materialize(
        store, producer_version, b"second features"
    )

    report = preflight(store, "main", store.last_step)

    assert report.recompute == [("train", 42.0)]


def test_preflight_reports_lost_nondeterministic_value_as_irrecoverable(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    uid = mint_ulid()
    version = _accept(store, uid, "sample", "d" * 64, volatility="nondeterministic")
    _mat_id, content_hash = _materialize(store, version, b"sample")
    target_step = store.last_step
    store.cas.path_for("values", content_hash).unlink()

    report = preflight(store, "main", target_step)

    assert report.recompute == []
    assert report.irrecoverable == ["sample"]


def test_adopt_detects_three_way_conflicts_and_accepts_one_sided_edit(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    uid = mint_ulid()
    _base = _accept(store, uid, "train", "0" * 64)
    sweep = fork(store, "main", "sweep")
    incoming = _accept(store, uid, "train", "1" * 64, branch=sweep.branch_id)

    adopted = adopt(
        store,
        "main",
        uid,
        incoming,
        from_branch=sweep.branch_id,
    )

    assert adopted is not None and adopted.ops[0].op == "adopted"
    assert selections(store, "main")[0].version_id == incoming

    other = fork(store, "main", "other")
    incoming_other = _accept(store, uid, "train", "2" * 64, branch=other.branch_id)
    _target = _accept(store, uid, "train", "3" * 64, branch=store.branch_id)
    with pytest.raises(AdoptConflictError):
        adopt(
            store,
            "main",
            uid,
            incoming_other,
            from_branch=other.branch_id,
        )


def test_adopt_surfaces_namespace_conflict_before_commit(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    producer_uid = mint_ulid()
    _producer = _accept(store, producer_uid, "features", "f" * 64)
    consumer_uid = mint_ulid()
    _consumer = _accept(store, consumer_uid, "train", "0" * 64)
    source = fork(store, "main", "source")
    incoming = _accept(
        store,
        consumer_uid,
        "train",
        "1" * 64,
        branch=source.branch_id,
        bindings={"features.data": f"uid:{mint_ulid()}.data"},
    )

    with pytest.raises(NamespaceConflictError, match="features"):
        adopt(
            store,
            "main",
            consumer_uid,
            incoming,
            from_branch=source.branch_id,
        )


def test_settled_is_computed_from_the_whole_branch_slice(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    uid = mint_ulid()
    version = _accept(store, uid, "train", "d" * 64)
    assert list(store.journal.replay())[-1].settled is False

    _materialize(store, version, b"model")

    assert list(store.journal.replay())[-1].settled is True
