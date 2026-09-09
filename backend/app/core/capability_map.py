"""
RBAC capability map — maps industrial unit identifiers to required
clearance levels.

The `required_clearance` function's signature is stable across phases:
today it does keyword matching on query text; in Phase 5 the planner's
tool-call target will pass the same unit string — same function, same
contract.
"""

import re

# ── Static capability map ─────────────────────────────────────
# unit keyword → minimum clearance level required

CAPABILITY_MAP: dict[str, int] = {
    "boiler-102":       1,
    "pump-201":         1,
    "cooling-loop-c3":  1,
    "turbine-gen-4":    2,
    "compressor":       2,
    "reactor-core-aux": 3,
}

# Pre-compiled pattern for efficient keyword matching
_UNIT_PATTERN = re.compile(
    "|".join(re.escape(k) for k in sorted(CAPABILITY_MAP.keys(), key=len, reverse=True)),
    re.IGNORECASE,
)


def required_clearance(unit_or_query: str) -> int:
    """
    Determine the minimum clearance level needed for a query or unit.
    
    Scans the input string for known unit keywords and returns the
    highest clearance level required among all matches. Returns 0 if
    no restricted units are referenced (anyone can query).
    
    Parameters
    ----------
    unit_or_query : str
        Either a direct unit identifier or a free-text query that may
        mention one or more units.
    
    Returns
    -------
    int
        Minimum clearance level required (0 = unrestricted).
    """
    matches = _UNIT_PATTERN.findall(unit_or_query)
    if not matches:
        return 0
    return max(CAPABILITY_MAP[m.lower()] for m in matches)
