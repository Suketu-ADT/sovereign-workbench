"""
Sandboxed Calculation Service.
Executes deterministic mathematical computations by delegating to an isolated
Docker sandbox microservice over an internal network.
"""

import httpx
import logging
from typing import Any

from app.schemas.query import CalculationResult

logger = logging.getLogger(__name__)

class CalculationService:
    """Delegates verified deterministic industrial calculations to a sandbox."""

    async def compute_differential_pressure(
        self,
        inlet_pressure: float,
        outlet_pressure: float = 2.6,
        normal_min: float = 2.0,
        normal_max: float = 5.0,
        equipment_unit: str = "boiler-102",
    ) -> CalculationResult:
        """
        Calls the sandbox API to compute delta-p.
        Applies normal/abnormal boundary checks locally.
        """
        import os
        sandbox_url = os.environ.get("SANDBOX_URL", "http://sandbox:8080/calculate")
        payload = {
            "inlet_pressure": inlet_pressure,
            "outlet_pressure": outlet_pressure
        }
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(sandbox_url, json=payload, timeout=2.0)
                resp.raise_for_status()
                data = resp.json()
                delta_p = data.get("pressure_drop")
                if delta_p is None:
                    raise ValueError("Sandbox returned invalid response format")
        except httpx.HTTPStatusError as e:
            logger.error("Sandbox returned HTTP error: %s", e.response.text)
            raise ValueError(f"Sandbox calculation rejected: {e.response.status_code}") from e
        except Exception as e:
            logger.error("Sandbox communication failed: %s", e)
            raise ValueError(f"Safe calculation failed: {e}") from e

        delta_p = round(delta_p, 2)
        formula = "inlet_pressure - outlet_pressure"

        # Boundary checks
        is_abnormal = (delta_p < normal_min) or (delta_p > normal_max)
        status = "ABNORMAL" if is_abnormal else "NORMAL"

        recommended_action = None
        if delta_p > normal_max:
            # Recommend actuator release valve opening (triggers HITL approval in Phase 5/6)
            recommended_action = "open_release_valve"
        elif delta_p < normal_min:
            recommended_action = "inspect_feedwater_valve"

        return CalculationResult(
            formula=formula,
            inlet_pressure=inlet_pressure,
            outlet_pressure=outlet_pressure,
            pressure_drop=delta_p,
            unit="bar",
            normal_range=f"{normal_min} – {normal_max} bar",
            status=status,
            is_abnormal=is_abnormal,
            recommended_action=recommended_action,
        )


# Singleton instance
calculation_service = CalculationService()
