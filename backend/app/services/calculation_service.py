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
        val = float(node.value)
        if abs(val) > 1e9:
            raise ValueError("Numeric constant exceeds maximum calculation limit (1e9)")
        return val

    if isinstance(node, ast.Name):
        if node.id in variables:
            val = float(variables[node.id])
            if abs(val) > 1e9:
                raise ValueError(f"Variable '{node.id}' exceeds maximum calculation limit (1e9)")
            return val
        raise ValueError(f"Undefined variable in calculation: '{node.id}'")

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_OPERATORS:
            raise ValueError(f"Unsupported mathematical operator: {op_type.__name__}")
        left = _safe_eval_node(node.left, variables)
        right = _safe_eval_node(node.right, variables)
        if op_type is ast.Div and abs(right) < 1e-12:
            raise ZeroDivisionError("Division by zero in calculation sandbox")
        if op_type is ast.Pow:
            if abs(right) > 8 or abs(left) > 10000:
                raise ValueError("Exponent or base exceeds safe calculation bounds (max base 10000, max exp 8)")
        res = _ALLOWED_OPERATORS[op_type](left, right)
        if abs(res) > 1e12:
            raise ValueError("Calculation result exceeds allowable magnitude")
        return res

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
        if len(formula) > 256:
            raise ValueError("Formula string exceeds safe length limit (256 chars)")

        try:
            parsed = ast.parse(formula, mode="eval")
            # Guard against complex AST trees
            if sum(1 for _ in ast.walk(parsed)) > 50:
                raise ValueError("Formula AST complexity exceeds safe limit (max 50 nodes)")
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
