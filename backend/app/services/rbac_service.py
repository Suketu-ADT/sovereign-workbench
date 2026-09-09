"""
RBAC service — wraps the capability map for route handlers.
"""

from app.core.capability_map import required_clearance


def check_access(query_text: str, user_clearance: int) -> tuple[bool, int]:
    """
    Check whether a user has sufficient clearance for a query.

    Parameters
    ----------
    query_text : str
        The free-text query that may reference industrial units.
    user_clearance : int
        The user's current clearance level.

    Returns
    -------
    tuple[bool, int]
        (allowed, required_level).
        If allowed is True, required_level is the level that was needed.
        If allowed is False, required_level is what was needed but not met.
    """
    required = required_clearance(query_text)
    allowed = user_clearance >= required
    return (allowed, required)
