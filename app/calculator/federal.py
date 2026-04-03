"""Federal income and SE tax calculation for MFJ with 2 children."""
from .constants import (
    FEDERAL_STANDARD_DEDUCTION_MFJ,
    FEDERAL_BRACKETS_MFJ,
    LTCG_BRACKETS_MFJ,
    SS_WAGE_BASE,
    SS_EMPLOYEE_RATE,
    MEDICARE_EMPLOYEE_RATE,
    ADDITIONAL_MEDICARE_RATE,
    ADDITIONAL_MEDICARE_THRESHOLD_MFJ,
    SE_SELF_EMPLOYMENT_RATE,
    SE_NET_EARNINGS_FACTOR,
    NIIT_RATE,
    NIIT_THRESHOLD_MFJ,
    CHILD_TAX_CREDIT,
    CHILD_TAX_CREDIT_PHASE_OUT_START_MFJ,
    CHILD_TAX_CREDIT_PHASE_OUT_PER_1K,
    CDCC_MAX_EXPENSES_2_PLUS,
    CDCC_MAX_EXPENSES_1_CHILD,
    CDCC_MIN_RATE,
    CDCC_MAX_RATE,
    CDCC_PHASE_DOWN_START,
    SALT_CAP,
)


def _apply_brackets(income, brackets):
    """Compute tax on `income` using a graduated bracket table.

    `brackets` is a list of (rate, upper_bound) pairs where upper_bound=None
    means no ceiling.  Income is taxed at `rate` on the portion that falls
    within each bracket.
    """
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


def _marginal_rate(income, brackets):
    """Return the marginal rate that applies to `income`."""
    prev_limit = 0.0
    for rate, upper in brackets:
        if upper is None or income <= upper:
            return rate
        prev_limit = upper
    return brackets[-1][0]


def calculate_se(inputs):
    """Calculate self-employment tax components.

    Returns a dict with:
      se_net_total, se_deduction (half-SE, above-the-line), federal_se_tax
    """
    year = inputs.get("tax_year", 2025)
    ss_base = SS_WAGE_BASE.get(year, SS_WAGE_BASE[2025])
    w2_wages = float(inputs.get("w2_wages", 0))

    se_net_p1 = float(inputs.get("se_net_income_p1", 0))
    se_net_p2 = float(inputs.get("se_net_income_p2", 0))
    se_total = se_net_p1 + se_net_p2

    if se_total <= 0:
        return {"se_net_total": 0.0, "se_deduction": 0.0, "federal_se_tax": 0.0}

    # SE subject to SS: net earnings × 92.35%, capped at SS wage base minus W-2 wages
    net_earnings = se_total * SE_NET_EARNINGS_FACTOR

    # SS portion – individual-level (per-person) but simplified here to combined
    # In reality each person has their own SS wage base. We simplify by treating
    # combined W-2 wages as filling the base, then SE for each person is separate.
    # For this app we use a per-person approach:
    def _person_se_tax(se_net, w2_for_person):
        ne = se_net * SE_NET_EARNINGS_FACTOR
        ss_room = max(0.0, ss_base - w2_for_person)
        ss_subject = min(ne, ss_room)
        ss_tax = ss_subject * 0.124  # both employee + employer halves
        medicare_tax = ne * 0.029    # both halves
        return ss_tax + medicare_tax

    # Simplification: assume W-2 wages split equally between two filers
    w2_per_person = w2_wages / 2
    se_tax = _person_se_tax(se_net_p1, w2_per_person) + _person_se_tax(se_net_p2, w2_per_person)
    half_se = se_tax / 2.0  # above-the-line deduction

    return {
        "se_net_total": se_total,
        "se_deduction": round(half_se, 2),
        "federal_se_tax": round(se_tax, 2),
    }


