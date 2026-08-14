from __future__ import annotations

from pathlib import Path

from lumlflow.flow.dsl.accept import accept_cells
from lumlflow.flow.store.cas import atomic_write
from lumlflow.flow.store.flowstore import FlowStore

_DEMO_LIBRARY = '''from __future__ import annotations

from typing import Any, BinaryIO

import cloudpickle


class DemoFrame:
    _rows: list[dict[str, object]]

    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = [dict(row) for row in rows]

    @property
    def columns(self) -> list[str]:
        return list(self._rows[0]) if self._rows else []

    def __len__(self) -> int:
        return len(self._rows)

    def head(self, limit: int) -> DemoFrame:
        return DemoFrame(self._rows[:limit])

    def slice(self, offset: int, limit: int) -> DemoFrame:
        return DemoFrame(self._rows[offset : offset + limit])

    def to_dict(self, orient: str = "records") -> list[dict[str, object]]:
        if orient != "records":
            raise ValueError("DemoFrame only supports records orientation")
        return [dict(row) for row in self._rows]


class DemoFrameKind:
    kind: str = "frame"
    priority: int = 1000
    provenance: str = "flow:demo-frame"

    def matches(self, value: Any) -> bool:
        return isinstance(value, DemoFrame)

    def serialize(self, value: Any, sink: BinaryIO) -> str:
        cloudpickle.dump(value, sink)
        return "cloudpickle"

    def deserialize(self, source: BinaryIO) -> Any:
        return cloudpickle.load(source)

    def page(self, source: BinaryIO, query: dict[str, Any]) -> dict[str, Any]:
        frame = self.deserialize(source)
        offset = max(int(query.get("offset", 0)), 0)
        limit = min(max(int(query.get("limit", 100)), 1), 1000)
        page = frame.slice(offset, limit)
        return {
            "columns": page.columns,
            "rows": page.to_dict(),
            "offset": offset,
            "total_rows": len(frame),
        }

    def preview(self, value: Any) -> dict[str, Any]:
        page = value.head(20)
        return {
            "schema": 1,
            "kind": "frame",
            "blocks": [
                {
                    "type": "table",
                    "columns": page.columns,
                    "rows": [
                        [row.get(column) for column in page.columns]
                        for row in page.to_dict()
                    ],
                    "total_rows": len(value),
                }
            ],
        }


LUMLFLOW_KINDS: list[DemoFrameKind] = [DemoFrameKind()]
'''

_DEMO_CELLS = {
    "data": '''from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from lib.demo import DemoFrame


class Data:
    params: dict[str, int] = {"seed": 7, "rows": 12}
    volatility: str = "seeded"
    produces: dict[str, dict[str, str]] = {
        "frame": {"type": "asset", "kind": "frame"}
    }

    def materialize(self, ctx: "Any") -> "dict[str, DemoFrame]":
        import random
        from lib.demo import DemoFrame

        ctx.seed()
        rows = []
        for row_id in range(ctx.params["rows"]):
            x = round(random.uniform(-1.0, 1.0), 4)
            y = round(random.uniform(-1.0, 1.0), 4)
            rows.append({"row": row_id, "x": x, "y": y, "label": int(x + y > 0)})
        return {"frame": DemoFrame(rows)}
''',
    "features": '''from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from lib.demo import DemoFrame


class Features:
    consumes: dict[str, str] = {"data": "data.frame"}
    produces: dict[str, dict[str, str]] = {
        "frame": {"type": "asset", "kind": "frame"}
    }

    def materialize(
        self, ctx: "Any", data: "DemoFrame"
    ) -> "dict[str, DemoFrame]":
        from lib.demo import DemoFrame

        rows = []
        for row in data.to_dict():
            rows.append({
                "row": row["row"],
                "signal": round(row["x"] + row["y"], 4),
                "distance": round(abs(row["x"] - row["y"]), 4),
                "label": row["label"],
            })
        return {"frame": DemoFrame(rows)}
''',
    "train": '''from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from lib.demo import DemoFrame


class Train:
    consumes: dict[str, str] = {"features": "features.frame"}
    params: dict[str, int | float] = {
        "seed": 17,
        "learning_rate": 0.2,
        "epochs": 6,
    }
    volatility: str = "seeded"
    produces: dict[str, dict[str, str]] = {
        "curve": {"type": "asset", "kind": "metric"}
    }

    def materialize(
        self, ctx: "Any", features: "DemoFrame"
    ) -> "dict[str, dict[str, float]]":
        import random

        ctx.seed()
        rows = features.to_dict()
        signal = sum(abs(row["signal"]) for row in rows) / len(rows)
        curve = {}
        for epoch in range(1, ctx.params["epochs"] + 1):
            decay = 1.0 / (1.0 + ctx.params["learning_rate"] * epoch)
            curve[str(epoch)] = round(
                decay + signal * 0.03 + random.random() * 0.005,
                4,
            )
        return {"curve": curve}
''',
    "evaluate": '''from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from lib.demo import DemoFrame


class Evaluate:
    consumes: dict[str, str] = {
        "features": "features.frame",
        "curve": "train.curve",
    }
    produces: dict[str, dict[str, str]] = {
        "report": {"type": "asset", "kind": "eval"}
    }

    def materialize(
        self,
        ctx: "Any",
        features: "DemoFrame",
        curve: "dict[str, float]",
    ) -> "dict[str, list[dict[str, int | float]]]":
        final_loss = curve[str(len(curve))]
        report = []
        for row in features.to_dict():
            prediction = int(row["signal"] >= 0)
            report.append({
                "row": row["row"],
                "prediction": prediction,
                "label": row["label"],
                "score": round(1.0 - final_loss, 4),
            })
        return {"report": report}
''',
    "plot": '''from __future__ import annotations

from typing import Any


class Plot:
    consumes: dict[str, str] = {
        "curve": "train.curve",
        "report": "evaluate.report",
    }
    produces: dict[str, dict[str, str]] = {
        "chart": {"type": "asset", "kind": "plot"}
    }

    def materialize(
        self,
        ctx: "Any",
        curve: "dict[str, float]",
        report: "list[dict[str, int | float]]",
    ) -> "dict[str, dict[str, Any]]":
        correct = sum(row["prediction"] == row["label"] for row in report)
        accuracy = correct / len(report)
        values = [
            {"epoch": int(epoch), "loss": loss, "accuracy": round(accuracy, 4)}
            for epoch, loss in curve.items()
        ]
        return {
            "chart": {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "mark": {"type": "line", "point": True},
                "data": {"values": values},
                "encoding": {
                    "x": {"field": "epoch", "type": "quantitative"},
                    "y": {"field": "loss", "type": "quantitative"},
                },
            }
        }
''',
    "note": '''from __future__ import annotations


class Note:
    """Demo walkthrough: run plot, sweep train.learning_rate, and compare variants."""
''',
}


def scaffold_demo(store: FlowStore) -> None:
    atomic_write(store.flow_dir / "lib" / "demo.py", _DEMO_LIBRARY.encode())
    paths: list[str | Path] = []
    for slug, source in _DEMO_CELLS.items():
        path = store.flow_dir / "cells" / f"{slug}.py"
        atomic_write(path, source.encode())
        paths.append(path)
    accept_cells(
        store,
        paths,
        actor="system:init",
        intent="scaffold demo flow",
    )
