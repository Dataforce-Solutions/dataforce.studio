from pathlib import Path

import pytest
from lumlflow.flow.store.journal import Journal, JournalCorruptionError
from lumlflow.flow.store.models import FlagSetOp, Transaction


def _transaction(step: int) -> Transaction:
    return Transaction(
        step=step,
        ts="2026-08-11T12:00:00Z",
        actor="agent:test",
        intent="test journal",
        branch="branch",
        ops=[FlagSetOp(flag="reviewed")],
    )


def test_journal_round_trips_canonical_transactions(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "journal.jsonl")
    journal.append(_transaction(1))
    journal.append(_transaction(2))

    assert [transaction.step for transaction in journal.replay()] == [1, 2]
    lines = journal.path.read_text().splitlines()
    assert all(": " not in line and ", " not in line for line in lines)
    assert lines[0].startswith('{"actor":"agent:test"')


def test_journal_truncates_a_torn_trailing_line(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "journal.jsonl")
    journal.append(_transaction(1))
    committed = journal.path.read_bytes()
    with journal.path.open("ab") as file:
        file.write(b'{"step":2,"actor":"agent')

    assert [transaction.step for transaction in journal.replay()] == [1]
    assert journal.path.read_bytes() == committed


def test_journal_rejects_corruption_before_the_trailing_line(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "journal.jsonl")
    journal.append(_transaction(1))
    first_line = journal.path.read_bytes()
    journal.append(_transaction(2))
    second_line = journal.path.read_bytes()[len(first_line) :]
    journal.path.write_bytes(first_line + b"not-json\n" + second_line)

    with pytest.raises(JournalCorruptionError, match="line 2"):
        list(journal.replay())


def test_journal_rejects_non_monotonic_steps(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "journal.jsonl")
    journal.append(_transaction(1))
    journal.append(_transaction(3))

    with pytest.raises(JournalCorruptionError, match="step 3 follows 1"):
        list(journal.replay())
