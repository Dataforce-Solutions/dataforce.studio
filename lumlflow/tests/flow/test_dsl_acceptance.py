import json
from pathlib import Path

from lumlflow.flow.dsl.accept import (
    accept_cell,
    compute_lib_tree_hash,
    reaccept_namespace_consumers,
)
from lumlflow.flow.dsl.loader import load_cell
from lumlflow.flow.dsl.normalize import read_flow_cells
from lumlflow.flow.hashing import sha256_bytes
from lumlflow.flow.ids import mint_ulid
from lumlflow.flow.scheduler.staleness import derive_staleness
from lumlflow.flow.store.branches import fork, remove_selection, selections
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import InputRecord, OutputRecord, RunRecordedOp


def _write_cell(flow_dir: Path, slug: str, source: str) -> Path:
    path = flow_dir / "cells" / f"{slug}.py"
    path.write_text(source, encoding="utf-8")
    return path


def _manifest(store: FlowStore, version_id: str) -> dict[str, object]:
    connection = store.index.connection
    assert connection is not None
    row = connection.execute(
        "SELECT manifest FROM asset_versions WHERE version_id = ?", (version_id,)
    ).fetchone()
    assert row is not None
    return json.loads(row[0])


def _selected_definition(store: FlowStore, uid: str) -> str:
    connection = store.index.connection
    assert connection is not None
    row = connection.execute(
        """
        SELECT versions.definition_hash FROM selections
        JOIN asset_versions AS versions USING(version_id)
        WHERE selections.branch_id = ? AND selections.uid = ?
        """,
        (store.branch_id, uid),
    ).fetchone()
    assert row is not None
    return str(row[0])


def _materialize(
    store: FlowStore,
    version_id: str,
    value: str,
    *,
    output_name: str = "value",
    inputs: dict[str, InputRecord] | None = None,
) -> tuple[str, str]:
    mat_id = mint_ulid()
    content_hash = sha256_bytes(value.encode())
    store.commit(
        actor="system:test",
        intent="materialize test cell",
        ops=[
            RunRecordedOp(
                mat_id=mat_id,
                version_id=version_id,
                memo_key=mint_ulid(),
                state="succeeded",
                inputs=inputs or {},
                outputs={
                    output_name: OutputRecord(
                        content_hash=content_hash,
                        kind="pickle",
                        size=len(value),
                        persisted=True,
                    )
                },
            )
        ],
    )
    return mat_id, content_hash


