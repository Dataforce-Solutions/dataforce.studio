import json
import os
import sqlite3
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import cast

from lumlflow.flow.hashing import canonical_json
from lumlflow.flow.store.cas import _replace_with_retry
from lumlflow.flow.store.models import (
    AdoptedOp,
    BranchArchivedOp,
    BranchCreatedOp,
    BranchRenamedOp,
    CellAcceptedOp,
    CellRemovedOp,
    EnvChangedOp,
    FlowInitOp,
    JsonValue,
    MemoHitOp,
    PromotedOp,
    RewoundOp,
    RunRecordedOp,
    SelectionSetOp,
    Transaction,
    UploadRecordedOp,
    UploadStateOp,
    WorktreeBoundOp,
)

SCHEMA_VERSION = 1
SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE cells(uid TEXT PRIMARY KEY, created_step INT, copied_from TEXT);
CREATE TABLE asset_versions(
  version_id TEXT PRIMARY KEY,
  uid TEXT NOT NULL REFERENCES cells,
  slug TEXT NOT NULL,
  source_hash TEXT NOT NULL,
  bound_hash TEXT NOT NULL,
  definition_hash TEXT NOT NULL,
  manifest TEXT NOT NULL,
  parent_version_id TEXT,
  author TEXT,
  created_step INT
);
CREATE TABLE branches(
  branch_id TEXT PRIMARY KEY,
  name TEXT UNIQUE,
  parent_branch_id TEXT,
  fork_step INT,
  archived INT DEFAULT 0,
  sweep_group TEXT
);
CREATE TABLE selections(
  branch_id TEXT,
  uid TEXT,
  version_id TEXT,
  pinned INT,
  PRIMARY KEY(branch_id, uid)
);
CREATE TABLE baselines(
  branch_id TEXT,
  uid TEXT,
  mat_id TEXT,
  PRIMARY KEY(branch_id, uid)
);
CREATE TABLE materializations(
  mat_id TEXT PRIMARY KEY,
  version_id TEXT,
  memo_key TEXT,
  state TEXT,
  branch_id TEXT,
  inputs TEXT,
  outputs TEXT,
  identity_dependent INT DEFAULT 0,
  env_lock_hash TEXT,
  cost_seconds REAL,
  log_ref TEXT,
  started_step INT,
  finished_step INT
);
CREATE INDEX mat_memo ON materializations(memo_key, state);
CREATE TABLE transactions(
  step INT PRIMARY KEY,
  actor TEXT,
  intent TEXT,
  branch_id TEXT,
  settled INT,
  offline INT,
  ts TEXT,
  ops TEXT
);
CREATE TABLE worktrees(
  path TEXT PRIMARY KEY,
  branch_id TEXT,
  actor TEXT,
  lock_holder TEXT
);
CREATE TABLE upload_queue(
  mat_id TEXT,
  output TEXT,
  state TEXT,
  attempts INT,
  PRIMARY KEY(mat_id, output)
);
CREATE TABLE value_pins(
  content_hash TEXT PRIMARY KEY,
  reason TEXT,
  expires_step INT
);
CREATE TABLE lib_tree(hash TEXT, computed_step INT);
"""


class SQLiteIndex:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection: sqlite3.Connection | None = None

    def open(self) -> None:
        if self.connection is None:
            self.connection = sqlite3.connect(self.path)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def is_current(self, journal_step: int) -> bool:
        if not self.path.is_file():
            return False
        try:
            self.open()
            connection = self._connection()
            version = connection.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'"
            ).fetchone()
            cursor = connection.execute(
                "SELECT value FROM meta WHERE key = 'journal_cursor'"
            ).fetchone()
            return (
                version is not None
                and int(version[0]) == SCHEMA_VERSION
                and cursor is not None
                and int(cursor[0]) == journal_step
            )
        except (sqlite3.DatabaseError, ValueError):
            return False

    def rebuild(self, transactions: Iterable[Transaction]) -> None:
        self.close()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", dir=self.path.parent
        )
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        try:
            temporary = SQLiteIndex(temporary_path)
            temporary.open()
            connection = temporary._connection()
            connection.executescript(SCHEMA)
            connection.execute(
                "INSERT INTO meta(key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            connection.execute(
                "INSERT INTO meta(key, value) VALUES ('journal_cursor', '0')"
            )
            connection.commit()
            for transaction in transactions:
                temporary.apply(transaction)
            temporary.close()
            _replace_with_retry(temporary_path, self.path)
        finally:
            temporary_path.unlink(missing_ok=True)
        self.open()

    def apply(self, transaction: Transaction) -> None:
        connection = self._connection()
        operations = cast(
            JsonValue, [op.model_dump(mode="json") for op in transaction.ops]
        )
        with connection:
            connection.execute(
                """
                INSERT INTO transactions(
                    step, actor, intent, branch_id, settled, offline, ts, ops
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transaction.step,
                    transaction.actor,
                    transaction.intent,
                    transaction.branch,
                    transaction.settled,
                    transaction.offline,
                    transaction.ts,
                    canonical_json(operations),
                ),
            )
            for operation in transaction.ops:
                if isinstance(operation, FlowInitOp):
                    self._apply_flow_init(connection, operation)
                elif isinstance(operation, CellAcceptedOp):
                    self._apply_cell_accepted(connection, transaction, operation)
                elif isinstance(operation, CellRemovedOp):
                    connection.execute(
                        "DELETE FROM selections WHERE branch_id = ? AND uid = ?",
                        (transaction.branch, operation.uid),
                    )
                    connection.execute(
                        "DELETE FROM baselines WHERE branch_id = ? AND uid = ?",
                        (transaction.branch, operation.uid),
                    )
                elif isinstance(operation, SelectionSetOp):
                    self._set_selection(connection, transaction.branch, operation)
                elif isinstance(operation, BranchCreatedOp):
                    self._apply_branch_created(connection, operation)
                elif isinstance(operation, BranchArchivedOp):
                    connection.execute(
                        "UPDATE branches SET archived = 1 WHERE branch_id = ?",
                        (operation.branch_id,),
                    )
                elif isinstance(operation, BranchRenamedOp):
                    connection.execute(
                        "UPDATE branches SET name = ? WHERE branch_id = ?",
                        (operation.new_name, operation.branch_id),
                    )
                elif isinstance(operation, WorktreeBoundOp):
                    connection.execute(
                        """
                        INSERT INTO worktrees(path, branch_id, actor, lock_holder)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(path) DO UPDATE SET
                          branch_id = excluded.branch_id,
                          actor = excluded.actor,
                          lock_holder = excluded.lock_holder
                        """,
                        (
                            operation.path,
                            operation.branch_id,
                            operation.actor,
                            operation.lock_holder,
                        ),
                    )
                elif isinstance(operation, AdoptedOp):
                    self._set_selection(
                        connection,
                        transaction.branch,
                        SelectionSetOp(
                            uid=operation.uid,
                            version_id=operation.version_id,
                            pinned=True,
                        ),
                    )
                elif isinstance(operation, RewoundOp):
                    self._apply_rewound(
                        connection, transaction.branch, operation.to_step
                    )
                elif isinstance(operation, RunRecordedOp):
                    self._apply_run_recorded(connection, transaction, operation)
                elif isinstance(operation, MemoHitOp):
                    self._apply_memo_hit(connection, transaction, operation)
                elif isinstance(operation, EnvChangedOp):
                    connection.execute(
                        """
                        INSERT INTO meta(key, value) VALUES ('env_lock_hash', ?)
                        ON CONFLICT(key) DO UPDATE SET value = excluded.value
                        """,
                        (operation.lock_hash,),
                    )
                elif isinstance(operation, UploadRecordedOp):
                    self._apply_upload_recorded(connection, operation)
                elif isinstance(operation, UploadStateOp):
                    self._apply_upload_state(connection, operation)
                elif isinstance(operation, PromotedOp):
                    self._apply_promoted(connection, operation)
            connection.execute(
                """
                INSERT INTO meta(key, value) VALUES ('journal_cursor', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (str(transaction.step),),
            )

    def _apply_flow_init(
        self, connection: sqlite3.Connection, operation: FlowInitOp
    ) -> None:
        connection.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES ('flow_id', ?)",
            (operation.flow_id,),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO branches(
                branch_id, name, parent_branch_id, fork_step, archived, sweep_group
            ) VALUES (?, ?, NULL, 0, 0, NULL)
            """,
            (operation.branch_id, operation.branch_name),
        )

    def _apply_cell_accepted(
        self,
        connection: sqlite3.Connection,
        transaction: Transaction,
        operation: CellAcceptedOp,
    ) -> None:
        connection.execute(
            """
            INSERT OR IGNORE INTO cells(uid, created_step, copied_from)
            VALUES (?, ?, ?)
            """,
            (operation.uid, transaction.step, operation.copied_from),
        )
        manifest = dict(operation.manifest)
        manifest["flags"] = cast(JsonValue, operation.flags)
        connection.execute(
            """
            INSERT INTO asset_versions(
                version_id, uid, slug, source_hash, bound_hash, definition_hash,
                manifest, parent_version_id, author, created_step
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                operation.version_id,
                operation.uid,
                operation.slug,
                operation.source_hash,
                operation.bound_hash,
                operation.definition_hash,
                canonical_json(cast(JsonValue, manifest)),
                operation.parent_version,
                operation.author or transaction.actor,
                transaction.step,
            ),
        )

    def _apply_branch_created(
        self, connection: sqlite3.Connection, operation: BranchCreatedOp
    ) -> None:
        connection.execute(
            """
            INSERT INTO branches(
                branch_id, name, parent_branch_id, fork_step, archived, sweep_group
            ) VALUES (?, ?, ?, ?, 0, ?)
            """,
            (
                operation.branch_id,
                operation.name,
                operation.parent,
                operation.fork_step,
                operation.sweep_group,
            ),
        )
        if operation.parent is not None:
            selections, baselines = self.branch_state_at_step(
                operation.parent, operation.fork_step
            )
            connection.executemany(
                """
                INSERT INTO selections(branch_id, uid, version_id, pinned)
                VALUES (?, ?, ?, 1)
                """,
                [
                    (operation.branch_id, uid, version_id)
                    for uid, (version_id, _pinned) in selections.items()
                ],
            )
            connection.executemany(
                """
                INSERT INTO baselines(branch_id, uid, mat_id)
                VALUES (?, ?, ?)
                """,
                [
                    (operation.branch_id, uid, mat_id)
                    for uid, mat_id in baselines.items()
                ],
            )

    def _apply_run_recorded(
        self,
        connection: sqlite3.Connection,
        transaction: Transaction,
        operation: RunRecordedOp,
    ) -> None:
        inputs = cast(
            JsonValue,
            {
                name: value.model_dump(mode="json")
                for name, value in operation.inputs.items()
            },
        )
        outputs = cast(
            JsonValue,
            {
                name: value.model_dump(mode="json")
                for name, value in operation.outputs.items()
            },
        )
        connection.execute(
            """
            INSERT OR REPLACE INTO materializations(
                mat_id, version_id, memo_key, state, branch_id, inputs, outputs,
                identity_dependent, env_lock_hash, cost_seconds, log_ref,
                started_step, finished_step
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                operation.mat_id,
                operation.version_id,
                operation.memo_key,
                operation.state,
                transaction.branch,
                canonical_json(inputs),
                canonical_json(outputs),
                operation.identity_dependent,
                operation.env_lock_hash,
                operation.cost_seconds,
                operation.log_ref,
                operation.started_step,
                operation.finished_step,
            ),
        )
        row = connection.execute(
            "SELECT uid FROM asset_versions WHERE version_id = ?",
            (operation.version_id,),
        ).fetchone()
        if row is not None:
            connection.execute(
                """
                INSERT INTO baselines(branch_id, uid, mat_id) VALUES (?, ?, ?)
                ON CONFLICT(branch_id, uid) DO UPDATE SET mat_id = excluded.mat_id
                """,
                (transaction.branch, row[0], operation.mat_id),
            )

    def _apply_memo_hit(
        self,
        connection: sqlite3.Connection,
        transaction: Transaction,
        operation: MemoHitOp,
    ) -> None:
        if operation.mat_id is None:
            return
        row = connection.execute(
            "SELECT state FROM materializations WHERE mat_id = ?",
            (operation.mat_id,),
        ).fetchone()
        if row is None or row[0] != "succeeded":
            return
        connection.execute(
            """
            INSERT INTO baselines(branch_id, uid, mat_id) VALUES (?, ?, ?)
            ON CONFLICT(branch_id, uid) DO UPDATE SET mat_id = excluded.mat_id
            """,
            (transaction.branch, operation.uid, operation.mat_id),
        )

    def _apply_rewound(
        self, connection: sqlite3.Connection, branch_id: str, to_step: int
    ) -> None:
        selections, baselines = self.branch_state_at_step(branch_id, to_step)
        connection.execute("DELETE FROM selections WHERE branch_id = ?", (branch_id,))
        connection.execute("DELETE FROM baselines WHERE branch_id = ?", (branch_id,))
        connection.executemany(
            """
            INSERT INTO selections(branch_id, uid, version_id, pinned)
            VALUES (?, ?, ?, ?)
            """,
            [
                (branch_id, uid, version_id, pinned)
                for uid, (version_id, pinned) in selections.items()
            ],
        )
        connection.executemany(
            "INSERT INTO baselines(branch_id, uid, mat_id) VALUES (?, ?, ?)",
            [(branch_id, uid, mat_id) for uid, mat_id in baselines.items()],
        )

    def branch_state_at_step(
        self, branch_id: str, to_step: int
    ) -> tuple[dict[str, tuple[str, bool]], dict[str, str]]:
        if to_step < 0:
            raise ValueError("rewind step must not be negative")
        connection = self._connection()
        rows = connection.execute(
            """
            SELECT step, actor, intent, branch_id, settled, offline, ts, ops
            FROM transactions WHERE step <= ? ORDER BY step
            """,
            (to_step,),
        ).fetchall()
        transactions = [
            Transaction.model_validate(
                {
                    "step": row["step"],
                    "actor": row["actor"],
                    "intent": row["intent"],
                    "branch": row["branch_id"],
                    "settled": bool(row["settled"]),
                    "offline": bool(row["offline"]),
                    "ts": row["ts"],
                    "ops": json.loads(row["ops"]),
                }
            )
            for row in rows
        ]
        return _replay_branch_state(transactions, branch_id)

    def is_branch_settled(
        self, branch_id: str, pending_ops: Iterable[object] = ()
    ) -> bool:
        connection = self._connection()
        selections = {
            row["uid"]: row["version_id"]
            for row in connection.execute(
                "SELECT uid, version_id FROM selections WHERE branch_id = ?",
                (branch_id,),
            )
        }
        baselines = {
            row["uid"]: row["mat_id"]
            for row in connection.execute(
                "SELECT uid, mat_id FROM baselines WHERE branch_id = ?",
                (branch_id,),
            )
        }
        pending_materializations: dict[str, RunRecordedOp] = {}
        pending_version_uids: dict[str, str] = {}
        for operation in pending_ops:
            if isinstance(operation, CellAcceptedOp):
                pending_version_uids[operation.version_id] = operation.uid
            elif isinstance(operation, CellRemovedOp):
                selections.pop(operation.uid, None)
                baselines.pop(operation.uid, None)
            elif isinstance(operation, SelectionSetOp):
                selections[operation.uid] = operation.version_id
            elif isinstance(operation, AdoptedOp):
                selections[operation.uid] = operation.version_id
            elif isinstance(operation, RewoundOp):
                rewound_selections, rewound_baselines = self.branch_state_at_step(
                    branch_id, operation.to_step
                )
                selections = {
                    uid: version_id
                    for uid, (version_id, _pinned) in rewound_selections.items()
                }
                baselines = rewound_baselines
            elif isinstance(operation, RunRecordedOp):
                pending_materializations[operation.mat_id] = operation
                uid = pending_version_uids.get(operation.version_id)
                if uid is None:
                    row = connection.execute(
                        "SELECT uid FROM asset_versions WHERE version_id = ?",
                        (operation.version_id,),
                    ).fetchone()
                    uid = None if row is None else str(row[0])
                if uid is not None:
                    baselines[uid] = operation.mat_id
            elif isinstance(operation, MemoHitOp) and operation.mat_id is not None:
                baselines[operation.uid] = operation.mat_id

        if not selections:
            return True
        for uid, version_id in selections.items():
            mat_id = baselines.get(uid)
            if mat_id is None:
                return False
            pending = pending_materializations.get(mat_id)
            if pending is not None:
                if pending.state != "succeeded" or pending.version_id != version_id:
                    return False
                inputs = {
                    name: value.model_dump(mode="json")
                    for name, value in pending.inputs.items()
                }
            else:
                row = connection.execute(
                    """
                    SELECT version_id, state, inputs FROM materializations
                    WHERE mat_id = ?
                    """,
                    (mat_id,),
                ).fetchone()
                if row is None or row["state"] != "succeeded":
                    return False
                selected_definition = connection.execute(
                    "SELECT definition_hash FROM asset_versions WHERE version_id = ?",
                    (version_id,),
                ).fetchone()
                materialized_definition = connection.execute(
                    "SELECT definition_hash FROM asset_versions WHERE version_id = ?",
                    (row["version_id"],),
                ).fetchone()
                if (
                    selected_definition is None
                    or materialized_definition is None
                    or selected_definition[0] != materialized_definition[0]
                ):
                    return False
                inputs = cast(
                    dict[str, dict[str, JsonValue]], json.loads(row["inputs"])
                )
            for input_record in inputs.values():
                input_uid = str(input_record["uid"])
                input_mat_id = baselines.get(input_uid)
                if input_mat_id is None:
                    return False
                expected_hash = str(input_record["content_hash"])
                output_name = str(input_record["output"])
                upstream_pending = pending_materializations.get(input_mat_id)
                if upstream_pending is not None:
                    output = upstream_pending.outputs.get(output_name)
                    actual_hash = None if output is None else output.content_hash
                else:
                    upstream = connection.execute(
                        "SELECT outputs FROM materializations WHERE mat_id = ?",
                        (input_mat_id,),
                    ).fetchone()
                    outputs = {} if upstream is None else json.loads(upstream[0])
                    output = outputs.get(output_name)
                    actual_hash = None if output is None else output["content_hash"]
                if actual_hash != expected_hash:
                    return False
        return True

    def _apply_upload_recorded(
        self, connection: sqlite3.Connection, operation: UploadRecordedOp
    ) -> None:
        row = connection.execute(
            "SELECT outputs FROM materializations WHERE mat_id = ?",
            (operation.mat_id,),
        ).fetchone()
        if row is not None:
            outputs = json.loads(row[0])
            if operation.output in outputs:
                outputs[operation.output]["luml_ref"] = operation.luml_ref.model_dump(
                    mode="json"
                )
                connection.execute(
                    "UPDATE materializations SET outputs = ? WHERE mat_id = ?",
                    (canonical_json(cast(JsonValue, outputs)), operation.mat_id),
                )
        connection.execute(
            """
            INSERT INTO upload_queue(mat_id, output, state, attempts)
            VALUES (?, ?, 'done', 0)
            ON CONFLICT(mat_id, output) DO UPDATE SET state = 'done'
            """,
            (operation.mat_id, operation.output),
        )

    def _apply_upload_state(
        self, connection: sqlite3.Connection, operation: UploadStateOp
    ) -> None:
        connection.execute(
            """
            INSERT INTO upload_queue(mat_id, output, state, attempts)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(mat_id, output) DO UPDATE SET
              state = excluded.state,
              attempts = excluded.attempts
            """,
            (
                operation.mat_id,
                operation.output,
                operation.state,
                operation.attempts,
            ),
        )

    def _apply_promoted(
        self, connection: sqlite3.Connection, operation: PromotedOp
    ) -> None:
        row = connection.execute(
            "SELECT outputs FROM materializations WHERE mat_id = ?",
            (operation.mat_id,),
        ).fetchone()
        if row is None:
            return
        outputs = json.loads(row[0])
        if operation.output not in outputs:
            return
        outputs[operation.output]["native_type"] = operation.native_type
        connection.execute(
            "UPDATE materializations SET outputs = ? WHERE mat_id = ?",
            (canonical_json(cast(JsonValue, outputs)), operation.mat_id),
        )

    def _set_selection(
        self,
        connection: sqlite3.Connection,
        branch_id: str,
        operation: SelectionSetOp,
    ) -> None:
        connection.execute(
            """
            INSERT INTO selections(branch_id, uid, version_id, pinned)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(branch_id, uid) DO UPDATE SET
              version_id = excluded.version_id,
              pinned = excluded.pinned
            """,
            (branch_id, operation.uid, operation.version_id, operation.pinned),
        )

    def _connection(self) -> sqlite3.Connection:
        if self.connection is None:
            raise RuntimeError("SQLite index is not open")
        return self.connection


