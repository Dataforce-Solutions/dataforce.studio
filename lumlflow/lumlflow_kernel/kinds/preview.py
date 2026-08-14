from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

PREVIEW_SCHEMA = 1
PREVIEW_LIMIT_BYTES = 64 * 1024
TABLE_ROW_LIMIT = 20
SERIES_POINT_LIMIT = 1000


def build_preview(kind: str, value: Any, content_hash: str) -> dict[str, Any]:
    if kind == "file" and isinstance(value, Path):
        blocks = [
            {
                "type": "file",
                "name": value.name,
                "size": value.stat().st_size,
                "content_hash": content_hash,
            }
        ]
    elif kind == "frame":
        blocks = [_frame_block(value)]
    elif kind == "experiment":
        blocks = _experiment_blocks(value)
    elif kind == "dataset" and hasattr(value, "columns"):
        blocks = [_frame_block(value)]
    elif kind in {"metric", "eval", "checkpoint", "model", "dataset"}:
        blocks = [{"type": "kv", "items": _kv_items(value)}]
    elif kind == "plot":
        blocks = [_plot_block(value)]
    else:
        blocks = [{"type": "markdown", "text": _bounded_repr(value)}]
    return cap_preview({"schema": PREVIEW_SCHEMA, "kind": kind, "blocks": blocks})


def _experiment_blocks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return [{"type": "kv", "items": _kv_items(value)}]
    blocks: list[dict[str, Any]] = []
    summary = {
        key: item for key, item in value.items() if key not in {"history", "metrics"}
    }
    metrics = value.get("metrics")
    if isinstance(metrics, dict):
        summary["metrics"] = metrics
    if summary:
        blocks.append({"type": "kv", "items": _kv_items(summary)})
    history = value.get("history")
    if isinstance(history, dict):
        for name, points in list(history.items())[:20]:
            if not isinstance(points, list):
                continue
            normalized = [_primitive(point) for point in points[:SERIES_POINT_LIMIT]]
            blocks.append({"type": "series", "name": str(name), "points": normalized})
    return blocks or [{"type": "kv", "items": []}]


def cap_preview(preview: dict[str, Any]) -> dict[str, Any]:
    encoded = _encode(preview)
    if len(encoded) <= PREVIEW_LIMIT_BYTES:
        return preview
    compact = {
        "schema": PREVIEW_SCHEMA,
        "kind": str(preview.get("kind", "unknown")),
        "blocks": [
            {
                "type": "markdown",
                "text": "Preview exceeded the 64 KB limit.",
            }
        ],
        "truncated": True,
    }
    return compact


def _frame_block(value: Any) -> dict[str, Any]:
    columns = [str(column) for column in getattr(value, "columns", [])]
    total_rows = _safe_len(value)
    rows: list[list[Any]] = []
    try:
        head = value.head(TABLE_ROW_LIMIT)
        if hasattr(head, "rows"):
            rows = [[_primitive(item) for item in row] for row in head.rows()]
        elif hasattr(head, "itertuples"):
            rows = [
                [_primitive(item) for item in row]
                for row in head.itertuples(index=False, name=None)
            ]
        elif hasattr(head, "to_dict"):
            records = head.to_dict(orient="records")
            rows = [
                [_primitive(record.get(column)) for column in columns]
                for record in records
            ]
    except (AttributeError, TypeError, ValueError):
        rows = []
    return {
        "type": "table",
        "columns": columns,
        "rows": rows,
        "total_rows": total_rows,
    }


def _plot_block(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {
            "type": "markdown",
            "text": f"```json\n{json.dumps(value, default=str)[:16000]}\n```",
        }
    try:
        from io import BytesIO

        sink = BytesIO()
        value.savefig(sink, format="png")
        return {
            "type": "image",
            "mime": "image/png",
            "data_b64": base64.b64encode(sink.getvalue()).decode("ascii"),
        }
    except (AttributeError, OSError, TypeError, ValueError):
        return {"type": "markdown", "text": _bounded_repr(value)}


def _kv_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [
            {"key": str(key), "value": _primitive(item)}
            for key, item in list(value.items())[:100]
        ]
    if isinstance(value, (list, tuple)):
        return [
            {"key": str(index), "value": _primitive(item)}
            for index, item in enumerate(value[:100])
        ]
    return [{"key": "value", "value": _primitive(value)}]


def _primitive(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "item"):
        try:
            return _primitive(value.item())
        except (TypeError, ValueError):
            pass
    return str(value)


def _bounded_repr(value: Any) -> str:
    rendered = repr(value)
    if len(rendered) > 16000:
        return rendered[:15999] + "…"
    return rendered


def _safe_len(value: Any) -> int:
    try:
        return len(value)
    except TypeError:
        return 0


def _encode(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
