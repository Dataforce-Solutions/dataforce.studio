import difflib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from lumlflow.flow.hashing import (
    definition_hash as hash_definition,
)
from lumlflow.flow.hashing import (
    lib_tree_hash,
    sha256_bytes,
)
from lumlflow.flow.ids import mint_ulid
from lumlflow.flow.store.cas import atomic_write
from lumlflow.flow.store.flowstore import CASWrite, FlowStore
from lumlflow.flow.store.models import (
    CellAcceptedOp,
    FlowOp,
    JsonValue,
    RenamedOp,
    SelectionSetOp,
    Transaction,
)

from .loader import LoadedCell, load_cell
from .normalize import (
    bound_class_source,
    normalize_slug,
    read_flow_cells,
    rewrite_consumes,
    write_flow_cells,
    write_uid,
)

_UNSET = object()


@dataclass(frozen=True)
class AcceptanceResult:
    path: Path
    uid: str
    version_id: str
    slug: str
    definition_hash: str
    flags: list[str]
    issues: list[str]
    transaction: Transaction
    selected: bool
    copied_from: str | None = None
    renamed_from: str | None = None


@dataclass(frozen=True)
class _PreparedAcceptance:
    path: Path
    loaded: LoadedCell
    uid: str
    copied_from: str | None
    renamed_from: str | None
    operations: list[FlowOp]
    blobs: list[CASWrite]
    definition_hash: str
    flags: list[str]
    issues: list[str]
    version_id: str
    selected: bool


@dataclass(frozen=True)
class _Namespace:
    slugs: dict[str, str]
    outputs: dict[str, list[tuple[str, str]]]

    @property
    def references(self) -> list[str]:
        return sorted(
            f"{slug}.{output}"
            for output, producers in self.outputs.items()
            for slug, _uid in producers
        )


def accept_cell(
    store: FlowStore,
    path: str | Path,
    *,
    branch: str | None = None,
    actor: str = "user",
    intent: str | None = None,
    parent_version: str | None | object = _UNSET,
) -> AcceptanceResult:
    return accept_cells(
        store,
        [path],
        branch=branch,
        actor=actor,
        intent=intent,
        parent_versions={"*": parent_version},
    )[0]


def accept_cells(
    store: FlowStore,
    paths: list[str | Path],
    *,
    branch: str | None = None,
    actor: str = "user",
    intent: str | None = None,
    parent_versions: dict[str, str | None | object] | None = None,
    offline: bool = False,
    extra_flags: list[str] | None = None,
    extra_ops: list[FlowOp] | None = None,
    remove_slugs: list[str] | None = None,
    source_root: Path | None = None,
) -> list[AcceptanceResult]:
    if not paths and not extra_ops:
        return []
    target_branch = branch or store.branch_id
    classification_root = source_root or store.flow_dir
    original_flow_cells = read_flow_cells(store.flow_dir)
    working_flow_cells = dict(original_flow_cells)
    pending = [Path(path) for path in paths]
    discovered: dict[Path, tuple[LoadedCell, str, str | None, str | None, bool]] = {}

    while pending:
        requested_path = pending.pop(0)
        normalized_path, slug_normalized = normalize_slug(requested_path)
        normalized_path = normalized_path.resolve()
        if normalized_path in discovered:
            continue
        loaded = load_cell(normalized_path, classification_root)
        if loaded.classification == "lib":
            raise ValueError(f"not a cell file: {normalized_path}")
        uid, copied_from, renamed_from = _resolve_uid(
            store.flow_dir, loaded, working_flow_cells
        )
        if write_uid(loaded, uid):
            loaded = load_cell(normalized_path, classification_root)
        if renamed_from is not None and source_root is None:
            working_flow_cells.pop(renamed_from, None)
        working_flow_cells[loaded.slug] = uid
        discovered[normalized_path] = (
            loaded,
            uid,
            copied_from,
            renamed_from,
            slug_normalized,
        )
        if renamed_from is not None:
            rewired = _rewrite_rename_consumers(
                store.flow_dir, renamed_from, loaded.slug, normalized_path
            )
            pending.extend(path for path in rewired if path.resolve() not in discovered)

    changed_uids = {entry[1] for entry in discovered.values()}
    namespace = _branch_namespace(store, target_branch)
    namespace = _without_uids(namespace, changed_uids)
    for loaded, uid, _copied, _renamed, _normalized in discovered.values():
        _add_to_namespace(namespace, loaded, uid)

    prepared: list[_PreparedAcceptance] = []
    for normalized_path, entry in discovered.items():
        loaded, uid, copied_from, renamed_from, slug_normalized = entry
        cell_namespace = _without_uids(namespace, {uid})
        versions = parent_versions or {}
        parent = versions.get(loaded.slug, versions.get("*", _UNSET))
        prepared.append(
            _prepare_acceptance(
                store,
                normalized_path,
                loaded,
                uid,
                copied_from,
                renamed_from,
                slug_normalized,
                target_branch,
                actor,
                parent,
                cell_namespace,
                extra_flags or [],
                classification_root,
            )
        )

    operations = [operation for item in prepared for operation in item.operations]
    operations.extend(extra_ops or [])
    blobs = [blob for item in prepared for blob in item.blobs]
    transaction = store.commit(
        actor=actor,
        intent=intent or _acceptance_intent(prepared, remove_slugs or []),
        branch=target_branch,
        ops=operations,
        blobs=blobs,
        offline=offline,
    )
    final_flow_cells = dict(original_flow_cells)
    for slug in remove_slugs or []:
        final_flow_cells.pop(slug, None)
    for item in prepared:
        if not item.selected:
            continue
        if item.renamed_from is not None:
            final_flow_cells.pop(item.renamed_from, None)
        final_flow_cells[item.loaded.slug] = item.uid
    write_flow_cells(store.flow_dir, final_flow_cells)
    if any(_declares_native_outputs(item.loaded) for item in prepared):
        _ensure_luml_sdk_dependency(store.flow_dir)

    return [
        AcceptanceResult(
            path=item.path,
            uid=item.uid,
            version_id=item.version_id,
            slug=item.loaded.slug,
            definition_hash=item.definition_hash,
            flags=item.flags,
            issues=item.issues,
            transaction=transaction,
            selected=item.selected,
            copied_from=item.copied_from,
            renamed_from=item.renamed_from,
        )
        for item in prepared
    ]


