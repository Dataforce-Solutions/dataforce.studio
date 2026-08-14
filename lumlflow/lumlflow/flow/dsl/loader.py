import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, cast

from lumlflow.flow.store.models import JsonValue

type CellClassification = Literal[
    "cell", "note", "incomplete", "ambiguous", "invalid", "lib"
]

_DECLARATIONS = {
    "uid",
    "consumes",
    "produces",
    "params",
    "volatility",
    "env_sensitive",
    "uses",
}
_COMPUTE_DECLARATIONS = _DECLARATIONS - {"uid"}
_OUTPUT_TYPES = {"model", "dataset", "experiment", "asset"}
_VOLATILITIES = {"pure", "seeded", "nondeterministic", "external"}


@dataclass
class LoadedCell:
    path: Path
    slug: str
    source: str
    module: ast.Module | None
    class_node: ast.ClassDef | None
    classification: CellClassification
    candidates: list[str] = field(default_factory=list)
    declarations: dict[str, JsonValue] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    @property
    def uid(self) -> str | None:
        value = self.declarations.get("uid")
        return value if isinstance(value, str) else None


def load_cell(path: str | Path, flow_dir: str | Path) -> LoadedCell:
    cell_path = Path(path)
    root = Path(flow_dir)
    source = cell_path.read_text(encoding="utf-8")
    if not _is_cell_path(cell_path, root):
        return LoadedCell(
            path=cell_path,
            slug=cell_path.stem,
            source=source,
            module=None,
            class_node=None,
            classification="lib",
        )

    try:
        module = ast.parse(source, filename=str(cell_path))
    except SyntaxError as error:
        return LoadedCell(
            path=cell_path,
            slug=cell_path.stem,
            source=source,
            module=None,
            class_node=None,
            classification="invalid",
            flags=["invalid"],
            issues=[f"syntax error: {error.msg}"],
        )

    classes = [node for node in module.body if isinstance(node, ast.ClassDef)]
    candidates = [node for node in classes if _is_compute_candidate(node)]
    if not candidates and len(classes) == 1 and ast.get_docstring(classes[0]):
        candidate = classes[0]
        classification: CellClassification = "note"
    elif not candidates:
        return LoadedCell(
            path=cell_path,
            slug=cell_path.stem,
            source=source,
            module=module,
            class_node=None,
            classification="invalid",
            flags=["invalid"],
            issues=["cell file has no qualifying class"],
        )
    else:
        candidate = candidates[0]
        classification = "cell"

    declarations, flags, issues = _extract_declarations(candidate)
    candidate_names = [node.name for node in candidates]
    if len(candidates) > 1:
        classification = "ambiguous"
        flags.append("ambiguous")
        issues.append(f"multiple cell candidates: {', '.join(candidate_names)}")
    elif not _defines_materialize(candidate):
        if ast.get_docstring(candidate) and not (
            _assigned_names(candidate) & _COMPUTE_DECLARATIONS
        ):
            classification = "note"
        else:
            classification = "incomplete"
            flags.append("incomplete")
            issues.append(
                f"{candidate.name} has declarations but no materialize method"
            )

    _validate_declarations(declarations, flags, issues)
    return LoadedCell(
        path=cell_path,
        slug=cell_path.stem,
        source=source,
        module=module,
        class_node=candidate,
        classification=classification,
        candidates=candidate_names,
        declarations=declarations,
        flags=_deduplicate(flags),
        issues=issues,
    )


def _is_cell_path(path: Path, flow_dir: Path) -> bool:
    try:
        relative = path.resolve().relative_to(flow_dir.resolve())
    except ValueError:
        return False
    return (
        len(relative.parts) == 2
        and relative.parts[0] == "cells"
        and path.suffix == ".py"
    )


def _is_compute_candidate(node: ast.ClassDef) -> bool:
    return _defines_materialize(node) or bool(_assigned_names(node) & _DECLARATIONS)


