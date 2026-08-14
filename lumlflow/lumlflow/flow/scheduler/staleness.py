import json
import sqlite3
from dataclasses import dataclass
from typing import Literal, cast

from lumlflow.flow.store.branches import get_branch
from lumlflow.flow.store.flowstore import FlowStore

StalenessState = Literal["synced", "unsynced", "unmaterialized", "failed"]


@dataclass(frozen=True)
class StalenessVerdict:
    state: StalenessState
    causes: tuple[str, ...] = ()


@dataclass(frozen=True)
class StalenessViews:
    direct: StalenessVerdict
    transitive: StalenessVerdict


@dataclass(frozen=True)
class _SelectedCell:
    uid: str
    version_id: str
    definition_hash: str
    dependencies: dict[str, tuple[str, str]]
    env_sensitive: bool


def derive_staleness(
    store: FlowStore,
    branch: str,
    uid: str,
    *,
    lib_changed_files: tuple[str, ...] | list[str] = (),
    env_lock_hash: str | None = None,
) -> StalenessViews:
    branch_id = get_branch(store, branch).branch_id
    connection = _connection(store)
    cells = _selected_cells(connection, branch_id)
    if uid not in cells:
        raise LookupError(f"cell {uid} is not selected on branch {branch}")
    baselines = {
        str(row["uid"]): str(row["mat_id"])
        for row in connection.execute(
            "SELECT uid, mat_id FROM baselines WHERE branch_id = ?", (branch_id,)
        )
    }
    direct = {
        cell_uid: _direct_verdict(
            connection,
            branch_id,
            cell,
            baselines,
            tuple(sorted(set(lib_changed_files))),
            env_lock_hash,
        )
        for cell_uid, cell in cells.items()
    }
    transitive = _transitive_verdict(uid, cells, direct, set())
    return StalenessViews(direct=direct[uid], transitive=transitive)


def derive_all_staleness(
    store: FlowStore,
    branch: str,
    *,
    lib_changed_files: tuple[str, ...] | list[str] = (),
    env_lock_hash: str | None = None,
) -> dict[str, StalenessViews]:
    branch_id = get_branch(store, branch).branch_id
    connection = _connection(store)
    rows = connection.execute(
        "SELECT uid FROM selections WHERE branch_id = ? ORDER BY uid", (branch_id,)
    ).fetchall()
    return {
        str(row["uid"]): derive_staleness(
            store,
            branch_id,
            str(row["uid"]),
            lib_changed_files=lib_changed_files,
            env_lock_hash=env_lock_hash,
        )
        for row in rows
    }


def _direct_verdict(
    connection: sqlite3.Connection,
    branch_id: str,
    cell: _SelectedCell,
    baselines: dict[str, str],
    lib_changed_files: tuple[str, ...],
    env_lock_hash: str | None,
) -> StalenessVerdict:
    baseline_id = baselines.get(cell.uid)
    if baseline_id is None:
        successful = connection.execute(
            """
            SELECT 1 FROM materializations AS mats
            JOIN asset_versions AS versions USING(version_id)
            WHERE versions.uid = ? AND versions.definition_hash = ?
              AND mats.state = 'succeeded'
            LIMIT 1
            """,
            (cell.uid, cell.definition_hash),
        ).fetchone()
        state: StalenessState = "unmaterialized" if successful is None else "unsynced"
        return StalenessVerdict(state)

    baseline = connection.execute(
        """
        SELECT mats.state, mats.inputs, mats.env_lock_hash,
               versions.definition_hash
        FROM materializations AS mats
        JOIN asset_versions AS versions USING(version_id)
        WHERE mats.mat_id = ?
        """,
        (baseline_id,),
    ).fetchone()
    if baseline is None:
        return StalenessVerdict("unmaterialized")
    if baseline["state"] == "failed":
        return StalenessVerdict("failed")
    if baseline["state"] != "succeeded":
        return StalenessVerdict("unsynced")

    causes: list[str] = []
    if str(baseline["definition_hash"]) != cell.definition_hash:
        causes.append("definition-changed")
    baseline_inputs = cast(dict[str, dict[str, object]], json.loads(baseline["inputs"]))
    baseline_dependencies = {
        name: (str(record["uid"]), str(record["output"]))
        for name, record in baseline_inputs.items()
    }
    if baseline_dependencies != cell.dependencies:
        causes.append("deps-rewired")
    else:
        for name, (parent_uid, output_name) in cell.dependencies.items():
            parent_mat_id = baselines.get(parent_uid)
            current_hash = _output_hash(connection, parent_mat_id, output_name)
            expected_hash = str(baseline_inputs[name]["content_hash"])
            if current_hash != expected_hash:
                causes.append("parent-rematerialized")
                break
    causes.extend(f"lib-changed({path})" for path in lib_changed_files)
    if (
        cell.env_sensitive
        and env_lock_hash is not None
        and baseline["env_lock_hash"] != env_lock_hash
    ):
        causes.append("env-changed")
    return StalenessVerdict("unsynced" if causes else "synced", tuple(causes))


