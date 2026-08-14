from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from lumlflow.flow.hashing import sha256_bytes
from lumlflow.flow.ids import mint_ulid
from lumlflow.flow.store.branches import archive, fork, preflight, remove_selection
from lumlflow.flow.store.flowstore import CASWrite, FlowStore
from lumlflow.flow.store.gc import sweep
from lumlflow.flow.store.models import (
    CellAcceptedOp,
    InputRecord,
    OutputRecord,
    RunRecordedOp,
    SelectionSetOp,
)

NOW = datetime(2026, 8, 11, 12, tzinfo=UTC)


def _cell(store: FlowStore, slug: str, volatility: str = "pure") -> tuple[str, str]:
    uid = mint_ulid()
    version = mint_ulid()
    source = slug.encode()
    store.commit(
        actor="agent:test",
        intent=f"accept {slug}",
        ops=[
            CellAcceptedOp(
                uid=uid,
                version_id=version,
                slug=slug,
                source_hash=sha256_bytes(source),
                bound_hash="b" * 64,
                definition_hash=slug[0] * 64,
                manifest={
                    "consumes": {},
                    "produces": {"value": "asset"},
                    "volatility": volatility,
                },
            ),
            SelectionSetOp(uid=uid, version_id=version),
        ],
        blobs=[CASWrite("objects", source)],
        timestamp=NOW,
    )
    return uid, version


def _run(
    store: FlowStore,
    version: str,
    payload: bytes,
    *,
    state: Literal["running", "succeeded", "failed", "cancelled"] = "succeeded",
    inputs: dict[str, InputRecord] | None = None,
) -> tuple[str, str]:
    mat_id = mint_ulid()
    value_hash = sha256_bytes(payload)
    store.commit(
        actor="agent:test",
        intent="run",
        ops=[
            RunRecordedOp(
                mat_id=mat_id,
                version_id=version,
                memo_key=mint_ulid(),
                state=state,
                inputs=inputs or {},
                outputs={
                    "value": OutputRecord(
                        content_hash=value_hash,
                        value_ref=value_hash,
                        kind="pickle",
                        size=len(payload),
                        persisted=True,
                    )
                },
            )
        ],
        blobs=[CASWrite("values", payload)],
        timestamp=NOW,
    )
    return mat_id, value_hash


def test_gc_reachability_matrix_and_retention_expiry(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")

    archived_uid, archived_version = _cell(store, "archived")
    archived_mat, archived_hash = _run(store, archived_version, b"archived")
    archived_branch = fork(store, "main", "archive-root")
    archive(store, archived_branch.branch_id)
    remove_selection(store, "main", archived_uid)

    running_uid, running_version = _cell(store, "running")
    inflight_input_hash = store.cas.put("values", b"in-flight input")
    _running_mat, running_hash = _run(
        store,
        running_version,
        b"running",
        state="running",
        inputs={
            "input": InputRecord(
                uid=archived_uid,
                output="value",
                content_hash=inflight_input_hash,
                mat_id=archived_mat,
            )
        },
    )
    remove_selection(store, "main", running_uid)

    nondeterministic_uid, nondeterministic_version = _cell(
        store, "random", "nondeterministic"
    )
    _random_mat, random_hash = _run(store, nondeterministic_version, b"random")
    random_step = store.last_step
    remove_selection(store, "main", nondeterministic_uid)

    recent_uid, recent_version = _cell(store, "recent")
    _recent_mat, recent_hash = _run(store, recent_version, b"recent")
    remove_selection(store, "main", recent_uid)

    unreachable_hash = store.cas.put("values", b"orphan")
    pinned_hash = store.cas.put("values", b"explicit pin")
    object_hash = store.cas.put("objects", b"unreferenced object")
    preview_hash = store.cas.put("previews", b"unreferenced preview")
    log_hash = store.cas.put("logs", b"unreferenced log")
    connection = store.index.connection
    assert connection is not None
    with connection:
        connection.execute(
            """
            INSERT INTO value_pins(content_hash, reason, expires_step)
            VALUES (?, 'test', NULL)
            """,
            (pinned_hash,),
        )
    journal_before = store.journal.path.read_bytes()

    result = sweep(store, journal_grace_steps=3, retention_days=30, now=NOW)

    assert result.deleted_hashes == (unreachable_hash,)
    for reachable in (
        archived_hash,
        inflight_input_hash,
        running_hash,
        random_hash,
        recent_hash,
        pinned_hash,
    ):
        assert store.cas.contains("values", reachable)
    assert store.journal.path.read_bytes() == journal_before
    assert store.cas.contains("objects", object_hash)
    assert store.cas.contains("previews", preview_hash)
    assert store.cas.contains("logs", log_hash)

    with connection:
        connection.execute("DELETE FROM value_pins")
    expired = sweep(
        store,
        journal_grace_steps=0,
        retention_days=30,
        now=NOW + timedelta(days=31),
    )

    assert random_hash in expired.deleted_hashes
    assert recent_hash in expired.deleted_hashes
    assert pinned_hash in expired.deleted_hashes
    assert store.cas.contains("values", archived_hash)
    assert store.cas.contains("values", inflight_input_hash)
    assert store.cas.contains("values", running_hash)
    assert preflight(store, "main", random_step).irrecoverable == ["random"]
