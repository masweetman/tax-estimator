"""Main entry point for the tax calculator.

Usage::
    from app.calculator.engine import calculate
    result = calculate(inputs_dict)

The returned dict contains all federal + CA tax line items, safe harbor data,
and quarterly payment recommendations.
"""
from .federal import calculate_federal
from .california import calculate_california
from .safe_harbor import calculate_safe_harbor


def calculate(inputs: dict) -> dict:
    """Run the full federal + CA tax calculation.

    Returns a merged dict of all computed values.
    """
    federal = calculate_federal(inputs)
    ca = calculate_california(inputs, federal)
    safe = calculate_safe_harbor(inputs, federal, ca)

    result = {}
    result.update(federal)
    result.update(ca)
    result.update(safe)
    return result
