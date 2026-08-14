import ast
import copy
import json
import re
from pathlib import Path

from lumlflow.flow.store.cas import _replace_with_retry, atomic_write

from .loader import LoadedCell

_ROOT_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*:")


def read_flow_cells(flow_dir: str | Path) -> dict[str, str]:
    lines = (Path(flow_dir) / "flow.yaml").read_text(encoding="utf-8").splitlines()
    cells: dict[str, str] = {}
    in_cells = False
    for line in lines:
        if line.startswith("cells:"):
            in_cells = True
            continue
        if in_cells and line and not line.startswith((" ", "\t")):
            break
        if not in_cells or not line.strip():
            continue
        key, separator, value = line.strip().partition(":")
        if separator and key and value.strip():
            cells[key] = value.strip().strip("\"'")
    return cells


def write_flow_cells(flow_dir: str | Path, cells: dict[str, str]) -> None:
    path = Path(flow_dir) / "flow.yaml"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    start = next(
        (index for index, line in enumerate(lines) if line.startswith("cells:")), None
    )
    if start is None:
        raise ValueError("flow.yaml has no cells index")
    end = start + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() and not line.startswith((" ", "\t")) and _ROOT_KEY.match(line):
            break
        end += 1
    replacement = ["cells:\n"]
    replacement.extend(f"  {slug}: {uid}\n" for slug, uid in sorted(cells.items()))
    atomic_write(path, "".join([*lines[:start], *replacement, *lines[end:]]).encode())


def normalize_slug(path: str | Path) -> tuple[Path, bool]:
    source = Path(path)
    lowered = source.stem.lower()
    if lowered == source.stem:
        return source, False
    destination = source.with_name(f"{lowered}{source.suffix.lower()}")
    counter = 2
    while destination.exists() and destination.resolve() != source.resolve():
        destination = source.with_name(f"{lowered}_{counter}{source.suffix.lower()}")
        counter += 1
    if source == destination:
        return source, False
    _rename_with_case_support(source, destination)
    return destination, True


def write_uid(cell: LoadedCell, uid: str) -> bool:
    if cell.class_node is None:
        return False
    assignment, value = _class_assignment(cell.class_node, "uid")
    if value is not None:
        if isinstance(value, ast.Constant) and value.value == uid:
            return False
        updated = _replace_node(cell.source, value, json.dumps(uid))
    else:
        insertion_line = cell.class_node.lineno
        body = cell.class_node.body
        if body and _is_docstring(body[0]):
            insertion_line = body[0].end_lineno or body[0].lineno
        elif body:
            insertion_line = body[0].lineno - 1
        lines = cell.source.splitlines(keepends=True)
        indentation = " " * (cell.class_node.col_offset + 4)
        lines.insert(insertion_line, f'{indentation}uid = "{uid}"\n')
        updated = "".join(lines)
    atomic_write(cell.path, updated.encode())
    return True


def rewrite_consumes(path: str | Path, replacements: dict[str, str]) -> bool:
    cell_path = Path(path)
    source = cell_path.read_text(encoding="utf-8")
    try:
        module = ast.parse(source)
    except SyntaxError:
        return False
    edits: list[tuple[int, int, str]] = []
    for class_node in (node for node in module.body if isinstance(node, ast.ClassDef)):
        _assignment, value = _class_assignment(class_node, "consumes")
        if not isinstance(value, ast.Dict):
            continue
        for reference_node in value.values:
            if not isinstance(reference_node, ast.Constant) or not isinstance(
                reference_node.value, str
            ):
                continue
            replacement = replacements.get(reference_node.value)
            if replacement is not None and replacement != reference_node.value:
                start, end = _node_offsets(source, reference_node)
                edits.append((start, end, json.dumps(replacement)))
    if not edits:
        return False
    for start, end, replacement in sorted(edits, reverse=True):
        source = f"{source[:start]}{replacement}{source[end:]}"
    atomic_write(cell_path, source.encode())
    return True


def bound_class_source(cell: LoadedCell, bindings_by_input: dict[str, str]) -> str:
    if cell.class_node is None:
        if cell.module is None:
            return cell.source
        return ast.unparse(cell.module)
    class_node = copy.deepcopy(cell.class_node)
    _assignment, consumes = _class_assignment(class_node, "consumes")
    if isinstance(consumes, ast.Dict):
        for index, (key, value) in enumerate(
            zip(consumes.keys, consumes.values, strict=True)
        ):
            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and key.value in bindings_by_input
            ):
                consumes.values[index] = ast.copy_location(
                    ast.Constant(bindings_by_input[key.value]), value
                )
    ast.fix_missing_locations(class_node)
    return ast.unparse(class_node)


def _class_assignment(
    class_node: ast.ClassDef, name: str
) -> tuple[ast.stmt | None, ast.expr | None]:
    for statement in class_node.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in statement.targets
        ):
            return statement, statement.value
        if (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == name
        ):
            return statement, statement.value
    return None, None


def _replace_node(source: str, node: ast.expr, replacement: str) -> str:
    start, end = _node_offsets(source, node)
    return f"{source[:start]}{replacement}{source[end:]}"


def _node_offsets(source: str, node: ast.expr) -> tuple[int, int]:
    if (
        not hasattr(node, "lineno")
        or not hasattr(node, "end_lineno")
        or node.end_lineno is None
        or node.end_col_offset is None
    ):
        raise ValueError("AST node has no source position")
    lines = source.splitlines(keepends=True)
    start = (
        sum(len(line.encode()) for line in lines[: node.lineno - 1]) + node.col_offset
    )
    end = (
        sum(len(line.encode()) for line in lines[: node.end_lineno - 1])
        + node.end_col_offset
    )
    encoded = source.encode()
    prefix = encoded[:start].decode()
    target = encoded[start:end].decode()
    return len(prefix), len(prefix) + len(target)


def _is_docstring(statement: ast.stmt) -> bool:
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    )


def _rename_with_case_support(source: Path, destination: Path) -> None:
    if source.parent != destination.parent:
        raise ValueError("slug normalization must stay in the same directory")
    if source.name.casefold() == destination.name.casefold():
        temporary = source.with_name(f".{source.name}.normalize")
        counter = 2
        while temporary.exists():
            temporary = source.with_name(f".{source.name}.normalize.{counter}")
            counter += 1
        _replace_with_retry(source, temporary)
        try:
            _replace_with_retry(temporary, destination)
        except BaseException:
            _replace_with_retry(temporary, source)
            raise
        return
    _replace_with_retry(source, destination)
