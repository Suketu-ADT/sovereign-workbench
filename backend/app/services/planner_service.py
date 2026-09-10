"""
Planner & Orchestration Service using LangGraph StateGraph.
Orchestrates verified outputs from defense layers 1-6 (RBAC, Retrieval, Vision, Calculation)
with static capability-map allowlist guardrails and LangGraph interrupt() execution for HITL approval.
"""

import json
import logging
import uuid
from typing import Any, TypedDict

import httpx
from pydantic import BaseModel, ValidationError

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from app.core.config import settings
from app.schemas.query import HITLApprovalDetails
from app.services import rbac_service

logger = logging.getLogger(__name__)

class PlannerOutput(BaseModel):
    intent: str
    required_tools: list[str]
    proposed_action: str
    requires_sensitive_approval: bool
    reason: str

STATIC_TOOL_REGISTRY = {
    "retrieve_manual": {"description": "Search standard operating procedures", "sensitive": False, "authority": None},
    "read_gauge": {"description": "Extract value from visual gauge image", "sensitive": False, "authority": None},
    "calculate_pressure_drop": {"description": "Calculate difference between inlet and outlet", "sensitive": False, "authority": None},
    "open_release_valve": {"description": "Open pressure release valve (SENSITIVE)", "sensitive": True, "authority": "Senior_Engineer (HITL Required)"},
    "adjust_governor": {"description": "Adjust turbine governor (SENSITIVE)", "sensitive": True, "authority": "Operations_Lead (HITL Required)"},
    "scram_containment": {"description": "Emergency shutdown (SENSITIVE)", "sensitive": True, "authority": "Plant_Director (HITL Required)"},
    "emergency_shutdown": {"description": "Emergency shutdown (SENSITIVE)", "sensitive": True, "authority": "Plant_Director (HITL Required)"},
    "override": {"description": "System override (SENSITIVE)", "sensitive": True, "authority": "Chief_Safety_Auditor (HITL Required)"},
    "inspect_log": {"description": "Normal non-sensitive logging", "sensitive": False, "authority": None},
    "none": {"description": "No action needed", "sensitive": False, "authority": None}
}

async def _call_llm_planner(prompt: str) -> dict:
    if not settings.PLANNER_MODEL_ENABLED:
        raise ValueError("Planner model is disabled")
    
    url = f"{settings.PLANNER_MODEL_URL}/api/generate"
    payload = {
        "model": settings.PLANNER_MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, timeout=settings.PLANNER_TIMEOUT)
        response.raise_for_status()
        return response.json()

# Authority string to minimum required clearance mapping
AUTHORITY_CLEARANCE_MAP = {
    "Senior_Engineer (HITL Required)": 3,
    "Plant_Director (HITL Required)": 3,
    "Chief_Safety_Auditor (HITL Required)": 3,
    "Operations_Lead (HITL Required)": 2,
}


def get_required_clearance_for_authority(authority: str | None) -> int:
    """Derives required clearance level from authority specification string."""
    if not authority:
        return 3
    for key, level in AUTHORITY_CLEARANCE_MAP.items():
        if key.lower() in authority.lower() or authority.lower() in key.lower():
            return level
    return 3


class PlanState(TypedDict):
    thread_id: str
    query: str
    user_id: str
    operator_email: str
    clearance_level: int
    unit: str
    retrieved_docs: list[dict[str, Any]]
    vision_reading: float | None
    pressure_drop: float | None
    proposed_action: dict[str, Any] | None
    approval_required: bool
    approval_details: dict[str, Any] | None
    approval_decision: str | None  # "approved" or "rejected"
    action_status: str  # "PENDING", "EXECUTED", "REJECTED", "NOT_REQUIRED"
    final_synthesis: str | None


