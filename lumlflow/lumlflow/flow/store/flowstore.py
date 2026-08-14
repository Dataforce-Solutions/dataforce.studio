import json
import re
import threading
import warnings
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from lumlflow.flow.ids import mint_ulid
from lumlflow.flow.store.cas import CASArea, ContentAddressedStore, atomic_write
from lumlflow.flow.store.index import SQLiteIndex
from lumlflow.flow.store.journal import Journal
from lumlflow.flow.store.models import FlowInitOp, FlowOp, Transaction

CommitStage = Literal["after_cas", "after_journal", "after_index"]
CommitListener = Callable[[Transaction], None]


class CloudSyncFolderWarning(UserWarning):
    pass


@dataclass(frozen=True)
class CASWrite:
    area: CASArea
    data: bytes | str
    expected_hash: str | None = None


def is_cloud_sync_path(path: str | Path) -> bool:
    normalized = str(path).replace("\\", "/").casefold()
    markers = (
        "/dropbox/",
        "/onedrive/",
        "/icloud drive/",
        "/mobile documents/",
    )
    padded = f"/{normalized.strip('/')}/"
    return any(marker in padded for marker in markers)


class FlowStore:
    def __init__(
        self,
        flow_dir: Path,
        flow_id: str,
        branch_id: str,
        *,
        crash_hook: Callable[[CommitStage], None] | None = None,
    ) -> None:
        self.flow_dir = flow_dir
        self.flow_id = flow_id
        self.branch_id = branch_id
        self.store_dir = flow_dir / ".lumlflow"
        self.cas = ContentAddressedStore(self.store_dir)
        self.journal = Journal(self.store_dir / "journal.jsonl")
        self.index = SQLiteIndex(self.store_dir / "store.sqlite")
        self._crash_hook = crash_hook
        self._commit_lock = threading.Lock()
        self._commit_listeners: list[CommitListener] = []
        self._last_step = self.journal.last_step()

    @classmethod
    def init(
        cls,
        flow_dir: str | Path,
        *,
        name: str | None = None,
        actor: str = "system:init",
        intent: str = "initialize flow",
        crash_hook: Callable[[CommitStage], None] | None = None,
    ) -> "FlowStore":
        root = Path(flow_dir)
        if (root / "flow.yaml").exists():
            raise FileExistsError(f"flow already exists at {root}")
        if is_cloud_sync_path(flow_dir):
            warnings.warn(
                "Flow stores are not safe inside Dropbox, OneDrive, or iCloud folders",
                CloudSyncFolderWarning,
                stacklevel=2,
            )

        root.mkdir(parents=True, exist_ok=True)
        (root / "cells").mkdir(exist_ok=True)
        (root / "lib").mkdir(exist_ok=True)
        flow_id = mint_ulid()
        branch_id = mint_ulid()
        flow_name = name or _default_flow_name(root)
        atomic_write(root / "flow.yaml", _flow_yaml(flow_id, flow_name))
        if _inside_git_repository(root):
            _ensure_gitignore_entry(root / ".gitignore", ".lumlflow/")

        store = cls(
            root,
            flow_id,
            branch_id,
            crash_hook=crash_hook,
        )
        store.index.rebuild([])
        store.commit(
            actor=actor,
            intent=intent,
            branch=branch_id,
            ops=[
                FlowInitOp(
                    flow_id=flow_id,
                    name=flow_name,
                    branch_id=branch_id,
                )
            ],
            settled=True,
        )
        return store

    @classmethod
    def open(
        cls,
        flow_dir: str | Path,
        *,
        crash_hook: Callable[[CommitStage], None] | None = None,
    ) -> "FlowStore":
        root = Path(flow_dir)
        yaml_path = root / "flow.yaml"
        if not yaml_path.is_file():
            raise FileNotFoundError(f"not a flow directory: {root}")
        store_dir = root / ".lumlflow"
        if not store_dir.exists():
            manifest = yaml_path.read_text(encoding="utf-8")
            flow_id = _yaml_flow_id(manifest)
            branch_id = mint_ulid()
            store = cls(
                root,
                flow_id,
                branch_id,
                crash_hook=crash_hook,
            )
            store.index.rebuild([])
            store.commit(
                actor="system:init",
                intent="initialize cloned flow",
                branch=branch_id,
                ops=[
                    FlowInitOp(
                        flow_id=flow_id,
                        name=_yaml_flow_name(manifest),
                        branch_id=branch_id,
                    )
                ],
                settled=True,
            )
            return store
        journal = Journal(store_dir / "journal.jsonl")
        transactions = list(journal.replay())
        if not transactions or not isinstance(transactions[0].ops[0], FlowInitOp):
            raise ValueError("flow journal has no flow_init transaction")
        initial_operation = transactions[0].ops[0]
        assert isinstance(initial_operation, FlowInitOp)
        flow_id = _yaml_flow_id(yaml_path.read_text())
        if flow_id != initial_operation.flow_id:
            raise ValueError("flow.yaml id does not match the journal")

        store = cls(
            root,
            flow_id,
            initial_operation.branch_id,
            crash_hook=crash_hook,
        )
        if not store.index.is_current(store._last_step):
            store.index.rebuild(transactions)
        connection = store.index.connection
        assert connection is not None
        binding = connection.execute(
            "SELECT branch_id FROM worktrees WHERE path = ?",
            (str(root.resolve()),),
        ).fetchone()
        if binding is not None:
            store.branch_id = str(binding[0])
        return store

    def commit(
        self,
        *,
        actor: str,
        intent: str,
        ops: list[FlowOp],
        branch: str | None = None,
        blobs: Iterable[CASWrite] = (),
        offline: bool = False,
        settled: bool | None = None,
        timestamp: datetime | None = None,
    ) -> Transaction:
        if not ops:
            raise ValueError("a transaction must contain at least one operation")
        with self._commit_lock:
            for blob in blobs:
                content_hash = self.cas.put(blob.area, blob.data)
                if (
                    blob.expected_hash is not None
                    and content_hash != blob.expected_hash
                ):
                    raise ValueError(
                        f"{blob.area} blob hash mismatch: expected {blob.expected_hash}"
                    )
            self._reached("after_cas")

            target_branch = branch or self.branch_id
            if settled is None:
                settled = self.index.is_branch_settled(target_branch, ops)

            transaction = Transaction(
                step=self._last_step + 1,
                ts=_format_timestamp(timestamp or datetime.now(UTC)),
                actor=actor,
                intent=intent,
                offline=offline,
                settled=settled,
                branch=target_branch,
                ops=ops,
            )
            self.journal.append(transaction)
            self._last_step = transaction.step
            self._reached("after_journal")
            self.index.apply(transaction)
            self._reached("after_index")
            for listener in tuple(self._commit_listeners):
                listener(transaction)
            return transaction

    def add_commit_listener(self, listener: CommitListener) -> Callable[[], None]:
        self._commit_listeners.append(listener)

        def remove() -> None:
            try:
                self._commit_listeners.remove(listener)
            except ValueError:
                pass

        return remove

    @property
    def last_step(self) -> int:
        return self._last_step

    def close(self) -> None:
        self.index.close()

    def __enter__(self) -> "FlowStore":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _reached(self, stage: CommitStage) -> None:
        if self._crash_hook is not None:
            self._crash_hook(stage)


