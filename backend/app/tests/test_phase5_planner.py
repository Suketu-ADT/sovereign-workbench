import pytest
from unittest.mock import patch, AsyncMock
from typing import Any

from app.services.planner_service import (
    reasoning_node, PlanState, PlannerOutput, STATIC_TOOL_REGISTRY,
    _route_after_reasoning, hitl_gate_node, action_execution_node
)
from app.services import rbac_service
from app.core.capability_map import CAPABILITY_MAP

@pytest.fixture
def base_state() -> PlanState:
    return {
        "thread_id": "test-thread-123",
        "query": "",
        "user_id": "test_user",
        "operator_email": "test@example.com",
        "clearance_level": 3,
        "unit": "boiler-102",
        "retrieved_docs": [],
        "vision_reading": 6.4,
        "pressure_drop": 5.5,
        "proposed_action": None,
        "approval_required": False,
        "approval_details": None,
        "approval_decision": None,
        "action_status": "PENDING",
        "final_synthesis": None,
    }

@pytest.mark.asyncio
@patch("app.services.planner_service._call_llm_planner", new_callable=AsyncMock)
async def test_1_novel_semantic_request(mock_call_llm, base_state):
    # Test 1: Novel semantic request (no exact hardcoded words like 'valve', 'shutdown')
    base_state["query"] = "The inlet reads high, should I vent the pressure?"
    
    # Mock LLM returning a valid proposed action "open_release_valve"
    mock_call_llm.return_value = {
        "response": '{"intent": "vent pressure", "required_tools": ["open_release_valve"], "proposed_action": "open_release_valve", "requires_sensitive_approval": true, "reason": "High inlet reading"}'
    }

    result = await reasoning_node(base_state)

    # Assert LLM was called
    mock_call_llm.assert_called_once()
    assert mock_call_llm.call_args[0][0].find("The inlet reads high, should I vent the pressure?") != -1

    # Assert valid output triggered HITL
    assert result["approval_required"] is True
    assert result["action_status"] == "PENDING"
    assert result["proposed_action"]["action"] == "open_release_valve"
    assert "approval_details" in result
    assert result["approval_details"]["authority"] == "Senior_Engineer (HITL Required)"

@pytest.mark.asyncio
@patch("app.services.planner_service._call_llm_planner", new_callable=AsyncMock)
async def test_2_non_sensitive_request(mock_call_llm, base_state):
    # Test 2: Non-sensitive request
    base_state["query"] = "Find the maintenance procedure for boiler-102."
    
    mock_call_llm.return_value = {
        "response": '{"intent": "find procedure", "required_tools": ["retrieve_manual"], "proposed_action": "retrieve_manual", "requires_sensitive_approval": false, "reason": "Reading documentation"}'
    }

    result = await reasoning_node(base_state)

    assert result["approval_required"] is False
    assert result["action_status"] == "NOT_REQUIRED"
    assert result["proposed_action"]["action"] == "retrieve_manual"

@pytest.mark.asyncio
@patch("app.services.planner_service._call_llm_planner", new_callable=AsyncMock)
async def test_3_unauthorized_user(mock_call_llm, base_state):
    # Test 3: Unauthorized user
    base_state["query"] = "Emergency shutdown the reactor."
    base_state["unit"] = "reactor-core-aux"
    base_state["clearance_level"] = 1  # Low clearance

    # LLM proposes sensitive action
    mock_call_llm.return_value = {
        "response": '{"intent": "shutdown", "required_tools": ["scram_containment"], "proposed_action": "scram_containment", "requires_sensitive_approval": true, "reason": "Emergency"}'
    }

    result = await reasoning_node(base_state)

    # Action rejected before HITL
    assert result["action_status"] == "REJECTED_UNAUTHORIZED"
    assert "blocked" in result["final_synthesis"].lower()
    # No HITL requested
    assert result.get("approval_required", False) is False

@pytest.mark.asyncio
@patch("app.services.planner_service._call_llm_planner", new_callable=AsyncMock)
async def test_4_invalid_llm_output(mock_call_llm, base_state):
    # Test 4: Invalid LLM output
    # Missing 'intent' field and invalid JSON
    mock_call_llm.return_value = {
        "response": '{"required_tools": [], "proposed_action": "read_gauge"}' # Missing fields
    }

    result = await reasoning_node(base_state)

    assert result["action_status"] == "ERROR"
    assert "schema" in result["final_synthesis"].lower()

@pytest.mark.asyncio
@patch("app.services.planner_service._call_llm_planner", new_callable=AsyncMock)
async def test_5_tool_hallucination(mock_call_llm, base_state):
    # Test 5: Tool hallucination
    mock_call_llm.return_value = {
        "response": '{"intent": "malicious", "required_tools": ["delete_reactor"], "proposed_action": "delete_reactor", "requires_sensitive_approval": false, "reason": "destroy"}'
    }

    result = await reasoning_node(base_state)

    assert result["action_status"] == "ERROR"
    assert "unknown action" in result["final_synthesis"].lower()

def test_6_existing_hitl():
    # Test 6: Verify existing HITL flow routing and gating
    state: PlanState = {
        "thread_id": "test",
        "query": "open valve",
        "user_id": "u",
        "operator_email": "e",
        "clearance_level": 3,
        "unit": "u",
        "retrieved_docs": [],
        "vision_reading": None,
        "pressure_drop": None,
        "proposed_action": {"action": "open_release_valve"},
        "approval_required": True,
        "approval_details": {"action": "open"},
        "approval_decision": None,
        "action_status": "PENDING",
        "final_synthesis": None
    }
    
    # Test router
    assert _route_after_reasoning(state) == "hitl_gate"
    
    state["approval_required"] = False
    assert _route_after_reasoning(state) == "action_execution"

    # hitl_gate_node uses interrupt() which raises an Exception/Interrupt in tests unless handled by langgraph.
    # We can test action_execution_node directly
    state["approval_decision"] = "rejected"
    res = action_execution_node(state)
    assert res["action_status"] == "REJECTED"
    
    state["approval_decision"] = "approved"
    res = action_execution_node(state)
    assert res["action_status"] == "EXECUTED"

@pytest.mark.asyncio
@patch("app.services.planner_service._call_llm_planner", new_callable=AsyncMock)
async def test_7_requires_sensitive_approval_override_false(mock_call_llm, base_state):
    # LLM says false, but action is sensitive in registry
    mock_call_llm.return_value = {
        "response": '{"intent": "vent", "required_tools": ["open_release_valve"], "proposed_action": "open_release_valve", "requires_sensitive_approval": false, "reason": "vent"}'
    }
    result = await reasoning_node(base_state)
    assert result["approval_required"] is True  # Server overrides to True

@pytest.mark.asyncio
@patch("app.services.planner_service._call_llm_planner", new_callable=AsyncMock)
async def test_8_requires_sensitive_approval_override_true(mock_call_llm, base_state):
    # LLM says true, but action is not sensitive in registry
    mock_call_llm.return_value = {
        "response": '{"intent": "log", "required_tools": ["inspect_log"], "proposed_action": "inspect_log", "requires_sensitive_approval": true, "reason": "log"}'
    }
    result = await reasoning_node(base_state)
    assert result["approval_required"] is False  # Server overrides to False
