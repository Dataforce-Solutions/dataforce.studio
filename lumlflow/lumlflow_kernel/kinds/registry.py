from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Protocol, cast

from ..fs import replace_with_retry
from .builtin import BuiltinKind, builtin_kinds
from .preview import build_preview, cap_preview


class KindHandler(Protocol):
    kind: str
    priority: int
    provenance: str

    def matches(self, value: Any) -> bool: ...

    def serialize(self, value: Any, sink: BinaryIO) -> str | None: ...

    def deserialize(self, source: BinaryIO) -> Any: ...


@dataclass(frozen=True)
class SerializedValue:
    kind: str
    content_hash: str
    value_ref: str
    preview_ref: str
    size: int
    provenance: str
    serializer: str | None
    persisted: bool = True

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "content_hash": self.content_hash,
            "value_ref": self.value_ref,
            "preview_ref": self.preview_ref,
            "size": self.size,
            "provenance": self.provenance,
            "serializer": self.serializer,
            "persisted": self.persisted,
        }


class _HashingSink:
    def __init__(self, sink: BinaryIO) -> None:
        self.sink = sink
        self.hasher = hashlib.sha256()
        self.size = 0

    def write(self, data: bytes) -> int:
        written = self.sink.write(data)
        self.hasher.update(data[:written])
        self.size += written
        return written

    def flush(self) -> None:
        self.sink.flush()

    def fileno(self) -> int:
        return self.sink.fileno()


