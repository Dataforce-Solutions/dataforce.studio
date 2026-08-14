from __future__ import annotations

import importlib
import pickle
from collections.abc import Callable
from pathlib import Path
from typing import Any, BinaryIO


class BuiltinKind:
    def __init__(
        self,
        kind: str,
        priority: int,
        matcher: Callable[[Any], bool],
    ) -> None:
        self.kind = kind
        self.priority = priority
        self.matcher = matcher
        self.provenance = f"builtin:{kind}"

    def matches(self, value: Any) -> bool:
        return self.matcher(value)

    def serialize(self, value: Any, sink: BinaryIO) -> str:
        if self.kind == "file":
            with Path(value).open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    sink.write(chunk)
            return "raw"
        if self.kind == "frame":
            return _dump_frame(value, sink)
        return _dump_pickle(value, sink)

    def deserialize(self, source: BinaryIO) -> Any:
        if self.kind == "file":
            return source.read()
        if self.kind == "frame":
            return _load_frame(source)
        return _load_pickle(source)

    def page(self, source: BinaryIO, query: dict[str, Any]) -> Any:
        value = self.deserialize(source)
        if self.kind != "frame":
            raise ValueError(f"kind {self.kind!r} does not support paging")
        offset = max(int(query.get("offset", 0)), 0)
        limit = min(max(int(query.get("limit", 100)), 1), 1000)
        if hasattr(value, "iloc"):
            page = value.iloc[offset : offset + limit]
            rows = page.to_dict(orient="records")
        else:
            page = value.slice(offset, limit)
            rows = page.to_dicts()
        return {
            "columns": [str(column) for column in page.columns],
            "rows": rows,
            "offset": offset,
            "total_rows": len(value),
        }

    def diff(self, source_a: BinaryIO, source_b: BinaryIO) -> Any:
        value_a = self.deserialize(source_a)
        value_b = self.deserialize(source_b)
        if self.kind == "frame":
            return {
                "rows_a": len(value_a),
                "rows_b": len(value_b),
                "columns_a": [str(column) for column in value_a.columns],
                "columns_b": [str(column) for column in value_b.columns],
            }
        return {"equal": value_a == value_b}


def builtin_kinds() -> list[BuiltinKind]:
    return [
        BuiltinKind("file", 1000, lambda value: isinstance(value, Path)),
        BuiltinKind("frame", 900, _is_frame),
        BuiltinKind("checkpoint", 800, _is_checkpoint),
        BuiltinKind("plot", 700, _is_plot),
        BuiltinKind("metric", 600, _is_metric),
        BuiltinKind("eval", 500, _is_eval),
        BuiltinKind("pickle", -1000, lambda value: True),
    ]


def _is_frame(value: Any) -> bool:
    module = type(value).__module__.split(".", maxsplit=1)[0]
    return module in {"pandas", "polars"} and hasattr(value, "columns")


def _is_checkpoint(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and bool(value)
        and all(type(item).__module__.startswith("torch") for item in value.values())
    )


def _is_plot(value: Any) -> bool:
    if type(value).__module__.startswith("matplotlib") and hasattr(value, "savefig"):
        return True
    return isinstance(value, dict) and (
        "$schema" in value or ("mark" in value and "data" in value)
    )


def _is_metric(value: Any) -> bool:
    if not isinstance(value, dict) or not value:
        return False
    if "value" in value and isinstance(value["value"], (int, float)):
        return True
    return all(isinstance(key, str) for key in value) and all(
        isinstance(item, (int, float)) and not isinstance(item, bool)
        for item in value.values()
    )


def _is_eval(value: Any) -> bool:
    if isinstance(value, list) and value:
        return all(isinstance(item, dict) for item in value)
    return isinstance(value, dict) and any(
        key in value for key in ("prediction", "label", "score", "metrics")
    )


def _dump_pickle(value: Any, sink: BinaryIO) -> str:
    try:
        cloudpickle = importlib.import_module("cloudpickle")
    except ImportError:
        sink.write(b"pickle\0")
        pickle.dump(value, sink, protocol=pickle.HIGHEST_PROTOCOL)
        return "pickle"
    sink.write(b"cloudpickle\0")
    cloudpickle.dump(value, sink, protocol=pickle.HIGHEST_PROTOCOL)
    return "cloudpickle"


def _dump_frame(value: Any, sink: BinaryIO) -> str:
    library = type(value).__module__.split(".", maxsplit=1)[0]
    try:
        pyarrow = importlib.import_module("pyarrow")
        ipc = importlib.import_module("pyarrow.ipc")
    except ImportError:
        return _dump_pickle(value, sink)
    table = (
        pyarrow.Table.from_pandas(value) if library == "pandas" else value.to_arrow()
    )
    buffer = pyarrow.BufferOutputStream()
    with ipc.new_stream(buffer, table.schema) as writer:
        writer.write_table(table)
    sink.write(f"arrow-{library}\0".encode())
    sink.write(buffer.getvalue().to_pybytes())
    return f"pyarrow-{library}"


def _load_frame(source: BinaryIO) -> Any:
    prefix = _read_prefix(source)
    if prefix in {"cloudpickle", "pickle"}:
        return _load_pickle_payload(prefix, source)
    if not prefix.startswith("arrow-"):
        raise ValueError(f"unknown frame serializer: {prefix}")
    library = prefix.removeprefix("arrow-")
    ipc = importlib.import_module("pyarrow.ipc")
    table = ipc.open_stream(source).read_all()
    if library == "pandas":
        return table.to_pandas()
    if library == "polars":
        polars = importlib.import_module("polars")
        return polars.from_arrow(table)
    raise ValueError(f"unknown frame library: {library}")


def _load_pickle(source: BinaryIO) -> Any:
    serializer = _read_prefix(source)
    return _load_pickle_payload(serializer, source)


def _load_pickle_payload(serializer: str, source: BinaryIO) -> Any:
    if serializer == "cloudpickle":
        try:
            cloudpickle = importlib.import_module("cloudpickle")
        except ImportError as error:
            raise RuntimeError("cloudpickle is required to load this value") from error
        return cloudpickle.load(source)
    if serializer == "pickle":
        return pickle.load(source)
    raise ValueError(f"unknown value serializer: {serializer}")


def _read_prefix(source: BinaryIO) -> str:
    prefix = bytearray()
    while len(prefix) < 32:
        byte = source.read(1)
        if byte == b"\0":
            return prefix.decode("ascii")
        if not byte:
            raise ValueError("invalid serialized value")
        prefix.extend(byte)
    raise ValueError("serialized value prefix is too long")