def _prepare_acceptance(
    store: FlowStore,
    path: Path,
    loaded: LoadedCell,
    uid: str,
    copied_from: str | None,
    renamed_from: str | None,
    slug_normalized: bool,
    branch: str,
    actor: str,
    parent_version: str | None | object,
    namespace: _Namespace,
    extra_flags: list[str],
    classification_root: Path,
) -> _PreparedAcceptance:
    partial_rewrites, partial_flags, partial_issues = _partial_references(
        loaded, namespace
    )
    if partial_rewrites and rewrite_consumes(path, partial_rewrites):
        loaded = load_cell(path, classification_root)
    bindings_by_input, bindings, binding_flags, binding_issues = _bind_references(
        loaded, namespace
    )
    flags = [*loaded.flags, *partial_flags, *binding_flags, *extra_flags]
    if slug_normalized:
        flags.append("slug_normalized")
    issues = [*loaded.issues, *partial_issues, *binding_issues]

    current_parent = _selected_version(store, branch, uid)
    recorded_parent = (
        current_parent if parent_version is _UNSET else cast(str | None, parent_version)
    )
    divergent = parent_version is not _UNSET and recorded_parent != current_parent
    if divergent:
        flags.append("divergent")
        issues.append(
            "branch advanced since this edit began; fork-my-edit is suggested"
        )

    source = path.read_bytes()
    bound_source = bound_class_source(loaded, bindings_by_input)
    source_hash = sha256_bytes(source)
    bound_hash = sha256_bytes(bound_source.encode())
    params = loaded.declarations.get("params", {})
    definition = hash_definition(
        bound_source,
        params if isinstance(params, dict) else {},
    )
    version_id = mint_ulid()
    operations: list[FlowOp] = []
    if renamed_from is not None:
        operations.append(
            RenamedOp(uid=uid, old_slug=renamed_from, new_slug=loaded.slug)
        )
    operations.append(
        CellAcceptedOp(
            uid=uid,
            version_id=version_id,
            slug=loaded.slug,
            source_hash=source_hash,
            bound_hash=bound_hash,
            definition_hash=definition,
            manifest=_manifest(loaded, bindings_by_input, bindings, issues),
            flags=list(dict.fromkeys(flags)),
            parent_version=recorded_parent,
            author=actor,
            copied_from=copied_from,
        )
    )
    if not divergent:
        operations.append(SelectionSetOp(uid=uid, version_id=version_id))
    return _PreparedAcceptance(
        path=path,
        loaded=loaded,
        uid=uid,
        copied_from=copied_from,
        renamed_from=renamed_from,
        operations=operations,
        blobs=[
            CASWrite("objects", source, expected_hash=source_hash),
            CASWrite("objects", bound_source, expected_hash=bound_hash),
        ],
        definition_hash=definition,
        flags=list(dict.fromkeys(flags)),
        issues=issues,
        version_id=version_id,
        selected=not divergent,
    )


