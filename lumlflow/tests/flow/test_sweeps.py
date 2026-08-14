from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from lumlflow.flow.daemon.api import DaemonRpcError, DaemonRuntime
from lumlflow.flow.dsl.accept import accept_cell
from lumlflow.flow.scheduler.planner import ExecutionResult, PlanNode, Scheduler
from lumlflow.flow.store.branches import get_branch, selections
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import InputRecord, JsonValue, OutputRecord


def _source() -> str:
    return """class Train:
    params = {"lr": 0.1, "epochs": 10}
    produces = {"score": "asset"}

    def materialize(self, ctx):
        return {"score": ctx.params["lr"]}
"""


def _selected_params(store: FlowStore, branch: str) -> dict[str, object]:
    connection = store.index.connection
    assert connection is not None
    row = connection.execute(
        """
        SELECT json_extract(versions.manifest, '$.params')
        FROM selections
        JOIN asset_versions AS versions USING(version_id)
        WHERE selections.branch_id = ?
        """,
        (get_branch(store, branch).branch_id,),
    ).fetchone()
    assert row is not None
    value = json.loads(str(row[0]))
    assert isinstance(value, dict)
    return value


async def test_param_edit_creates_a_version_without_rewriting_source(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    path = store.flow_dir / "cells" / "train.py"
    path.write_text(_source(), encoding="utf-8")
    accepted = accept_cell(store, path)
    source_before = path.read_bytes()
    runtime = DaemonRuntime(store, watch_worktree=False)
    try:
        result = await runtime.dispatch(
            "params_edit",
            {
                "slug": "train",
                "params": {"lr": 0.2, "epochs": 10},
                "base_definition_hash": accepted.definition_hash,
            },
        )

        result = cast(dict[str, JsonValue], result)
        assert path.read_bytes() == source_before
        assert result["params"] == {"lr": 0.2, "epochs": 10}
        connection = store.index.connection
        assert connection is not None
        versions = connection.execute(
            """
            SELECT source_hash, bound_hash, definition_hash
            FROM asset_versions WHERE uid = ? ORDER BY created_step
            """,
            (accepted.uid,),
        ).fetchall()
        assert len(versions) == 2
        assert versions[0]["source_hash"] == versions[1]["source_hash"]
        assert versions[0]["bound_hash"] == versions[1]["bound_hash"]
        assert versions[0]["definition_hash"] != versions[1]["definition_hash"]
    finally:
        await runtime.close()


async def test_param_edit_rejects_stale_bases_and_non_json_numbers(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    path = store.flow_dir / "cells" / "train.py"
    path.write_text(_source(), encoding="utf-8")
    accepted = accept_cell(store, path)
    runtime = DaemonRuntime(store, watch_worktree=False)
    try:
        await runtime.dispatch(
            "params_edit",
            {
                "slug": "train",
                "params": {"lr": 0.2, "epochs": 10},
                "base_definition_hash": accepted.definition_hash,
            },
        )
        with pytest.raises(DaemonRpcError) as conflict:
            await runtime.dispatch(
                "params_edit",
                {
                    "slug": "train",
                    "params": {"lr": 0.3, "epochs": 10},
                    "base_definition_hash": accepted.definition_hash,
                },
            )
        assert conflict.value.code == -32009
        with pytest.raises(DaemonRpcError, match="JSON object"):
            await runtime.dispatch(
                "params_edit",
                {
                    "slug": "train",
                    "params": {"lr": float("nan")},
                    "base_definition_hash": "current",
                },
            )
    finally:
        await runtime.close()


async def test_sweep_forks_one_snapshot_and_reuses_memos_before_winner_adopt(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    path = store.flow_dir / "cells" / "train.py"
    path.write_text(_source(), encoding="utf-8")
    accepted = accept_cell(store, path)
    runtime = DaemonRuntime(store, watch_worktree=False)
    try:
        result = await runtime.dispatch(
            "sweep",
            {
                "slug": "train",
                "overrides": [
                    {"lr": 0.2},
                    {"lr": 0.2},
                    {"lr": 0.3},
                ],
                "group": "learning-rate",
            },
        )
        result = cast(dict[str, JsonValue], result)
        raw_variants = result["variants"]
        assert isinstance(raw_variants, list)
        assert all(isinstance(variant, dict) for variant in raw_variants)
        variants = cast(list[dict[str, JsonValue]], raw_variants)
        names = [str(variant["branch"]) for variant in variants]
        created = [get_branch(store, name) for name in names]
        assert {branch.sweep_group for branch in created} == {"learning-rate"}
        assert len({branch.fork_step for branch in created}) == 1
        assert all(
            next(
                item
                for item in selections(store, branch.name)
                if item.uid == accepted.uid
            ).pinned
            for branch in created
        )

        calls: list[float] = []

        async def execute(
            node: PlanNode, _inputs: dict[str, InputRecord]
        ) -> ExecutionResult:
            params = node.manifest["params"]
            assert isinstance(params, dict)
            lr_value = params["lr"]
            assert isinstance(lr_value, (int, float))
            lr = float(lr_value)
            calls.append(lr)
            return ExecutionResult(
                outputs={
                    "score": OutputRecord(
                        content_hash=f"{int(lr * 100):064d}",
                        kind="pickle",
                        size=1,
                        persisted=True,
                    )
                },
                cost_seconds=0.1,
            )

        summaries = []
        for branch in created:
            summaries.append(
                await Scheduler(store, execute, lib_tree_hash="lib").run(
                    branch.branch_id, accepted.uid
                )
            )

        assert calls == [0.2, 0.3]
        assert summaries[1].memo_hits == (accepted.uid,)

        comparison = await runtime.dispatch(
            "sweep_compare", {"group": "learning-rate"}
        )
        comparison = cast(dict[str, JsonValue], comparison)
        compared = comparison["variants"]
        assert isinstance(compared, list)
        first_compared = compared[0]
        assert isinstance(first_compared, dict)
        output_hashes = first_compared["output_hashes"]
        assert isinstance(output_hashes, dict)
        assert output_hashes["train.score"]

        adopted = await runtime.dispatch(
            "adopt",
            {
                "slug": "train",
                "from_branch": names[2],
                "branch": "main",
                "project": False,
            },
        )
        adopted = cast(dict[str, JsonValue], adopted)
        assert adopted["adopted"] is True
        assert _selected_params(store, "main") == {"epochs": 10, "lr": 0.3}
    finally:
        await runtime.close()
