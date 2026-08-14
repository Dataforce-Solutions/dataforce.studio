from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Literal

import pytest
from lumlflow.flow.daemon import api as daemon_api
from lumlflow.flow.daemon.api import DaemonRuntime
from lumlflow.flow.daemon.uploads import OfflineUploadError, UploadQueue
from lumlflow.flow.dsl.accept import accept_cell, compute_lib_tree_hash
from lumlflow.flow.ids import mint_ulid
from lumlflow.flow.scheduler.memo import memo_key_for
from lumlflow.flow.store.branches import fork
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import (
    JsonValue,
    LumlReference,
    OutputRecord,
    RunRecordedOp,
)


class MockLumlAPI:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, dict[str, JsonValue]]] = []

    async def upload(
        self, staged_path: Path, metadata: dict[str, JsonValue]
    ) -> LumlReference:
        self.calls.append((staged_path, metadata))
        return LumlReference(
            collection="drafts",
            artifact_id="artifact-1",
            version="1",
            digest=str(metadata["content_hash"]),
        )


class OfflineAPI:
    async def upload(
        self, staged_path: Path, metadata: dict[str, JsonValue]
    ) -> LumlReference:
        raise OfflineUploadError("offline")


class RecoveringAPI(MockLumlAPI):
    async def upload(
        self, staged_path: Path, metadata: dict[str, JsonValue]
    ) -> LumlReference:
        if not self.calls:
            self.calls.append((staged_path, metadata))
            raise OfflineUploadError("offline")
        return await super().upload(staged_path, metadata)


def _native_materialization(
    store: FlowStore,
    *,
    declaration: str = "experiment",
    state: Literal["succeeded", "failed"] = "succeeded",
    slug: str = "train",
) -> tuple[str, str]:
    path = store.flow_dir / "cells" / f"{slug}.py"
    path.write_text(
        f'''class Train:
    produces = {{"run": "{declaration}"}}
    def materialize(self, ctx):
        return {{"run": {{"accuracy": 0.9}}}}
''',
        encoding="utf-8",
    )
    accepted = accept_cell(store, path)
    mat_id = mint_ulid()
    value_ref = store.cas.put("values", b"staged experiment")
    output = OutputRecord(
        content_hash=value_ref,
        kind="pickle",
        size=17,
        value_ref=value_ref,
        native_type="experiment" if declaration == "experiment" else None,
        metadata={"tracker_records": []},
        persisted=True,
    )
    store.commit(
        actor="system:test",
        intent="run train",
        ops=[
            RunRecordedOp(
                mat_id=mat_id,
                version_id=accepted.version_id,
                memo_key="memo",
                state=state,
                outputs={"run": output} if state == "succeeded" else {},
            )
        ],
    )
    return accepted.uid, mat_id


