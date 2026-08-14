from __future__ import annotations

import ast
import json
import pprint
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from lumlflow.flow.dsl.accept import AcceptanceResult, accept_cells
from lumlflow.flow.dsl.normalize import write_flow_cells
from lumlflow.flow.hashing import canonical_json
from lumlflow.flow.ids import is_ulid
from lumlflow.flow.store.branches import get_branch
from lumlflow.flow.store.cas import atomic_write
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import JsonValue

_EXPORT_NAME = "LUMLFLOW_EXPORT"
_HASH = re.compile(r"[0-9a-f]{64}")
_SLUG = re.compile(r"[a-z][a-z0-9_]*")


@dataclass(frozen=True)
class PortableCell:
    slug: str
    uid: str
    source: str
    params: dict[str, JsonValue]
    definition_hash: str


@dataclass(frozen=True)
class FlowProjection:
    branch: str
    cells: tuple[PortableCell, ...]
    source: str


def export_projection(store: FlowStore, branch: str | None = None) -> FlowProjection:
    selected_branch = get_branch(store, branch or store.branch_id)
    connection = store.index.connection
    if connection is None:
        raise RuntimeError("store index is closed")
    rows = connection.execute(
        """
        SELECT selections.uid, versions.slug, versions.source_hash,
               versions.definition_hash, versions.manifest
        FROM selections
        JOIN asset_versions AS versions USING(version_id)
        WHERE selections.branch_id = ?
        ORDER BY versions.slug
        """,
        (selected_branch.branch_id,),
    ).fetchall()
    cells: list[PortableCell] = []
    for row in rows:
        manifest = json.loads(str(row["manifest"]))
        raw_params = manifest.get("params", {}) if isinstance(manifest, dict) else {}
        params = (
            cast(dict[str, JsonValue], raw_params)
            if isinstance(raw_params, dict)
            else {}
        )
        cells.append(
            PortableCell(
                slug=str(row["slug"]),
                uid=str(row["uid"]),
                source=store.cas.get("objects", str(row["source_hash"])).decode(),
                params=params,
                definition_hash=str(row["definition_hash"]),
            )
        )
    _ensure_unique_slugs(cells)
    payload: dict[str, JsonValue] = {
        "format": 1,
        "cells": [
            {
                "definition_hash": cell.definition_hash,
                "params": cell.params,
                "slug": cell.slug,
                "source": cell.source,
                "uid": cell.uid,
            }
            for cell in cells
        ],
    }
    source = (
        "# Deterministic lumlflow single-file export.\n"
        f"{_EXPORT_NAME} = "
        + pprint.pformat(payload, sort_dicts=True, width=88)
        + "\n"
    )
    return FlowProjection(
        branch=selected_branch.name,
        cells=tuple(cells),
        source=source,
    )


def parse_projection(source: str) -> tuple[PortableCell, ...]:
    try:
        module = ast.parse(source)
    except SyntaxError as error:
        raise ValueError("invalid lumlflow export: malformed Python") from error
    if len(module.body) != 1:
        raise ValueError("invalid lumlflow export: expected one data assignment")
    statement = module.body[0]
    if not (
        isinstance(statement, ast.Assign)
        and len(statement.targets) == 1
        and isinstance(statement.targets[0], ast.Name)
        and statement.targets[0].id == _EXPORT_NAME
    ):
        raise ValueError(f"invalid lumlflow export: missing {_EXPORT_NAME}")
    try:
        payload = ast.literal_eval(statement.value)
    except (ValueError, TypeError, SyntaxError) as error:
        raise ValueError("invalid lumlflow export: data must be literal") from error
    if not isinstance(payload, dict) or payload.get("format") != 1:
        raise ValueError("unsupported lumlflow export format")
    raw_cells = payload.get("cells")
    if not isinstance(raw_cells, list):
        raise ValueError("invalid lumlflow export: cells must be a list")
    cells = tuple(_parse_cell(item) for item in raw_cells)
    _ensure_unique_slugs(cells)
    uids = [cell.uid for cell in cells]
    if len(uids) != len(set(uids)):
        raise ValueError("invalid lumlflow export: duplicate cell uid")
    return cells


