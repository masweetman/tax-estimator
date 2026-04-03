"""California income tax calculation for MFJ."""
from .constants import (
    CA_STANDARD_DEDUCTION_MFJ,
    CA_BRACKETS_MFJ,
    CA_MENTAL_HEALTH_SURTAX_RATE,
    CA_MENTAL_HEALTH_SURTAX_THRESHOLD,
    SALT_CAP,
)


def _apply_brackets(income, brackets):
    tax = 0.0
    prev_limit = 0.0
    for rate, upper in brackets:
        if income <= prev_limit:
            break
        top = upper if upper is not None else income
        top = min(top, income)
        tax += (top - prev_limit) * rate
        prev_limit = upper if upper is not None else income
        if upper is None or income <= upper:
            break
    return tax


def calculate_california(inputs, federal_result):
    """Compute California income tax.

    California:
    - Conforms to most federal AGI adjustments but has its own brackets.
    - No SALT cap on CA return (state deduction is full amount).
    - No NIIT or additional Medicare (CA doesn't have these).
    - CA taxes LTCG as ordinary income.
    - CA standard deduction is much lower than federal.
    - CA does NOT allow SDI deduction on CA return.
    - 1% Mental Health Services surtax on taxable income > $1M.
    """
    year = inputs.get("tax_year", 2025)
    brackets = CA_BRACKETS_MFJ.get(year, CA_BRACKETS_MFJ[2025])
    std_deduction = CA_STANDARD_DEDUCTION_MFJ.get(year, CA_STANDARD_DEDUCTION_MFJ[2025])

    # CA AGI = federal AGI (simplified; CA conforms to most above-the-line deductions)
    # Note: CA does not allow IRA deduction for some cases, but we simplify here.
    ca_agi = float(federal_result["federal_agi"])

    # --- CA Itemized deductions (no SALT cap; SDI not deductible on CA) ---
    mortgage_interest = float(inputs.get("mortgage_interest", 0))
    charitable = float(inputs.get("charitable", 0))
    # CA allows full state/local tax deduction (not capped) BUT SDI not deductible
    salt_paid = float(inputs.get("salt_taxes_paid", 0))  # property tax + other state taxes
    medical_agi_floor = ca_agi * 0.075
    medical = max(0.0, float(inputs.get("medical_expenses", 0)) - medical_agi_floor)

    ca_itemized = mortgage_interest + charitable + salt_paid + medical

    if ca_itemized > std_deduction:
        ca_deduction = ca_itemized
        ca_deduction_type = "itemized"
    else:
        ca_deduction = std_deduction
        ca_deduction_type = "standard"

    ca_taxable_income = max(0.0, ca_agi - ca_deduction)

    # --- CA ordinary income tax ---
    ca_income_tax_before_surtax = _apply_brackets(ca_taxable_income, brackets)

    # --- Mental Health Services surtax ---
    mh_base = max(0.0, ca_taxable_income - CA_MENTAL_HEALTH_SURTAX_THRESHOLD)
    ca_mental_health_surtax = round(mh_base * CA_MENTAL_HEALTH_SURTAX_RATE, 2)

    ca_income_tax = round(ca_income_tax_before_surtax + ca_mental_health_surtax, 2)

    return {
        "ca_agi": round(ca_agi, 2),
        "ca_taxable_income": round(ca_taxable_income, 2),
        "ca_deduction_type": ca_deduction_type,
        "ca_deduction_amount": round(ca_deduction, 2),
        "ca_income_tax_before_surtax": round(ca_income_tax_before_surtax, 2),
        "ca_mental_health_surtax": ca_mental_health_surtax,
        "ca_income_tax": ca_income_tax,
    }