def test_new_cell_gets_uid_and_version_without_execution(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    marker = store.flow_dir / "executed"
    path = _write_cell(
        store.flow_dir,
        "train_model",
        f'''class TrainModel:
    """Train a model."""
    produces = {{"model": "model"}}

    def materialize(self, ctx):
        open({str(marker)!r}, "w").write("bad")
''',
    )

    result = accept_cell(store, path, actor="agent:test")

    lines = path.read_text().splitlines()
    assert lines[1] == '    """Train a model."""'
    assert lines[2] == f'    uid = "{result.uid}"'
    assert read_flow_cells(store.flow_dir) == {"train_model": result.uid}
    assert not marker.exists()
    assert _manifest(store, result.version_id)["produces"] == {"model": "model"}


def test_ambiguous_and_invalid_files_are_accepted_with_flags(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    initial_lib_hash = compute_lib_tree_hash(store.flow_dir)
    ambiguous = _write_cell(
        store.flow_dir,
        "ambiguous",
        """class First:
    def materialize(self, ctx):
        return {}

class Second:
    def materialize(self, ctx):
        return {}
""",
    )
    invalid = _write_cell(store.flow_dir, "oops", "def helper():\n    return 1\n")

    ambiguous_result = accept_cell(store, ambiguous)
    invalid_result = accept_cell(store, invalid)

    ambiguous_manifest = _manifest(store, ambiguous_result.version_id)
    assert "ambiguous" in ambiguous_result.flags
    assert ambiguous_manifest["candidates"] == ["First", "Second"]
    assert "First, Second" in ambiguous_result.issues[0]
    assert invalid_result.flags == ["invalid"]
    assert _manifest(store, invalid_result.version_id)["classification"] == "invalid"
    assert compute_lib_tree_hash(store.flow_dir) == initial_lib_hash


def test_note_and_incomplete_classification_survives_uid_writeback(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    note = _write_cell(store.flow_dir, "notes", 'class Notes:\n    """Findings."""\n')
    incomplete = _write_cell(
        store.flow_dir,
        "draft",
        'class Draft:\n    consumes = {"data": "missing.value"}\n',
    )

    note_result = accept_cell(store, note)
    incomplete_result = accept_cell(store, incomplete)

    assert note_result.flags == []
    assert _manifest(store, note_result.version_id)["classification"] == "note"
    assert "incomplete" in incomplete_result.flags
    assert _manifest(store, incomplete_result.version_id)["classification"] == (
        "incomplete"
    )


def test_comment_only_edit_keeps_definition_hash(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    path = _write_cell(
        store.flow_dir,
        "features",
        """class Features:
    produces = {"data": "dataset"}
    params = {"limit": 10}
    def materialize(self, ctx):
        return {"data": [1]}
""",
    )
    first = accept_cell(store, path)
    _materialize(store, first.version_id, "features")
    path.write_text(f"# comment only change\n{path.read_text()}\n", encoding="utf-8")

    second = accept_cell(store, path)

    assert first.version_id != second.version_id
    assert first.definition_hash == second.definition_hash
    assert derive_staleness(store, "main", first.uid).direct.state == "synced"


def test_copied_cell_is_reminted_with_provenance(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    original = _write_cell(
        store.flow_dir,
        "eval",
        """class Evaluate:
    produces = {"score": "asset"}
    def materialize(self, ctx):
        return {"score": 1}
""",
    )
    accepted = accept_cell(store, original)
    copied = store.flow_dir / "cells" / "eval_v2.py"
    copied.write_text(original.read_text(), encoding="utf-8")

    copy_result = accept_cell(store, copied)

    assert copy_result.uid != accepted.uid
    assert copy_result.copied_from == accepted.uid
    assert f'uid = "{copy_result.uid}"' in copied.read_text()
    assert f'uid = "{accepted.uid}"' in original.read_text()
    connection = store.index.connection
    assert connection is not None
    copied_from = connection.execute(
        "SELECT copied_from FROM cells WHERE uid = ?", (copy_result.uid,)
    ).fetchone()
    assert copied_from is not None and copied_from[0] == accepted.uid


def test_move_rewires_consumers_without_changing_definition(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    producer = _write_cell(
        store.flow_dir,
        "train_model",
        """class Train:
    produces = {"model": "model"}
    def materialize(self, ctx):
        return {"model": object()}
""",
    )
    producer_result = accept_cell(store, producer)
    producer_mat, producer_hash = _materialize(
        store, producer_result.version_id, "model", output_name="model"
    )
    consumer = _write_cell(
        store.flow_dir,
        "evaluate",
        """class Evaluate:
    consumes = {"model": "train_model.model"}
    produces = {"score": "asset"}
    def materialize(self, ctx, model):
        return {"score": 1}
""",
    )
    consumer_result = accept_cell(store, consumer)
    _materialize(
        store,
        consumer_result.version_id,
        "score",
        inputs={
            "model": InputRecord(
                uid=producer_result.uid,
                output="model",
                content_hash=producer_hash,
                mat_id=producer_mat,
            )
        },
    )
    before = consumer_result.definition_hash
    renamed = producer.with_name("train_xgb.py")
    producer.rename(renamed)

    rename_result = accept_cell(store, renamed)

    assert rename_result.uid == producer_result.uid
    assert rename_result.renamed_from == "train_model"
    assert "train_xgb.model" in consumer.read_text()
    assert _selected_definition(store, consumer_result.uid) == before
    assert any(operation.op == "renamed" for operation in rename_result.transaction.ops)
    assert derive_staleness(store, "main", producer_result.uid).direct.state == "synced"
    assert derive_staleness(store, "main", consumer_result.uid).direct.state == "synced"


def test_dropped_uid_reattaches_from_flow_index(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    path = _write_cell(
        store.flow_dir,
        "features",
        """class Features:
    produces = {"value": "asset"}
    def materialize(self, ctx):
        return {"value": 1}
""",
    )
    first = accept_cell(store, path)
    path.write_text(path.read_text().replace(f'    uid = "{first.uid}"\n', ""))

    second = accept_cell(store, path)

    assert second.uid == first.uid
    assert f'uid = "{first.uid}"' in path.read_text()


def test_dangling_reference_has_did_you_mean(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    producer = _write_cell(
        store.flow_dir,
        "features",
        """class Features:
    produces = {"train_split": "dataset"}
    def materialize(self, ctx):
        return {"train_split": []}
""",
    )
    accept_cell(store, producer)
    consumer = _write_cell(
        store.flow_dir,
        "train",
        """class Train:
    consumes = {"data": "features.train_spilt"}
    def materialize(self, ctx, data):
        return {}
""",
    )

    result = accept_cell(store, consumer)

    assert "dangling_ref" in result.flags
    assert result.issues == [
        "unknown reference `features.train_spilt` — did you mean "
        "`features.train_split`?"
    ]
    assert _manifest(store, result.version_id)["consumes"] == {
        "data": "features.train_spilt"
    }


def test_partial_reference_is_canonicalized_or_flagged_with_candidates(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    features = _write_cell(
        store.flow_dir,
        "features",
        """class Features:
    produces = {"train_split": "dataset"}
    def materialize(self, ctx):
        return {"train_split": []}
""",
    )
    accept_cell(store, features)
    consumer = _write_cell(
        store.flow_dir,
        "train",
        """class Train:
    consumes = {"train": "train_split"}
    def materialize(self, ctx, train):
        return {}
""",
    )

    canonical = accept_cell(store, consumer)

    assert "features.train_split" in consumer.read_text()
    assert canonical.flags == []
    assert _manifest(store, canonical.version_id)["consumes"] == {
        "train": f"uid:{read_flow_cells(store.flow_dir)['features']}.train_split"
    }

    backup = _write_cell(
        store.flow_dir,
        "backup",
        """class Backup:
    produces = {"train_split": "dataset"}
    def materialize(self, ctx):
        return {"train_split": []}
""",
    )
    accept_cell(store, backup)
    ambiguous = _write_cell(
        store.flow_dir,
        "compare",
        """class Compare:
    consumes = {"train": "train_split"}
    def materialize(self, ctx, train):
        return {}
""",
    )

    ambiguous_result = accept_cell(store, ambiguous)

    assert "ambiguous_ref" in ambiguous_result.flags
    assert "backup.train_split" in ambiguous_result.issues[0]
    assert "features.train_split" in ambiguous_result.issues[0]


def test_namespace_change_reaccepts_bound_consumers(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    producer = _write_cell(
        store.flow_dir,
        "features",
        """class Features:
    produces = {"data": "dataset"}
    def materialize(self, ctx):
        return {"data": []}
""",
    )
    original = accept_cell(store, producer)
    consumer = _write_cell(
        store.flow_dir,
        "train",
        """class Train:
    consumes = {"data": "features.data"}
    def materialize(self, ctx, data):
        return {}
""",
    )
    original_consumer = accept_cell(store, consumer)
    replacement_uid = mint_ulid()
    remove_selection(store, "main", original.uid)
    producer.write_text(
        producer.read_text().replace(original.uid, replacement_uid), encoding="utf-8"
    )
    replacement = accept_cell(store, producer)

    results = reaccept_namespace_consumers(
        store, changed_uid=replacement.uid, actor="system:test"
    )

    assert [result.uid for result in results] == [original_consumer.uid]
    assert results[0].definition_hash != original_consumer.definition_hash
    assert _manifest(store, results[0].version_id)["consumes"] == {
        "data": f"uid:{replacement_uid}.data"
    }


def test_per_branch_delete_flags_consumers_only_on_deleted_branch(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    producer = _write_cell(
        store.flow_dir,
        "metrics",
        """class Metrics:
    produces = {"summary": "asset"}
    def materialize(self, ctx):
        return {"summary": {}}
""",
    )
    producer_result = accept_cell(store, producer)
    consumer = _write_cell(
        store.flow_dir,
        "plot_curves",
        """class PlotCurves:
    consumes = {"summary": "metrics.summary"}
    produces = {"plot": "asset"}
    def materialize(self, ctx, summary):
        return {"plot": summary}
""",
    )
    consumer_result = accept_cell(store, consumer)
    other_branch = fork(store, "main", "other")

    remove_selection(store, "main", producer_result.uid)
    reaccepted = reaccept_namespace_consumers(
        store,
        branch=store.branch_id,
        changed_uid=producer_result.uid,
        actor="system:test",
    )

    assert [result.uid for result in reaccepted] == [consumer_result.uid]
    assert "dangling_ref" in reaccepted[0].flags
    other_selection = next(
        item
        for item in selections(store, other_branch.branch_id)
        if item.uid == consumer_result.uid
    )
    assert other_selection.version_id == consumer_result.version_id
    other_flags = _manifest(store, other_selection.version_id)["flags"]
    assert isinstance(other_flags, list)
    assert "dangling_ref" not in other_flags


def test_lowercase_divergence_lib_hash_and_directory_scope(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    uppercase = _write_cell(
        store.flow_dir,
        "Train",
        """class Train:
    def materialize(self, ctx):
        return {}
""",
    )
    first = accept_cell(store, uppercase)
    assert first.path.name == "train.py"
    assert "slug_normalized" in first.flags

    first.path.write_text(first.path.read_text().replace("return {}", "return {1: 2}"))
    normal_edit = accept_cell(store, first.path)
    first.path.write_text(
        first.path.read_text().replace("return {1: 2}", "return {2: 3}")
    )
    divergent = accept_cell(store, first.path, parent_version=first.version_id)
    assert "divergent" in divergent.flags
    assert not divergent.selected
    assert _selected_definition(store, first.uid) == normal_edit.definition_hash

    helper = store.flow_dir / "lib" / "helper.py"
    helper.write_text("VALUE = 1\n")
    initial_hash = compute_lib_tree_hash(store.flow_dir)
    helper.write_text("VALUE = 2\n")
    assert compute_lib_tree_hash(store.flow_dir) != initial_hash
    outside = load_cell(helper, store.flow_dir)
    assert outside.classification == "lib"
