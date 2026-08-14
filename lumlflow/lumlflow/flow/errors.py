from __future__ import annotations

import re

_ULID = re.compile(r"\b[0-9A-HJKMNP-TV-Z]{26}\b")
_HASH = re.compile(r"\b[0-9a-f]{64}\b", re.IGNORECASE)
_INTERNAL_WORDS = re.compile(
    r"\b(?:uid|memo[_ -]?key|content[_ -]?hash)\b", re.IGNORECASE
)


class FlowSurfaceError(RuntimeError):
    exit_code = 1


class FlowNotFoundError(FlowSurfaceError):
    exit_code = 2


class FlowConflictError(FlowSurfaceError):
    exit_code = 3


class FlowUnavailableError(FlowSurfaceError):
    exit_code = 4


def clean_human_message(message: str) -> str:
    cleaned = _ULID.sub("internal identifier", message)
    cleaned = _HASH.sub("internal hash", cleaned)
    return _INTERNAL_WORDS.sub("internal detail", cleaned)


def contains_internal_identifier(message: str) -> bool:
    return bool(_ULID.search(message) or _HASH.search(message))
