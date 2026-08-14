from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast

import pytest
from lumlflow.cli import app
from lumlflow.flow.daemon.api import DaemonRuntime
from lumlflow.flow.dsl.loader import load_cell
from lumlflow.flow.dsl.normalize import read_flow_cells
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import JsonValue
from typer.testing import CliRunner

runner = CliRunner()


def _init_demo(tmp_path: Path) -> Path:
    flow_dir = tmp_path / "demo.flow"
    result = runner.invoke(app, ["init", str(flow_dir), "--demo", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["root"] == str(flow_dir.resolve())
    return flow_dir


def _install_test_venv(flow_dir: Path) -> None:
    venv = flow_dir / ".venv"
    try:
        venv.symlink_to(Path(sys.prefix).resolve(), target_is_directory=True)
    except OSError:
        pytest.skip("the end-to-end demo test requires a venv symlink")


def test_demo_init_accepts_the_complete_cell_set(tmp_path: Path) -> None:
    flow_dir = _init_demo(tmp_path)

    cells = read_flow_cells(flow_dir)
    assert set(cells) == {"data", "features", "train", "evaluate", "plot", "note"}
    assert all(cells.values())
    checkout = (flow_dir / ".lumlflow" / "CHECKOUT.md").read_text(encoding="utf-8")
    assert "Checkpoint: step 2" in checkout
    assert "Staleness: unmaterialized: 6" in checkout
    for slug in cells:
        loaded = load_cell(flow_dir / "cells" / f"{slug}.py", flow_dir)
        assert loaded.uid == cells[slug]
        assert loaded.issues == []
    assert load_cell(flow_dir / "cells" / "note.py", flow_dir).classification == "note"
    store = FlowStore.open(flow_dir)
    try:
        connection = store.index.connection
        assert connection is not None
        rows = connection.execute(
            """
            SELECT versions.slug, versions.manifest
            FROM selections
            JOIN asset_versions AS versions USING(version_id)
            WHERE selections.branch_id = ?
            """,
            (store.branch_id,),
        ).fetchall()
        manifests = {
            str(row["slug"]): cast(dict[str, JsonValue], json.loads(row["manifest"]))
            for row in rows
        }
        assert all(manifest["issues"] == [] for manifest in manifests.values())
        assert manifests["note"]["classification"] == "note"
    finally:
        store.close()


async def test_demo_chain_runs_green_with_all_preview_kinds(tmp_path: Path) -> None:
    flow_dir = _init_demo(tmp_path)
    _install_test_venv(flow_dir)
    runtime = DaemonRuntime(FlowStore.open(flow_dir), watch_worktree=False)
    try:
        result = cast(
            dict[str, JsonValue],
            await runtime.dispatch("run", {"target": "plot"}),
        )

        assert len(cast(list[JsonValue], result["executed"])) == 5
        assert result["memo_hits"] == []
        status = cast(dict[str, JsonValue], await runtime.dispatch("status", {}))
        records = cast(list[dict[str, JsonValue]], status["cell_status"])
        states = {str(record["slug"]): record["state"] for record in records}
        assert states == {
            "data": "synced",
            "features": "synced",
            "train": "synced",
            "evaluate": "synced",
            "plot": "synced",
            "note": "unmaterialized",
        }
        previews = {
            target: cast(
                dict[str, JsonValue],
                await runtime.dispatch("asset_preview", {"target": target}),
            )["kind"]
            for target in (
                "data.frame",
                "features.frame",
                "train.curve",
                "evaluate.report",
                "plot.chart",
            )
        }
        assert previews == {
            "data.frame": "frame",
            "features.frame": "frame",
            "train.curve": "metric",
            "evaluate.report": "eval",
            "plot.chart": "plot",
        }
    finally:
        await runtime.close()


async def test_demo_param_change_recomputes_downstream_and_revert_memo_hits(
    tmp_path: Path,
) -> None:
    flow_dir = _init_demo(tmp_path)
    _install_test_venv(flow_dir)
    runtime = DaemonRuntime(FlowStore.open(flow_dir), watch_worktree=False)
    try:
        await runtime.dispatch("run", {"target": "plot"})
        train = cast(
            dict[str, JsonValue],
            await runtime.dispatch("cells_show", {"slug": "train"}),
        )
        original_hash = cast(str, train["definition_hash"])
        original_params = cast(dict[str, JsonValue], train["manifest"])["params"]
        assert isinstance(original_params, dict)
        changed_params = {**original_params, "learning_rate": 0.3}
        changed = cast(
            dict[str, JsonValue],
            await runtime.dispatch(
                "params_edit",
                {
                    "slug": "train",
                    "params": changed_params,
                    "base_definition_hash": original_hash,
                },
            ),
        )

        changed_run = cast(
            dict[str, JsonValue],
            await runtime.dispatch("run", {"target": "plot"}),
        )
        assert len(cast(list[JsonValue], changed_run["executed"])) == 3
        assert changed_run["memo_hits"] == []

        await runtime.dispatch(
            "params_edit",
            {
                "slug": "train",
                "params": original_params,
                "base_definition_hash": cast(str, changed["definition_hash"]),
            },
        )
        reverted_run = cast(
            dict[str, JsonValue],
            await runtime.dispatch("run", {"target": "plot"}),
        )

        assert reverted_run["executed"] == []
        assert len(cast(list[JsonValue], reverted_run["memo_hits"])) == 3
    finally:
        await runtime.close()


async def test_demo_train_params_are_sweepable(tmp_path: Path) -> None:
    flow_dir = _init_demo(tmp_path)
    runtime = DaemonRuntime(FlowStore.open(flow_dir), watch_worktree=False)
    try:
        train = cast(
            dict[str, JsonValue],
            await runtime.dispatch("cells_show", {"slug": "train"}),
        )
        manifest = cast(dict[str, JsonValue], train["manifest"])
        assert manifest["params"] == {
            "seed": 17,
            "learning_rate": 0.2,
            "epochs": 6,
        }

        sweep = cast(
            dict[str, JsonValue],
            await runtime.dispatch(
                "sweep",
                {
                    "slug": "train",
                    "group": "demo-learning-rate",
                    "overrides": [
                        {"learning_rate": 0.1},
                        {"learning_rate": 0.3},
                    ],
                },
            ),
        )

        variants = cast(list[dict[str, JsonValue]], sweep["variants"])
        assert [variant["params"] for variant in variants] == [
            {"seed": 17, "learning_rate": 0.1, "epochs": 6},
            {"seed": 17, "learning_rate": 0.3, "epochs": 6},
        ]
    finally:
        await runtime.close()