class KindRegistry:
    def __init__(self, flow_dir: Path, values_root: Path, previews_root: Path) -> None:
        self.flow_dir = flow_dir
        self.values_root = values_root
        self.previews_root = previews_root
        self._handlers: dict[str, KindHandler] = {}
        for handler in builtin_kinds():
            self.register(handler)
        self._load_entry_points()
        self._load_flow_plugins()

    def register(self, handler: KindHandler) -> None:
        if not hasattr(handler, "priority"):
            handler.priority = 0
        if not hasattr(handler, "provenance"):
            handler.provenance = f"plugin:{handler.kind}"
        if not handler.kind or not isinstance(handler.priority, int):
            raise ValueError("kind plugins require a name and integer priority")
        existing = self._handlers.get(handler.kind)
        if existing is None or handler.priority >= existing.priority:
            self._handlers[handler.kind] = handler

    def report(self) -> list[dict[str, object]]:
        return [
            {
                "name": handler.kind,
                "priority": handler.priority,
                "matcher": handler.provenance,
            }
            for handler in self._ordered_handlers()
        ]

    def infer(self, value: Any, override: str | None = None) -> KindHandler:
        if override is not None:
            try:
                return self._handlers[override]
            except KeyError as error:
                raise ValueError(f"unknown output kind override: {override}") from error
        for handler in self._ordered_handlers():
            matcher = getattr(handler, "matches", None)
            python_types = getattr(handler, "python_types", ())
            if (callable(matcher) and matcher(value)) or (
                python_types and isinstance(value, python_types)
            ):
                return handler
        raise RuntimeError("pickle fallback kind is not registered")

    def serialize(
        self,
        value: Any,
        override: str | None = None,
        *,
        preview_kind: str | None = None,
    ) -> SerializedValue:
        handler = self.infer(value, override)
        self.values_root.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".kernel-value.", dir=self.values_root
        )
        temporary = Path(temporary_name)
        serializer: str | None = None
        try:
            with os.fdopen(descriptor, "wb") as raw_sink:
                hashing_sink = _HashingSink(raw_sink)
                serializer = handler.serialize(
                    value,
                    cast(BinaryIO, hashing_sink),
                )
                hashing_sink.flush()
                os.fsync(raw_sink.fileno())
            content_hash = hashing_sink.hasher.hexdigest()
            destination = self._path_for(self.values_root, content_hash)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                temporary.unlink()
            else:
                replace_with_retry(temporary, destination)
            preview = self._preview(
                handler,
                value,
                content_hash,
                preview_kind=preview_kind,
            )
            preview_bytes = json.dumps(
                preview,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
            preview_ref = hashlib.sha256(preview_bytes).hexdigest()
            preview_path = self._path_for(
                self.previews_root,
                preview_ref,
                suffix=".json",
            )
            self._write_once(preview_path, preview_bytes)
            return SerializedValue(
                kind=handler.kind,
                content_hash=content_hash,
                value_ref=content_hash,
                preview_ref=preview_ref,
                size=hashing_sink.size,
                provenance=handler.provenance,
                serializer=serializer,
            )
        finally:
            temporary.unlink(missing_ok=True)

    def deserialize(self, value_ref: str, kind: str) -> Any:
        handler = self._require(kind)
        with self._path_for(self.values_root, value_ref).open("rb") as source:
            return handler.deserialize(source)

    def content_hash(self, value: Any, kind: str) -> str:
        handler = self._require(kind)
        with tempfile.TemporaryFile() as raw_sink:
            hashing_sink = _HashingSink(raw_sink)
            handler.serialize(value, cast(BinaryIO, hashing_sink))
        return hashing_sink.hasher.hexdigest()

    def page(self, value_ref: str, kind: str, query: dict[str, Any]) -> Any:
        handler = self._require(kind)
        page = getattr(handler, "page", None)
        if page is None:
            raise ValueError(f"kind {kind!r} does not support paging")
        with self._path_for(self.values_root, value_ref).open("rb") as source:
            return page(source, query)

    def diff(self, ref_a: str, ref_b: str, kind: str) -> Any:
        handler = self._require(kind)
        diff = getattr(handler, "diff", None)
        if diff is None:
            raise ValueError(f"kind {kind!r} does not support diffing")
        with (
            self._path_for(self.values_root, ref_a).open("rb") as source_a,
            self._path_for(self.values_root, ref_b).open("rb") as source_b,
        ):
            return diff(source_a, source_b)

    def preview(self, value: Any) -> dict[str, Any]:
        handler = self.infer(value)
        return self._preview(handler, value, "")

    def _preview(
        self,
        handler: KindHandler,
        value: Any,
        content_hash: str,
        *,
        preview_kind: str | None = None,
    ) -> dict[str, Any]:
        plugin_preview = getattr(handler, "preview", None)
        if plugin_preview is not None and not isinstance(handler, BuiltinKind):
            return cap_preview(plugin_preview(value))
        return build_preview(preview_kind or handler.kind, value, content_hash)

    def _ordered_handlers(self) -> list[KindHandler]:
        return sorted(
            self._handlers.values(),
            key=lambda handler: (-handler.priority, handler.kind, handler.provenance),
        )

    def _require(self, kind: str) -> KindHandler:
        try:
            return self._handlers[kind]
        except KeyError as error:
            raise ValueError(f"unknown kind: {kind}") from error

    def _load_entry_points(self) -> None:
        entry_points = importlib.metadata.entry_points()
        selected = entry_points.select(group="lumlflow.kinds")
        for entry_point in selected:
            loaded = entry_point.load()
            handler = loaded() if isinstance(loaded, type) else loaded
            if not hasattr(handler, "provenance"):
                handler.provenance = f"entrypoint:{entry_point.name}"
            self.register(handler)

    def _load_flow_plugins(self) -> None:
        library_dir = self.flow_dir / "lib"
        if not library_dir.is_dir():
            return
        for path in sorted(library_dir.rglob("*.py")):
            tree = ast.parse(path.read_bytes(), filename=str(path))
            declared_names = {
                target.id
                for node in tree.body
                if isinstance(node, (ast.Assign, ast.AnnAssign))
                for target in (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                if isinstance(target, ast.Name)
            }
            function_names = {
                node.name
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            if (
                "LUMLFLOW_KINDS" not in declared_names
                and "register_kinds" not in function_names
            ):
                continue
            path_hash = hashlib.sha256(str(path).encode()).hexdigest()
            module_name = f"lumlflow_flow_kind_{path_hash}"
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            register = getattr(module, "register_kinds", None)
            if callable(register):
                register(self)
            for handler in getattr(module, "LUMLFLOW_KINDS", ()):
                if not hasattr(handler, "provenance"):
                    handler.provenance = f"flow:{path.relative_to(self.flow_dir)}"
                self.register(handler)

    @staticmethod
    def _path_for(root: Path, content_hash: str, *, suffix: str = "") -> Path:
        if len(content_hash) != 64 or any(
            character not in "0123456789abcdef" for character in content_hash
        ):
            raise ValueError("content reference must be a lowercase sha256 digest")
        return root / content_hash[:2] / f"{content_hash}{suffix}"

    @staticmethod
    def _write_once(path: Path, data: bytes) -> None:
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as sink:
                sink.write(data)
                sink.flush()
                os.fsync(sink.fileno())
            if path.exists():
                temporary.unlink()
            else:
                replace_with_retry(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
