"""Tax constants for 2025–2026 (and prior years where needed).

All dollar amounts are plain ints/floats.  Percentages are 0–1 floats.
"""

# ---------------------------------------------------------------------------
# Federal – Standard Deductions (MFJ)
# ---------------------------------------------------------------------------
FEDERAL_STANDARD_DEDUCTION_MFJ = {
    2023: 27_700,
    2024: 29_200,
    2025: 30_000,
    2026: 32_200,  # OBBBA
}

# ---------------------------------------------------------------------------
# Federal – Income Tax Brackets (MFJ) {year: [(rate, upper_bound), ...]}
#   upper_bound = None means "no limit"
# ---------------------------------------------------------------------------
FEDERAL_BRACKETS_MFJ = {
    2025: [
        (0.10,  23_850),
        (0.12,  96_950),
        (0.22, 206_700),
        (0.24, 394_600),
        (0.32, 501_050),
        (0.35, 751_600),
        (0.37,      None),
    ],
}

FEDERAL_BRACKETS_MFJ[2024] = [
    (0.10,  23_200),
    (0.12,  94_300),
    (0.22, 201_050),
    (0.24, 383_900),
    (0.32, 487_450),
    (0.35, 731_200),
    (0.37,      None),
]

# 2026 – OBBBA inflation-adjusted thresholds
FEDERAL_BRACKETS_MFJ[2026] = [
    (0.10,  24_800),
    (0.12, 100_800),
    (0.22, 211_400),
    (0.24, 403_550),
    (0.32, 512_450),
    (0.35, 768_700),
    (0.37,      None),
]

# ---------------------------------------------------------------------------
# Federal – Long-term Capital Gains Brackets (MFJ)
# ---------------------------------------------------------------------------
LTCG_BRACKETS_MFJ = {
    2025: [
        (0.00,  96_700),
        (0.15, 583_750),
        (0.20,      None),
    ],
}
LTCG_BRACKETS_MFJ[2024] = [
    (0.00,  94_050),
    (0.15, 583_750),
    (0.20,      None),
]
LTCG_BRACKETS_MFJ[2026] = [
    (0.00,  98_900),
    (0.15, 613_700),
    (0.20,      None),
]

# ---------------------------------------------------------------------------
# Social Security wage base
# ---------------------------------------------------------------------------
SS_WAGE_BASE = {
    2023: 160_200,
    2024: 168_600,
    2025: 176_100,
    2026: 184_500,  # OBBBA
}

SS_EMPLOYEE_RATE = 0.062
MEDICARE_EMPLOYEE_RATE = 0.0145
ADDITIONAL_MEDICARE_RATE = 0.009
ADDITIONAL_MEDICARE_THRESHOLD_MFJ = 250_000

# SE tax rates (before half-SE deduction)
SE_SELF_EMPLOYMENT_RATE = 0.153   # 12.4% SS + 2.9% Medicare on 92.35% of net
SE_NET_EARNINGS_FACTOR = 0.9235

# Net Investment Income Tax
NIIT_RATE = 0.038
NIIT_THRESHOLD_MFJ = 250_000

# ---------------------------------------------------------------------------
# Child Tax Credit  {year: amount_per_child}
# ---------------------------------------------------------------------------
CHILD_TAX_CREDIT = {
    2023: 2_000,
    2024: 2_000,
    2025: 2_000,
    2026: 2_200,  # OBBBA increase
}
CHILD_TAX_CREDIT_PHASE_OUT_START_MFJ = 400_000
CHILD_TAX_CREDIT_PHASE_OUT_PER_1K = 50  # reduces by $50 per $1k over threshold

# Child & Dependent Care Credit
CDCC_MAX_EXPENSES_1_CHILD = 3_000
CDCC_MAX_EXPENSES_2_PLUS = 6_000
CDCC_MIN_RATE = 0.20
CDCC_MAX_RATE = 0.35
CDCC_PHASE_DOWN_START = 15_000   # AGI above which rate phases from 35% down to 20%

# ---------------------------------------------------------------------------
# SALT cap  {year: amount}  (OBBBA raised 2026 cap to $40,400 with phase-down)
# ---------------------------------------------------------------------------
SALT_CAP = {2023: 10_000, 2024: 10_000, 2025: 10_000, 2026: 40_400}
# Phase-down: SALT cap reduces $1-for-$1 above threshold, floor = $10,000
SALT_PHASE_DOWN_START = {2026: 505_000}  # MAGI above this triggers phase-down
SALT_FLOOR = 10_000