def _acceptance_intent(
    prepared: list[_PreparedAcceptance], removed_slugs: list[str]
) -> str:
    slugs = ", ".join([*(item.loaded.slug for item in prepared), *removed_slugs])
    return f"accept {slugs}"


def _declares_native_outputs(loaded: LoadedCell) -> bool:
    produces = loaded.declarations.get("produces", {})
    if not isinstance(produces, dict):
        return False
    for declaration in produces.values():
        output_type = (
            declaration.get("type") if isinstance(declaration, dict) else declaration
        )
        if output_type in {"model", "dataset", "experiment"}:
            return True
    return False


def _ensure_luml_sdk_dependency(flow_dir: Path) -> None:
    path = flow_dir / "pyproject.toml"
    if not path.exists():
        atomic_write(
            path,
            (
                f'[project]\nname = "{flow_dir.stem}"\nversion = "0.1.0"\n'
                'requires-python = ">=3.10"\n'
                'dependencies = ["cloudpickle>=3", "luml-sdk>=0.2.0,<0.3.0"]\n'
            ).encode(),
        )
        return
    contents = path.read_text(encoding="utf-8")
    if re.search(r"['\"]luml-sdk(?:[<>=!~ ]|['\"])", contents):
        return
    match = re.search(r"(?ms)^dependencies\s*=\s*\[(.*?)\]", contents)
    if match is None:
        project = re.search(r"(?m)^\[project\]\s*$", contents)
        if project is None:
            raise ValueError("flow pyproject.toml has no [project] table")
        insertion = project.end()
        updated = (
            contents[:insertion]
            + '\ndependencies = ["luml-sdk>=0.2.0,<0.3.0"]'
            + contents[insertion:]
        )
    else:
        body = match.group(1).rstrip()
        if not body:
            separator = ""
        elif body.endswith(","):
            separator = "\n"
        elif "\n" in body:
            separator = ",\n"
        else:
            separator = ", "
        replacement = f'{body}{separator}"luml-sdk>=0.2.0,<0.3.0"'
        updated = contents[: match.start(1)] + replacement + contents[match.end(1) :]
    atomic_write(path, updated.encode())


def _without_uids(namespace: _Namespace, uids: set[str]) -> _Namespace:
    return _Namespace(
        slugs={slug: uid for slug, uid in namespace.slugs.items() if uid not in uids},
        outputs={
            output: [(slug, uid) for slug, uid in producers if uid not in uids]
            for output, producers in namespace.outputs.items()
        },
    )


def _add_to_namespace(namespace: _Namespace, loaded: LoadedCell, uid: str) -> None:
    namespace.slugs[loaded.slug] = uid
    produces = loaded.declarations.get("produces", {})
    if not isinstance(produces, dict):
        return
    for output in produces:
        namespace.outputs.setdefault(output, []).append((loaded.slug, uid))


def _rewrite_rename_consumers(
    flow_dir: Path, old_slug: str, new_slug: str, renamed_path: Path
) -> list[Path]:
    prefix = f"{old_slug}."
    rewritten: list[Path] = []
    for path in sorted((flow_dir / "cells").glob("*.py")):
        if path.resolve() == renamed_path.resolve():
            continue
        loaded = load_cell(path, flow_dir)
        consumes = loaded.declarations.get("consumes", {})
        if not isinstance(consumes, dict):
            continue
        replacements = {
            reference: f"{new_slug}.{reference.removeprefix(prefix)}"
            for reference in consumes.values()
            if isinstance(reference, str) and reference.startswith(prefix)
        }
        if rewrite_consumes(path, replacements):
            rewritten.append(path)
    return rewritten