def import_projection(
    source_path: str | Path,
    destination: str | Path,
    *,
    name: str | None = None,
    actor: str = "user",
    intent: str | None = None,
) -> FlowStore:
    source = Path(source_path)
    cells = parse_projection(source.read_text(encoding="utf-8"))
    root = Path(destination)
    if root.exists():
        raise FileExistsError(f"import destination already exists: {root}")
    store = FlowStore.init(
        root,
        name=name,
        actor=actor,
        intent=intent or f"import {source.name}",
    )
    try:
        write_flow_cells(root, {cell.slug: cell.uid for cell in cells})
        paths: list[str | Path] = []
        for cell in cells:
            path = root / "cells" / f"{cell.slug}.py"
            atomic_write(path, cell.source.encode())
            paths.append(path)
        accepted = accept_cells(
            store,
            paths,
            actor=actor,
            intent=intent or f"import {source.name}",
        )
        _restore_params(store, cells, accepted, actor, intent)
        _verify_import(store, cells)
    except BaseException:
        store.close()
        raise
    return store


def _parse_cell(value: object) -> PortableCell:
    if not isinstance(value, dict):
        raise ValueError("invalid lumlflow export: cell must be an object")
    slug = value.get("slug")
    uid = value.get("uid")
    source = value.get("source")
    params = value.get("params")
    definition = value.get("definition_hash")
    if not isinstance(slug, str) or _SLUG.fullmatch(slug) is None:
        raise ValueError("invalid lumlflow export: invalid cell slug")
    if not isinstance(uid, str) or not is_ulid(uid):
        raise ValueError(f"invalid lumlflow export: invalid uid for {slug}")
    if not isinstance(source, str):
        raise ValueError(f"invalid lumlflow export: invalid source for {slug}")
    if not isinstance(params, dict) or not all(
        isinstance(key, str) for key in params
    ):
        raise ValueError(f"invalid lumlflow export: invalid params for {slug}")
    try:
        canonical_json(cast(JsonValue, params))
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"invalid lumlflow export: invalid params for {slug}"
        ) from error
    if not isinstance(definition, str) or _HASH.fullmatch(definition) is None:
        raise ValueError(f"invalid lumlflow export: invalid definition for {slug}")
    return PortableCell(
        slug=slug,
        uid=uid,
        source=source,
        params=cast(dict[str, JsonValue], params),
        definition_hash=definition,
    )


def _ensure_unique_slugs(cells: list[PortableCell] | tuple[PortableCell, ...]) -> None:
    slugs = [cell.slug for cell in cells]
    if len(slugs) != len(set(slugs)):
        raise ValueError("active slice contains duplicate cell slugs")


def _restore_params(
    store: FlowStore,
    cells: tuple[PortableCell, ...],
    accepted: list[AcceptanceResult],
    actor: str,
    intent: str | None,
) -> None:
    from lumlflow.flow.daemon.projections import ProjectionManager

    manager = ProjectionManager(store)
    accepted_by_slug = {result.slug: result for result in accepted}
    for cell in cells:
        result = accepted_by_slug[cell.slug]
        if result.definition_hash == cell.definition_hash:
            continue
        manager.edit_params(
            cell.slug,
            cell.params,
            base_definition_hash=result.definition_hash,
            actor=actor,
            intent=intent or f"restore {cell.slug} params",
        )


def _verify_import(store: FlowStore, cells: tuple[PortableCell, ...]) -> None:
    connection = store.index.connection
    if connection is None:
        raise RuntimeError("store index is closed")
    rows = connection.execute(
        """
        SELECT selections.uid, versions.slug, versions.definition_hash
        FROM selections
        JOIN asset_versions AS versions USING(version_id)
        WHERE selections.branch_id = ?
        """,
        (store.branch_id,),
    ).fetchall()
    actual = {
        str(row["slug"]): (str(row["uid"]), str(row["definition_hash"]))
        for row in rows
    }
    expected = {
        cell.slug: (cell.uid, cell.definition_hash)
        for cell in cells
    }
    if actual != expected:
        raise ValueError("imported flow does not match the exported active slice")


__all__ = [
    "FlowProjection",
    "PortableCell",
    "export_projection",
    "import_projection",
    "parse_projection",
]
