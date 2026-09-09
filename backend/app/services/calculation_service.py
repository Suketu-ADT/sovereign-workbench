"""
Sandboxed Calculation Service.
Executes deterministic mathematical computations in an isolated Python runtime
without relying on generative LLM arithmetic (anti-hallucination guarantee).
"""

import ast
import logging
import operator
from typing import Any

from app.schemas.query import CalculationResult

logger = logging.getLogger(__name__)

# Permitted AST node types for safe mathematical evaluation
_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval_node(node: ast.AST, variables: dict[str, float]) -> float:
    """Recursively evaluates an AST node containing only arithmetic operations."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)

    if isinstance(node, ast.Name):
        if node.id in variables:
            return float(variables[node.id])
        raise ValueError(f"Undefined variable in calculation: '{node.id}'")

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_OPERATORS:
            raise ValueError(f"Unsupported mathematical operator: {op_type.__name__}")
        left = _safe_eval_node(node.left, variables)
        right = _safe_eval_node(node.right, variables)
        if op_type is ast.Div and abs(right) < 1e-12:
            raise ZeroDivisionError("Division by zero in calculation sandbox")
        return _ALLOWED_OPERATORS[op_type](left, right)

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_OPERATORS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        operand = _safe_eval_node(node.operand, variables)
        return _ALLOWED_OPERATORS[op_type](operand)

    raise ValueError(f"Disallowed syntax node in sandboxed calculation: {type(node).__name__}")


class CalculationService:
    """Executes verified deterministic industrial calculations."""

    def evaluate_sandboxed(self, formula: str, variables: dict[str, float]) -> float:
        """
        Safely evaluates an arithmetic expression using AST inspection.
        Rejects function calls, imports, attribute access, and arbitrary code.
        """
        try:
            parsed = ast.parse(formula, mode="eval")
            return _safe_eval_node(parsed.body, variables)
        except Exception as e:
            logger.error("Sandboxed calculation error for '%s': %s", formula, e)
            raise ValueError(f"Safe calculation failed: {e}") from e

    def compute_differential_pressure(
        self,
        inlet_pressure: float,
        outlet_pressure: float = 2.6,
        normal_min: float = 2.0,
        normal_max: float = 5.0,
        equipment_unit: str = "boiler-102",
    ) -> CalculationResult:
        """
        Calculates differential pressure (delta-p = p_inlet - p_outlet)
        and checks against nominal operational safety boundaries.
        """
        formula = "inlet_pressure - outlet_pressure"
        delta_p = self.evaluate_sandboxed(
            formula=formula,
            variables={"inlet_pressure": inlet_pressure, "outlet_pressure": outlet_pressure},
        )
        delta_p = round(delta_p, 2)

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
