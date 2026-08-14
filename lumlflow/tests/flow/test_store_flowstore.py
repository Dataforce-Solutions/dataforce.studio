import sqlite3
from pathlib import Path

import pytest
from lumlflow.flow.hashing import sha256_bytes
from lumlflow.flow.ids import mint_ulid
from lumlflow.flow.store.flowstore import (
    CASWrite,
    CloudSyncFolderWarning,
    CommitStage,
    FlowStore,
    is_cloud_sync_path,
)
from lumlflow.flow.store.models import CellAcceptedOp, SelectionSetOp


def _accepted_cell(source_hash: str) -> CellAcceptedOp:
    return CellAcceptedOp(
        uid=mint_ulid(),
        version_id=mint_ulid(),
        slug="train",
        source_hash=source_hash,
        bound_hash="b" * 64,
        definition_hash="d" * 64,
        manifest={"consumes": {}, "produces": {"model": "model"}},
        flags=[],
    )


def test_init_scaffolds_flow_and_gitignore(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    flow_dir = tmp_path / "churn.flow"

    store = FlowStore.init(flow_dir)

    assert 'name: "churn"' in (flow_dir / "flow.yaml").read_text()
    assert (flow_dir / "cells").is_dir()
    assert (flow_dir / "lib").is_dir()
    assert (flow_dir / ".gitignore").read_text() == ".lumlflow/\n"
    assert store.last_step == 1
    assert list(store.journal.replay())[0].ops[0].op == "flow_init"


def test_cloud_sync_detection_handles_windows_and_posix_paths(tmp_path: Path) -> None:
    assert is_cloud_sync_path(r"C:\\Users\\Ada\\OneDrive\\project.flow")
    assert is_cloud_sync_path("/Users/ada/Library/Mobile Documents/project.flow")
    with pytest.warns(CloudSyncFolderWarning):
        FlowStore.init(tmp_path / "Dropbox" / "project.flow")


def test_cas_write_precedes_journal_commit(tmp_path: Path) -> None:
    flow_dir = tmp_path / "flow"
    store = FlowStore.init(flow_dir)
    payload = b"source"
    cell = _accepted_cell(sha256_bytes(payload))

    def crash(stage: CommitStage) -> None:
        if stage == "after_cas":
            raise RuntimeError("simulated crash")

    store._crash_hook = crash
    with pytest.raises(RuntimeError, match="simulated crash"):
        store.commit(
            actor="agent:test",
            intent="accept cell",
            ops=[cell],
            blobs=[CASWrite("objects", payload)],
        )

    assert store.cas.get("objects", cell.source_hash) == payload
    assert store.journal.last_step() == 1


def test_open_rebuilds_index_after_post_journal_crash(tmp_path: Path) -> None:
    flow_dir = tmp_path / "flow"
    store = FlowStore.init(flow_dir)
    payload = b"source"
    cell = _accepted_cell(sha256_bytes(payload))

    def crash(stage: CommitStage) -> None:
        if stage == "after_journal":
            raise RuntimeError("simulated crash")

    store._crash_hook = crash
    with pytest.raises(RuntimeError, match="simulated crash"):
        store.commit(
            actor="agent:test",
            intent="accept cell",
            ops=[cell, SelectionSetOp(uid=cell.uid, version_id=cell.version_id)],
            blobs=[CASWrite("objects", payload)],
        )
    store.close()

    recovered = FlowStore.open(flow_dir)
    connection = recovered.index.connection
    assert connection is not None
    row = connection.execute(
        "SELECT uid, source_hash FROM asset_versions WHERE version_id = ?",
        (cell.version_id,),
    ).fetchone()
    selection = connection.execute(
        "SELECT version_id FROM selections WHERE branch_id = ? AND uid = ?",
        (recovered.branch_id, cell.uid),
    ).fetchone()
    assert tuple(row) == (cell.uid, cell.source_hash)
    assert selection[0] == cell.version_id
    assert recovered.last_step == 2


def test_open_keeps_committed_index_after_post_index_crash(tmp_path: Path) -> None:
    flow_dir = tmp_path / "flow"
    store = FlowStore.init(flow_dir)
    payload = b"source"
    cell = _accepted_cell(sha256_bytes(payload))

    def crash(stage: CommitStage) -> None:
        if stage == "after_index":
            raise RuntimeError("simulated crash")

    store._crash_hook = crash
    with pytest.raises(RuntimeError, match="simulated crash"):
        store.commit(
            actor="agent:test",
            intent="accept cell",
            ops=[cell, SelectionSetOp(uid=cell.uid, version_id=cell.version_id)],
            blobs=[CASWrite("objects", payload)],
        )
    store.close()

    recovered = FlowStore.open(flow_dir)
    connection = recovered.index.connection
    assert connection is not None
    row = connection.execute(
        "SELECT version_id FROM selections WHERE branch_id = ? AND uid = ?",
        (recovered.branch_id, cell.uid),
    ).fetchone()
    assert row[0] == cell.version_id
    assert recovered.last_step == 2


def test_open_rebuilds_a_missing_or_wrong_version_index(tmp_path: Path) -> None:
    flow_dir = tmp_path / "flow"
    store = FlowStore.init(flow_dir)
    store.close()
    database = flow_dir / ".lumlflow" / "store.sqlite"
    with sqlite3.connect(database) as setup_connection:
        setup_connection.execute(
            "UPDATE meta SET value = '999' WHERE key = 'schema_version'"
        )

    rebuilt = FlowStore.open(flow_dir)
    connection = rebuilt.index.connection
    assert connection is not None
    assert (
        connection.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()[0]
        == "1"
    )
    rebuilt.close()

    database.unlink()
    reopened = FlowStore.open(flow_dir)
    assert reopened.index.connection is not None
    assert reopened.last_step == 1
