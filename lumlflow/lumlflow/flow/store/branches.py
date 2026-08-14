import json
import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from lumlflow.flow.ids import mint_ulid
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import (
    AdoptedOp,
    AssetVersion,
    Baseline,
    Branch,
    BranchArchivedOp,
    BranchCreatedOp,
    BranchRenamedOp,
    CellRemovedOp,
    RewoundOp,
    Selection,
    Transaction,
    WorktreeBoundOp,
)


class BranchNotFoundError(LookupError):
    pass


class WorktreeLockedError(RuntimeError):
    pass


class AdoptConflictError(RuntimeError):
    def __init__(
        self,
        uid: str,
        base_definition: str | None,
        target_definition: str,
        incoming_definition: str,
    ) -> None:
        super().__init__(f"both branches edited {uid} since their fork point")
        self.uid = uid
        self.base_definition = base_definition
        self.target_definition = target_definition
        self.incoming_definition = incoming_definition


@dataclass(frozen=True)
class NamespaceConflict:
    slug: str
    expected_uid: str
    actual_uid: str | None


class NamespaceConflictError(RuntimeError):
    def __init__(self, conflicts: Iterable[NamespaceConflict]) -> None:
        self.conflicts = tuple(conflicts)
        details = ", ".join(conflict.slug for conflict in self.conflicts)
        super().__init__(f"adopt would rebind namespace entries: {details}")


@dataclass(frozen=True)
class PreflightResult:
    recompute: list[tuple[str, float | None]]
    irrecoverable: list[str]


NamespaceValidator = Callable[
    [AssetVersion, dict[str, str]], Iterable[NamespaceConflict]
]
NamespaceChangeHook = Callable[[str, str], None]


def list_branches(store: FlowStore, *, include_archived: bool = True) -> list[Branch]:
    connection = _connection(store)
    where = "" if include_archived else "WHERE archived = 0"
    rows = connection.execute(
        f"""SELECT branch_id, name, parent_branch_id, fork_step, archived,
                   sweep_group FROM branches {where} ORDER BY rowid"""
    ).fetchall()
    return [_branch_from_row(row) for row in rows]


def get_branch(store: FlowStore, branch: str) -> Branch:
    row = (
        _connection(store)
        .execute(
            """
        SELECT branch_id, name, parent_branch_id, fork_step, archived, sweep_group
        FROM branches WHERE branch_id = ? OR name = ?
        """,
            (branch, branch),
        )
        .fetchone()
    )
    if row is None:
        raise BranchNotFoundError(f"unknown branch: {branch}")
    return _branch_from_row(row)


def selections(store: FlowStore, branch: str) -> list[Selection]:
    branch_id = get_branch(store, branch).branch_id
    rows = (
        _connection(store)
        .execute(
            """
        SELECT branch_id, uid, version_id, pinned FROM selections
        WHERE branch_id = ? ORDER BY uid
        """,
            (branch_id,),
        )
        .fetchall()
    )
    return [
        Selection(
            branch_id=row["branch_id"],
            uid=row["uid"],
            version_id=row["version_id"],
            pinned=bool(row["pinned"]),
        )
        for row in rows
    ]


def baselines(store: FlowStore, branch: str) -> list[Baseline]:
    branch_id = get_branch(store, branch).branch_id
    rows = (
        _connection(store)
        .execute(
            """
        SELECT branch_id, uid, mat_id FROM baselines
        WHERE branch_id = ? ORDER BY uid
        """,
            (branch_id,),
        )
        .fetchall()
    )
    return [Baseline.model_validate(dict(row)) for row in rows]


