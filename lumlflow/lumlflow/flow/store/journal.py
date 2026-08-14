import os
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import cast

from pydantic import ValidationError

from lumlflow.flow.hashing import canonical_json_bytes
from lumlflow.flow.store.models import JsonValue, Transaction


class JournalCorruptionError(RuntimeError):
    pass


class Journal:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        self._lock = threading.Lock()

    def append(self, transaction: Transaction) -> None:
        payload = cast(JsonValue, transaction.model_dump(mode="json"))
        line = canonical_json_bytes(payload) + b"\n"
        with self._lock, self.path.open("ab", buffering=0) as journal:
            view = memoryview(line)
            while view:
                written = journal.write(view)
                if written is None or written == 0:
                    raise OSError("journal append made no progress")
                view = view[written:]
            os.fsync(journal.fileno())

    def recover(self) -> bool:
        with self._lock:
            data = self.path.read_bytes()
            committed_length = 0
            for line_number, line in enumerate(data.splitlines(keepends=True), start=1):
                if not line.endswith(b"\n"):
                    self._truncate(committed_length)
                    return True
                try:
                    Transaction.model_validate_json(line)
                except (ValidationError, ValueError) as error:
                    raise JournalCorruptionError(
                        f"invalid journal transaction on line {line_number}"
                    ) from error
                committed_length += len(line)
            return False

    def replay(self) -> Iterator[Transaction]:
        self.recover()
        with self.path.open("rb") as journal:
            previous_step = 0
            for line_number, line in enumerate(journal, start=1):
                try:
                    transaction = Transaction.model_validate_json(line)
                except (ValidationError, ValueError) as error:
                    raise JournalCorruptionError(
                        f"invalid journal transaction on line {line_number}"
                    ) from error
                if transaction.step != previous_step + 1:
                    raise JournalCorruptionError(
                        f"journal step {transaction.step} follows {previous_step}"
                    )
                previous_step = transaction.step
                yield transaction

    def last_step(self) -> int:
        last_step = 0
        for transaction in self.replay():
            last_step = transaction.step
        return last_step

    def _truncate(self, length: int) -> None:
        with self.path.open("r+b") as journal:
            journal.truncate(length)
            journal.flush()
            os.fsync(journal.fileno())