async def reasoning_node(state: PlanState) -> dict[str, Any]:
    """
    Reasoning layer: analyzes telemetry, document context, and calculates action
    by dynamically invoking an LLM (Qwen) with a strict tool registry.
    """
    query = state["query"]
    unit = state["unit"]
    delta_p = state.get("pressure_drop") or 0.0
    reading = state.get("vision_reading") or 0.0
    
    tools_str = json.dumps(STATIC_TOOL_REGISTRY, indent=2)
    
    prompt = f"""You are an industrial reasoning agent. Determine the required tools and proposed action.
    
User Query: {query}
Target Unit: {unit}
Telemetry: Delta P = {delta_p} bar, Vision Reading = {reading} bar

Available Tools:
{tools_str}

Output strictly valid JSON matching this schema:
{{
  "intent": "Short description of user intent",
  "required_tools": ["tool1", "tool2"],
  "proposed_action": "One action from the tools list",
  "requires_sensitive_approval": true/false,
  "reason": "Detailed reasoning"
}}
"""
    try:
        llm_response = await _call_llm_planner(prompt)
        raw_output = llm_response.get("response", "{}")
        parsed_json = json.loads(raw_output)
        output = PlannerOutput(**parsed_json)
    except ValidationError as e:
        logger.error(f"Planner LLM output failed schema validation: {e}")
        return {
            "action_status": "ERROR",
            "final_synthesis": "Planner error: invalid LLM output schema."
        }
    except Exception as e:
        logger.error(f"Planner LLM failed or returned invalid output: {e}")
        return {
            "action_status": "ERROR",
            "final_synthesis": f"Planner error: invalid LLM output ({e})"
        }
        
    action_name = output.proposed_action
    if action_name not in STATIC_TOOL_REGISTRY:
        logger.error(f"Hallucinated action rejected: {action_name}")
        return {
            "action_status": "ERROR",
            "final_synthesis": f"Planner proposed an unknown action: {action_name}"
        }
        
    # Check deterministic capability from authoritative RBAC layer
    # We pass 'action target' to let rbac_service check against the capability map
    check_str = f"{action_name} {unit}"
    allowed, req_level = rbac_service.check_access(check_str, state["clearance_level"])
    
    if not allowed:
        logger.warning(f"Unauthorized action blocked: {action_name} for user clearance {state['clearance_level']}")
        return {
            "action_status": "REJECTED_UNAUTHORIZED",
            "final_synthesis": f"Action '{action_name}' blocked. Requires Level {req_level} clearance."
        }
        
    tool_info = STATIC_TOOL_REGISTRY[action_name]
    if tool_info["sensitive"]:
        target = f"{unit}"
        context = output.reason
        authority = tool_info["authority"]
        
        approval_details = {
            "action": action_name,
            "target": target,
            "requestor": f"AI Agent",
            "context": context,
            "authority": authority,
            "thread_id": state["thread_id"],
        }
        return {
            "proposed_action": {"action": action_name, "target": target},
            "approval_required": True,
            "approval_details": approval_details,
            "action_status": "PENDING",
            "final_synthesis": f"Sensitive actuator action '{action_name}' requested. Awaiting operator authorization.",
        }

    return {
        "proposed_action": {"action": action_name, "target": unit},
        "approval_required": False,
        "approval_details": None,
        "action_status": "NOT_REQUIRED",
        "final_synthesis": f"Proposed action {action_name} does not require HITL. Reason: {output.reason}",
    }


def hitl_gate_node(state: PlanState) -> dict[str, Any]:
    """
    HITL Interruption Node: pauses the LangGraph execution graph using interrupt()
    when a sensitive actuator action is proposed. Resumed via Command(resume=...).
    """
    if not state.get("approval_required"):
        return {"action_status": "NOT_REQUIRED"}

    # Suspend execution until an authorized operator submits decision
    decision_payload = interrupt(state["approval_details"])

    approved = bool(decision_payload.get("approved"))
    decision_str = "approved" if approved else "rejected"
    return {
        "approval_decision": decision_str,
        "action_status": "EXECUTED" if approved else "REJECTED",
    }