def reaccept_namespace_consumers(
    store: FlowStore,
    *,
    branch: str | None = None,
    actor: str = "system:namespace",
    changed_uid: str | None = None,
) -> list[AcceptanceResult]:
    target_branch = branch or store.branch_id
    namespace = _branch_namespace(store, target_branch)
    results: list[AcceptanceResult] = []
    for path in sorted((store.flow_dir / "cells").glob("*.py")):
        loaded = load_cell(path, store.flow_dir)
        if loaded.uid == changed_uid:
            continue
        expected, _bindings, _flags, _issues = _bind_references(loaded, namespace)
        selected = _selected_manifest(store, target_branch, loaded.uid)
        if selected is None:
            continue
        current_bindings = selected.get("bound_inputs", {})
        if current_bindings != expected:
            results.append(
                accept_cell(
                    store,
                    path,
                    branch=target_branch,
                    actor=actor,
                    intent="rebind namespace consumers",
                )
            )
    return results


def compute_lib_tree_hash(flow_dir: str | Path) -> str:
    root = Path(flow_dir)
    files: list[tuple[str, str]] = []
    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        if relative.parts[0] in {"cells", ".lumlflow", ".venv"}:
            continue
        files.append((relative.as_posix(), sha256_bytes(path.read_bytes())))
    return lib_tree_hash(files)


def _resolve_uid(
    flow_dir: Path, loaded: LoadedCell, flow_cells: dict[str, str]
) -> tuple[str, str | None, str | None]:
    declared_uid = loaded.uid
    indexed_uid = flow_cells.get(loaded.slug)
    if declared_uid is None:
        return indexed_uid or mint_ulid(), None, None

    other_slugs = [
        slug
        for slug, uid in flow_cells.items()
        if uid == declared_uid and slug != loaded.slug
    ]
    if not other_slugs:
        return declared_uid, None, None
    old_slug = other_slugs[0]
    old_path = flow_dir / "cells" / f"{old_slug}.py"
    if old_path.exists():
        return mint_ulid(), declared_uid, None
    return declared_uid, None, old_slug


def _branch_namespace(
    store: FlowStore, branch: str, *, excluding_uid: str | None = None
) -> _Namespace:
    connection = store.index.connection
    if connection is None:
        raise RuntimeError("SQLite index is not open")
    rows = connection.execute(
        """
        SELECT selections.uid, versions.slug, versions.manifest
        FROM selections
        JOIN asset_versions AS versions USING(version_id)
        WHERE selections.branch_id = ?
        """,
        (branch,),
    ).fetchall()
    slugs: dict[str, str] = {}
    outputs: dict[str, list[tuple[str, str]]] = {}
    for row in rows:
        uid = str(row["uid"])
        if uid == excluding_uid:
            continue
        slug = str(row["slug"])
        slugs[slug] = uid
        manifest = json.loads(row["manifest"])
        declared_outputs = manifest.get("produces", {})
        if isinstance(declared_outputs, dict):
            for output in declared_outputs:
                outputs.setdefault(output, []).append((slug, uid))
    return _Namespace(slugs=slugs, outputs=outputs)


def _partial_references(
    loaded: LoadedCell, namespace: _Namespace
) -> tuple[dict[str, str], list[str], list[str]]:
    consumes = loaded.declarations.get("consumes", {})
    if not isinstance(consumes, dict):
        return {}, [], []
    replacements: dict[str, str] = {}
    flags: list[str] = []
    issues: list[str] = []
    for reference in consumes.values():
        if not isinstance(reference, str) or "." in reference:
            continue
        candidates = namespace.outputs.get(reference, [])
        if len(candidates) == 1:
            replacements[reference] = f"{candidates[0][0]}.{reference}"
        elif len(candidates) > 1:
            flags.append("ambiguous_ref")
            names = ", ".join(f"{slug}.{reference}" for slug, _uid in candidates)
            issues.append(f"ambiguous reference `{reference}` — candidates: {names}")
    return replacements, flags, issues


