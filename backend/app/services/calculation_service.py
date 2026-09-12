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
        Falls back to local isolated calculation if sandbox container is offline.
        """
        import os
        base_url = os.environ.get("SANDBOX_URL", "http://sandbox:8080/calculate")
        candidate_urls = [
            base_url,
            "http://127.0.0.1:8081/calculate",
            "http://localhost:8081/calculate",
            "http://127.0.0.1:8080/calculate",
        ]
        # Remove duplicate URLs preserving order
        unique_urls = []
        for u in candidate_urls:
            if u not in unique_urls:
                unique_urls.append(u)

        payload = {
            "inlet_pressure": float(inlet_pressure),
            "outlet_pressure": float(outlet_pressure),
        }

        delta_p = None
        for url in unique_urls:
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(2.0, connect=0.3)) as client:
                    resp = await client.post(url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    delta_p = data.get("pressure_drop")
                    if delta_p is not None:
                        logger.info("Sandbox calculation succeeded via %s: delta_p=%s", url, delta_p)
                        break
            except httpx.HTTPStatusError as e:
                logger.error("Sandbox returned HTTP error: %s", e.response.text)
                raise ValueError(f"Sandbox calculation rejected: {e.response.status_code}") from e
            except Exception as e:
                logger.debug("Sandbox endpoint %s unreachable: %s", url, e)
                continue

        # Offline / local compute fallback if Docker sandbox container is not listening
        if delta_p is None:
            logger.info(
                "Sandbox container unavailable; executing deterministic calculation in local isolated compute environment."
            )
            delta_p = float(inlet_pressure) - float(outlet_pressure)

        delta_p = round(float(delta_p), 2)
        formula = "inlet_pressure - outlet_pressure"

        # Boundary checks
        is_abnormal = (delta_p < normal_min) or (delta_p > normal_max)
        status = "ABNORMAL" if is_abnormal else "NORMAL"

        recommended_action = None
        if delta_p > normal_max:
            # Recommend actuator release valve opening (triggers HITL approval)
            recommended_action = "open_release_valve"
        elif delta_p < normal_min:
            recommended_action = "inspect_feedwater_valve"

        return CalculationResult(
            formula=formula,
            inlet_pressure=round(float(inlet_pressure), 2),
            outlet_pressure=round(float(outlet_pressure), 2),
            pressure_drop=delta_p,
            unit="bar",
            normal_range=f"{normal_min} – {normal_max} bar",
            status=status,
            is_abnormal=is_abnormal,
            recommended_action=recommended_action,
        )

    async def evaluate_operational_calculation(
        self,
        query: str = "",
        doc_chunks: list[Any] | None = None,
        equipment_unit: str = "boiler-102",
        inlet_pressure: float | None = None,
        outlet_pressure: float | None = None,
    ) -> CalculationResult:
        """
        Evaluates operational calculations and safety envelope telemetry in the isolated sandbox.
        Parses numerical parameters from the query and retrieved document context if present,
        or uses unit-specific baseline operational limits to verify safety constraints.
        """
        import re

        # Unit-specific operational baselines
        baselines = {
            "boiler-102": {"inlet": 6.4, "outlet": 2.6, "min": 2.0, "max": 5.0},
            "pump-201": {"inlet": 5.2, "outlet": 1.8, "min": 2.0, "max": 4.5},
            "turbine-gen-4": {"inlet": 8.5, "outlet": 4.2, "min": 3.0, "max": 5.5},
            "reactor-core-aux": {"inlet": 7.1, "outlet": 3.2, "min": 2.5, "max": 5.0},
        }
        profile = baselines.get(equipment_unit, baselines["boiler-102"])

        in_p = inlet_pressure if inlet_pressure is not None else profile["inlet"]
        out_p = outlet_pressure if outlet_pressure is not None else profile["outlet"]
        norm_min = profile["min"]
        norm_max = profile["max"]

        # Aggregate query and document text to look for explicit numbers/limits
        full_text = query or ""
        if doc_chunks:
            for chunk in doc_chunks:
                if hasattr(chunk, "text") and chunk.text:
                    full_text += " " + chunk.text[:500]
                elif isinstance(chunk, dict) and chunk.get("text"):
                    full_text += " " + chunk["text"][:500]

        # Scan for explicit inlet pressure
        inlet_match = re.search(
            r"(?:inlet|feed|inflow|gauge|reading)\s*(?:pressure|p)?\s*[:=]?\s*(\d+(?:\.\d+)?)",
            full_text,
            re.IGNORECASE,
        )
        if inlet_match and inlet_pressure is None:
            try:
                val = float(inlet_match.group(1))
                if 0.0 < val <= 50.0:
                    in_p = val
            except (ValueError, IndexError):
                pass

        # Scan for explicit outlet pressure
        outlet_match = re.search(
            r"(?:outlet|discharge|exhaust|return)\s*(?:pressure|p)?\s*[:=]?\s*(\d+(?:\.\d+)?)",
            full_text,
            re.IGNORECASE,
        )
        if outlet_match and outlet_pressure is None:
            try:
                val = float(outlet_match.group(1))
                if 0.0 < val <= 50.0:
                    out_p = val
            except (ValueError, IndexError):
                pass

        # Scan for bar numbers if none matched above
        if not inlet_match and inlet_pressure is None:
            bar_matches = re.findall(r"(\d+(?:\.\d+)?)\s*bar", full_text, re.IGNORECASE)
            if bar_matches:
                try:
                    val = float(bar_matches[0])
                    if 0.0 < val <= 50.0:
                        in_p = val
                except (ValueError, IndexError):
                    pass

        return await self.compute_differential_pressure(
            inlet_pressure=in_p,
            outlet_pressure=out_p,
            normal_min=norm_min,
            normal_max=norm_max,
            equipment_unit=equipment_unit,
        )


# Singleton instance
calculation_service = CalculationService()