def fork(
    store: FlowStore,
    parent: str,
    name: str,
    *,
    actor: str = "agent:unknown",
    intent: str | None = None,
    sweep_group: str | None = None,
    fork_step: int | None = None,
) -> Branch:
    parent_branch = get_branch(store, parent)
    if parent_branch.archived:
        raise ValueError("cannot fork an archived branch")
    if not name.strip():
        raise ValueError("branch name must not be empty")
    if (
        _connection(store)
        .execute("SELECT 1 FROM branches WHERE name = ?", (name,))
        .fetchone()
    ):
        raise ValueError(f"branch already exists: {name}")
    branch_id = mint_ulid()
    selected_fork_step = store.last_step if fork_step is None else fork_step
    if selected_fork_step < 1 or selected_fork_step > store.last_step:
        raise ValueError(f"fork step must be between 1 and {store.last_step}")
    store.commit(
        actor=actor,
        intent=intent or f"fork {name} from {parent_branch.name}",
        branch=parent_branch.branch_id,
        ops=[
            BranchCreatedOp(
                branch_id=branch_id,
                name=name,
                parent=parent_branch.branch_id,
                fork_step=selected_fork_step,
                sweep_group=sweep_group,
            )
        ],
    )
    return get_branch(store, branch_id)


def switch(
    store: FlowStore,
    branch: str,
    *,
    path: str | Path | None = None,
    actor: str = "agent:unknown",
    intent: str | None = None,
    force: bool = False,
) -> Transaction:
    target = get_branch(store, branch)
    if target.archived:
        raise ValueError("cannot switch to an archived branch")
    worktree_path = str((Path(path) if path is not None else store.flow_dir).resolve())
    row = (
        _connection(store)
        .execute("SELECT lock_holder FROM worktrees WHERE path = ?", (worktree_path,))
        .fetchone()
    )
    if row is not None and row["lock_holder"] is not None and not force:
        raise WorktreeLockedError(f"worktree is locked by {row['lock_holder']}")
    transaction = store.commit(
        actor=actor,
        intent=intent or f"switch to {target.name}",
        branch=target.branch_id,
        ops=[
            WorktreeBoundOp(
                path=worktree_path,
                branch_id=target.branch_id,
                actor=actor,
                lock_holder=None,
            )
        ],
    )
    store.branch_id = target.branch_id
    return transaction


def rename_branch(
    store: FlowStore,
    branch: str,
    name: str,
    *,
    actor: str = "agent:unknown",
    intent: str | None = None,
) -> Transaction:
    target = get_branch(store, branch)
    new_name = name.strip()
    if not new_name:
        raise ValueError("branch name must not be empty")
    if target.archived:
        raise ValueError("cannot rename an archived branch")
    if (
        _connection(store)
        .execute(
            "SELECT 1 FROM branches WHERE name = ? AND branch_id != ?",
            (new_name, target.branch_id),
        )
        .fetchone()
    ):
        raise ValueError(f"branch already exists: {new_name}")
    return store.commit(
        actor=actor,
        intent=intent or f"rename {target.name} to {new_name}",
        branch=target.branch_id,
        ops=[
            BranchRenamedOp(
                branch_id=target.branch_id,
                old_name=target.name,
                new_name=new_name,
            )
        ],
    )


def archive(
    store: FlowStore,
    branch: str,
    *,
    actor: str = "agent:unknown",
    intent: str | None = None,
) -> Transaction:
    target = get_branch(store, branch)
    if target.archived:
        raise ValueError(f"branch is already archived: {target.name}")
    return store.commit(
        actor=actor,
        intent=intent or f"archive {target.name}",
        branch=target.branch_id,
        ops=[BranchArchivedOp(branch_id=target.branch_id)],
    )


def remove_selection(
    store: FlowStore,
    branch: str,
    uid: str,
    *,
    actor: str = "agent:unknown",
    intent: str | None = None,
) -> Transaction:
    target = get_branch(store, branch)
    if not any(
        selection.uid == uid for selection in selections(store, target.branch_id)
    ):
        raise LookupError(f"cell {uid} is not selected on {target.name}")
    return store.commit(
        actor=actor,
        intent=intent or f"remove cell {uid} from {target.name}",
        branch=target.branch_id,
        ops=[CellRemovedOp(uid=uid)],
    )