def _transitive_verdict(
    uid: str,
    cells: dict[str, _SelectedCell],
    direct: dict[str, StalenessVerdict],
    visiting: set[str],
) -> StalenessVerdict:
    own = direct[uid]
    if uid in visiting:
        return own
    visiting.add(uid)
    causes = list(own.causes)
    upstream_changed = False
    for parent_uid, _output in cells[uid].dependencies.values():
        if parent_uid not in cells:
            continue
        parent = _transitive_verdict(parent_uid, cells, direct, visiting)
        if parent.state != "synced":
            upstream_changed = True
            causes.extend(parent.causes)
    visiting.remove(uid)
    result_state: StalenessState
    if own.state in {"failed", "unmaterialized"}:
        result_state = own.state
    elif own.state == "unsynced" or upstream_changed:
        result_state = "unsynced"
    else:
        result_state = "synced"
    return StalenessVerdict(result_state, tuple(dict.fromkeys(causes)))


def _selected_cells(
    connection: sqlite3.Connection, branch_id: str
) -> dict[str, _SelectedCell]:
    rows = connection.execute(
        """
        SELECT selections.uid, versions.version_id, versions.definition_hash,
               versions.manifest
        FROM selections
        JOIN asset_versions AS versions USING(version_id)
        WHERE selections.branch_id = ?
        """,
        (branch_id,),
    ).fetchall()
    cells: dict[str, _SelectedCell] = {}
    for row in rows:
        manifest = cast(dict[str, object], json.loads(row["manifest"]))
        raw_inputs = manifest.get("bound_inputs", manifest.get("consumes", {}))
        dependencies: dict[str, tuple[str, str]] = {}
        if isinstance(raw_inputs, dict):
            for name, reference in raw_inputs.items():
                if not isinstance(name, str) or not isinstance(reference, str):
                    continue
                parsed = _parse_bound_reference(reference)
                if parsed is not None:
                    dependencies[name] = parsed
        cell_uid = str(row["uid"])
        cells[cell_uid] = _SelectedCell(
            uid=cell_uid,
            version_id=str(row["version_id"]),
            definition_hash=str(row["definition_hash"]),
            dependencies=dependencies,
            env_sensitive=manifest.get("env_sensitive", False) is True,
        )
    return cells


def _parse_bound_reference(reference: str) -> tuple[str, str] | None:
    if not reference.startswith("uid:") or "." not in reference[4:]:
        return None
    uid, output = reference[4:].split(".", 1)
    return (uid, output)


def _output_hash(
    connection: sqlite3.Connection, mat_id: str | None, output_name: str
) -> str | None:
    if mat_id is None:
        return None
    row = connection.execute(
        "SELECT state, outputs FROM materializations WHERE mat_id = ?", (mat_id,)
    ).fetchone()
    if row is None or row["state"] != "succeeded":
        return None
    outputs = cast(dict[str, dict[str, object]], json.loads(row["outputs"]))
    output = outputs.get(output_name)
    return None if output is None else str(output["content_hash"])


def _connection(store: FlowStore) -> sqlite3.Connection:
    connection = store.index.connection
    if connection is None:
        raise RuntimeError("SQLite index is not open")
    return connection
