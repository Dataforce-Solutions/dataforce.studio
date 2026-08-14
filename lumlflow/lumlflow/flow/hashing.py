import hashlib
import json
from collections.abc import Mapping, Sequence

type JsonValue = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)


def canonical_json(value: JsonValue) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )


def canonical_json_bytes(value: JsonValue) -> bytes:
    return canonical_json(value).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: JsonValue) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def definition_hash(bound_source: str, params: Mapping[str, JsonValue]) -> str:
    return sha256_json({"bound_source": bound_source, "params": dict(params)})


def lib_tree_hash(files: Sequence[tuple[str, str]]) -> str:
    ordered: list[JsonValue] = [list(item) for item in sorted(files)]
    return sha256_json(ordered)


def behavior_hash(cell_definition_hash: str, library_tree_hash: str) -> str:
    return sha256_bytes((cell_definition_hash + library_tree_hash).encode())


def memo_key(
    behavior: str,
    inputs: Mapping[str, str],
    *,
    env_lock_hash: str | None = None,
) -> str:
    payload: dict[str, JsonValue] = {
        "behavior": behavior,
        "inputs": dict(inputs),
    }
    if env_lock_hash is not None:
        payload["env"] = env_lock_hash
    return sha256_json(payload)
