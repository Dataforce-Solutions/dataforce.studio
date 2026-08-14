from __future__ import annotations

import ast
import json
import re
import sqlite3
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, cast

from lumlflow.flow.dsl.accept import AcceptanceResult, accept_cells
from lumlflow.flow.dsl.normalize import read_flow_cells, write_flow_cells
from lumlflow.flow.hashing import definition_hash
from lumlflow.flow.ids import mint_ulid
from lumlflow.flow.scheduler.staleness import derive_all_staleness
from lumlflow.flow.store import branches
from lumlflow.flow.store.cas import atomic_write
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import (
    CellAcceptedOp,
    JsonValue,
    SelectionSetOp,
    Transaction,
    WorktreeBoundOp,
)


class EditConflictError(RuntimeError):
    def __init__(
        self,
        slug: str,
        base_definition_hash: str,
        current_definition_hash: str,
        current_source: str,
        incoming_source: str,
    ) -> None:
        super().__init__(f"cell changed since editing began: {slug}")
        self.slug = slug
        self.base_definition_hash = base_definition_hash
        self.current_definition_hash = current_definition_hash
        self.current_source = current_source
        self.incoming_source = incoming_source

    @property
    def menu(self) -> list[dict[str, JsonValue]]:
        return [
            {"action": "fork-my-edit", "suggested": True},
            {"action": "overwrite", "suggested": False},
        ]


class ParamEditConflictError(RuntimeError):
    def __init__(
        self,
        slug: str,
        base_definition_hash: str,
        current_definition_hash: str,
        current_params: dict[str, JsonValue],
        incoming_params: dict[str, JsonValue],
    ) -> None:
        super().__init__(f"cell changed since parameter editing began: {slug}")
        self.slug = slug
        self.base_definition_hash = base_definition_hash
        self.current_definition_hash = current_definition_hash
        self.current_params = current_params
        self.incoming_params = incoming_params

    @property
    def menu(self) -> list[dict[str, JsonValue]]:
        return [
            {"action": "fork-my-edit", "suggested": True},
            {"action": "overwrite", "suggested": False},
        ]


@dataclass(frozen=True)
class PendingProjection:
    branch_id: str
    uid: str
    version_id: str
    slug: str
    base_version_id: str | None


@dataclass(frozen=True)
class NewCellResult:
    accepted: AcceptanceResult
    suggested_slug: str


@dataclass(frozen=True)
class ParamEditResult:
    uid: str
    version_id: str
    slug: str
    definition_hash: str
    params: dict[str, JsonValue]
    transaction: Transaction | None
    branch_id: str


