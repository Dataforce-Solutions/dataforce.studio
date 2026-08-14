import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import MemoHitOp, RunRecordedOp

_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class SweepResult:
    kept: int
    deleted: int
    freed_bytes: int
    deleted_hashes: tuple[str, ...]


def sweep(
    store: FlowStore,
    *,
    journal_grace_steps: int = 100,
    retention_days: int | None = None,
    now: datetime | None = None,
) -> SweepResult:
    if journal_grace_steps < 0:
        raise ValueError("journal grace steps must not be negative")
    if retention_days is not None and retention_days < 0:
        raise ValueError("retention days must not be negative")
    current_time = now or datetime.now(UTC)
    if current_time.tzinfo is None:
        raise ValueError("GC time must be timezone-aware")
    retention = (
        _configured_retention_days(store.flow_dir)
        if retention_days is None
        else retention_days
    )

    marked: set[str] = set()
    connection = store.index.connection
    if connection is None:
        raise RuntimeError("SQLite index is not open")

    selected_materializations = connection.execute(
        """
        SELECT DISTINCT materializations.inputs, materializations.outputs
        FROM selections
        JOIN materializations USING(version_id)
        WHERE materializations.state IN ('running', 'succeeded')
        """
    ).fetchall()
    for row in selected_materializations:
        _mark_records(marked, json.loads(row["inputs"]), json.loads(row["outputs"]))

    running = connection.execute(
        "SELECT inputs, outputs FROM materializations WHERE state = 'running'"
    ).fetchall()
    for row in running:
        _mark_records(marked, json.loads(row["inputs"]), json.loads(row["outputs"]))

    grace_start = max(1, store.last_step - journal_grace_steps + 1)
    for transaction in store.journal.replay():
        for operation in transaction.ops:
            if transaction.step >= grace_start and isinstance(operation, RunRecordedOp):
                _mark_run(marked, operation)
            elif transaction.step >= grace_start and isinstance(operation, MemoHitOp):
                if operation.mat_id is not None:
                    _mark_materialization(store, marked, operation.mat_id)
            if isinstance(operation, RunRecordedOp) and _within_retention(
                transaction.ts, current_time, retention
            ):
                volatility = _volatility(store, operation.version_id)
                if volatility in {"nondeterministic", "external"}:
                    _mark_run(marked, operation)

    pins = connection.execute(
        """
        SELECT content_hash FROM value_pins
        WHERE expires_step IS NULL OR expires_step >= ?
        """,
        (store.last_step,),
    ).fetchall()
    marked.update(str(row[0]) for row in pins if _is_hash(row[0]))

    deleted_hashes: list[str] = []
    freed_bytes = 0
    kept = 0
    values_dir = store.store_dir / "values"
    for path in values_dir.glob("*/*"):
        if not path.is_file() or not _is_hash(path.name):
            continue
        if path.name in marked:
            kept += 1
            continue
        freed_bytes += path.stat().st_size
        path.unlink()
        deleted_hashes.append(path.name)
    for shard in values_dir.iterdir():
        if shard.is_dir() and not any(shard.iterdir()):
            shard.rmdir()
    deleted_hashes.sort()
    return SweepResult(
        kept=kept,
        deleted=len(deleted_hashes),
        freed_bytes=freed_bytes,
        deleted_hashes=tuple(deleted_hashes),
    )


def _mark_materialization(store: FlowStore, marked: set[str], mat_id: str) -> None:
    connection = store.index.connection
    assert connection is not None
    row = connection.execute(
        "SELECT inputs, outputs FROM materializations WHERE mat_id = ?", (mat_id,)
    ).fetchone()
    if row is not None:
        _mark_records(marked, json.loads(row["inputs"]), json.loads(row["outputs"]))


def _mark_run(marked: set[str], operation: RunRecordedOp) -> None:
    for input_record in operation.inputs.values():
        if _is_hash(input_record.content_hash):
            marked.add(input_record.content_hash)
    for output_record in operation.outputs.values():
        _mark_output(marked, output_record.model_dump(mode="json"))


def _mark_records(
    marked: set[str], inputs: dict[str, object], outputs: dict[str, object]
) -> None:
    for input_record in inputs.values():
        if isinstance(input_record, dict) and _is_hash(
            input_record.get("content_hash")
        ):
            marked.add(str(input_record["content_hash"]))
    for output_record in outputs.values():
        if isinstance(output_record, dict):
            _mark_output(marked, output_record)


def _mark_output(marked: set[str], output: dict[str, object]) -> None:
    for key in ("value_ref", "content_hash"):
        reference = output.get(key)
        if _is_hash(reference):
            marked.add(str(reference))


def _volatility(store: FlowStore, version_id: str) -> str:
    connection = store.index.connection
    assert connection is not None
    row = connection.execute(
        "SELECT manifest FROM asset_versions WHERE version_id = ?", (version_id,)
    ).fetchone()
    if row is None:
        return "pure"
    manifest = json.loads(row[0])
    volatility = manifest.get("volatility", "pure")
    return volatility if isinstance(volatility, str) else "pure"


def _within_retention(timestamp: str, now: datetime, retention_days: int) -> bool:
    recorded = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return recorded <= now <= recorded + timedelta(days=retention_days)


def _configured_retention_days(flow_dir: Path) -> int:
    match = re.search(
        r"^\s*value_retention_days:\s*(\d+)\s*$",
        (flow_dir / "flow.yaml").read_text(),
        re.MULTILINE,
    )
    return 30 if match is None else int(match.group(1))


def _is_hash(value: object) -> bool:
    return isinstance(value, str) and _HASH_PATTERN.fullmatch(value) is not None