Index = SQLiteIndex


def _replay_branch_state(
    transactions: Iterable[Transaction], branch_id: str
) -> tuple[dict[str, tuple[str, bool]], dict[str, str]]:
    selections: dict[str, dict[str, tuple[str, bool]]] = {}
    baselines: dict[str, dict[str, str]] = {}
    snapshots: dict[
        int, tuple[dict[str, dict[str, tuple[str, bool]]], dict[str, dict[str, str]]]
    ] = {}
    version_uids: dict[str, str] = {}

    for transaction in transactions:
        selections.setdefault(transaction.branch, {})
        baselines.setdefault(transaction.branch, {})
        for operation in transaction.ops:
            if isinstance(operation, FlowInitOp):
                selections.setdefault(operation.branch_id, {})
                baselines.setdefault(operation.branch_id, {})
            elif isinstance(operation, CellAcceptedOp):
                version_uids[operation.version_id] = operation.uid
            elif isinstance(operation, CellRemovedOp):
                selections[transaction.branch].pop(operation.uid, None)
                baselines[transaction.branch].pop(operation.uid, None)
            elif isinstance(operation, SelectionSetOp):
                selections[transaction.branch][operation.uid] = (
                    operation.version_id,
                    operation.pinned,
                )
            elif isinstance(operation, BranchCreatedOp):
                historical = snapshots.get(operation.fork_step)
                historical_selections = {} if historical is None else historical[0]
                historical_baselines = {} if historical is None else historical[1]
                parent_selections = historical_selections.get(
                    operation.parent or "", selections.get(operation.parent or "", {})
                )
                parent_baselines = historical_baselines.get(
                    operation.parent or "", baselines.get(operation.parent or "", {})
                )
                selections[operation.branch_id] = {
                    uid: (version_id, True)
                    for uid, (version_id, _pinned) in parent_selections.items()
                }
                baselines[operation.branch_id] = dict(parent_baselines)
            elif isinstance(operation, AdoptedOp):
                selections[transaction.branch][operation.uid] = (
                    operation.version_id,
                    True,
                )
            elif isinstance(operation, RunRecordedOp):
                uid = version_uids.get(operation.version_id)
                if uid is not None:
                    baselines[transaction.branch][uid] = operation.mat_id
            elif isinstance(operation, MemoHitOp) and operation.mat_id is not None:
                baselines[transaction.branch][operation.uid] = operation.mat_id
            elif isinstance(operation, RewoundOp):
                prior = snapshots.get(operation.to_step)
                if prior is None:
                    selections[transaction.branch] = {}
                    baselines[transaction.branch] = {}
                else:
                    selections[transaction.branch] = dict(
                        prior[0].get(transaction.branch, {})
                    )
                    baselines[transaction.branch] = dict(
                        prior[1].get(transaction.branch, {})
                    )
        snapshots[transaction.step] = (
            {key: dict(value) for key, value in selections.items()},
            {key: dict(value) for key, value in baselines.items()},
        )

    return dict(selections.get(branch_id, {})), dict(baselines.get(branch_id, {}))
