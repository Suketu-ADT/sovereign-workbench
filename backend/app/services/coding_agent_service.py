"""
Coding Agent Workflow Service for Sovereign Workbench.
Coordinates code generation, isolated Docker sandbox execution,
error feedback loop, and autonomous remediation up to a maximum retry limit.
"""

import logging
import re
from typing import Any, Dict, Optional

from app.services.code_sandbox_service import code_sandbox_service
from app.services.model_provider import get_provider
from app.services.model_router import select_model

logger = logging.getLogger(__name__)

CODING_SYSTEM_PROMPT = """You are DeepSeek-Coder-V2, an elite industrial Python software engineer.
Generate clean, self-contained, executable Python code to solve the user's request.
Requirements:
1. Output pure executable Python code inside a ```python ``` markdown fence.
2. Ensure all calculations and output print the results clearly to stdout.
3. Handle potential divide-by-zero or value errors safely.
4. Do not include external network requests or disk modifications outside standard temporary paths.
"""

RETRY_SYSTEM_PROMPT = """You are DeepSeek-Coder-V2.
The previously generated Python script failed in the sandbox execution environment.
Analyze the error traceback provided and produce corrected, robust, self-contained Python code.
Output the complete corrected code inside a ```python ``` markdown fence.
"""


def _extract_code(text: str) -> str:
    """Extracts Python code from markdown code fences or returns raw text."""
    pattern = r"```(?:python)?\s*(.*?)\s*```"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()


class CodingAgentService:
    """Orchestrates iterative code generation and sandboxed verification."""

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    async def run_coding_workflow(
        self,
        prompt: str,
        custom_provider: Optional[str] = None,
        custom_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes the full coding agent workflow:
        1. Router selects coding model (DeepSeek-Coder-V2-Instruct).
        2. Generates code.
        3. Executes inside Docker sandbox.
        4. If error occurs, sends error back to coding model to fix.
        5. Retries up to max_retries.
        """
        # Step 1: Model & Provider Selection
        routing = select_model("coding")
        provider_name = custom_provider or routing["provider"]
        model_name = custom_model or routing["model"]

        provider = get_provider(provider_name)
        logger.info(
            "Starting coding agent workflow: model=%s, provider=%s, prompt=%s",
            model_name,
            provider_name,
            prompt[:100],
        )

        current_prompt = prompt
        system_prompt = CODING_SYSTEM_PROMPT
        last_error = ""
        last_code = ""
        attempts = 0

        for attempt in range(1, self.max_retries + 1):
            attempts = attempt
            logger.info("Coding agent iteration %d/%d for model %s", attempt, self.max_retries, model_name)

            # Step 2: Generate Code via Provider
            try:
                raw_response = await provider.generate_async(
                    model=model_name,
                    system_prompt=system_prompt,
                    user_prompt=current_prompt,
                )
            except Exception as e:
                logger.error("Model generation failed on attempt %d with provider %s: %s", attempt, provider_name, e)
                # Resilient fallback: If Hugging Face provider errors (e.g. model not enabled on HF tier, network outage),
                # fallback to LocalProvider to maintain continuous operation
                if provider_name == "huggingface":
                    logger.warning("Hugging Face provider failed; falling back to resilient LocalProvider...")
                    try:
                        local_prov = get_provider("local")
                        raw_response = await local_prov.generate_async(
                            model=model_name,
                            system_prompt=system_prompt,
                            user_prompt=current_prompt,
                        )
                    except Exception as local_e:
                        logger.error("Local fallback also failed: %s", local_e)
                        return {
                            "status": "error",
                            "task_type": "coding",
                            "provider": provider_name,
                            "model": model_name,
                            "error": str(e),
                            "code": last_code,
                            "output": "",
                            "attempts": attempts,
                        }
                else:
                    return {
                        "status": "error",
                        "task_type": "coding",
                        "provider": provider_name,
                        "model": model_name,
                        "error": str(e),
                        "code": last_code,
                        "output": "",
                        "attempts": attempts,
                    }

            code_to_run = _extract_code(raw_response)
            last_code = code_to_run

            # Step 3: Run code inside Docker sandbox
            exec_result = await code_sandbox_service.execute_code(code_to_run)
            logger.info("Sandbox execution attempt %d status: %s", attempt, exec_result.get("status"))

            if exec_result.get("status") == "success":
                # Successful execution
                stdout = exec_result.get("stdout", "").strip()
                logger.info("Sandbox execution succeeded on attempt %d with output: %s", attempt, stdout[:200])
                return {
                    "status": "success",
                    "task_type": "coding",
                    "provider": provider_name,
                    "model": model_name,
                    "code": code_to_run,
                    "raw_response": raw_response,
                    "output": stdout,
                    "sandbox_type": exec_result.get("sandbox_type", "docker_sandbox"),
                    "attempts": attempts,
                }
            else:
                # Failed execution - prepare feedback for self-healing iteration
                last_error = exec_result.get("stderr") or exec_result.get("status") or "Execution failed"
                logger.warning(
                    "Sandbox execution failed on attempt %d: %s. Sending error back to coding model.",
                    attempt,
                    last_error[:200],
                )

                system_prompt = RETRY_SYSTEM_PROMPT
                current_prompt = (
                    f"Original Task:\n{prompt}\n\n"
                    f"Failed Code:\n```python\n{code_to_run}\n```\n\n"
                    f"Execution Error Traceback:\n{last_error}\n\n"
                    "Please fix all errors and output the corrected, self-contained Python code."
                )

        # Retries exhausted
        return {
            "status": "failed_retry_limit",
            "task_type": "coding",
            "provider": provider_name,
            "model": model_name,
            "code": last_code,
            "error": f"Max retries ({self.max_retries}) exceeded. Last error: {last_error}",
            "output": "",
            "attempts": attempts,
        }


coding_agent_service = CodingAgentService()