def rewind(
    store: FlowStore,
    branch: str,
    step: int,
    *,
    actor: str = "agent:unknown",
    intent: str | None = None,
) -> Transaction:
    target = get_branch(store, branch)
    _validate_rewind_step(store, target, step)
    return store.commit(
        actor=actor,
        intent=intent or f"rewind {target.name} to step {step}",
        branch=target.branch_id,
        ops=[RewoundOp(to_step=step)],
    )


def preflight(store: FlowStore, branch: str, step: int) -> PreflightResult:
    target = get_branch(store, branch)
    _validate_rewind_step(store, target, step)
    target_selections, target_baselines = store.index.branch_state_at_step(
        target.branch_id, step
    )
    recompute: list[tuple[str, float | None]] = []
    irrecoverable: list[str] = []
    connection = _connection(store)
    for uid, (version_id, _pinned) in sorted(target_selections.items()):
        version = connection.execute(
            """
            SELECT slug, definition_hash, manifest FROM asset_versions
            WHERE version_id = ? AND uid = ?
            """,
            (version_id, uid),
        ).fetchone()
        if version is None:
            continue
        slug = str(version["slug"])
        mat_id = target_baselines.get(uid)
        materialization = (
            None
            if mat_id is None
            else connection.execute(
                """
                SELECT version_id, state, inputs, outputs FROM materializations
                WHERE mat_id = ?
                """,
                (mat_id,),
            ).fetchone()
        )
        baseline_matches = materialization is not None and _baseline_matches_state(
            store,
            materialization,
            str(version["definition_hash"]),
            target_baselines,
        )
        if (
            materialization is not None
            and baseline_matches
            and _outputs_available(store, json.loads(materialization["outputs"]))
        ):
            continue
        manifest = json.loads(version["manifest"])
        volatility = manifest.get("volatility", "pure")
        if baseline_matches and volatility in {"nondeterministic", "external"}:
            irrecoverable.append(slug)
            continue
        estimate = _cost_estimate(store, uid)
        recompute.append((slug, estimate))
    return PreflightResult(recompute=recompute, irrecoverable=irrecoverable)


def adopt(
    store: FlowStore,
    branch: str,
    uid: str,
    version_id: str,
    *,
    from_branch: str,
    actor: str = "agent:unknown",
    intent: str | None = None,
    resolution: Literal["incoming", "current"] | None = None,
    namespace_validator: NamespaceValidator | None = None,
    namespace_change_hook: NamespaceChangeHook | None = None,
) -> Transaction | None:
    target = get_branch(store, branch)
    source = get_branch(store, from_branch)
    incoming = _asset_version(store, uid, version_id)
    source_selection = next(
        (item for item in selections(store, source.branch_id) if item.uid == uid), None
    )
    if source_selection is None or source_selection.version_id != version_id:
        raise ValueError("the source branch does not select the requested version")
    target_selection = next(
        (item for item in selections(store, target.branch_id) if item.uid == uid), None
    )
    if target_selection is not None:
        base_version_id = _common_base_version(store, target, source, uid)
        base_definition = _definition_hash(store, base_version_id)
        target_definition = _definition_hash(store, target_selection.version_id)
        assert target_definition is not None
        target_changed = target_definition != base_definition
        incoming_changed = incoming.definition_hash != base_definition
        if (
            target_changed
            and incoming_changed
            and target_definition != incoming.definition_hash
        ):
            if resolution is None:
                raise AdoptConflictError(
                    uid,
                    base_definition,
                    target_definition,
                    incoming.definition_hash,
                )
            if resolution == "current":
                return None

    namespace = _namespace(store, target.branch_id, excluding_uid=uid)
    conflicts = _manifest_namespace_conflicts(incoming, namespace)
    if namespace_validator is not None:
        conflicts.extend(namespace_validator(incoming, namespace))
    if conflicts and resolution is None:
        raise NamespaceConflictError(conflicts)
    if conflicts and resolution == "current":
        return None

    transaction = store.commit(
        actor=actor,
        intent=intent or f"adopt {incoming.slug} from {source.name}",
        branch=target.branch_id,
        ops=[
            AdoptedOp(
                uid=uid,
                from_branch=source.branch_id,
                version_id=version_id,
            )
        ],
    )
    if namespace_change_hook is not None and conflicts:
        namespace_change_hook(target.branch_id, uid)
    return transaction


