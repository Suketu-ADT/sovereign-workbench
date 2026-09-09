"""
Prompt Guard service — input safety and adversarial prompt injection screening.

Situated as Step 2 in the Sovereign Workbench visible defense pipeline
(immediately after rate limiting and ahead of SCADA RBAC).

Integrates local Llama-Guard-3 model inference with a deterministic OT safety
scanner for high-precision prompt injection and jailbreak prevention.
"""

import logging
import re
from typing import Tuple

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Deterministic OT Safety Patterns ──────────────────────────────────────────

# Compiled regex patterns for immediate high-confidence screening
_INJECTION_PATTERNS = [
    # Instruction override & prompt jailbreaks
    (
        r"(?i)\b(ignore|disregard|forget|bypass|override)\b.*?\b(previous|prior|above|all|system)\b.*?\b(instructions|directions|rules|prompts|protocols|checks)\b",
        "PROMPT_INJECTION_OVERRIDE",
    ),
    (
        r"(?i)\b(you are now|act as|pretend to be)\b.*?\b(unrestricted|jailbroken|unfiltered|god mode|developer mode|dan)\b",
        "JAILBREAK_ROLEPLAY",
    ),
    (
        r"(?i)\b(dan|do anything now)\b",
        "JAILBREAK_DAN",
    ),
    (
        r"(?i)\b(dump|reveal|show|print|leak|output|repeat)\b.*?\b(system prompt|hidden instructions|internal prompt|initial instructions|prompt verbatim)\b",
        "SYSTEM_PROMPT_EXTRACTION",
    ),
    (
        r"(?i)(<\|im_start\|>|<\|im_end\|>|\[SYSTEM\]|\[INST\]|\[\/INST\])",
        "DELIMITER_INJECTION",
    ),
    # Malicious actuator bypass patterns
    (
        r"(?i)\b(force|emergency)\b.*?\b(open|scram|trip|purge|vent|release|override)\b.*?\b(without|bypass|disable)\b.*?\b(approval|authorization|auth|interlock|safety|hitl)\b",
        "MALICIOUS_ACTUATOR_BYPASS",
    ),
]

_COMPILED_PATTERNS = [(re.compile(p), cat) for p, cat in _INJECTION_PATTERNS]


def _scan_deterministic(prompt: str) -> Tuple[bool, str | None]:
    """
    Fast, deterministic heuristic scanner for prompt injection and jailbreak syntax.
    Returns (is_safe, reason).
    """
    for pattern, category in _COMPILED_PATTERNS:
        match = pattern.search(prompt)
        if match:
            matched_text = match.group(0)[:60]
            logger.warning(
                "PromptGuard deterministic block: %s (matched: '%s')",
                category,
                matched_text,
            )
            return False, f"{category}: detected adversarial pattern '{matched_text}'"

    return True, None


import time

_last_endpoint_failure_time: float = 0.0
_CIRCUIT_BREAKER_COOLDOWN: float = 30.0


def get_llm_status() -> str:
    """
    Returns the operational status of the secondary Llama-Guard LLM safety layer.
    
    Status values:
      - 'active': Endpoint configured and operational (circuit breaker healthy).
      - 'degraded': Circuit-breaker tripped due to network timeout or connection error.
      - 'disabled': PromptGuard LLM screening disabled or URL not configured.
    """
    if not settings.PROMPT_GUARD_ENABLED or not settings.PROMPT_GUARD_URL:
        return "disabled"
    if _last_endpoint_failure_time > 0 and (
        time.time() - _last_endpoint_failure_time < _CIRCUIT_BREAKER_COOLDOWN
    ):
        return "degraded"
    return "active"


async def _query_llama_guard(prompt: str) -> Tuple[bool, str | None]:
    """
    Query local Llama-Guard-3 instance (via Ollama /api/generate or vLLM).
    Returns (is_safe, reason).

    ARCHITECTURE DESIGN DECISION (FAIL-OPEN vs FAIL-CLOSED):
    The Sovereign Workbench implements a two-tier defense-in-depth safety architecture:
      - Tier 1 (Deterministic OT Heuristics): STRICT FAIL-CLOSED. All prompt injection,
        jailbreak, delimiter, and unauthorized actuator bypass strings are unconditionally
        blocked with HTTP 400 Bad Request.
      - Tier 2 (Llama-Guard-3 Semantic LLM): FAIL-OPEN to Tier 1 with Circuit Breaker.
        In mission-critical industrial SCADA environments, plant operations and sensor
        telemetry inspections must not suffer total denial-of-service if an on-premise
        LLM container stalls or is restarting. When unreachable, the failure is surfaced
        immediately via WARNING log level and the /health endpoint reports 'degraded',
        while Tier 1 ensures zero bypass of known adversarial syntax.
    """
    global _last_endpoint_failure_time
    if time.time() - _last_endpoint_failure_time < _CIRCUIT_BREAKER_COOLDOWN:
        return True, None

    url = f"{settings.PROMPT_GUARD_URL.rstrip('/')}/api/generate"
    payload = {
        "model": settings.PROMPT_GUARD_MODEL,
        "prompt": (
            "<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n"
            f"{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
        ),
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.PROMPT_GUARD_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                body = resp.json()
                output = body.get("response", "").strip()
                if output.lower().startswith("unsafe"):
                    lines = output.split("\n")
                    category = lines[1].strip() if len(lines) > 1 else "UNSPECIFIED"
                    return False, f"LLAMA_GUARD_VIOLATION: {category}"
                elif output.lower().startswith("safe"):
                    return True, None
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError) as e:
        _last_endpoint_failure_time = time.time()
        logger.warning(
            "Local Llama-Guard-3 endpoint unavailable (%s: %s) — relying on deterministic safety scanner.",
            type(e).__name__,
            e,
        )

    return True, None


async def is_safe(prompt: str) -> Tuple[bool, str | None]:
    """
    Main entry point for prompt safety evaluation.

    Returns:
        (True, None) if prompt is clean and safe.
        (False, reason_string) if prompt violates safety or injection rules.
    """
    if not settings.PROMPT_GUARD_ENABLED:
        return True, None

    if not prompt or not prompt.strip():
        return True, None

    # Step 1: Fast deterministic scan (catches prompt injection, jailbreaks, delimiters)
    safe, reason = _scan_deterministic(prompt)
    if not safe:
        return False, reason

    # Step 2: Local Llama-Guard-3 screening (if endpoint is configured and active)
    if settings.PROMPT_GUARD_URL:
        lg_safe, lg_reason = await _query_llama_guard(prompt)
        if not lg_safe:
            return False, lg_reason

    return True, None