def calculate_federal(inputs):
    """Compute federal income tax and related amounts.

    Returns a dict with all tax line items.
    """
    year = inputs.get("tax_year", 2025)
    brackets = FEDERAL_BRACKETS_MFJ.get(year, FEDERAL_BRACKETS_MFJ[2025])
    ltcg_brackets = LTCG_BRACKETS_MFJ.get(year, LTCG_BRACKETS_MFJ[2025])
    std_deduction = FEDERAL_STANDARD_DEDUCTION_MFJ.get(year, FEDERAL_STANDARD_DEDUCTION_MFJ[2025])
    ss_base = SS_WAGE_BASE.get(year, SS_WAGE_BASE[2025])

    w2_wages = float(inputs.get("w2_wages", 0))
    ltcg = float(inputs.get("long_term_capital_gains", 0))
    stcg = float(inputs.get("short_term_capital_gains", 0))

    # --- SE components ---
    se = calculate_se(inputs)
    se_net_total = se["se_net_total"]
    se_deduction = se["se_deduction"]

    # --- Above-the-line AGI adjustments ---
    pretax_401k = float(inputs.get("pretax_401k_total", 0))
    # Note: pre-tax 401k is typically excluded from Box 1 wages (W-2), so it's
    # already not in w2_wages. We don't double-subtract it here.
    # However, if the caller passes w2_wages as GROSS before 401k, we subtract.
    # Convention: w2_wages = box-1 wages (post 401k). No double-deduction.

    ira_deduction = float(inputs.get("traditional_ira_total", 0))
    sep_ira = float(inputs.get("sep_ira_total", 0))
    hsa = float(inputs.get("hsa_total", 0))
    se_health_ins = float(inputs.get("se_health_insurance", 0))
    vehicle_mileage_deduction = float(inputs.get("vehicle_mileage_deduction", 0))

    gross_income = w2_wages + se_net_total + stcg + ltcg

    federal_agi = (
        gross_income
        - pretax_401k
        - se_deduction
        - ira_deduction
        - sep_ira
        - hsa
        - se_health_ins
    )
    federal_agi = max(0.0, federal_agi)

    # --- Itemized deductions ---
    mortgage_interest = float(inputs.get("mortgage_interest", 0))
    charitable = float(inputs.get("charitable", 0))
    salt_paid = float(inputs.get("salt_taxes_paid", 0))
    salt_deductible = min(salt_paid, SALT_CAP)
    medical = max(0.0, float(inputs.get("medical_expenses", 0)) - federal_agi * 0.075)
    # SDI paid is deductible as state tax (but still subject to SALT cap combined)
    ca_sdi = float(inputs.get("ca_sdi_withheld", 0))
    salt_total = min(salt_paid + ca_sdi, SALT_CAP)

    itemized = mortgage_interest + charitable + salt_total + medical

    if itemized > std_deduction:
        deduction = itemized
        deduction_type = "itemized"
    else:
        deduction = std_deduction
        deduction_type = "standard"

    # --- Taxable income ---
    # Capital gains are "stacked" on top of ordinary income for bracket calculation
    ordinary_income = federal_agi - ltcg  # ordinary part only
    federal_taxable_income = max(0.0, federal_agi - deduction)
    ordinary_taxable = max(0.0, federal_taxable_income - ltcg)

    # --- Ordinary income tax ---
    income_tax = _apply_brackets(ordinary_taxable, brackets)

    # --- LTCG tax ---
    ltcg_for_tax = max(0.0, min(ltcg, federal_taxable_income))
    # "Stack" ordinary income in lower brackets, LTCG fills above
    ltcg_base = ordinary_taxable  # income below LTCG
    ltcg_tax = _apply_brackets(ltcg_base + ltcg_for_tax, ltcg_brackets) - \
               _apply_brackets(ltcg_base, ltcg_brackets)
    ltcg_tax = max(0.0, ltcg_tax)

    federal_income_tax_before_credits = income_tax + ltcg_tax

    # --- Child Tax Credit ---
    qualifying_children = int(inputs.get("qualifying_children", 0))
    raw_ctc = qualifying_children * CHILD_TAX_CREDIT
    # Phase out: $50 per $1,000 (or fraction) over threshold
    excess = max(0.0, federal_agi - CHILD_TAX_CREDIT_PHASE_OUT_START_MFJ)
    phase_out_units = int((excess + 999) // 1_000) if excess > 0 else 0
    ctc = max(0, raw_ctc - phase_out_units * CHILD_TAX_CREDIT_PHASE_OUT_PER_1K)

    # --- Child & Dependent Care Credit ---
    child_care_expenses = float(inputs.get("child_care_expenses", 0))
    max_care_exp = CDCC_MAX_EXPENSES_2_PLUS if qualifying_children >= 2 else (
        CDCC_MAX_EXPENSES_1_CHILD if qualifying_children == 1 else 0
    )
    eligible_care_exp = min(child_care_expenses, max_care_exp)
    # Credit rate phases from 35% to 20% as AGI goes from $15k to $43k
    if federal_agi <= CDCC_PHASE_DOWN_START:
        care_rate = CDCC_MAX_RATE
    else:
        reduction_units = min(28, int((federal_agi - CDCC_PHASE_DOWN_START) / 2_000))
        care_rate = max(CDCC_MIN_RATE, CDCC_MAX_RATE - reduction_units * 0.01)
    child_care_credit = round(eligible_care_exp * care_rate, 2)

    # --- Apply credits ---
    tax_after_credits = max(0.0,
        federal_income_tax_before_credits - ctc - child_care_credit
    )
    # Note: CTC and CDCC are non-refundable (simplified; partial refundability ignored)

    # --- SE tax ---
    federal_se_tax = se["federal_se_tax"]

    # --- Additional Medicare Tax ---
    total_wages_and_se = w2_wages + se_net_total
    amt_base = max(0.0, total_wages_and_se - ADDITIONAL_MEDICARE_THRESHOLD_MFJ)
    additional_medicare_tax = round(amt_base * ADDITIONAL_MEDICARE_RATE, 2)

    # --- Net Investment Income Tax ---
    nii = ltcg + max(0.0, stcg)  # simplified: NII = capital gains
    niit_base = min(nii, max(0.0, federal_agi - NIIT_THRESHOLD_MFJ))
    niit = round(max(0.0, niit_base) * NIIT_RATE, 2)

    federal_total_tax = round(
        tax_after_credits + federal_se_tax + additional_medicare_tax + niit, 2
    )

    # --- Marginal rate ---
    marginal_rate = _marginal_rate(ordinary_taxable, brackets)

    return {
        "federal_agi": round(federal_agi, 2),
        "federal_taxable_income": round(federal_taxable_income, 2),
        "deduction_type": deduction_type,
        "deduction_amount": round(deduction, 2),
        "federal_income_tax_before_credits": round(federal_income_tax_before_credits, 2),
        "child_tax_credit": ctc,
        "child_care_credit": child_care_credit,
        "federal_income_tax": round(tax_after_credits, 2),
        "se_deduction": se["se_deduction"],
        "federal_se_tax": federal_se_tax,
        "additional_medicare_tax": additional_medicare_tax,
        "niit": niit,
        "federal_total_tax": federal_total_tax,
        "effective_federal_rate": round(tax_after_credits / federal_agi, 4) if federal_agi else 0,
        "marginal_federal_rate": marginal_rate,
    }