def _validate_rewind_step(store: FlowStore, branch: Branch, step: int) -> None:
    if step < 1 or step > store.last_step:
        raise ValueError(f"step must be between 1 and {store.last_step}")
    created_step = (
        _connection(store)
        .execute(
            """
        SELECT MIN(step) FROM transactions
        WHERE EXISTS (
          SELECT 1 FROM json_each(transactions.ops)
          WHERE json_extract(value, '$.op') = 'branch_created'
            AND json_extract(value, '$.branch_id') = ?
        )
        """,
            (branch.branch_id,),
        )
        .fetchone()[0]
    )
    if (
        branch.parent_branch_id is not None
        and created_step is not None
        and step < created_step
    ):
        raise ValueError(f"branch {branch.name} did not exist at step {step}")


def _common_base_version(
    store: FlowStore, target: Branch, source: Branch, uid: str
) -> str | None:
    target_ancestors = _ancestors(store, target)
    source_ancestors = _ancestors(store, source)
    common = next(
        (
            branch
            for branch in target_ancestors.values()
            if branch.branch_id in source_ancestors
        ),
        None,
    )
    if common is None:
        return None
    target_step = _divergence_step(target_ancestors, common.branch_id, store.last_step)
    source_step = _divergence_step(source_ancestors, common.branch_id, store.last_step)
    base_step = min(target_step, source_step)
    state, _baselines = store.index.branch_state_at_step(common.branch_id, base_step)
    selection = state.get(uid)
    return None if selection is None else selection[0]


def _ancestors(store: FlowStore, branch: Branch) -> dict[str, Branch]:
    ancestors: dict[str, Branch] = {}
    current: Branch | None = branch
    while current is not None:
        ancestors[current.branch_id] = current
        current = (
            None
            if current.parent_branch_id is None
            else get_branch(store, current.parent_branch_id)
        )
    return ancestors


def _divergence_step(ancestors: dict[str, Branch], common_id: str, default: int) -> int:
    child = next(
        (
            branch
            for branch in ancestors.values()
            if branch.parent_branch_id == common_id
        ),
        None,
    )
    return default if child is None else child.fork_step


def _asset_version(store: FlowStore, uid: str, version_id: str) -> AssetVersion:
    row = (
        _connection(store)
        .execute(
            "SELECT * FROM asset_versions WHERE uid = ? AND version_id = ?",
            (uid, version_id),
        )
        .fetchone()
    )
    if row is None:
        raise LookupError(f"unknown version {version_id} for cell {uid}")
    return AssetVersion(
        version_id=row["version_id"],
        uid=row["uid"],
        slug=row["slug"],
        source_hash=row["source_hash"],
        bound_hash=row["bound_hash"],
        definition_hash=row["definition_hash"],
        manifest=json.loads(row["manifest"]),
        parent_version_id=row["parent_version_id"],
        author=row["author"],
        created_step=row["created_step"],
    )


def _definition_hash(store: FlowStore, version_id: str | None) -> str | None:
    if version_id is None:
        return None
    row = (
        _connection(store)
        .execute(
            "SELECT definition_hash FROM asset_versions WHERE version_id = ?",
            (version_id,),
        )
        .fetchone()
    )
    return None if row is None else str(row[0])


