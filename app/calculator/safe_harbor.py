"""Safe harbor calculations and quarterly payment recommendations."""
from .constants import (
    SAFE_HARBOR_HIGH_INCOME_THRESHOLD,
    SAFE_HARBOR_LOW_MULTIPLIER,
    SAFE_HARBOR_HIGH_MULTIPLIER,
    CA_SAFE_HARBOR_CURRENT_YEAR_PCT,
    FEDERAL_SAFE_HARBOR_CURRENT_YEAR_PCT,
    CA_MILLIONAIRE_THRESHOLD,
)


def calculate_safe_harbor(inputs, federal_result, ca_result):
    """Return safe harbor amounts and quarterly payment recommendations.

    Federal safe harbor (IRS Form 1040-ES):
      - 90% of current-year total federal tax, OR
      - 100% of prior-year federal tax (110% if prior-year AGI > $150k)
      - Safe harbor = the SMALLER of the two

    California safe harbor (FTB Form 540-ES):
      - Millionaire exception: if current OR prior AGI >= $1M, MUST use 90% of
        current-year CA tax only (prior-year safe harbor not available).
      - High-income (AGI > $150k): smaller of 90% current or 110% prior CA tax.
      - Standard (AGI <= $150k): smaller of 90% current or 100% prior CA tax.

    CA quarterly schedule (FTB weighted, not equal fourths):
      Q1 Apr 15: 30% of safe harbor − 25% of annual withholding
      Q2 Jun 15: 40% of safe harbor − 25% of annual withholding
      Q3 Sep 15: $0 (no CA installment due)
      Q4 Jan 15: 30% of safe harbor − 25% of annual withholding

    Federal quarterly schedule (IRS equal fourths):
      Q1–Q4: 25% each, due Apr 15 / Jun 15 / Sep 15 / Jan 15
    """
    prior_agi = float(inputs.get("prior_year_agi", 0))
    prior_fed_tax = float(inputs.get("prior_year_federal_tax", 0))
    prior_ca_tax = float(inputs.get("prior_year_ca_tax", 0))

    current_fed_tax = float(federal_result.get("federal_total_tax", 0))
    current_ca_tax = float(ca_result.get("ca_income_tax", 0))
    ca_agi = float(ca_result.get("ca_agi", 0))

    # ------------------------------------------------------------------
    # Federal safe harbor: min(90% current, 100%/110% prior)
    # ------------------------------------------------------------------
    federal_90pct = round(current_fed_tax * FEDERAL_SAFE_HARBOR_CURRENT_YEAR_PCT, 2)
    if prior_agi > SAFE_HARBOR_HIGH_INCOME_THRESHOLD:
        federal_prior = round(prior_fed_tax * SAFE_HARBOR_HIGH_MULTIPLIER, 2)
    else:
        federal_prior = round(prior_fed_tax * SAFE_HARBOR_LOW_MULTIPLIER, 2)
    safe_harbor_federal = min(federal_90pct, federal_prior)

    # ------------------------------------------------------------------
    # California safe harbor
    # ------------------------------------------------------------------
    ca_millionaire_exception = (
        ca_agi >= CA_MILLIONAIRE_THRESHOLD or prior_agi >= CA_MILLIONAIRE_THRESHOLD
    )

    ca_90pct = round(current_ca_tax * CA_SAFE_HARBOR_CURRENT_YEAR_PCT, 2)

    if ca_millionaire_exception:
        # Must use 90% of current year — prior-year safe harbor not available
        safe_harbor_ca = ca_90pct
        ca_prior = None
    else:
        if prior_agi > SAFE_HARBOR_HIGH_INCOME_THRESHOLD:
            ca_prior = round(prior_ca_tax * SAFE_HARBOR_HIGH_MULTIPLIER, 2)
        else:
            ca_prior = round(prior_ca_tax * SAFE_HARBOR_LOW_MULTIPLIER, 2)
        safe_harbor_ca = min(ca_90pct, ca_prior)

    # ------------------------------------------------------------------
    # Payments made so far
    # ------------------------------------------------------------------
    fed_withheld = float(inputs.get("federal_income_withheld", 0))
    fed_estimated = float(inputs.get("federal_estimated_paid", 0))
    excess_ss = float(federal_result.get("excess_ss", 0))
    ca_withheld = float(inputs.get("ca_income_withheld", 0))
    ca_estimated = float(inputs.get("ca_estimated_paid", 0))

    fed_paid_ytd = fed_withheld + fed_estimated + excess_ss
    ca_paid_ytd = ca_withheld + ca_estimated

    # ------------------------------------------------------------------
    # Federal quarterly: (safe_harbor − all_payments_ytd) / 4
    # ------------------------------------------------------------------
    fed_remaining = max(0.0, safe_harbor_federal - fed_paid_ytd)
    quarterly_federal_recommended = round(fed_remaining / 4, 2)

    # ------------------------------------------------------------------
    # CA quarterly: FTB weighted 30/40/0/30 schedule, net of withholding
    # Each installment is reduced by 25% of annual withholding (even distribution).
    # Estimated payments already made reduce the total CA remaining, but the
    # per-installment amounts are based on the full safe harbor schedule.
    # ------------------------------------------------------------------
    ca_wh_per_quarter = ca_withheld * 0.25

    ca_q1_payment = round(max(0.0, safe_harbor_ca * 0.30 - ca_wh_per_quarter), 2)
    ca_q2_payment = round(max(0.0, safe_harbor_ca * 0.40 - ca_wh_per_quarter), 2)
    ca_q3_payment = 0.0  # No CA installment in Q3
    ca_q4_payment = round(max(0.0, safe_harbor_ca * 0.30 - ca_wh_per_quarter), 2)

    # backward-compat single quarterly value: use Q2 (largest installment)
    quarterly_ca_recommended = ca_q2_payment

    # ------------------------------------------------------------------
    # Balance due (current year tax vs total paid)
    # ------------------------------------------------------------------
    federal_balance_due = round(current_fed_tax - fed_paid_ytd, 2)
    ca_balance_due = round(current_ca_tax - ca_paid_ytd, 2)

    return {
        # Safe harbor amounts
        "safe_harbor_federal": round(safe_harbor_federal, 2),
        "safe_harbor_ca": round(safe_harbor_ca, 2),
        # Intermediate federal safe harbor components (for display)
        "federal_safe_harbor_90pct": federal_90pct,
        "federal_safe_harbor_prior": federal_prior,
        # Intermediate CA safe harbor components (for display)
        "ca_safe_harbor_90pct": ca_90pct,
        "ca_safe_harbor_prior": ca_prior,
        "ca_millionaire_exception": ca_millionaire_exception,
        # Payments
        "excess_ss": round(excess_ss, 2),
        "federal_paid_ytd": round(fed_paid_ytd, 2),
        "ca_paid_ytd": round(ca_paid_ytd, 2),
        # Balance due
        "federal_balance_due": federal_balance_due,
        "ca_balance_due": ca_balance_due,
        # Quarterly recommendations
        "quarterly_federal_recommended": quarterly_federal_recommended,
        "quarterly_ca_recommended": quarterly_ca_recommended,
        "ca_q1_payment": ca_q1_payment,
        "ca_q2_payment": ca_q2_payment,
        "ca_q3_payment": ca_q3_payment,
        "ca_q4_payment": ca_q4_payment,
    }