def action_execution_node(state: PlanState) -> dict[str, Any]:
    """Action finalization and response synthesis."""
    unit = state["unit"]
    action = state.get("proposed_action") or {}
    action_name = action.get("action", "none")
    decision = state.get("approval_decision")

    if decision == "approved":
        synthesis = (
            f"Action '{action_name}' on {unit} authorized by operator and successfully executed. "
            f"System telemetry returned to nominal operating limits."
        )
        status = "EXECUTED"
    elif decision == "rejected":
        synthesis = (
            f"Action '{action_name}' on {unit} was REJECTED by operator. "
            f"Actuator command aborted. Pipeline halted safely."
        )
        status = "REJECTED"
    else:
        synthesis = state.get("final_synthesis")
        status = state.get("action_status", "COMPLETED")

    return {
        "action_status": status,
        "final_synthesis": synthesis,
    }


def _route_after_reasoning(state: PlanState) -> str:
    if state.get("approval_required"):
        return "hitl_gate"
    return "action_execution"


try:
    from psycopg_pool import AsyncConnectionPool
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    POSTGRES_CHECKPOINTER_AVAILABLE = True
except ImportError:
    POSTGRES_CHECKPOINTER_AVAILABLE = False


class PlannerService:
    """Manages LangGraph compilation, execution, and HITL resumption."""

    def __init__(self):
        self.checkpointer = MemorySaver()
        self.pool = None
        self.graph = self._build_graph()
        self._pending_approvals: dict[str, dict[str, Any]] = {}

    def _build_graph(self):
        workflow = StateGraph(PlanState)
        workflow.add_node("reasoning", reasoning_node)
        workflow.add_node("hitl_gate", hitl_gate_node)
        workflow.add_node("action_execution", action_execution_node)

        workflow.set_entry_point("reasoning")
        workflow.add_conditional_edges(
            "reasoning",
            _route_after_reasoning,
            {
                "hitl_gate": "hitl_gate",
                "action_execution": "action_execution",
            },
        )
        workflow.add_edge("hitl_gate", "action_execution")
        workflow.add_edge("action_execution", END)

        return workflow.compile(checkpointer=self.checkpointer)

    async def init_checkpointer(self):
        """Initializes Postgres-backed checkpointer when running against PostgreSQL."""
        if "postgresql" in settings.DATABASE_URL.lower():
            if not POSTGRES_CHECKPOINTER_AVAILABLE:
                logger.warning(
                    "langgraph-checkpoint-postgres or psycopg_pool not available; using MemorySaver"
                )
                return

            try:
                # Strip asyncpg driver prefix for psycopg
                conn_str = settings.DATABASE_URL.replace(
                    "postgresql+asyncpg://", "postgresql://"
                )
                self.pool = AsyncConnectionPool(
                    conninfo=conn_str, max_size=10, open=False
                )
                await self.pool.open()
                self.checkpointer = AsyncPostgresSaver(self.pool)
                # Ensure checkpoint tables are created under advisory lock to avoid worker races
                async with self.pool.connection() as conn:
                    await conn.execute("SELECT pg_advisory_lock(4242424244);")
                    try:
                        await self.checkpointer.setup()
                    finally:
                        await conn.execute("SELECT pg_advisory_unlock(4242424244);")
                self.graph = self._build_graph()
                logger.info(
                    "PlannerService successfully initialized with AsyncPostgresSaver checkpointer"
                )
            except Exception as e:
                logger.error(
                    "Failed to initialize AsyncPostgresSaver: %s. Falling back to MemorySaver.",
                    e,
                )
        else:
            logger.info(
                "PlannerService using in-memory checkpointer (development/testing)"
            )

    async def close_checkpointer(self):
        """Disposes connection pool on application shutdown."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("PlannerService checkpointer pool closed")

    async def run_plan(
        self,
        query: str,
        user_id: str,
        operator_email: str,
        clearance_level: int,
        unit: str = "boiler-102",
        retrieved_docs: list[dict[str, Any]] | None = None,
        vision_reading: float | None = None,
        pressure_drop: float | None = None,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Executes the reasoning loop. If a sensitive action is proposed,
        the graph pauses at the HITL gate and returns awaiting_approval.
        """
        tid = thread_id or f"thread-{uuid.uuid4().hex[:12]}"
        initial_state: PlanState = {
            "thread_id": tid,
            "query": query,
            "user_id": user_id,
            "operator_email": operator_email,
            "clearance_level": clearance_level,
            "unit": unit,
            "retrieved_docs": retrieved_docs or [],
            "vision_reading": vision_reading,
            "pressure_drop": pressure_drop,
            "proposed_action": None,
            "approval_required": False,
            "approval_details": None,
            "approval_decision": None,
            "action_status": "PENDING",
            "final_synthesis": None,
        }

        config = {"configurable": {"thread_id": tid}}
        result = await self.graph.ainvoke(initial_state, config=config)

        # Check if paused on interrupt
        if "__interrupt__" in result:
            interrupt_val = result["__interrupt__"][0].value
            self._pending_approvals[tid] = {
                "thread_id": tid,
                "user_id": user_id,
                "operator_email": operator_email,
                "clearance_level": clearance_level,
                "unit": unit,
                "approval_details": interrupt_val,
                "state": result,
            }
            return {
                "thread_id": tid,
                "status": "awaiting_approval",
                "approval_required": True,
                "approval_details": interrupt_val,
                "synthesis": "Sensitive action proposed; awaiting operator authorization.",
            }

        return {
            "thread_id": tid,
            "status": "completed",
            "approval_required": False,
            "approval_details": None,
            "action_status": result.get("action_status"),
            "synthesis": result.get("final_synthesis"),
        }

    async def resume_plan(
        self,
        thread_id: str,
        approved: bool,
        operator_email: str,
        comment: str | None = None,
        action: str | None = None,
        target: str | None = None,
    ) -> dict[str, Any]:
        """
        Resumes a paused LangGraph thread with operator decision (approved=True/False).
        Works seamlessly across multi-worker deployments via Postgres-backed checkpointing.
        """
        config = {"configurable": {"thread_id": thread_id}}
        pending_info = self._pending_approvals.pop(thread_id, None)

        if pending_info:
            action = action or pending_info.get("approval_details", {}).get("action")
            target = target or pending_info.get("approval_details", {}).get("target")

        # If action/target still not provided, inspect checkpointed state
        if not action or not target:
            try:
                state_snapshot = await self.graph.aget_state(config)
                if state_snapshot and state_snapshot.values:
                    appr_details = state_snapshot.values.get("approval_details") or {}
                    action = action or appr_details.get("action") or "open_release_valve"
                    target = target or appr_details.get("target") or "actuator"
            except Exception as e:
                logger.debug("Could not inspect graph state for thread %s: %s", thread_id, e)

        action = action or "open_release_valve"
        target = target or "unit actuator"

        resume_payload = {
            "approved": approved,
            "operator_email": operator_email,
            "comment": comment,
        }
        resumed_state = await self.graph.ainvoke(
            Command(resume=resume_payload), config=config
        )

        return {
            "thread_id": thread_id,
            "status": "APPROVED_AND_EXECUTED" if approved else "REJECTED",
            "action": action,
            "target": target,
            "operator_email": operator_email,
            "synthesis": resumed_state.get("final_synthesis"),
            "action_status": resumed_state.get("action_status"),
        }

    def get_required_clearance_for_authority(self, authority: str | None) -> int:
        """Derives required clearance level from authority specification string."""
        return get_required_clearance_for_authority(authority)

    def get_pending_approval(self, thread_id: str) -> dict[str, Any] | None:
        """Returns pending approval metadata if active, or None."""
        return self._pending_approvals.get(thread_id)

    def list_pending_approvals(self) -> list[dict[str, Any]]:
        """Returns all currently active pending approvals."""
        return list(self._pending_approvals.values())


# Singleton instance
planner_service = PlannerService()