def _defines_materialize(node: ast.ClassDef) -> bool:
    return any(
        isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
        and statement.name == "materialize"
        for statement in node.body
    )


def _assigned_names(node: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for statement in node.body:
        if isinstance(statement, ast.Assign):
            names.update(
                target.id
                for target in statement.targets
                if isinstance(target, ast.Name)
            )
        elif isinstance(statement, ast.AnnAssign) and isinstance(
            statement.target, ast.Name
        ):
            names.add(statement.target.id)
    return names


def _extract_declarations(
    node: ast.ClassDef,
) -> tuple[dict[str, JsonValue], list[str], list[str]]:
    declarations: dict[str, JsonValue] = {}
    flags: list[str] = []
    issues: list[str] = []
    for statement in node.body:
        name, value_node = _declaration_assignment(statement)
        if name is None or value_node is None or name not in _DECLARATIONS:
            continue
        try:
            value = ast.literal_eval(value_node)
        except (ValueError, TypeError, SyntaxError):
            flags.append("nonliteral_declaration")
            issues.append(f"{name} must be a literal declaration")
            continue
        if not _is_json_value(value):
            flags.append("nonliteral_declaration")
            issues.append(f"{name} must contain JSON-compatible literal values")
            continue
        declarations[name] = cast(JsonValue, value)
    return declarations, flags, issues


def _declaration_assignment(
    statement: ast.stmt,
) -> tuple[str | None, ast.expr | None]:
    if (
        isinstance(statement, ast.Assign)
        and len(statement.targets) == 1
        and isinstance(statement.targets[0], ast.Name)
    ):
        return statement.targets[0].id, statement.value
    if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
        return statement.target.id, statement.value
    return None, None


def _is_json_value(value: object) -> bool:
    if value is None or isinstance(value, (bool, int, float, str)):
        return True
    if isinstance(value, list):
        return all(_is_json_value(item) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _is_json_value(item) for key, item in value.items()
        )
    return False


def _validate_declarations(
    declarations: dict[str, JsonValue], flags: list[str], issues: list[str]
) -> None:
    consumes = declarations.get("consumes", {})
    if not isinstance(consumes, dict) or not all(
        isinstance(name, str) and isinstance(reference, str)
        for name, reference in consumes.items()
    ):
        flags.append("invalid_consumes")
        issues.append("consumes must map input names to string references")

    produces = declarations.get("produces", {})
    if not isinstance(produces, dict):
        flags.append("invalid_produces")
        issues.append("produces must be a mapping")
    else:
        for name, declaration in produces.items():
            if not isinstance(name, str) or not _valid_output(declaration):
                flags.append("invalid_produces")
                issues.append(f"invalid output declaration for {name!r}")

    params = declarations.get("params", {})
    if not isinstance(params, dict):
        flags.append("invalid_params")
        issues.append("params must be a mapping")

    volatility = declarations.get("volatility", "pure")
    if volatility not in _VOLATILITIES:
        flags.append("invalid_volatility")
        issues.append("volatility must be pure, seeded, nondeterministic, or external")

    env_sensitive = declarations.get("env_sensitive", False)
    if not isinstance(env_sensitive, bool):
        flags.append("invalid_env_sensitive")
        issues.append("env_sensitive must be a boolean")

    uses = declarations.get("uses", [])
    if not isinstance(uses, list) or not all(isinstance(item, str) for item in uses):
        flags.append("invalid_uses")
        issues.append("uses must be a list of strings")


def _valid_output(value: JsonValue) -> bool:
    if isinstance(value, str):
        return value in _OUTPUT_TYPES
    if not isinstance(value, dict) or value.get("type") not in _OUTPUT_TYPES:
        return False
    allowed = {"type", "kind", "persist", "ephemeral"}
    if set(value) - allowed:
        return False
    return (
        ("kind" not in value or isinstance(value["kind"], str))
        and ("persist" not in value or isinstance(value["persist"], bool))
        and ("ephemeral" not in value or isinstance(value["ephemeral"], bool))
    )


def _deduplicate(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
