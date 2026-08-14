from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, cast

from lumlflow.flow.store.branches import get_branch
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import (
    JsonValue,
    LumlReference,
    PromotedOp,
    UploadRecordedOp,
    UploadStateOp,
)

NativeType = Literal["model", "dataset", "experiment"]


class OfflineUploadError(ConnectionError):
    pass


class LumlUploadAPI(Protocol):
    async def upload(
        self,
        staged_path: Path,
        metadata: dict[str, JsonValue],
    ) -> LumlReference | dict[str, str]: ...


class OfflineLumlAPI:
    async def upload(
        self,
        staged_path: Path,
        metadata: dict[str, JsonValue],
    ) -> LumlReference:
        raise OfflineUploadError("luml upload credentials are unavailable")


@dataclass(frozen=True)
class UploadItem:
    mat_id: str
    output: str
    state: str
    attempts: int


class UploadQueue:
    def __init__(
        self,
        store: FlowStore,
        api: LumlUploadAPI | None = None,
    ) -> None:
        self.store = store
        self.api = api or OfflineLumlAPI()

    def enqueue_successful(
        self,
        branch: str,
        uids: Iterable[str],
        *,
        actor: str = "system:uploads",
    ) -> list[UploadItem]:
        branch_id = get_branch(self.store, branch).branch_id
        connection = self._connection()
        pending: list[tuple[str, str]] = []
        pending_keys: set[tuple[str, str]] = set()
        for uid in uids:
            row = connection.execute(
                """
                SELECT mats.mat_id, mats.state, mats.outputs
                FROM baselines
                JOIN materializations AS mats USING(mat_id)
                WHERE baselines.branch_id = ? AND baselines.uid = ?
                """,
                (branch_id, uid),
            ).fetchone()
            if row is None or row["state"] != "succeeded":
                continue
            outputs = json.loads(str(row["outputs"]))
            for output, value in outputs.items():
                if not isinstance(value, dict) or value.get("native_type") is None:
                    continue
                if value.get("luml_ref") is not None:
                    continue
                exists = connection.execute(
                    "SELECT 1 FROM upload_queue WHERE mat_id = ? AND output = ?",
                    (row["mat_id"], output),
                ).fetchone()
                key = (str(row["mat_id"]), str(output))
                if exists is None and key not in pending_keys:
                    pending.append(key)
                    pending_keys.add(key)
        if not pending:
            return []
        self.store.commit(
            actor=actor,
            intent="queue native outputs",
            branch=branch_id,
            ops=[
                UploadStateOp(
                    mat_id=mat_id,
                    output=output,
                    state="queued",
                    attempts=0,
                )
                for mat_id, output in pending
            ],
        )
        return [UploadItem(mat_id, output, "queued", 0) for mat_id, output in pending]

    def promote(
        self,
        branch: str,
        slug: str,
        output: str,
        *,
        actor: str = "user",
        intent: str | None = None,
    ) -> UploadItem:
        branch_id = get_branch(self.store, branch).branch_id
        row = self._connection().execute(
            """
            SELECT mats.mat_id, mats.state, mats.outputs
            FROM selections
            JOIN asset_versions AS versions USING(version_id)
            JOIN baselines
              ON baselines.branch_id = selections.branch_id
             AND baselines.uid = selections.uid
            JOIN materializations AS mats USING(mat_id)
            WHERE selections.branch_id = ? AND versions.slug = ?
            """,
            (branch_id, slug),
        ).fetchone()
        if row is None or row["state"] != "succeeded":
            raise LookupError(f"materialized cell not found: {slug}")
        outputs = json.loads(str(row["outputs"]))
        value = outputs.get(output)
        if not isinstance(value, dict):
            raise LookupError(f"output not found: {slug}.{output}")
        if value.get("luml_ref") is not None:
            return UploadItem(str(row["mat_id"]), output, "done", 0)
        native_type = _promoted_type(value.get("kind"))
        operation = PromotedOp(
            mat_id=str(row["mat_id"]),
            output=output,
            native_type=native_type,
        )
        state = self._connection().execute(
            "SELECT attempts FROM upload_queue WHERE mat_id = ? AND output = ?",
            (row["mat_id"], output),
        ).fetchone()
        attempts = 0 if state is None else int(state["attempts"])
        self.store.commit(
            actor=actor,
            intent=intent or f"promote {slug}.{output}",
            branch=branch_id,
            ops=[
                operation,
                UploadStateOp(
                    mat_id=str(row["mat_id"]),
                    output=output,
                    state="queued",
                    attempts=attempts,
                ),
            ],
        )
        return UploadItem(str(row["mat_id"]), output, "queued", attempts)

    async def process_pending(self) -> list[UploadItem]:
        rows = self._connection().execute(
            """
            SELECT queue.mat_id, queue.output, queue.state, queue.attempts,
                   mats.branch_id, mats.outputs, versions.slug
            FROM upload_queue AS queue
            JOIN materializations AS mats USING(mat_id)
            JOIN asset_versions AS versions USING(version_id)
            WHERE queue.state IN ('queued', 'failed')
            ORDER BY mats.rowid, queue.output
            """
        ).fetchall()
        return [await self._process(row) for row in rows]

    def items(self) -> list[UploadItem]:
        rows = self._connection().execute(
            "SELECT mat_id, output, state, attempts FROM upload_queue ORDER BY rowid"
        ).fetchall()
        return [
            UploadItem(
                str(row["mat_id"]),
                str(row["output"]),
                str(row["state"]),
                int(row["attempts"]),
            )
            for row in rows
        ]

    async def _process(self, row: sqlite3.Row) -> UploadItem:
        mat_id = str(row["mat_id"])
        output = str(row["output"])
        branch_id = str(row["branch_id"])
        attempts = int(row["attempts"]) + 1
        self._record_state(mat_id, output, branch_id, "uploading", attempts)
        outputs = json.loads(str(row["outputs"]))
        value = outputs[output]
        value_ref = value.get("value_ref")
        if not isinstance(value_ref, str):
            self._record_state(
                mat_id,
                output,
                branch_id,
                "failed",
                attempts,
                "staged value is unavailable",
            )
            return UploadItem(mat_id, output, "failed", attempts)
        staged_path = self.store.cas.path_for("values", value_ref)
        metadata = cast(
            dict[str, JsonValue],
            {
                "flow": self.store.flow_id,
                "branch": branch_id,
                "cell": str(row["slug"]),
                "output": output,
                "native_type": value.get("native_type"),
                "content_hash": value.get("content_hash"),
                "metadata": value.get("metadata", {}),
            },
        )
        try:
            reference = LumlReference.model_validate(
                await self.api.upload(staged_path, metadata)
            )
        except OfflineUploadError as error:
            self._record_state(
                mat_id,
                output,
                branch_id,
                "queued",
                attempts,
                str(error),
            )
            return UploadItem(mat_id, output, "queued", attempts)
        except Exception as error:
            self._record_state(
                mat_id,
                output,
                branch_id,
                "failed",
                attempts,
                str(error),
            )
            return UploadItem(mat_id, output, "failed", attempts)
        self.store.commit(
            actor="system:uploads",
            intent=f"upload {row['slug']}.{output}",
            branch=branch_id,
            ops=[
                UploadRecordedOp(
                    mat_id=mat_id,
                    output=output,
                    luml_ref=reference,
                ),
                UploadStateOp(
                    mat_id=mat_id,
                    output=output,
                    state="done",
                    attempts=attempts,
                ),
            ],
        )
        return UploadItem(mat_id, output, "done", attempts)

    def _record_state(
        self,
        mat_id: str,
        output: str,
        branch_id: str,
        state: Literal["queued", "uploading", "failed"],
        attempts: int,
        error: str | None = None,
    ) -> None:
        self.store.commit(
            actor="system:uploads",
            intent=f"upload {state}",
            branch=branch_id,
            ops=[
                UploadStateOp(
                    mat_id=mat_id,
                    output=output,
                    state=state,
                    attempts=attempts,
                    error=error[:500] if error else None,
                )
            ],
        )

    def _connection(self) -> sqlite3.Connection:
        connection = self.store.index.connection
        if connection is None:
            raise RuntimeError("store index is closed")
        return connection


def _promoted_type(kind: object) -> NativeType:
    if kind == "frame":
        return "dataset"
    if kind in {"metric", "eval"}:
        return "experiment"
    return "model"
