import json
import sqlite3
from typing import Literal, cast

from lumlflow.flow.hashing import behavior_hash, memo_key
from lumlflow.flow.store.branches import get_branch
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import (
    InputRecord,
    Materialization,
    MemoHitOp,
    OutputRecord,
    Transaction,
)


def memo_key_for(
    definition_hash: str,
    lib_tree_hash: str,
    inputs: dict[str, str],
    *,
    env_sensitive: bool = False,
    env_lock_hash: str | None = None,
) -> str:
    if env_sensitive and env_lock_hash is None:
        raise ValueError("env-sensitive cells require an environment lock hash")
    behavior = behavior_hash(definition_hash, lib_tree_hash)
    return memo_key(
        behavior,
        inputs,
        env_lock_hash=env_lock_hash if env_sensitive else None,
    )


def find_memo_hit(
    store: FlowStore,
    branch: str,
    key: str,
    *,
    volatility: str = "pure",
) -> Materialization | None:
    if volatility in {"nondeterministic", "external"}:
        return None
    branch_id = get_branch(store, branch).branch_id
    connection = _connection(store)
    rows = connection.execute(
        """
        SELECT * FROM materializations
        WHERE memo_key = ? AND state = 'succeeded'
        ORDER BY rowid DESC
        """,
        (key,),
    ).fetchall()
    for row in rows:
        if bool(row["identity_dependent"]) and row["branch_id"] != branch_id:
            continue
        return _materialization(row)
    return None


def record_memo_hit(
    store: FlowStore,
    branch: str,
    uid: str,
    version_id: str,
    key: str,
    mat_id: str,
    *,
    actor: str = "system:scheduler",
    intent: str | None = None,
) -> Transaction:
    branch_id = get_branch(store, branch).branch_id
    return store.commit(
        actor=actor,
        intent=intent or "reuse memoized materialization",
        branch=branch_id,
        ops=[
            MemoHitOp(
                uid=uid,
                version_id=version_id,
                memo_key=key,
                mat_id=mat_id,
            )
        ],
    )


def _materialization(row: sqlite3.Row) -> Materialization:
    inputs = {
        name: InputRecord.model_validate(value)
        for name, value in cast(dict[str, object], json.loads(row["inputs"])).items()
    }
    outputs = {
        name: OutputRecord.model_validate(value)
        for name, value in cast(dict[str, object], json.loads(row["outputs"])).items()
    }
    state = cast(
        Literal["running", "succeeded", "failed", "cancelled"], str(row["state"])
    )
    return Materialization(
        mat_id=str(row["mat_id"]),
        version_id=str(row["version_id"]),
        memo_key=str(row["memo_key"]),
        state=state,
        branch_id=str(row["branch_id"]),
        inputs=inputs,
        outputs=outputs,
        identity_dependent=bool(row["identity_dependent"]),
        env_lock_hash=row["env_lock_hash"],
        cost_seconds=row["cost_seconds"],
        log_ref=row["log_ref"],
        started_step=row["started_step"],
        finished_step=row["finished_step"],
    )


def _connection(store: FlowStore) -> sqlite3.Connection:
    connection = store.index.connection
    if connection is None:
        raise RuntimeError("SQLite index is not open")
    return connection
