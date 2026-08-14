import os
from pathlib import Path

import pytest
from lumlflow.flow.hashing import canonical_json, memo_key, sha256_json
from lumlflow.flow.ids import is_ulid, mint_ulid
from lumlflow.flow.store import cas
from lumlflow.flow.store.cas import ContentAddressedStore, atomic_write


def test_ulids_are_valid_and_monotonic_within_a_millisecond() -> None:
    first = mint_ulid(1_700_000_000_000)
    second = mint_ulid(1_700_000_000_000)

    assert is_ulid(first)
    assert first < second
    assert all(character not in first for character in "ILOU")


def test_canonical_hashing_preserves_named_input_mapping() -> None:
    assert canonical_json({"b": 2, "a": "é"}) == '{"a":"é","b":2}'
    assert sha256_json({"a": 1, "b": 2}) == sha256_json({"b": 2, "a": 1})
    assert memo_key("behavior", {"train": "a", "test": "b"}) != memo_key(
        "behavior", {"train": "b", "test": "a"}
    )


@pytest.mark.parametrize("area", ["objects", "values", "previews", "logs"])
def test_cas_uses_shards_and_deduplicates(tmp_path: Path, area: str) -> None:
    store = ContentAddressedStore(tmp_path)
    content_hash = store.put(area, b"payload")  # type: ignore[arg-type]
    second_hash = store.put(area, b"payload")  # type: ignore[arg-type]

    path = store.path_for(area, content_hash)  # type: ignore[arg-type]
    assert second_hash == content_hash
    assert path.parent.name == content_hash[:2]
    assert path.suffix == (".json" if area == "previews" else "")
    assert store.get(area, content_hash) == b"payload"  # type: ignore[arg-type]


def test_atomic_write_retries_windows_sharing_violations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "destination"
    real_replace = os.replace
    attempts = 0

    def flaky_replace(source: str | Path, target: str | Path) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("sharing violation")
        real_replace(source, target)

    monkeypatch.setattr(cas.os, "replace", flaky_replace)

    atomic_write(destination, b"complete")

    assert destination.read_bytes() == b"complete"
    assert attempts == 3
    assert list(tmp_path.iterdir()) == [destination]