def _flow_yaml(flow_id: str, name: str) -> bytes:
    quoted_name = json.dumps(name, ensure_ascii=False)
    return (
        f"flow: {flow_id}\n"
        f"name: {quoted_name}\n"
        "language: python\n"
        "cells: {}\n"
        "settings:\n"
        "  value_persist_limit_mb: 500\n"
        "  value_retention_days: 30\n"
        "  eager_cost_threshold_s: 5\n"
        "  paranoid: false\n"
        "  strict: false\n"
    ).encode()


def _yaml_flow_id(contents: str) -> str:
    match = re.search(r"^flow:\s*([0-9A-HJKMNP-TV-Z]{26})\s*$", contents, re.MULTILINE)
    if match is None:
        raise ValueError("flow.yaml has no valid flow id")
    return match.group(1)


def _yaml_flow_name(contents: str) -> str:
    match = re.search(r"^name:\s*(.+?)\s*$", contents, re.MULTILINE)
    if match is None:
        raise ValueError("flow.yaml has no name")
    encoded = match.group(1)
    try:
        value = json.loads(encoded)
    except json.JSONDecodeError:
        value = encoded
    if not isinstance(value, str) or not value:
        raise ValueError("flow.yaml has no valid name")
    return value


def _default_flow_name(root: Path) -> str:
    return root.stem if root.suffix == ".flow" else root.name


def _inside_git_repository(root: Path) -> bool:
    return any((candidate / ".git").exists() for candidate in (root, *root.parents))


def _ensure_gitignore_entry(path: Path, entry: str) -> None:
    contents = path.read_text() if path.exists() else ""
    if entry in {line.strip() for line in contents.splitlines()}:
        return
    separator = "" if not contents or contents.endswith("\n") else "\n"
    atomic_write(path, f"{contents}{separator}{entry}\n".encode())


def _format_timestamp(timestamp: datetime) -> str:
    if timestamp.tzinfo is None:
        raise ValueError("transaction timestamps must be timezone-aware")
    utc_timestamp = timestamp.astimezone(UTC).replace(microsecond=0)
    return utc_timestamp.isoformat().replace("+00:00", "Z")
