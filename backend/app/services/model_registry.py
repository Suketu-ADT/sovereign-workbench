"""
Configuration-Driven Model Registry for Sovereign Workbench.
Provides an extensible registry mapping tasks and capabilities to AI models and providers.
"""

import copy
import logging
from typing import Any, Dict, List, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

# Base configuration-driven model registry
# Adding a new model or task type can be done via configuration without modifying backend routing architecture.
DEFAULT_MODELS: Dict[str, Dict[str, Any]] = {
    "coding": {
        "provider": "huggingface",
        "model": "Qwen/Qwen2.5-Coder-32B-Instruct",
        "capabilities": ["code", "debugging", "programming", "python", "scripting"],
        "description": "Qwen 2.5 Coder 32B specialized instruction-tuned code intelligence",
        "sandboxed": True,
    },
    "debugging": {
        "provider": "huggingface",
        "model": "Qwen/Qwen2.5-Coder-32B-Instruct",
        "capabilities": ["code", "debugging", "programming", "troubleshooting"],
        "description": "Qwen 2.5 Coder 32B code debugging and syntax error remediation",
        "sandboxed": True,
    },
    "reasoning": {
        "provider": "huggingface",
        "model": getattr(settings, "PLANNER_MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct"),
        "capabilities": ["reasoning", "planning", "text", "analysis", "synthesis"],
        "description": "Qwen 2.5 72B high-parameter general reasoning and multi-step planning",
        "sandboxed": False,
    },
    "planning": {
        "provider": "huggingface",
        "model": getattr(settings, "PLANNER_MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct"),
        "capabilities": ["reasoning", "planning", "workflow", "safety"],
        "description": "LangGraph HITL planning and deterministic safety routing",
        "sandboxed": False,
    },
    "document": {
        "provider": "huggingface",
        "model": getattr(settings, "PLANNER_MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct"),
        "capabilities": ["document", "summarization", "rag", "sop", "manual"],
        "description": "Standard operating procedure analysis and document synthesis",
        "sandboxed": False,
    },
    "summarization": {
        "provider": "huggingface",
        "model": getattr(settings, "PLANNER_MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct"),
        "capabilities": ["summarization", "document", "executive_summary"],
        "description": "Engineering inspection summary and telemetry digest",
        "sandboxed": False,
    },
    "vision": {
        "provider": "local",
        "model": "Qwen/Qwen2.5-VL-72B-Instruct",
        "capabilities": ["image", "pdf", "vision", "ocr", "gauge", "telemetry", "diagram", "multimodal", "flowchart"],
        "description": "Qwen 2.5-VL 72B multimodal visual analyst for diagrams, workflows, and industrial gauges",
        "sandboxed": False,
    },
    "calculation": {
        "provider": "local",
        "model": "deterministic-sandbox",
        "capabilities": ["calculation", "math", "delta_p", "differential_pressure"],
        "description": "Isolated deterministic AST sandbox computation (e.g. pressure drop)",
        "sandboxed": True,
    },
}


class ModelRegistry:
    """Manages active models, task capabilities, and extensible model definitions."""

    def __init__(self, initial_models: Optional[Dict[str, Dict[str, Any]]] = None):
        self._models: Dict[str, Dict[str, Any]] = copy.deepcopy(initial_models or DEFAULT_MODELS)

    def get_model_for_task(self, task_type: str) -> Dict[str, Any]:
        """Retrieves model configuration for a specific task type with fallback to reasoning."""
        task_normalized = task_type.lower().strip()
        if task_normalized in self._models:
            return copy.deepcopy(self._models[task_normalized])

        # Match by capability
        for name, config in self._models.items():
            if task_normalized in config.get("capabilities", []):
                return copy.deepcopy(config)

        # Default fallback
        logger.info("Task type '%s' not explicitly registered; routing to general reasoning model.", task_type)
        return copy.deepcopy(self._models.get("reasoning", self._models["coding"]))

    def register_model(
        self,
        task_or_name: str,
        provider: str,
        model: str,
        capabilities: Optional[List[str]] = None,
        description: str = "",
        sandboxed: bool = False,
    ) -> None:
        """Dynamically registers or overrides a model entry."""
        self._models[task_or_name.lower().strip()] = {
            "provider": provider.lower().strip(),
            "model": model.strip(),
            "capabilities": [c.lower().strip() for c in (capabilities or [])],
            "description": description,
            "sandboxed": sandboxed,
        }
        logger.info("Registered model '%s' for task '%s' via provider '%s'", model, task_or_name, provider)

    def list_models(self) -> Dict[str, Dict[str, Any]]:
        """Returns all configured models in the registry."""
        return copy.deepcopy(self._models)

    def get_all_capabilities(self) -> List[str]:
        """Returns unique list of all supported capabilities across models."""
        capabilities = set()
        for m in self._models.values():
            capabilities.update(m.get("capabilities", []))
        return sorted(list(capabilities))


# Global singleton registry instance
model_registry = ModelRegistry()
MODELS = model_registry.list_models()
