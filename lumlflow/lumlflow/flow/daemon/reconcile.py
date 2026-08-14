from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from lumlflow.flow.dsl.accept import AcceptanceResult, accept_cells
from lumlflow.flow.dsl.loader import load_cell
from lumlflow.flow.hashing import sha256_bytes
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import CellRemovedOp, FlagSetOp, FlowOp

from .projections import ProjectionManager

type ReconciliationTier = Literal["live", "quiesce", "cold"]


@dataclass(frozen=True)
class ReconciliationResult:
    accepted: list[AcceptanceResult]
    removed: list[str]
    projected: list[str]
    lib_changed: list[str]

    @property
    def changed(self) -> bool:
        return bool(self.accepted or self.removed or self.projected or self.lib_changed)


class Reconciler:
    def __init__(self, store: FlowStore, projections: ProjectionManager) -> None:
        self.store = store
        self.projections = projections
        self._lib_hashes = self._current_lib_hashes()

    def reconcile(
        self,
        tier: ReconciliationTier,
        *,
        paths: set[Path] | None = None,
        actor: str | None = None,
        intent: str | None = None,
        mixed_editing: bool = False,
    ) -> ReconciliationResult:
        effective_actor = actor or "user"
        holder = self.projections.lock_holder
        if holder is not None and actor != holder:
            return ReconciliationResult([], [], [], [])

        scoped_paths = None if tier in {"cold", "quiesce"} else paths
        selected = self._selected_by_slug()
        changed_paths: list[Path] = []
        parent_versions: dict[str, str | None | object] = {}
        projected: list[str] = []
        pending_to_discard: list[str] = []

        for path in self._cell_paths(scoped_paths):
            slug = path.stem
            current = selected.get(slug)
            source_hash = sha256_bytes(path.read_bytes())
            if current is not None and source_hash == current[2]:
                continue

            pending = self.projections.pending_for_slug(slug)
            if pending is not None:
                base_hash = self._version_source_hash(pending.base_version_id)
                if source_hash == base_hash and holder is None:
                    projected.extend(self.projections.flush_pending())
                    continue
                parent_versions[slug] = pending.base_version_id
                pending_to_discard.append(pending.uid)
                changed_paths.append(path)
                continue

            if (
                tier == "cold"
                and current is not None
                and self._is_known_source(current[0], source_hash)
            ):
                if holder is None:
                    self.projections.project_slice(self.store.branch_id)
                    projected.append(slug)
                continue
            changed_paths.append(path)
            if current is not None:
                parent_versions[slug] = current[1]

        changed_count = len(changed_paths)
        existing_slugs = {path.stem for path in self._cell_paths(None)}
        existing_uids = {
            loaded.uid
            for path in self._cell_paths(None)
            if (loaded := load_cell(path, self.store.flow_dir)).uid is not None
        }
        removed = sorted(
            slug
            for slug, (uid, _version, _source) in selected.items()
            if slug not in existing_slugs and uid not in existing_uids
        )
        offline_intent = (
            f"offline edits: {changed_count + len(removed)} cells changed"
            if tier == "cold"
            else None
        )
        lib_hashes, lib_changed = self._changed_libs(scoped_paths)
        extra_ops: list[FlowOp] = [
            CellRemovedOp(uid=selected[slug][0]) for slug in removed
        ]
        extra_ops.extend(FlagSetOp(flag=f"lib_changed:{path}") for path in lib_changed)
        default_intent = offline_intent
        if default_intent is None and lib_changed and not changed_paths and not removed:
            default_intent = f"lib changed: {', '.join(lib_changed)}"
        with self.projections.operation_lock(actor=effective_actor):
            accepted = accept_cells(
                self.store,
                [path for path in changed_paths if path.exists()],
                actor=effective_actor,
                intent=intent or default_intent,
                parent_versions=parent_versions,
                offline=tier == "cold",
                extra_flags=["mixed_editing"] if mixed_editing else None,
                extra_ops=extra_ops,
                remove_slugs=removed,
            )
        for uid in pending_to_discard:
            self.projections.discard_pending(uid)

        if lib_changed:
            self._lib_hashes = lib_hashes
        return ReconciliationResult(accepted, removed, projected, lib_changed)

    def _selected_by_slug(self) -> dict[str, tuple[str, str, str]]:
        connection = self.store.index.connection
        if connection is None:
            raise RuntimeError("store index is closed")
        rows = connection.execute(
            """
            SELECT versions.slug, selections.uid, selections.version_id,
                   versions.source_hash
            FROM selections JOIN asset_versions AS versions USING(version_id)
            WHERE selections.branch_id = ?
            """,
            (self.store.branch_id,),
        ).fetchall()
        return {
            str(row["slug"]): (
                str(row["uid"]),
                str(row["version_id"]),
                str(row["source_hash"]),
            )
            for row in rows
        }

    def _cell_paths(self, paths: set[Path] | None) -> list[Path]:
        if paths is None:
            return sorted((self.store.flow_dir / "cells").glob("*.py"))
        return sorted(
            path
            for path in {candidate.resolve() for candidate in paths}
            if path.exists() and self._is_cell_path(path)
        )

    def _is_cell_path(self, path: Path) -> bool:
        try:
            relative = path.relative_to(self.store.flow_dir.resolve())
        except ValueError:
            return False
        return (
            len(relative.parts) == 2
            and relative.parts[0] == "cells"
            and path.suffix == ".py"
        )

    def _is_known_source(self, uid: str, source_hash: str) -> bool:
        connection = self.store.index.connection
        if connection is None:
            raise RuntimeError("store index is closed")
        return (
            connection.execute(
                "SELECT 1 FROM asset_versions WHERE uid = ? AND source_hash = ?",
                (uid, source_hash),
            ).fetchone()
            is not None
        )

    def _version_source_hash(self, version_id: str | None) -> str | None:
        if version_id is None:
            return None
        connection = self.store.index.connection
        if connection is None:
            raise RuntimeError("store index is closed")
        row = connection.execute(
            "SELECT source_hash FROM asset_versions WHERE version_id = ?",
            (version_id,),
        ).fetchone()
        return None if row is None else str(row[0])

    def _current_lib_hashes(self) -> dict[str, str]:
        hashes: dict[str, str] = {}
        for path in self.store.flow_dir.rglob("*.py"):
            relative = path.relative_to(self.store.flow_dir)
            if relative.parts[0] in {"cells", ".lumlflow", ".venv"}:
                continue
            hashes[relative.as_posix()] = sha256_bytes(path.read_bytes())
        return hashes

    def _changed_libs(
        self, paths: set[Path] | None
    ) -> tuple[dict[str, str], list[str]]:
        current = self._current_lib_hashes()
        changed = sorted(
            path
            for path in self._lib_hashes.keys() | current.keys()
            if self._lib_hashes.get(path) != current.get(path)
        )
        if paths is not None:
            scoped = {
                candidate.resolve()
                .relative_to(self.store.flow_dir.resolve())
                .as_posix()
                for candidate in paths
                if candidate.resolve().is_relative_to(self.store.flow_dir.resolve())
            }
            changed = [path for path in changed if path in scoped]
        return current, changed


def is_observed_path(flow_dir: Path, path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(flow_dir.resolve())
    except ValueError:
        return False
    if not relative.parts or relative.parts[0] in {".lumlflow", ".venv"}:
        return False
    if len(relative.parts) == 2 and relative.parts[0] == "cells":
        return path.suffix == ".py"
    if path.suffix != ".py":
        return False
    return True
