from __future__ import annotations

import json
from pathlib import Path

import pytest
from lumlflow.cli import app
from lumlflow.flow.daemon.projections import ProjectionManager
from lumlflow.flow.dsl.accept import accept_cells
from lumlflow.flow.portable import export_projection, import_projection
from lumlflow.flow.store.branches import fork
from lumlflow.flow.store.flowstore import FlowStore
from typer.testing import CliRunner

runner = CliRunner()


def _train_source(epochs: int, value: int) -> str:
    return f"""class Train:
    params = {{"epochs": {epochs}}}
    produces = {{"value": "asset"}}

    def materialize(self, ctx):
        return {{"value": {value}}}
"""


def _score_source() -> str:
    return """class Score:
    consumes = {"trained": "train.value"}
    produces = {"metric": "asset"}

    def materialize(self, ctx, trained):
        return {"metric": trained}
"""


def test_export_import_round_trip_preserves_active_slice_hashes_and_uids(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "original.flow")
    train = store.flow_dir / "cells" / "train.py"
    score = store.flow_dir / "cells" / "score.py"
    train.write_text(_train_source(1, 1), encoding="utf-8")
    score.write_text(_score_source(), encoding="utf-8")
    accept_cells(store, [train, score])
    experiment = fork(store, "main", "experiment")

    train.write_text(_train_source(1, 2), encoding="utf-8")
    changed = accept_cells(store, [train], branch=experiment.branch_id)[0]
    ProjectionManager(store).edit_params(
        "train",
        {"epochs": 5, "label": None, "shuffle": True},
        base_definition_hash=changed.definition_hash,
        branch=experiment.branch_id,
    )

    projection = export_projection(store, experiment.branch_id)
    repeated = export_projection(store, experiment.branch_id)
    main_projection = export_projection(store, "main")

    assert projection.source == repeated.source
    assert compile(projection.source, "flow.py", "exec")
    assert projection.source != main_projection.source
    export_path = tmp_path / "flow.py"
    export_path.write_text(projection.source, encoding="utf-8")

    imported = import_projection(export_path, tmp_path / "imported.flow")
    try:
        imported_projection = export_projection(imported)
        expected = {
            cell.slug: (cell.uid, cell.definition_hash) for cell in projection.cells
        }
        actual = {
            cell.slug: (cell.uid, cell.definition_hash)
            for cell in imported_projection.cells
        }
        assert actual == expected
        assert imported_projection.source == projection.source
        train_cell = next(
            cell for cell in imported_projection.cells if cell.slug == "train"
        )
        assert train_cell.params == {"epochs": 5, "label": None, "shuffle": True}
    finally:
        imported.close()
        store.close()


def test_import_rejects_nonliteral_projection_without_creating_flow(
    tmp_path: Path,
) -> None:
    source = tmp_path / "unsafe.py"
    source.write_text(
        'LUMLFLOW_EXPORT = __import__("pathlib").Path("owned").touch()\n',
        encoding="utf-8",
    )
    destination = tmp_path / "unsafe.flow"

    with pytest.raises(ValueError, match="data must be literal"):
        import_projection(source, destination)

    assert not destination.exists()


def test_export_cli_writes_daemon_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "flow.yaml").write_text("flow: placeholder\n", encoding="utf-8")
    exported_source = "LUMLFLOW_EXPORT = {'format': 1, 'cells': []}\n"

    class FakeClient:
        def request(self, method: str, params: object = None) -> object:
            assert (method, params) == ("export", {"branch": "experiment"})
            return {
                "branch": "experiment",
                "cells": 0,
                "source": exported_source,
            }

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("lumlflow.flow.cli._client", lambda: FakeClient())
    destination = tmp_path / "flow.py"

    result = runner.invoke(
        app,
        ["export", str(destination), "--branch", "experiment", "--json"],
    )

    assert result.exit_code == 0, result.output
    assert destination.read_text(encoding="utf-8") == exported_source
    assert json.loads(result.stdout) == {
        "branch": "experiment",
        "cells": 0,
        "path": str(destination),
    }


def test_import_cli_creates_complete_fresh_flow(tmp_path: Path) -> None:
    original = FlowStore.init(tmp_path / "source.flow")
    cell = original.flow_dir / "cells" / "train.py"
    cell.write_text(_train_source(1, 1), encoding="utf-8")
    accept_cells(original, [cell])
    projection = export_projection(original)
    original.close()
    source = tmp_path / "flow.py"
    source.write_text(projection.source, encoding="utf-8")
    destination = tmp_path / "fresh.flow"

    result = runner.invoke(
        app,
        ["import", str(source), str(destination), "-m", "restore flow", "--json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["root"] == str(destination)
    assert payload["cells"] == 1
    assert (destination / "pyproject.toml").is_file()
    assert (destination / "AGENTS.md").is_file()
