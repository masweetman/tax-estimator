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
    ADDITIONAL_MEDICARE_THRESHOLD_SINGLE,
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
    CDCC_PHASE_DOWN_STEP,
    MEDICAL_EXPENSE_FLOOR,
    SALT_CAP,
    SALT_PHASE_DOWN_START,
    SALT_FLOOR,
    CHARITABLE_NONITEMIZER_CAP_MFJ,
    QBI_RATE,
    QBI_THRESHOLD_MFJ,
    QBI_THRESHOLD_SINGLE,
    QBI_PHASE_IN_RANGE,
    QBI_PHASE_IN_RANGE_SINGLE,
    SOLO_401K_EMPLOYEE_LIMIT,
    SOLO_401K_TOTAL_LIMIT,
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


def calculate_solo_401k_max(net_profit, year, employee_limit_override=None, total_limit_override=None):
    """Compute the maximum Solo 401(k) contribution for a Schedule C / SMLLC owner.

    Follows Solo_401k_Instructions.txt exactly:
      Step 1 – SE Tax Deduction
        net_se_earnings = net_profit * 0.9235
        se_tax          = net_se_earnings * 0.153
        D (deductible)  = se_tax * 0.50
      Step 2 – Net Earned Income (Plan Compensation)
        C = net_profit - D
      Step 3 – Employee Elective Deferral
        max_employee = min(C, annual_employee_limit)
      Step 4 – Employer Non-Elective (20% of C for SMLLC / sole proprietor)
        max_employer = C * 0.20
      Step 5 – Section 415(c) Total Limit
        grand_total = min(max_employee + max_employer, total_limit, C)

    Returns a dict with all intermediate values for display.
    """
    year = int(year)
    net_profit = max(0.0, float(net_profit))

    employee_limit = employee_limit_override or SOLO_401K_EMPLOYEE_LIMIT.get(year, SOLO_401K_EMPLOYEE_LIMIT[2025])
    total_limit = total_limit_override or SOLO_401K_TOTAL_LIMIT.get(year, SOLO_401K_TOTAL_LIMIT[2025])

    net_se_earnings = net_profit * SE_NET_EARNINGS_FACTOR          # * 0.9235
    se_tax = net_se_earnings * 0.153                                # both halves
    d = round(se_tax * 0.5, 2)                                      # deductible half
    c = round(net_profit - d, 2)                                    # Net Earned Income

    max_employee = round(min(c, employee_limit), 2)
    max_employer = round(c * 0.20, 2)
    combined = round(max_employee + max_employer, 2)
    grand_total = round(min(combined, total_limit, max(0.0, c)), 2)

    return {
        "net_profit": net_profit,
        "net_se_earnings": round(net_se_earnings, 2),
        "se_tax": round(se_tax, 2),
        "se_deductible": d,
        "net_earned_income": c,
        "max_employee": max_employee,
        "max_employer": max_employer,
        "grand_total": grand_total,
        "employee_limit": employee_limit,
        "total_limit": total_limit,
    }


def calculate_qbi(qbi_base, pre_qbi_taxable_income, net_cap_gains, year, inputs):
    """Compute the §199A Qualified Business Income deduction.

    Three-zone logic per §199A (OBBBA 2025 thresholds, $0 W-2 wages / UBIA):
      Zone 1: TI <= lower threshold  → 20% × QBI
      Zone 2: TI >  upper threshold  → $0  (wage-limit = $0 with no employees)
      Zone 3: phase-in range         → linearly blend Zone 1 → Zone 2
    Overall cap: deduction <= 20% × (TI − net capital gains).
    """
    if qbi_base <= 0:
        return 0.0

    filing_status = inputs.get("filing_status", "MFJ")
    if filing_status == "MFJ":
        lower = inputs.get("qbi_threshold") or QBI_THRESHOLD_MFJ.get(year, QBI_THRESHOLD_MFJ[2025])
        phase_range = QBI_PHASE_IN_RANGE
    else:
        lower = QBI_THRESHOLD_SINGLE.get(year, QBI_THRESHOLD_SINGLE[2025])
        phase_range = QBI_PHASE_IN_RANGE_SINGLE
    upper = lower + phase_range

    tentative = qbi_base * QBI_RATE
    if pre_qbi_taxable_income <= lower:
        deduction = tentative                                # Zone 1
    elif pre_qbi_taxable_income > upper:
        deduction = 0.0                                     # Zone 2 ($0 W-2/UBIA)
    else:
        phase_in_pct = (pre_qbi_taxable_income - lower) / phase_range
        deduction = tentative * (1.0 - phase_in_pct)        # Zone 3

    # Overall income cap: deduction <= 20% of (TI - net capital gains)
    income_cap = max(0.0, (pre_qbi_taxable_income - net_cap_gains) * QBI_RATE)
    return round(min(deduction, income_cap), 2)