class ProjectionManager:
    def __init__(self, store: FlowStore) -> None:
        self.store = store
        self.flow_dir = store.flow_dir.resolve()
        self.pending_path = store.store_dir / "pending-projections.json"
        self._operation_lock = threading.RLock()

    @contextmanager
    def operation_lock(
        self, *, actor: str | None = None, force: bool = False
    ) -> Iterator[None]:
        holder = self.lock_holder
        if holder is not None and holder != actor and not force:
            raise branches.WorktreeLockedError(f"worktree is locked by {holder}")
        with self._operation_lock:
            yield

    @property
    def lock_holder(self) -> str | None:
        row = self._worktree_row()
        return (
            None
            if row is None or row["lock_holder"] is None
            else str(row["lock_holder"])
        )

    @property
    def checked_out_branch(self) -> str | None:
        row = self._worktree_row()
        return None if row is None else str(row["branch_id"])

    def recover_stale_session(self) -> str | None:
        holder = self.lock_holder
        if holder is None:
            return None
        self.store.commit(
            actor="system:daemon",
            intent=f"recover stale agent session {holder}",
            ops=[
                WorktreeBoundOp(
                    path=str(self.flow_dir),
                    branch_id=self.store.branch_id,
                    actor=None,
                    lock_holder=None,
                )
            ],
        )
        return holder

    def agent_begin(self, actor: str, *, intent: str | None = None) -> None:
        if not actor:
            raise ValueError("actor must not be empty")
        current_holder = self.lock_holder
        if current_holder is not None and current_holder != actor:
            raise branches.WorktreeLockedError(
                f"worktree is locked by {current_holder}"
            )
        self.store.commit(
            actor=actor,
            intent=intent or f"agent begin {actor}",
            ops=[
                WorktreeBoundOp(
                    path=str(self.flow_dir),
                    branch_id=self.store.branch_id,
                    actor=actor,
                    lock_holder=actor,
                )
            ],
        )

    def agent_end(self, actor: str, *, intent: str | None = None) -> None:
        if self.lock_holder != actor:
            raise branches.WorktreeLockedError(f"worktree is not locked by {actor}")
        self.store.commit(
            actor=actor,
            intent=intent or f"agent end {actor}",
            ops=[
                WorktreeBoundOp(
                    path=str(self.flow_dir),
                    branch_id=self.store.branch_id,
                    actor=actor,
                    lock_holder=None,
                )
            ],
        )

    def switch(
        self,
        branch: str,
        *,
        actor: str = "user",
        intent: str | None = None,
        force: bool = False,
    ) -> None:
        with self.operation_lock(actor=actor, force=force):
            transaction = branches.switch(
                self.store,
                branch,
                actor=actor,
                intent=intent,
                force=force,
            )
            self.project_slice(transaction.branch)

    def project_slice(self, branch_id: str | None = None) -> None:
        target_branch = branch_id or self.store.branch_id
        selected = self._selected_versions(target_branch)
        desired_paths: set[Path] = set()
        flow_cells: dict[str, str] = {}
        for uid, _version_id, slug, source_hash, _definition in selected:
            path = self.flow_dir / "cells" / f"{slug}.py"
            desired_paths.add(path.resolve())
            flow_cells[slug] = uid
            source = self.store.cas.get("objects", source_hash)
            if not path.exists() or path.read_bytes() != source:
                atomic_write(path, source)
        for path in (self.flow_dir / "cells").glob("*.py"):
            if path.resolve() not in desired_paths:
                path.unlink()
        write_flow_cells(self.flow_dir, flow_cells)
        self._write_pending([])

    def edit_cell(
        self,
        slug: str,
        source: str,
        *,
        base_definition_hash: str,
        branch: str | None = None,
        actor: str = "user",
        intent: str | None = None,
        resolution: Literal["overwrite", "fork-my-edit"] | None = None,
        project: bool = True,
    ) -> AcceptanceResult:
        target_branch = branches.get_branch(
            self.store, branch or self.store.branch_id
        ).branch_id
        current = self._selected_by_slug(target_branch, slug)
        if current is None:
            raise LookupError(f"cell not found: {slug}")
        uid, current_version, _current_slug, source_hash, current_definition = current
        if current_definition != base_definition_hash and resolution is None:
            raise EditConflictError(
                slug,
                base_definition_hash,
                current_definition,
                self.store.cas.get("objects", source_hash).decode(),
                source,
            )
        if resolution == "fork-my-edit":
            fork_name = self._available_branch_name(f"edit/{slug}")
            target_branch = branches.fork(
                self.store, target_branch, fork_name, actor=actor
            ).branch_id
            current_version = (
                self._selected_version(target_branch, uid) or current_version
            )

        return self._accept_daemon_source(
            slug,
            source,
            target_branch,
            actor=actor,
            intent=intent or f"edit {slug}",
            base_version_id=current_version,
            project=project,
        )

    def edit_params(
        self,
        slug: str,
        params: dict[str, JsonValue],
        *,
        base_definition_hash: str,
        branch: str | None = None,
        actor: str = "user",
        intent: str | None = None,
        resolution: Literal["overwrite", "fork-my-edit"] | None = None,
    ) -> ParamEditResult:
        target_branch = branches.get_branch(
            self.store, branch or self.store.branch_id
        ).branch_id
        current = self._selected_by_slug(target_branch, slug)
        if current is None:
            raise LookupError(f"cell not found: {slug}")
        uid, current_version, _current_slug, _source_hash, current_definition = current
        row = self._asset_version(current_version)
        manifest = self._selected_manifest(current_version)
        current_params = manifest.get("params", {})
        if not isinstance(current_params, dict):
            current_params = {}
        normalized_current = cast(dict[str, JsonValue], current_params)
        if current_definition != base_definition_hash and resolution is None:
            raise ParamEditConflictError(
                slug,
                base_definition_hash,
                current_definition,
                normalized_current,
                params,
            )
        if resolution == "fork-my-edit":
            target_branch = branches.fork(
                self.store,
                target_branch,
                self._available_branch_name(f"edit/{slug}"),
                actor=actor,
            ).branch_id
            current_version = (
                self._selected_version(target_branch, uid) or current_version
            )
            row = self._asset_version(current_version)
            manifest = self._selected_manifest(current_version)
        if normalized_current == params:
            return ParamEditResult(
                uid=uid,
                version_id=current_version,
                slug=slug,
                definition_hash=current_definition,
                params=params,
                transaction=None,
                branch_id=target_branch,
            )

        raw_flags = manifest.pop("flags", [])
        flags = (
            [item for item in raw_flags if isinstance(item, str)]
            if isinstance(raw_flags, list)
            else []
        )
        manifest["params"] = cast(JsonValue, params)
        bound_source = self.store.cas.get("objects", str(row["bound_hash"])).decode()
        updated_definition = definition_hash(bound_source, params)
        version_id = mint_ulid()
        transaction = self.store.commit(
            actor=actor,
            intent=intent or f"edit {slug} params",
            branch=target_branch,
            ops=[
                CellAcceptedOp(
                    uid=uid,
                    version_id=version_id,
                    slug=slug,
                    source_hash=str(row["source_hash"]),
                    bound_hash=str(row["bound_hash"]),
                    definition_hash=updated_definition,
                    manifest=manifest,
                    flags=flags,
                    parent_version=current_version,
                    author=actor,
                ),
                SelectionSetOp(uid=uid, version_id=version_id, pinned=True),
            ],
        )
        return ParamEditResult(
            uid=uid,
            version_id=version_id,
            slug=slug,
            definition_hash=updated_definition,
            params=params,
            transaction=transaction,
            branch_id=target_branch,
        )

    def new_cell(
        self,
        source: str,
        *,
        slug: str | None = None,
        branch: str | None = None,
        actor: str = "user",
        intent: str | None = None,
        project: bool = True,
    ) -> NewCellResult:
        target_branch = branches.get_branch(
            self.store, branch or self.store.branch_id
        ).branch_id
        selected_slug = (
            self._available_placeholder_slug(target_branch)
            if slug is None
            else self._validate_new_slug(target_branch, slug)
        )
        accepted = self._accept_daemon_source(
            selected_slug,
            source,
            target_branch,
            actor=actor,
            intent=intent or f"new cell {selected_slug}",
            base_version_id=None,
            project=project,
            extra_flags=["placeholder_slug"] if slug is None else None,
        )
        return NewCellResult(
            accepted=accepted,
            suggested_slug=_suggest_slug(source) or selected_slug,
        )

    def scaffold_cell(self, slug: str, after: str | None = None) -> str:
        class_name = "".join(part.capitalize() for part in slug.split("_"))
        if not class_name:
            raise ValueError("cell slug must contain a letter or number")
        consumes: dict[str, str] = {}
        if after is not None:
            row = self._selected_by_slug(self.store.branch_id, after)
            if row is None:
                raise LookupError(f"cell not found: {after}")
            manifest = self._selected_manifest(row[1])
            produces = manifest.get("produces", {})
            if isinstance(produces, dict):
                consumes = {name: f"{after}.{name}" for name in produces}
        arguments = ", ".join(["self", "ctx", *consumes])
        return (
            "from __future__ import annotations\n\n"
            "from typing import TYPE_CHECKING\n\n"
            "if TYPE_CHECKING:\n"
            "    from lumlflow_typing import CellProtocol\n\n\n"
            f"class {class_name}:\n"
            f"    consumes = {consumes!r}\n"
            '    produces = {"result": "asset"}\n\n'
            f"    def materialize({arguments}):\n"
            '        return {"result": None}\n\n\n'
            "if TYPE_CHECKING:\n"
            f"    _check: CellProtocol = {class_name}()\n"
        )

    def refresh_generated_docs(self) -> None:
        atomic_write(self.flow_dir / "AGENTS.md", self._agents_guide().encode())
        atomic_write(self.store.store_dir / "CHECKOUT.md", self._checkout().encode())

    def pending(self) -> list[PendingProjection]:
        if not self.pending_path.exists():
            return []
        try:
            payload = json.loads(self.pending_path.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                return []
            return [
                PendingProjection(**item) for item in payload if isinstance(item, dict)
            ]
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return []

    def add_pending(self, pending: PendingProjection) -> None:
        entries = [entry for entry in self.pending() if entry.uid != pending.uid]
        entries.append(pending)
        self._write_pending(entries)

    def pending_for_slug(self, slug: str) -> PendingProjection | None:
        return next((entry for entry in self.pending() if entry.slug == slug), None)

    def discard_pending(self, uid: str) -> None:
        self._write_pending([entry for entry in self.pending() if entry.uid != uid])

    def flush_pending(self) -> list[str]:
        if self.lock_holder is not None:
            return []
        projected: list[str] = []
        remaining: list[PendingProjection] = []
        active_branch = self.checked_out_branch or self.store.branch_id
        for entry in self.pending():
            if entry.branch_id != active_branch:
                remaining.append(entry)
                continue
            if self._selected_version(entry.branch_id, entry.uid) != entry.version_id:
                continue
            row = self._version(entry.version_id)
            if row is None:
                continue
            source = self.store.cas.get("objects", str(row["source_hash"]))
            atomic_write(self.flow_dir / "cells" / f"{entry.slug}.py", source)
            projected.append(entry.slug)
        self._write_pending(remaining)
        return projected

    def _accept_daemon_source(
        self,
        slug: str,
        source: str,
        branch_id: str,
        *,
        actor: str,
        intent: str,
        base_version_id: str | None,
        project: bool,
        extra_flags: list[str] | None = None,
    ) -> AcceptanceResult:
        path = self.flow_dir / "cells" / f"{slug}.py"
        scratch = self.store.store_dir / "kernel" / "scratch"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="edit-", dir=scratch) as temporary:
            staging_root = Path(temporary)
            staged_path = staging_root / "cells" / f"{slug}.py"
            staged_path.parent.mkdir()
            atomic_write(staged_path, source.encode())
            accepted = accept_cells(
                self.store,
                [staged_path],
                branch=branch_id,
                actor=actor,
                intent=intent,
                parent_versions={slug: base_version_id},
                extra_flags=extra_flags,
                source_root=staging_root,
            )[0]
        accepted = replace(accepted, path=path)
        active_branch = self.checked_out_branch or self.store.branch_id
        should_project = (
            project and active_branch == branch_id and self.lock_holder is None
        )
        if should_project:
            row = self._version(accepted.version_id)
            assert row is not None
            atomic_write(path, self.store.cas.get("objects", str(row["source_hash"])))
            return accepted
        if project and active_branch == branch_id:
            self.add_pending(
                PendingProjection(
                    branch_id=branch_id,
                    uid=accepted.uid,
                    version_id=accepted.version_id,
                    slug=accepted.slug,
                    base_version_id=base_version_id,
                )
            )
        return accepted

    def _selected_versions(
        self, branch_id: str
    ) -> list[tuple[str, str, str, str, str]]:
        connection = self.store.index.connection
        if connection is None:
            raise RuntimeError("store index is closed")
        rows = connection.execute(
            """
            SELECT selections.uid, selections.version_id, versions.slug,
                   versions.source_hash, versions.definition_hash
            FROM selections JOIN asset_versions AS versions USING(version_id)
            WHERE selections.branch_id = ? ORDER BY versions.slug
            """,
            (branch_id,),
        ).fetchall()
        return [cast(tuple[str, str, str, str, str], tuple(row)) for row in rows]

    def _selected_by_slug(
        self, branch_id: str, slug: str
    ) -> tuple[str, str, str, str, str] | None:
        return next(
            (row for row in self._selected_versions(branch_id) if row[2] == slug),
            None,
        )

    def _selected_version(self, branch_id: str, uid: str) -> str | None:
        return next(
            (
                version
                for row_uid, version, *_rest in self._selected_versions(branch_id)
                if row_uid == uid
            ),
            None,
        )

    def _version(self, version_id: str) -> sqlite3.Row | None:
        connection = self.store.index.connection
        if connection is None:
            raise RuntimeError("store index is closed")
        return connection.execute(
            "SELECT source_hash FROM asset_versions WHERE version_id = ?",
            (version_id,),
        ).fetchone()

    def _asset_version(self, version_id: str) -> sqlite3.Row:
        connection = self.store.index.connection
        if connection is None:
            raise RuntimeError("store index is closed")
        row = connection.execute(
            "SELECT * FROM asset_versions WHERE version_id = ?", (version_id,)
        ).fetchone()
        if row is None:
            raise LookupError("cell version not found")
        return row

    def _write_pending(self, pending: list[PendingProjection]) -> None:
        if not pending:
            self.pending_path.unlink(missing_ok=True)
            return
        payload = [entry.__dict__ for entry in pending]
        atomic_write(
            self.pending_path,
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(),
        )

    def _worktree_row(self) -> sqlite3.Row | None:
        connection = self.store.index.connection
        if connection is None:
            raise RuntimeError("store index is closed")
        return connection.execute(
            "SELECT branch_id, actor, lock_holder FROM worktrees WHERE path = ?",
            (str(self.flow_dir),),
        ).fetchone()

    def _available_placeholder_slug(self, branch_id: str) -> str:
        selected = {row[2] for row in self._selected_versions(branch_id)}
        selected.update(read_flow_cells(self.flow_dir))
        counter = 1
        while f"untitled_{counter}" in selected:
            counter += 1
        return f"untitled_{counter}"

    def _validate_new_slug(self, branch_id: str, slug: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", slug):
            raise ValueError("cell slug must be lowercase snake_case")
        if self._selected_by_slug(branch_id, slug) is not None:
            raise ValueError(f"cell already exists: {slug}")
        return slug

    def _selected_manifest(self, version_id: str) -> dict[str, JsonValue]:
        connection = self.store.index.connection
        if connection is None:
            raise RuntimeError("store index is closed")
        row = connection.execute(
            "SELECT manifest FROM asset_versions WHERE version_id = ?",
            (version_id,),
        ).fetchone()
        if row is None:
            raise LookupError("cell version not found")
        value = json.loads(str(row[0]))
        return cast(dict[str, JsonValue], value)

    def _agents_guide(self) -> str:
        return """# Lumlflow agent quickstart
1. Run `lumlflow context` first.
2. Cells are named files in `cells/`; always name new cells.
3. After each edit, run `lumlflow run <cell>`; stale dependencies run first.
4. Inspect `lumlflow status`; failures include a traceback and plain cause.
5. Fix the failing cell and rerun it until status reports `synced`.
6. Cell classes are importless; declarations are literal class attributes.
7. Use `consumes = {"input": "producer.output"}` for dependencies.
8. Use `produces = {"output": "asset"}` and return the same keys.
9. Output types are `asset`, `model`, `dataset`, and `experiment`.
10. Declare `asset` unless you mean to publish; use `promote` later.
11. Metric values are dicts with `name`, `value`, and optional `step`.
12. Eval values are lists of dict rows with inputs, outputs, and scores.
13. Treat consumed inputs as immutable; return a new value.
14. Read workspace files through `ctx.flow_dir`; they are not versioned.
15. Use `params` for literal configuration and `ctx.secret()` for secrets.
16. Use `lumlflow cells new <name> --after <producer>` to scaffold wiring.
17. Use `lumlflow tree`, `graph`, `diff`, and `asset preview` to inspect.
18. See `.lumlflow/CHECKOUT.md` for the current branch and staleness.
"""

    def _checkout(self) -> str:
        branch = branches.get_branch(self.store, self.store.branch_id)
        verdicts = derive_all_staleness(self.store, branch.branch_id)
        counts: dict[str, int] = {}
        for views in verdicts.values():
            state = views.transitive.state
            counts[state] = counts.get(state, 0) + 1
        summary = (
            ", ".join(f"{state}: {count}" for state, count in sorted(counts.items()))
            or "no cells"
        )
        return (
            "# Lumlflow checkout\n\n"
            f"Branch: {branch.name}\n\n"
            f"Checkpoint: step {self.store.last_step}\n\n"
            f"Staleness: {summary}\n"
        )

    def _available_branch_name(self, prefix: str) -> str:
        names = {branch.name for branch in branches.list_branches(self.store)}
        if prefix not in names:
            return prefix
        counter = 2
        while f"{prefix}-{counter}" in names:
            counter += 1
        return f"{prefix}-{counter}"


def _suggest_slug(source: str) -> str | None:
    try:
        module = ast.parse(source)
    except SyntaxError:
        return None
    cell_class = next(
        (node for node in module.body if isinstance(node, ast.ClassDef)), None
    )
    if cell_class is None:
        return None
    words = re.sub(r"(?<!^)(?=[A-Z])", "_", cell_class.name).lower()
    return re.sub(r"[^a-z0-9_]+", "_", words).strip("_") or None