def _namespace(
    store: FlowStore, branch_id: str, *, excluding_uid: str
) -> dict[str, str]:
    rows = (
        _connection(store)
        .execute(
            """
        SELECT versions.slug, selections.uid
        FROM selections
        JOIN asset_versions AS versions USING(version_id)
        WHERE selections.branch_id = ? AND selections.uid != ?
        """,
            (branch_id, excluding_uid),
        )
        .fetchall()
    )
    return {str(row["slug"]): str(row["uid"]) for row in rows}


def _manifest_namespace_conflicts(
    version: AssetVersion, namespace: dict[str, str]
) -> list[NamespaceConflict]:
    conflicts: list[NamespaceConflict] = []
    occupying_uid = namespace.get(version.slug)
    if occupying_uid is not None and occupying_uid != version.uid:
        conflicts.append(NamespaceConflict(version.slug, version.uid, occupying_uid))
    bindings = version.manifest.get("bindings")
    if isinstance(bindings, dict):
        for reference, bound in bindings.items():
            if not isinstance(reference, str) or not isinstance(bound, str):
                continue
            expected_uid = _bound_uid(bound)
            slug = reference.split(".", 1)[0]
            actual_uid = namespace.get(slug)
            if expected_uid is not None and actual_uid != expected_uid:
                conflicts.append(NamespaceConflict(slug, expected_uid, actual_uid))
    return conflicts


def _bound_uid(reference: str) -> str | None:
    if not reference.startswith("uid:"):
        return None
    return reference.removeprefix("uid:").split(".", 1)[0]


def _outputs_available(store: FlowStore, outputs: dict[str, object]) -> bool:
    for output in outputs.values():
        if not isinstance(output, dict):
            return False
        if output.get("luml_ref"):
            continue
        references = [output.get("value_ref"), output.get("content_hash")]
        if not any(
            isinstance(reference, str) and store.cas.contains("values", reference)
            for reference in references
        ):
            return False
    return True


def _baseline_matches_state(
    store: FlowStore,
    materialization: sqlite3.Row,
    selected_definition: str,
    baselines_at_step: dict[str, str],
) -> bool:
    if materialization["state"] != "succeeded":
        return False
    materialized_definition = _definition_hash(store, materialization["version_id"])
    if materialized_definition != selected_definition:
        return False

    connection = _connection(store)
    inputs = json.loads(materialization["inputs"])
    for input_record in inputs.values():
        if not isinstance(input_record, dict):
            return False
        input_uid = input_record.get("uid")
        output_name = input_record.get("output")
        expected_hash = input_record.get("content_hash")
        if (
            not isinstance(input_uid, str)
            or not isinstance(output_name, str)
            or not isinstance(expected_hash, str)
        ):
            return False
        input_mat_id = baselines_at_step.get(input_uid)
        if input_mat_id is None:
            return False
        upstream = connection.execute(
            "SELECT state, outputs FROM materializations WHERE mat_id = ?",
            (input_mat_id,),
        ).fetchone()
        if upstream is None or upstream["state"] != "succeeded":
            return False
        output = json.loads(upstream["outputs"]).get(output_name)
        if not isinstance(output, dict) or output.get("content_hash") != expected_hash:
            return False
    return True


def _cost_estimate(store: FlowStore, uid: str) -> float | None:
    row = (
        _connection(store)
        .execute(
            """
        SELECT materializations.cost_seconds
        FROM materializations
        JOIN asset_versions USING(version_id)
        WHERE asset_versions.uid = ? AND materializations.state = 'succeeded'
          AND materializations.cost_seconds IS NOT NULL
        ORDER BY COALESCE(materializations.finished_step,
                          materializations.started_step) DESC
        LIMIT 1
        """,
            (uid,),
        )
        .fetchone()
    )
    return None if row is None else float(row[0])


def _branch_from_row(row: sqlite3.Row) -> Branch:
    values = dict(row)
    values["archived"] = bool(values["archived"])
    return Branch.model_validate(values)


def _connection(store: FlowStore) -> sqlite3.Connection:
    connection = store.index.connection
    if connection is None:
        raise RuntimeError("SQLite index is not open")
    return connection