def _bind_references(
    loaded: LoadedCell, namespace: _Namespace
) -> tuple[dict[str, str], dict[str, str], list[str], list[str]]:
    consumes = loaded.declarations.get("consumes", {})
    if not isinstance(consumes, dict):
        return {}, {}, [], []
    bound_inputs: dict[str, str] = {}
    bindings: dict[str, str] = {}
    flags: list[str] = []
    issues: list[str] = []
    for input_name, reference in consumes.items():
        if not isinstance(input_name, str) or not isinstance(reference, str):
            continue
        if "." not in reference:
            candidates = namespace.outputs.get(reference, [])
            if len(candidates) == 1:
                slug, uid = candidates[0]
                bound = f"uid:{uid}.{reference}"
                bindings[f"{slug}.{reference}"] = bound
                bound_inputs[input_name] = bound
                continue
            if len(candidates) > 1:
                flags.append("ambiguous_ref")
                bound_inputs[input_name] = reference
                continue
            bound_inputs[input_name] = reference
            _add_dangling(reference, namespace, flags, issues)
            continue
        slug, output = reference.split(".", 1)
        producer_uid = namespace.slugs.get(slug)
        candidates = namespace.outputs.get(output, [])
        if producer_uid is None or (slug, producer_uid) not in candidates:
            bound_inputs[input_name] = reference
            _add_dangling(reference, namespace, flags, issues)
            continue
        bound = f"uid:{producer_uid}.{output}"
        bindings[reference] = bound
        bound_inputs[input_name] = bound
    return bound_inputs, bindings, list(dict.fromkeys(flags)), issues


def _add_dangling(
    reference: str, namespace: _Namespace, flags: list[str], issues: list[str]
) -> None:
    flags.append("dangling_ref")
    match = difflib.get_close_matches(reference, namespace.references, n=1, cutoff=0.6)
    suggestion = f" — did you mean `{match[0]}`?" if match else ""
    issues.append(f"unknown reference `{reference}`{suggestion}")


def _manifest(
    loaded: LoadedCell,
    bound_inputs: dict[str, str],
    bindings: dict[str, str],
    issues: list[str],
) -> dict[str, JsonValue]:
    declarations = loaded.declarations
    manifest: dict[str, JsonValue] = {
        "classification": loaded.classification,
        "consumes": cast(JsonValue, bound_inputs),
        "produces": declarations.get("produces", {}),
        "params": declarations.get("params", {}),
        "volatility": declarations.get("volatility", "pure"),
        "env_sensitive": declarations.get("env_sensitive", False),
        "uses": declarations.get("uses", []),
        "bound_inputs": cast(JsonValue, bound_inputs),
        "bindings": cast(JsonValue, bindings),
        "issues": cast(JsonValue, issues),
    }
    if loaded.candidates:
        manifest["candidates"] = cast(JsonValue, loaded.candidates)
    return manifest


def _selected_version(store: FlowStore, branch: str, uid: str) -> str | None:
    connection = store.index.connection
    if connection is None:
        raise RuntimeError("SQLite index is not open")
    row = connection.execute(
        "SELECT version_id FROM selections WHERE branch_id = ? AND uid = ?",
        (branch, uid),
    ).fetchone()
    return None if row is None else str(row[0])


def _selected_manifest(
    store: FlowStore, branch: str, uid: str | None
) -> dict[str, object] | None:
    if uid is None:
        return None
    connection = store.index.connection
    if connection is None:
        raise RuntimeError("SQLite index is not open")
    row = connection.execute(
        """
        SELECT versions.manifest FROM selections
        JOIN asset_versions AS versions USING(version_id)
        WHERE selections.branch_id = ? AND selections.uid = ?
        """,
        (branch, uid),
    ).fetchone()
    return None if row is None else cast(dict[str, object], json.loads(row[0]))


def _rewire_rename(
    store: FlowStore,
    old_slug: str,
    new_slug: str,
    branch: str,
    actor: str,
    renamed_path: Path,
) -> None:
    prefix = f"{old_slug}."
    for path in sorted((store.flow_dir / "cells").glob("*.py")):
        if path == renamed_path:
            continue
        loaded = load_cell(path, store.flow_dir)
        consumes = loaded.declarations.get("consumes", {})
        if not isinstance(consumes, dict):
            continue
        replacements = {
            reference: f"{new_slug}.{reference.removeprefix(prefix)}"
            for reference in consumes.values()
            if isinstance(reference, str) and reference.startswith(prefix)
        }
        if rewrite_consumes(path, replacements):
            accept_cell(
                store,
                path,
                branch=branch,
                actor=actor,
                intent=f"rewire {old_slug} to {new_slug}",
            )