# Non-itemizer charitable deduction (above-the-line, 2026 OBBBA)
CHARITABLE_NONITEMIZER_CAP_MFJ = {2026: 2_000}

# ---------------------------------------------------------------------------
# Qualified Business Income (QBI) Deduction  §199A
# ---------------------------------------------------------------------------
QBI_RATE = 0.20
# Taxable income threshold above which the W-2 wage limit kicks in.
# For sole proprietors/SMLLCs (no employees) the W-2 wage limitation zeroes
# out QBI entirely once income exceeds threshold + QBI_PHASE_IN_RANGE.
QBI_THRESHOLD_MFJ = {
    2023: 364_200,
    2024: 383_900,
    2025: 394_600,
    2026: 404_100,
}
QBI_PHASE_IN_RANGE = 100_000   # phase-out window width

# ---------------------------------------------------------------------------
# IRS Mileage Rate  {year: rate_per_mile}
# ---------------------------------------------------------------------------
IRS_MILEAGE_RATE = {2025: 0.70, 2026: 0.725}

# ---------------------------------------------------------------------------
# California – Standard Deductions (MFJ)
# ---------------------------------------------------------------------------
CA_STANDARD_DEDUCTION_MFJ = {
    2023: 10_726,
    2024: 11_080,
    2025: 11_392,
    2026: 11_720,  # confirmed 2026 (OBBBA)
}

# ---------------------------------------------------------------------------
# California – Income Tax Brackets (MFJ) [(rate, upper_bound), ...]
# ---------------------------------------------------------------------------
CA_BRACKETS_MFJ = {
    2025: [
        (0.01,   20_824),
        (0.02,   49_368),
        (0.04,   77_918),
        (0.06,  108_162),
        (0.08,  136_700),
        (0.093, 698_274),
        (0.103, 837_922),
        (0.113, 1_000_000),
        (0.123,       None),
    ],
}
CA_BRACKETS_MFJ[2024] = [
    (0.01,   20_198),
    (0.02,   47_884),
    (0.04,   75_576),
    (0.06,  104_910),
    (0.08,  132_590),
    (0.093, 677_278),
    (0.103, 812_728),
    (0.113, 1_000_000),
    (0.123,       None),
]
CA_BRACKETS_MFJ[2026] = [
    (0.01,    22_756),
    (0.02,    53_946),
    (0.04,    85_142),
    (0.06,   118_191),
    (0.08,   149_375),
    (0.093,  763_018),
    (0.103,  915_614),
    (0.113, 1_526_025),
    (0.123,       None),
]

# CA 1% Mental Health Services surtax on income > $1M
CA_MENTAL_HEALTH_SURTAX_RATE = 0.01
CA_MENTAL_HEALTH_SURTAX_THRESHOLD = 1_000_000

# CA SDI – deductible on federal Schedule A but NOT on CA return
# {year: rate}  (no wage cap)
CA_SDI_RATE = {2025: 0.011, 2026: 0.013}

# California credits
CA_PERSONAL_EXEMPTION_MFJ = 314     # Nonrefundable personal exemption credit (MFJ)
CA_DEPENDENT_CREDIT = 488           # Per-dependent credit
CA_YOUNG_CHILD_TAX_CREDIT = 1_117   # Per child under age 6

# California does NOT have:
# - SALT cap deduction limit (CA has no SALT cap for CA return)
# - NIIT or additional Medicare (CA taxes)
# CA has no separate LTCG rate (taxed as ordinary income)

# ---------------------------------------------------------------------------
# Safe harbor thresholds
# ---------------------------------------------------------------------------
SAFE_HARBOR_HIGH_INCOME_THRESHOLD = 150_000  # prior-year AGI above this → 110%
SAFE_HARBOR_LOW_MULTIPLIER = 1.00
SAFE_HARBOR_HIGH_MULTIPLIER = 1.10
CA_SAFE_HARBOR_CURRENT_YEAR_PCT = 0.90  # 90% of current-year CA tax

# ---------------------------------------------------------------------------
# Solo 401(k) Contribution Limits
# ---------------------------------------------------------------------------
# Employee elective deferral limit (no catch-up per instructions)
SOLO_401K_EMPLOYEE_LIMIT = {2024: 23_000, 2025: 23_500, 2026: 24_000}
# Section 415(c) combined (employee + employer) annual limit
SOLO_401K_TOTAL_LIMIT = {2024: 69_000, 2025: 70_000, 2026: 71_000}
