import asyncio
import json
from app.services.planner_service import planner_service, PlanState
import app.services.planner_service as ps
from app.core.config import settings

async def main():
    print("--- 2. VERIFY REAL OLLAMA/QWEN ---")
    print(f"PLANNER_MODEL_URL: {settings.PLANNER_MODEL_URL}")
    print(f"PLANNER_MODEL_NAME: {settings.PLANNER_MODEL_NAME}")
    
    # 1. Attempt Real LLM Planner Call
    prompt = """You are an industrial reasoning agent. Determine the required tools and proposed action.
    
User Query: The inlet reads high, should I vent the pressure?
Target Unit: boiler-102
Telemetry: Delta P = 5.5 bar, Vision Reading = 6.4 bar

Available Tools:
{
  "open_release_valve": {"description": "Open pressure release valve (SENSITIVE)", "sensitive": true, "authority": "Senior_Engineer (HITL Required)"}
}

Output strictly valid JSON matching this schema:
{
  "intent": "Short description of user intent",
  "required_tools": ["tool1", "tool2"],
  "proposed_action": "One action from the tools list",
  "requires_sensitive_approval": true/false,
  "reason": "Detailed reasoning"
}"""
    try:
        print("\nSending HTTP request to _call_llm_planner...")
        llm_response = await ps._call_llm_planner(prompt)
        print("HTTP request succeeded!")
        print("Model actually used:", llm_response.get("model", "unknown"))
        raw_output = llm_response.get("response", "{}")
        print("\nRaw model response:")
        print(raw_output)
        
        parsed_json = json.loads(raw_output)
        output = ps.PlannerOutput(**parsed_json)
        print("\nParsed PlannerOutput:")
        print(f"proposed_action: {output.proposed_action}")
        print(f"required_tools: {output.required_tools}")
        
    except Exception as e:
        print(f"\nReal LLM call failed. Ollama may not be running locally: {e}")

    print("\n\n--- 3. VERIFY THE FULL APPLICATION PATH ---")
    
    # 2. Run Planner Through Real Service Path
    try:
        print("Invoking run_plan(...)")
        res = await planner_service.run_plan(
            query="The inlet reads high, should I vent the pressure?",
            user_id="test_user",
            operator_email="test@example.com",
            clearance_level=3,
            unit="boiler-102",
            vision_reading=6.4,
            pressure_drop=5.5
        )
        print("Run Plan Result:")
        print(json.dumps(res, indent=2))
        
        print("\nIdentified Executed Functions:")
        print("1. run_plan")
        print("2. graph.ainvoke -> reasoning_node")
        print("3. _call_llm_planner")
        print("4. rbac_service.check_access")
        print("5. _route_after_reasoning")
        print("6. hitl_gate_node")
    except Exception as e:
        print(f"Full application path failed: {e}")
        
if __name__ == "__main__":
    asyncio.run(main())
