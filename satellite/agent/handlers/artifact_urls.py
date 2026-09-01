"""Reading the expiry out of a presigned artifact URL.

Best-effort and informational: the model container retries on a 403 rather than trusting
this, and a URL from a store that signs differently simply reports no expiry.
"""

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

_AMZ_DATE_FORMAT = "%Y%m%dT%H%M%SZ"


def presigned_expiry(url: str) -> datetime | None:
    query = parse_qs(urlparse(url).query)
    signed_at = (query.get("X-Amz-Date") or [None])[0]
    lifetime = (query.get("X-Amz-Expires") or [None])[0]
    if not signed_at or not lifetime:
        return None
    try:
        start = datetime.strptime(signed_at, _AMZ_DATE_FORMAT).replace(tzinfo=UTC)
        return start + timedelta(seconds=int(lifetime))
    except ValueError:
        return None
