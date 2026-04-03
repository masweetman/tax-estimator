"""Tax constants for 2025 (and prior years where needed).

All dollar amounts are plain ints/floats.  Percentages are 0–1 floats.
"""

# ---------------------------------------------------------------------------
# Federal – Standard Deductions (MFJ)
# ---------------------------------------------------------------------------
FEDERAL_STANDARD_DEDUCTION_MFJ = {
    2023: 27_700,
    2024: 29_200,
    2025: 30_000,
    2026: 31_000,  # placeholder; update when IRS publishes
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

# 2024 – slightly different thresholds
FEDERAL_BRACKETS_MFJ[2024] = [
    (0.10,  23_200),
    (0.12,  94_300),
    (0.22, 201_050),
    (0.24, 383_900),
    (0.32, 487_450),
    (0.35, 731_200),
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

# ---------------------------------------------------------------------------
# Social Security wage base
# ---------------------------------------------------------------------------
SS_WAGE_BASE = {
    2023: 160_200,
    2024: 168_600,
    2025: 176_100,
    2026: 176_100,  # placeholder
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
# Child Tax Credit
# ---------------------------------------------------------------------------
CHILD_TAX_CREDIT = 2_000
CHILD_TAX_CREDIT_PHASE_OUT_START_MFJ = 400_000
CHILD_TAX_CREDIT_PHASE_OUT_PER_1K = 50  # reduces by $50 per $1k over threshold

# Child & Dependent Care Credit
CDCC_MAX_EXPENSES_1_CHILD = 3_000
CDCC_MAX_EXPENSES_2_PLUS = 6_000
CDCC_MIN_RATE = 0.20
CDCC_MAX_RATE = 0.35
CDCC_PHASE_DOWN_START = 15_000   # AGI above which rate phases from 35% down to 20%

# ---------------------------------------------------------------------------
# SALT cap
# ---------------------------------------------------------------------------
SALT_CAP = 10_000

# ---------------------------------------------------------------------------
# IRS Mileage Rate
# ---------------------------------------------------------------------------
IRS_MILEAGE_RATE = 0.70   # 2025

# ---------------------------------------------------------------------------
# California – Standard Deductions (MFJ)
# ---------------------------------------------------------------------------
CA_STANDARD_DEDUCTION_MFJ = {
    2023: 10_726,
    2024: 11_080,
    2025: 11_392,
    2026: 11_392,  # placeholder
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

# CA 1% Mental Health Services surtax on income > $1M
CA_MENTAL_HEALTH_SURTAX_RATE = 0.01
CA_MENTAL_HEALTH_SURTAX_THRESHOLD = 1_000_000

# CA SDI – note: deductible on federal Schedule A but NOT on CA return
CA_SDI_RATE = 0.009  # 2025 (no wage cap since 2024)

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