def calculate_se(inputs):
    """Calculate self-employment tax components.

    Returns a dict with:
      se_net_total, se_deduction (half-SE, above-the-line), federal_se_tax
    """
    year = inputs.get("tax_year", 2025)
    ss_base = inputs.get("ss_wage_base") or SS_WAGE_BASE.get(year, SS_WAGE_BASE[2025])

    se_net_p1 = float(inputs.get("se_net_income_p1", 0))
    se_net_p2 = float(inputs.get("se_net_income_p2", 0))
    se_total = se_net_p1 + se_net_p2

    if se_total <= 0:
        return {"se_net_total": 0.0, "se_deduction": 0.0, "federal_se_tax": 0.0}

    def _person_se_tax(se_net, w2_for_person):
        ne = se_net * SE_NET_EARNINGS_FACTOR
        ss_room = max(0.0, ss_base - w2_for_person)
        ss_subject = min(ne, ss_room)
        ss_tax = ss_subject * (SS_EMPLOYEE_RATE * 2)      # both employee + employer halves
        medicare_tax = ne * (MEDICARE_EMPLOYEE_RATE * 2)    # both halves
        return ss_tax + medicare_tax

    # Use actual per-person W-2 wages to correctly offset each person's SS wage base.
    w2_p1 = float(inputs.get("w2_wages_p1", 0))
    w2_p2 = float(inputs.get("w2_wages_p2", 0))
    se_tax = _person_se_tax(se_net_p1, w2_p1) + _person_se_tax(se_net_p2, w2_p2)
    half_se = se_tax / 2.0  # above-the-line deduction (Addl. Medicare is not deductible)

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
    brackets = inputs.get("federal_brackets") or FEDERAL_BRACKETS_MFJ.get(year, FEDERAL_BRACKETS_MFJ[2025])
    ltcg_brackets = inputs.get("ltcg_brackets") or LTCG_BRACKETS_MFJ.get(year, LTCG_BRACKETS_MFJ[2025])
    std_deduction = inputs.get("federal_standard_deduction") or FEDERAL_STANDARD_DEDUCTION_MFJ.get(year, FEDERAL_STANDARD_DEDUCTION_MFJ[2025])
    ss_base = inputs.get("ss_wage_base") or SS_WAGE_BASE.get(year, SS_WAGE_BASE[2025])

    w2_wages = float(inputs.get("w2_wages", 0))
    ltcg = float(inputs.get("long_term_capital_gains", 0))
    stcg = float(inputs.get("short_term_capital_gains", 0))
    interest_income = float(inputs.get("interest_income", 0))
    ordinary_dividends = float(inputs.get("ordinary_dividends", 0))
    qualified_dividends = min(float(inputs.get("qualified_dividends", 0)), ordinary_dividends)
    taxable_state_refund = float(inputs.get("taxable_state_refund", 0))
    unemployment_compensation = float(inputs.get("unemployment_compensation", 0))

    # --- SE components ---
    se = calculate_se(inputs)
    se_net_total = se["se_net_total"]
    se_deduction = se["se_deduction"]

    # --- Above-the-line AGI adjustments ---
    # Note: w2_wages is Box-1 wages (pre-tax 401k and other payroll benefits are
    # already excluded). Only Schedule-1 items are subtracted below.
    ira_deduction = float(inputs.get("traditional_ira_total", 0))
    sep_ira = float(inputs.get("sep_ira_total", 0))
    solo_401k = float(inputs.get("solo_401k_total", 0))
    hsa = float(inputs.get("hsa_total", 0))
    se_health_ins = float(inputs.get("se_health_insurance", 0))

    # All ordinary dividends enter gross income / AGI.
    # Qualified dividends are a subset that gets LTCG-rate treatment at the
    # bracket calculation stage — they do NOT reduce gross income here.
    gross_income = (w2_wages + se_net_total + stcg + ltcg
                    + interest_income + ordinary_dividends + taxable_state_refund
                    + unemployment_compensation)

    federal_agi = (
        gross_income
        - se_deduction
        - ira_deduction
        - sep_ira
        - solo_401k
        - hsa
        - se_health_ins
    )
    federal_agi = max(0.0, federal_agi)

    # --- Itemized deductions ---
    mortgage_interest = float(inputs.get("mortgage_interest", 0))
    charitable = float(inputs.get("charitable", 0))
    salt_paid = float(inputs.get("salt_taxes_paid", 0))
    medical = max(0.0, float(inputs.get("medical_expenses", 0)) - federal_agi * MEDICAL_EXPENSE_FLOOR)
    # SDI and CA state income tax are deductible as state taxes (subject to SALT cap)
    ca_sdi = float(inputs.get("ca_sdi_withheld", 0))
    ca_state_income = float(inputs.get("ca_income_withheld", 0))
    # SALT cap: year-keyed, with OBBBA phase-down for high incomes (2026+)
    salt_cap_base = inputs.get("salt_cap") or SALT_CAP.get(year, SALT_CAP[2025])
    phase_down_start = SALT_PHASE_DOWN_START.get(year)
    if phase_down_start and federal_agi > phase_down_start:
        salt_cap_base = max(SALT_FLOOR, salt_cap_base - (federal_agi - phase_down_start))
    salt_total = min(salt_paid + ca_sdi + ca_state_income, salt_cap_base)

    itemized = mortgage_interest + charitable + salt_total + medical

    if itemized > std_deduction:
        deduction = itemized
        deduction_type = "itemized"
    else:
        deduction = std_deduction
        deduction_type = "standard"

    # Non-itemizer charitable deduction (above-the-line addition when using standard deduction)
    charitable_nonitemizer_cap = CHARITABLE_NONITEMIZER_CAP_MFJ.get(year, 0)
    charitable_nonitemizer = min(charitable, charitable_nonitemizer_cap) if deduction_type == "standard" else 0.0

    # --- Taxable income ---
    # Capital gains are "stacked" on top of ordinary income for bracket calculation
    federal_taxable_income = max(0.0, federal_agi - deduction - charitable_nonitemizer)

    # --- QBI deduction (§199A) ---
    # Use full pre-QBI taxable income for threshold zone test; net cap gains for income cap.
    pre_qbi_total = federal_taxable_income
    net_cap_gains = ltcg + qualified_dividends
    qbi_deduction = calculate_qbi(se_net_total, pre_qbi_total, net_cap_gains, year, inputs)
    federal_taxable_income = max(0.0, federal_taxable_income - qbi_deduction)

    ordinary_taxable = max(0.0, federal_taxable_income - ltcg - qualified_dividends)

    # --- Ordinary income tax ---
    income_tax = _apply_brackets(ordinary_taxable, brackets)

    # --- LTCG tax ---
    # Qualified dividends are taxed at preferential rates alongside LTCG.
    preferential_income = ltcg + qualified_dividends
    ltcg_for_tax = max(0.0, min(preferential_income, federal_taxable_income))
    # "Stack" ordinary income in lower brackets, preferential income fills above
    ltcg_base = ordinary_taxable  # income below preferential
    ltcg_tax = _apply_brackets(ltcg_base + ltcg_for_tax, ltcg_brackets) - \
               _apply_brackets(ltcg_base, ltcg_brackets)
    ltcg_tax = max(0.0, ltcg_tax)

    federal_income_tax_before_credits = income_tax + ltcg_tax

    # --- Child Tax Credit ---
    qualifying_children = int(inputs.get("qualifying_children", 0))
    ctc_per_child = inputs.get("child_tax_credit") or CHILD_TAX_CREDIT.get(year, CHILD_TAX_CREDIT[2025])
    raw_ctc = qualifying_children * ctc_per_child
    # Phase out: $50 per $1,000 (or fraction) over threshold
    ctc_phase_out_start = inputs.get("ctc_phase_out_start") or CHILD_TAX_CREDIT_PHASE_OUT_START_MFJ
    excess = max(0.0, federal_agi - ctc_phase_out_start)
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
        reduction_units = min(28, int((federal_agi - CDCC_PHASE_DOWN_START) / CDCC_PHASE_DOWN_STEP))
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
    filing_status = inputs.get("filing_status", "MFJ")
    default_amt_threshold = (
        ADDITIONAL_MEDICARE_THRESHOLD_MFJ if filing_status == "MFJ"
        else ADDITIONAL_MEDICARE_THRESHOLD_SINGLE
    )
    amt_threshold = inputs.get("additional_medicare_threshold") or default_amt_threshold
    amt_rate = inputs.get("additional_medicare_rate") or ADDITIONAL_MEDICARE_RATE
    amt_base = max(0.0, total_wages_and_se - amt_threshold)
    additional_medicare_tax = round(amt_base * amt_rate, 2)

    # --- Net Investment Income Tax ---
    # NII includes capital gains, qualified dividends, interest, and all dividends
    nii = ltcg + max(0.0, stcg) + interest_income + ordinary_dividends
    niit_rate = inputs.get("niit_rate") or NIIT_RATE
    niit_threshold = inputs.get("niit_threshold") or NIIT_THRESHOLD_MFJ
    niit_base = min(nii, max(0.0, federal_agi - niit_threshold))
    niit = round(max(0.0, niit_base) * niit_rate, 2)

    federal_total_tax = round(
        tax_after_credits + federal_se_tax + additional_medicare_tax + niit, 2
    )

    # --- Excess Social Security withholding ---
    # Each person's SS withholding is capped independently at ss_base * 6.2%.
    # Any excess is refundable (Schedule 3, Line 11) and treated as a payment.
    max_ss_per_person = ss_base * SS_EMPLOYEE_RATE
    ss_withheld_p1 = float(inputs.get("ss_withheld_p1", 0))
    ss_withheld_p2 = float(inputs.get("ss_withheld_p2", 0))
    excess_ss = round(
        max(0.0, ss_withheld_p1 - max_ss_per_person)
        + max(0.0, ss_withheld_p2 - max_ss_per_person),
        2,
    )

    # --- Marginal rate ---
    marginal_rate = _marginal_rate(ordinary_taxable, brackets)

    return {
        "federal_agi": round(federal_agi, 2),
        "federal_taxable_income": round(federal_taxable_income, 2),
        "deduction_type": deduction_type,
        "deduction_amount": round(deduction, 2),
        "standard_deduction": round(std_deduction, 2),
        "itemized_total": round(itemized, 2),
        "salt_total": round(salt_total, 2),
        "salt_cap_applied": round(salt_cap_base, 2),
        "medical_deduction": round(medical, 2),
        "charitable_nonitemizer_deduction": round(charitable_nonitemizer, 2),
        "federal_income_tax_before_credits": round(federal_income_tax_before_credits, 2),
        "child_tax_credit": ctc,
        "child_care_credit": child_care_credit,
        "federal_income_tax": round(tax_after_credits, 2),
        "qbi_deduction": qbi_deduction,
        "se_deduction": se["se_deduction"],
        "se_health_insurance": round(se_health_ins, 2),
        "solo_401k_deduction": round(solo_401k, 2),
        "federal_se_tax": federal_se_tax,
        "additional_medicare_tax": additional_medicare_tax,
        "niit": niit,
        "federal_total_tax": federal_total_tax,
        "effective_federal_rate": round(tax_after_credits / federal_agi, 4) if federal_agi else 0,
        "marginal_federal_rate": marginal_rate,
        "excess_ss": excess_ss,
    }
