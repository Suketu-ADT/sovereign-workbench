"""
Per-user token-bucket rate limiter (in-memory, swappable interface).

60 requests per 10-minute rolling window per user.
In production this could be backed by Redis — the interface stays
the same.
"""

import time
import uuid
from collections import defaultdict, deque


# ── Configuration ─────────────────────────────────────────────

MAX_REQUESTS = 60
WINDOW_SECONDS = 600  # 10 minutes

# ── In-memory storage ─────────────────────────────────────────
# user_id -> deque of request timestamps (epoch float)

_buckets: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(user_id: uuid.UUID | str) -> tuple[bool, int]:
    """
    Check whether a user is within their rate limit.

    Parameters
    ----------
    user_id : uuid.UUID | str
        The user identifier.

    Returns
    -------
    tuple[bool, int]
        (allowed, retry_after_seconds).
        If allowed is True, retry_after_seconds is 0.
        If allowed is False, retry_after_seconds is how long until
        the oldest request in the window expires.
    """
    key = str(user_id)
    now = time.time()
    window_start = now - WINDOW_SECONDS
    bucket = _buckets[key]

    # Evict expired timestamps
    while bucket and bucket[0] < window_start:
        bucket.popleft()

    if len(bucket) >= MAX_REQUESTS:
        # Earliest request still in the window
        retry_after = int(bucket[0] - window_start) + 1
        return (False, max(retry_after, 1))

    bucket.append(now)
    return (True, 0)


def reset_rate_limit(user_id: uuid.UUID | str) -> None:
    """Reset a user's rate limit bucket (for testing)."""
    key = str(user_id)
    _buckets.pop(key, None)
