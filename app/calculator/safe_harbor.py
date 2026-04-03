"""Safe harbor calculations and quarterly payment recommendations."""
from .constants import (
    SAFE_HARBOR_HIGH_INCOME_THRESHOLD,
    SAFE_HARBOR_LOW_MULTIPLIER,
    SAFE_HARBOR_HIGH_MULTIPLIER,
    CA_SAFE_HARBOR_CURRENT_YEAR_PCT,
)


def calculate_safe_harbor(inputs, federal_result, ca_result):
    """Return safe harbor amounts and quarterly payment recommendations.

    Federal safe harbor:
      - Prior-year AGI ≤ $150k → 100% of prior-year federal tax
      - Prior-year AGI > $150k → 110% of prior-year federal tax
      - Also: 90% of current-year federal tax (use the LOWER of the two)

    California safe harbor:
      - 100% of prior-year CA tax  OR  90% of current-year CA tax
      - Use the lower of the two thresholds

    Quarterly payment = (safe_harbor - ytd_withholding - ytd_estimates) / remaining_quarters
    """
    prior_agi = float(inputs.get("prior_year_agi", 0))
    prior_fed_tax = float(inputs.get("prior_year_federal_tax", 0))
    prior_ca_tax = float(inputs.get("prior_year_ca_tax", 0))

    current_fed_tax = float(federal_result.get("federal_total_tax", 0))
    current_ca_tax = float(ca_result.get("ca_income_tax", 0))

    # Federal safe harbor (prior-year based)
    if prior_agi > SAFE_HARBOR_HIGH_INCOME_THRESHOLD:
        safe_harbor_federal = round(prior_fed_tax * SAFE_HARBOR_HIGH_MULTIPLIER, 2)
    else:
        safe_harbor_federal = round(prior_fed_tax * SAFE_HARBOR_LOW_MULTIPLIER, 2)

    # California safe harbor (prior-year based; 100% of prior CA tax)
    safe_harbor_ca = round(prior_ca_tax * 1.00, 2)

    # --- Payments made so far ---
    fed_withheld = float(inputs.get("federal_income_withheld", 0))
    fed_estimated = float(inputs.get("federal_estimated_paid", 0))
    ca_withheld = float(inputs.get("ca_income_withheld", 0))
    ca_estimated = float(inputs.get("ca_estimated_paid", 0))

    fed_paid_ytd = fed_withheld + fed_estimated
    ca_paid_ytd = ca_withheld + ca_estimated

    # Remaining quarterly payments needed
    fed_remaining = max(0.0, safe_harbor_federal - fed_paid_ytd)
    ca_remaining = max(0.0, safe_harbor_ca - ca_paid_ytd)

    # Divide remaining by 4 quarters (simple approximation)
    quarterly_federal_recommended = round(max(0.0, fed_remaining / 4), 2)
    quarterly_ca_recommended = round(max(0.0, ca_remaining / 4), 2)

    # Balance due
    federal_balance_due = round(current_fed_tax - fed_paid_ytd, 2)
    ca_balance_due = round(current_ca_tax - ca_paid_ytd, 2)

    return {
        "safe_harbor_federal": round(safe_harbor_federal, 2),
        "safe_harbor_ca": round(safe_harbor_ca, 2),
        "federal_paid_ytd": round(fed_paid_ytd, 2),
        "ca_paid_ytd": round(ca_paid_ytd, 2),
        "federal_balance_due": federal_balance_due,
        "ca_balance_due": ca_balance_due,
        "quarterly_federal_recommended": quarterly_federal_recommended,
        "quarterly_ca_recommended": quarterly_ca_recommended,
    }
