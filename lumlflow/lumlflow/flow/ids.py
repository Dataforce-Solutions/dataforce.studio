import os
import threading
import time

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_MAX_TIMESTAMP = (1 << 48) - 1
_MAX_RANDOMNESS = (1 << 80) - 1
_lock = threading.Lock()
_last_timestamp = -1
_last_randomness = 0


def _encode(value: int, length: int) -> str:
    encoded = ["0"] * length
    for index in range(length - 1, -1, -1):
        encoded[index] = _ALPHABET[value & 31]
        value >>= 5
    return "".join(encoded)


def mint_ulid(timestamp_ms: int | None = None) -> str:
    global _last_randomness, _last_timestamp

    use_clock = timestamp_ms is None
    requested_timestamp = time.time_ns() // 1_000_000 if use_clock else timestamp_ms
    assert requested_timestamp is not None
    if not 0 <= requested_timestamp <= _MAX_TIMESTAMP:
        raise ValueError("ULID timestamp must fit in 48 bits")

    with _lock:
        timestamp = (
            max(requested_timestamp, _last_timestamp)
            if use_clock
            else requested_timestamp
        )
        if timestamp == _last_timestamp:
            if _last_randomness == _MAX_RANDOMNESS:
                timestamp += 1
                if timestamp > _MAX_TIMESTAMP:
                    raise OverflowError("ULID space exhausted")
                randomness = int.from_bytes(os.urandom(10))
            else:
                randomness = _last_randomness + 1
        else:
            randomness = int.from_bytes(os.urandom(10))
        _last_timestamp = timestamp
        _last_randomness = randomness

    return _encode(timestamp, 10) + _encode(randomness, 16)


def is_ulid(value: str) -> bool:
    return len(value) == 26 and all(character in _ALPHABET for character in value)