async def test_successful_native_output_uploads_once_and_rebuilds(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    uid, mat_id = _native_materialization(store)
    api = MockLumlAPI()
    queue = UploadQueue(store, api)

    queued = queue.enqueue_successful(store.branch_id, [uid])

    assert [(item.output, item.state) for item in queued] == [("run", "queued")]
    assert queue.enqueue_successful(store.branch_id, [uid]) == []
    assert list(store.journal.replay())[-1].ops[0].op == "upload_state"

    processed = await queue.process_pending()

    assert processed[0].state == "done"
    assert len(api.calls) == 1
    staged_path, metadata = api.calls[0]
    assert staged_path.read_bytes() == b"staged experiment"
    assert metadata["native_type"] == "experiment"
    connection = store.index.connection
    assert connection is not None
    outputs = json.loads(
        connection.execute(
            "SELECT outputs FROM materializations WHERE mat_id = ?", (mat_id,)
        ).fetchone()[0]
    )
    assert outputs["run"]["luml_ref"] == {
        "artifact_id": "artifact-1",
        "collection": "drafts",
        "digest": outputs["run"]["content_hash"],
        "version": "1",
    }
    store.close()

    rebuilt = FlowStore.open(tmp_path / "flow")
    assert UploadQueue(rebuilt).items()[0].state == "done"
    rebuilt.close()


async def test_offline_upload_stays_queued_and_failed_run_never_enqueues(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    uid, _mat_id = _native_materialization(store)
    failed_uid, _failed_mat_id = _native_materialization(
        store, declaration="model", state="failed", slug="failed_train"
    )
    queue = UploadQueue(store, OfflineAPI())

    queue.enqueue_successful(store.branch_id, [uid, failed_uid])
    result = await queue.process_pending()

    assert len(result) == 1
    assert result[0].state == "queued"
    assert result[0].attempts == 1
    assert queue.items()[0].state == "queued"
    store.close()


async def test_daemon_retries_queued_upload_after_connectivity_returns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(daemon_api, "_UPLOAD_RETRY_SECONDS", 0.01)
    store = FlowStore.init(tmp_path / "flow")
    uid, _mat_id = _native_materialization(store)
    api = RecoveringAPI()
    runtime = DaemonRuntime(store, watch_worktree=False, upload_api=api)
    runtime.uploads.enqueue_successful(store.branch_id, [uid])

    runtime._schedule_uploads()
    for _ in range(100):
        if runtime.uploads.items()[0].state == "done":
            break
        await asyncio.sleep(0.01)

    assert runtime.uploads.items()[0].state == "done"
    assert len(api.calls) == 2
    await runtime.close()


async def test_memo_hit_does_not_enqueue_a_native_upload(tmp_path: Path) -> None:
    store = FlowStore.init(tmp_path / "flow")
    path = store.flow_dir / "cells" / "train.py"
    path.write_text(
        '''class Train:
    produces = {"run": "experiment"}
    def materialize(self, ctx):
        return {"run": {"accuracy": 0.9}}
''',
        encoding="utf-8",
    )
    accepted = accept_cell(store, path)
    child = fork(store, "main", "memo-branch")
    value_ref = store.cas.put("values", b"staged experiment")
    key = memo_key_for(
        accepted.definition_hash,
        compute_lib_tree_hash(store.flow_dir),
        {},
    )
    store.commit(
        actor="system:test",
        intent="run train",
        ops=[
            RunRecordedOp(
                mat_id=mint_ulid(),
                version_id=accepted.version_id,
                memo_key=key,
                state="succeeded",
                outputs={
                    "run": OutputRecord(
                        content_hash=value_ref,
                        kind="pickle",
                        size=17,
                        value_ref=value_ref,
                        native_type="experiment",
                        persisted=True,
                    )
                },
            )
        ],
    )
    runtime = DaemonRuntime(store, watch_worktree=False)

    result = await runtime.dispatch(
        "run", {"target": "train", "branch": child.name}
    )

    assert isinstance(result, dict)
    assert result["executed"] == []
    assert result["memo_hits"] == [accepted.uid]
    assert runtime.uploads.items() == []
    await runtime.close()


def test_promote_stages_existing_inline_output_and_sdk_is_scaffolded(
    tmp_path: Path,
) -> None:
    store = FlowStore.init(tmp_path / "flow")
    (store.flow_dir / "pyproject.toml").write_text(
        '[project]\nname = "flow"\nversion = "0.1.0"\n'
        'dependencies = ["cloudpickle>=3"]\n',
        encoding="utf-8",
    )
    uid, mat_id = _native_materialization(store, declaration="asset")
    pyproject = store.flow_dir / "pyproject.toml"
    assert "luml-sdk" not in pyproject.read_text()

    native_path = store.flow_dir / "cells" / "publish.py"
    native_path.write_text(
        '''class Publish:
    produces = {"model": "model"}
    def materialize(self, ctx):
        return {"model": object()}
''',
        encoding="utf-8",
    )
    accept_cell(store, native_path)
    accept_cell(store, native_path)
    assert pyproject.read_text().count("luml-sdk") == 1

    item = UploadQueue(store).promote(store.branch_id, "train", "run")

    assert item.mat_id == mat_id
    assert item.state == "queued"
    connection = store.index.connection
    assert connection is not None
    outputs = json.loads(
        connection.execute(
            "SELECT outputs FROM materializations WHERE mat_id = ?", (mat_id,)
        ).fetchone()[0]
    )
    assert outputs["run"]["native_type"] == "model"
    assert uid
    store.close()
