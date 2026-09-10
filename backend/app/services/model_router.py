"""
Model Router Service for Sovereign Workbench.
Analyzes user requests, automatically classifies the intent/task type,
and routes to the appropriate AI model and provider.
"""

import logging
import re
from typing import Any, Dict, Optional

from app.core.config import settings
from app.services.model_registry import model_registry

logger = logging.getLogger(__name__)

# Keywords / patterns for deterministic task classification
_CODING_PATTERNS = [
    r"\b(write|generate|create|build|implement|develop)\b.*\b(python|code|script|function|class|program|algorithm)\b",
    r"\b(code|python|script|function|algorithm|syntax)\b",
    r"\b(debug|fix|troubleshoot|refactor|error in code)\b",
    r"\bcalculate pump efficiency\b",
]

_DEBUGGING_PATTERNS = [
    r"\b(debug|fix|traceback|syntaxerror|nameerror|typeerror|indentationerror)\b",
]

_VISION_PATTERNS = [
    r"\b(image|photo|picture|gauge|dial|needle|camera|inspect image|inspection image|visual|ocr)\b",
]

_CALCULATION_PATTERNS = [
    r"\b(calculate|compute|evaluate)\b.*\b(differential pressure|pressure drop|delta-p|delta p)\b",
    r"\b(inlet pressure|outlet pressure)\b",
]

_DOCUMENT_PATTERNS = [
    r"\b(summarize|summary|report|document|sop|manual|operating procedure|key findings|digest|overview)\b",
    r"\b(read|review|extract from)\b.*\b(manual|sop|spec|guideline)\b",
]

_PLANNING_PATTERNS = [
    r"\b(plan|workflow|orchestrate|mitigate|protocol|scram|emergency shutdown|isolate)\b",
]


def classify_task(prompt: str, has_image: bool = False) -> str:
    """
    Automatically classifies an input query into one of the supported task types:
    coding, debugging, vision, calculation, document, summarization, planning, reasoning.
    """
    if has_image:
        return "vision"

    prompt_clean = prompt.lower().strip()

    # Check for vision keywords
    if any(re.search(p, prompt_clean) for p in _VISION_PATTERNS):
        # If user explicitly asks to "write python code to inspect image", prioritize coding
        if not any(re.search(p, prompt_clean) for p in _CODING_PATTERNS):
            return "vision"

    # Check for debugging keywords
    if any(re.search(p, prompt_clean) for p in _DEBUGGING_PATTERNS):
        return "debugging"

    # Check for coding keywords
    if any(re.search(p, prompt_clean) for p in _CODING_PATTERNS):
        return "coding"

    # Check for pure calculation keywords
    if any(re.search(p, prompt_clean) for p in _CALCULATION_PATTERNS):
        return "calculation"

    # Check for document summarization
    if any(re.search(p, prompt_clean) for p in _DOCUMENT_PATTERNS):
        if "summar" in prompt_clean:
            return "summarization"
        return "document"

    # Check for planning
    if any(re.search(p, prompt_clean) for p in _PLANNING_PATTERNS):
        return "planning"

    # Default to reasoning
    return "reasoning"


def select_model(task_type: str) -> Dict[str, Any]:
    """
    Selects the appropriate provider and model for the specified task type.
    Enforces Sovereign Mode: in Sovereign Mode, cloud providers are redirected
    to local model provider.
    
    Returns:
    {
        "task_type": "coding",
        "provider": "huggingface",
        "model": "deepseek-ai/DeepSeek-Coder-V2-Instruct"
    }
    """
    normalized_task = task_type.lower().strip()
    model_info = model_registry.get_model_for_task(normalized_task)

    provider = model_info.get("provider", "local")
    model = model_info.get("model", "deepseek-ai/DeepSeek-Coder-V2-Instruct")

    # In Sovereign Mode, external providers must be blocked or redirected to local
    if settings.SOVEREIGN_MODE and provider != "local":
        logger.info(
            "Sovereign Mode active: redirecting external provider '%s' for task '%s' to 'local'",
            provider,
            normalized_task,
        )
        provider = "local"
        # In air-gap mode, map to local model identifier if appropriate
        if normalized_task in ("coding", "debugging"):
            model = "deepseek-coder-v2:local"
        elif normalized_task in ("reasoning", "planning", "document", "summarization"):
            model = getattr(settings, "PLANNER_MODEL_NAME", "qwen2.5-32b:local")

    routing_decision = {
        "task_type": normalized_task,
        "provider": provider,
        "model": model,
        "description": model_info.get("description", ""),
        "sandboxed": model_info.get("sandboxed", False),
    }

    logger.info(
        "MODEL_ROUTER: Task: %s -> Provider: %s, Model: %s",
        normalized_task,
        provider,
        model,
    )

    return routing_decision


def route_request(prompt: str, task_type: Optional[str] = None, has_image: bool = False) -> Dict[str, Any]:
    """
    End-to-end routing helper: classifies prompt if task_type not supplied,
    and returns model selection configuration.
    """
    final_task = (task_type or "").strip()
    if not final_task:
        final_task = classify_task(prompt, has_image=has_image)

    decision = select_model(final_task)
    return decision
