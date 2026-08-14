from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from lumlflow_kernel.executor import Executor


def test_eval_hydrates_only_referenced_names_and_isolates_mutation(
    tmp_path: Path,
) -> None:
    executor = Executor(tmp_path, lambda event, payload: None)
    values = executor.registry.serialize([1, 2, 3], "pickle")
    unused = executor.registry.serialize([9], "pickle")
    branch_slice = {
        "prepare.values": {
            "value_ref": values.value_ref,
            "content_hash": values.content_hash,
            "kind": values.kind,
        },
        "other.unused": {
            "value_ref": unused.value_ref,
            "content_hash": unused.content_hash,
            "kind": unused.kind,
        },
    }

    result = executor.evaluate(
        branch_slice,
        "values.clear(); len(values)",
        paranoid=True,
    )

    assert result == {
        "state": "succeeded",
        "result": "0",
        "result_type": "int",
        "stdout": "",
        "stderr": "",
        "touched": ["prepare.values"],
        "preview": {
            "schema": 1,
            "kind": "pickle",
            "blocks": [{"type": "markdown", "text": "0"}],
        },
    }
    assert (unused.value_ref, unused.kind) not in executor._hot_values
    assert executor._get_cached(values.value_ref, values.kind) == [1, 2, 3]
    assert executor.registry.deserialize(values.value_ref, values.kind) == [1, 2, 3]


def test_eval_resolves_unique_output_and_cell_qualified_names(tmp_path: Path) -> None:
    executor = Executor(tmp_path, lambda event, payload: None)
    first = executor.registry.serialize(4, "pickle")
    second = executor.registry.serialize(7, "pickle")
    branch_slice = {
        "left.score": {
            "value_ref": first.value_ref,
            "content_hash": first.content_hash,
            "kind": first.kind,
        },
        "right.score": {
            "value_ref": second.value_ref,
            "content_hash": second.content_hash,
            "kind": second.kind,
        },
        "right.total": {
            "value_ref": second.value_ref,
            "content_hash": second.content_hash,
            "kind": second.kind,
        },
    }

    qualified = executor.evaluate(branch_slice, "left.score + right.score")
    unique = executor.evaluate(branch_slice, "total + 1")
    ambiguous = executor.evaluate(branch_slice, "score")

    assert qualified["result"] == "11"
    assert qualified["preview"] == {
        "schema": 1,
        "kind": "pickle",
        "blocks": [{"type": "markdown", "text": "11"}],
    }
    assert qualified["touched"] == ["left.score", "right.score"]
    assert unique["result"] == "8"
    assert ambiguous["state"] == "failed"
    assert ambiguous["error_type"] == "NameError"
    assert "ambiguous" in str(ambiguous["error"])
    assert "left.score" in str(ambiguous["error"])
    assert "right.score" in str(ambiguous["error"])


def test_eval_resolves_assets_inside_defined_functions(tmp_path: Path) -> None:
    executor = Executor(tmp_path, lambda event, payload: None)
    serialized = executor.registry.serialize([2, 3], "pickle")
    branch_slice = {
        "prepare.values": {
            "value_ref": serialized.value_ref,
            "content_hash": serialized.content_hash,
            "kind": serialized.kind,
        }
    }

    result = executor.evaluate(
        branch_slice,
        "def total():\n    return sum(values)\ntotal()",
    )

    assert result["state"] == "succeeded"
    assert result["result"] == "5"
    assert result["touched"] == ["prepare.values"]


def test_eval_reports_syntax_and_unknown_name_errors(tmp_path: Path) -> None:
    executor = Executor(tmp_path, lambda event, payload: None)

    syntax = executor.evaluate({}, "if")
    missing = executor.evaluate({}, "missing_asset")

    assert syntax["state"] == "failed"
    assert syntax["error_type"] == "SyntaxError"
    assert "invalid syntax" in str(syntax["error"])
    assert missing == {
        "state": "failed",
        "error_type": "NameError",
        "error": "name 'missing_asset' is not defined",
    }


def test_paranoid_eval_rehash_evicts_a_mutated_cached_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executor = Executor(tmp_path, lambda event, payload: None)
    serialized = executor.registry.serialize([1, 2, 3], "pickle")
    descriptor = {
        "value_ref": serialized.value_ref,
        "content_hash": serialized.content_hash,
        "kind": serialized.kind,
    }
    cached = executor._get_cached(serialized.value_ref, serialized.kind)
    original_deserialize = executor.registry.deserialize

    def broken_deserialize(value_ref: str, kind: str) -> Any:
        assert value_ref == serialized.value_ref
        assert kind == serialized.kind
        return cached

    monkeypatch.setattr(executor.registry, "deserialize", broken_deserialize)

    result = executor.evaluate(
        {"prepare.values": descriptor},
        "values.clear()",
        paranoid=True,
    )

    assert result["state"] == "failed"
    assert "mutated a cached asset" in str(result["error"])
    assert (serialized.value_ref, serialized.kind) not in executor._hot_values
    monkeypatch.setattr(executor.registry, "deserialize", original_deserialize)
    assert executor._get_cached(serialized.value_ref, serialized.kind) == [1, 2, 3]
