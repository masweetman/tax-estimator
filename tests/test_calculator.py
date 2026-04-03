"""Tests for the tax calculator — written before implementation (TDD).

The calculator operates on plain dicts/numbers, NOT on ORM models, so these
tests have NO database dependency and run very fast.

Scenario: MFJ, 2 dependent children, California resident.
"""
import pytest
from decimal import Decimal


# ---------------------------------------------------------------------------
# Helpers – build minimal input dicts
# ---------------------------------------------------------------------------

def make_inputs(**overrides):
    """Return a base-case income/deduction input dict."""
    base = {
        # W-2 wages (both spouses combined)
        "w2_wages": 200_000.00,
        # W-2 withholdings
        "federal_income_withheld": 25_000.00,
        "ss_withheld": 9_932.40,   # 160,200 × 6.2%
        "medicare_withheld": 2_900.00,
        "ca_income_withheld": 10_000.00,
        "ca_sdi_withheld": 2_000.00,
        # SE (net profit after expenses, for person1, person2 separately)
        "se_net_income_p1": 0.00,
        "se_net_income_p2": 0.00,
        # Capital gains (long-term and short-term)
        "long_term_capital_gains": 0.00,
        "short_term_capital_gains": 0.00,
        # Deductions
        "mortgage_interest": 20_000.00,
        "charitable": 5_000.00,
        "salt_taxes_paid": 10_000.00,   # will be capped at 10k
        "medical_expenses": 0.00,
        # Retirement pre-tax
        "pretax_401k_total": 23_000.00,
        "traditional_ira_total": 7_000.00,
        "sep_ira_total": 0.00,
        # HSA
        "hsa_total": 8_300.00,
        # SE health insurance
        "se_health_insurance": 0.00,
        # Child/dependent care expenses
        "child_care_expenses": 6_000.00,
        # Number of qualifying children for CTC
        "qualifying_children": 2,
        # Estimated + withholding payments
        "federal_estimated_paid": 0.00,
        "ca_estimated_paid": 0.00,
        # Prior-year tax (for safe harbor)
        "prior_year_federal_tax": 30_000.00,
        "prior_year_ca_tax": 8_000.00,
        "prior_year_agi": 190_000.00,
        # Filing details
        "tax_year": 2025,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Import path (will be created in app/calculator/)
# ---------------------------------------------------------------------------

def _calc(inputs=None, **overrides):
    from app.calculator.engine import calculate
    if inputs is None:
        inputs = make_inputs(**overrides)
    return calculate(inputs)


# ===========================================================================
# Section 1: Constants
# ===========================================================================

class TestConstants:
    def test_standard_deduction_mfj(self):
        from app.calculator.constants import FEDERAL_STANDARD_DEDUCTION_MFJ
        assert FEDERAL_STANDARD_DEDUCTION_MFJ[2025] == 30_000

    def test_ss_wage_base(self):
        from app.calculator.constants import SS_WAGE_BASE
        assert SS_WAGE_BASE[2025] == 176_100

    def test_child_tax_credit_amount(self):
        from app.calculator.constants import CHILD_TAX_CREDIT
        assert CHILD_TAX_CREDIT == 2_000

    def test_irs_mileage_rate(self):
        from app.calculator.constants import IRS_MILEAGE_RATE
        assert IRS_MILEAGE_RATE == 0.70

    def test_salt_cap(self):
        from app.calculator.constants import SALT_CAP
        assert SALT_CAP == 10_000

    def test_ca_standard_deduction_mfj(self):
        from app.calculator.constants import CA_STANDARD_DEDUCTION_MFJ
        assert CA_STANDARD_DEDUCTION_MFJ[2025] > 0

    def test_ca_mental_health_surtax_threshold(self):
        from app.calculator.constants import CA_MENTAL_HEALTH_SURTAX_THRESHOLD
        assert CA_MENTAL_HEALTH_SURTAX_THRESHOLD == 1_000_000


# ===========================================================================
# Section 2: Federal calculator
# ===========================================================================

class TestFederalTax:
    def test_returns_dict_with_expected_keys(self):
        result = _calc()
        for key in (
            "federal_agi", "federal_taxable_income",
            "federal_income_tax", "federal_total_tax",
            "federal_se_tax",
        ):
            assert key in result, f"Missing key: {key}"

    def test_agi_reduces_by_pretax_401k(self):
        result_base = _calc(w2_wages=100_000, pretax_401k_total=0)
        result_401k = _calc(w2_wages=100_000, pretax_401k_total=10_000)
        # AGI should be lower when 401k contribution is made
        # (pre-tax 401k reduces Box 1 wages, hence AGI)
        assert result_401k["federal_agi"] < result_base["federal_agi"]

    def test_standard_vs_itemized_uses_higher(self):
        """With large mortgage interest + charitable, itemized > standard."""
        result = _calc(
            w2_wages=300_000,
            mortgage_interest=28_000,
            charitable=5_000,
            salt_taxes_paid=10_000,
        )
        # Itemized = 28000 + 5000 + 10000 = 43000 > standard deduction 30000
        assert result.get("deduction_type") == "itemized"

    def test_standard_deduction_used_when_itemized_lower(self):
        """With minimal deductions, standard deduction is used."""
        result = _calc(
            w2_wages=100_000,
            mortgage_interest=0,
            charitable=0,
            salt_taxes_paid=5_000,
        )
        assert result.get("deduction_type") == "standard"

    def test_salt_capped_at_10k(self):
        """SALT deduction is capped at $10,000 for itemizers."""
        result_low = _calc(
            mortgage_interest=40_000, charitable=0,
            salt_taxes_paid=8_000,
        )
        result_high = _calc(
            mortgage_interest=40_000, charitable=0,
            salt_taxes_paid=25_000,
        )
        # Both are itemizing; SALT is capped at 10k so taxable income should be same
        assert result_low["federal_taxable_income"] == result_high["federal_taxable_income"]

    def test_child_tax_credit_2_children(self):
        result = _calc(qualifying_children=2, w2_wages=100_000)
        # 2 children × $2,000 = $4,000 credit
        assert result.get("child_tax_credit") == 4_000

    def test_child_tax_credit_phases_out_at_high_income(self):
        """CTC phases out above $400k AGI for MFJ."""
        result = _calc(qualifying_children=2, w2_wages=500_000,
                       pretax_401k_total=0, traditional_ira_total=0,
                       hsa_total=0, mortgage_interest=0, charitable=0)
        assert result.get("child_tax_credit") < 4_000

    def test_child_dependent_care_credit_applied(self):
        result = _calc(child_care_expenses=6_000, qualifying_children=2)
        # Should have a positive care credit
        assert result.get("child_care_credit", 0) > 0

    def test_se_tax_calculated_on_net_profit(self):
        result = _calc(se_net_income_p1=50_000)
        # SE tax ≈ 50k × 0.9235 × 15.3% ≈ 7,065
        assert result["federal_se_tax"] > 5_000

    def test_se_deduction_reduces_agi(self):
        """Half of SE tax is deductible above-the-line."""
        result_no_se = _calc(se_net_income_p1=0)
        result_with_se = _calc(se_net_income_p1=50_000)
        # Net effect: SE income raises AGI, but half-SE deduction partially offsets
        # Most importantly, the se_deduction field should be > 0
        assert result_with_se.get("se_deduction", 0) > 0

    def test_federal_tax_bracket_example(self):
        """Rough sanity-check: $200k W2, std deduction → tax should be in plausible range."""
        result = _calc(
            w2_wages=200_000,
            pretax_401k_total=20_000,
            traditional_ira_total=0,
            hsa_total=0,
            mortgage_interest=0,
            charitable=0,
            salt_taxes_paid=0,
        )
        # Taxable income ≈ 200000 - 20000 - 30000 = 150000
        # MFJ tax on 150k: ~$22,000 +/- 20%
        assert 15_000 < result["federal_income_tax"] < 35_000

    def test_additional_medicare_tax_above_250k(self):
        """Additional 0.9% Medicare tax on wages above $250k (MFJ)."""
        result = _calc(w2_wages=300_000, se_net_income_p1=0)
        # Total wages = 300k; 50k × 0.9% = $450 additional Medicare
        assert result.get("additional_medicare_tax", 0) > 0

    def test_net_investment_income_tax(self):
        """3.8% NIIT on lower of NII or (MAGI - 250k)."""
        result = _calc(w2_wages=300_000, long_term_capital_gains=50_000)
        # MAGI > 250k, NII = 50k; NIIT = min(50k, MAGI-250k) × 3.8%
        assert result.get("niit", 0) > 0


# ===========================================================================
# Section 3: California calculator
# ===========================================================================

class TestCaliforniaTax:
    def test_returns_dict_with_ca_keys(self):
        result = _calc()
        for key in ("ca_agi", "ca_taxable_income", "ca_income_tax"):
            assert key in result, f"Missing key: {key}"

    def test_ca_standard_vs_itemized(self):
        """CA itemized should be used when it exceeds CA standard deduction."""
        result = _calc(mortgage_interest=40_000, charitable=5_000)
        assert result.get("ca_deduction_type") in ("standard", "itemized")

    def test_ca_sdi_not_a_deduction_for_ca(self):
        """SDI is deductible only on federal Schedule A, not on CA return."""
        # Just ensuring no crash and the field exists
        result = _calc()
        assert "ca_income_tax" in result

    def test_ca_mental_health_surtax(self):
        """1% surtax on CA taxable income above $1M."""
        result = _calc(w2_wages=1_200_000,
                       pretax_401k_total=0, traditional_ira_total=0, hsa_total=0,
                       mortgage_interest=0, charitable=0)
        assert result.get("ca_mental_health_surtax", 0) > 0

    def test_ca_no_mental_health_surtax_below_1m(self):
        result = _calc()  # default w2 = 200k
        assert result.get("ca_mental_health_surtax", 0) == 0


# ===========================================================================
# Section 4: Safe harbor
# ===========================================================================

class TestSafeHarbor:
    def test_safe_harbor_federal_100pct(self):
        """If prior-year AGI ≤ 150k, safe harbor = 100% of prior-year tax."""
        result = _calc(prior_year_federal_tax=25_000, prior_year_agi=100_000)
        assert result["safe_harbor_federal"] == 25_000.0

    def test_safe_harbor_federal_110pct_above_150k(self):
        """If prior-year AGI > 150k, safe harbor = 110% of prior-year tax."""
        result = _calc(prior_year_federal_tax=20_000, prior_year_agi=200_000)
        assert result["safe_harbor_federal"] == pytest.approx(22_000.0)

    def test_safe_harbor_ca_100pct_or_90pct_current(self):
        """CA safe harbor: 100% of prior-year CA tax OR 90% of current CA tax."""
        result = _calc(prior_year_ca_tax=5_000)
        assert result.get("safe_harbor_ca") is not None

    def test_quarterly_federal_recommendation(self):
        """Each quarterly payment = (safe_harbor - withholding_ytd) / remaining_quarters."""
        result = _calc(
            federal_income_withheld=5_000,
            federal_estimated_paid=0,
        )
        assert "quarterly_federal_recommended" in result

    def test_quarterly_federal_no_payment_needed_when_overpaid(self):
        """If already covered by withholding, no quarterly payment needed."""
        result = _calc(
            prior_year_federal_tax=10_000,
            prior_year_agi=100_000,  # 100% safe harbor = 10k
            federal_income_withheld=15_000,  # already exceeds
            federal_estimated_paid=0,
        )
        # quarterly recommended should be 0 (can't be negative)
        assert result["quarterly_federal_recommended"] == 0


# ===========================================================================
# Section 5: Summary / totals
# ===========================================================================

class TestSummary:
    def test_federal_balance_due(self):
        """Balance due = total tax − (withholding + estimated)."""
        result = _calc(
            federal_income_withheld=10_000,
            federal_estimated_paid=5_000,
        )
        expected = result["federal_total_tax"] - 10_000 - 5_000
        assert result["federal_balance_due"] == pytest.approx(expected)

    def test_ca_balance_due(self):
        result = _calc(
            ca_income_withheld=5_000,
            ca_estimated_paid=2_000,
        )
        expected = result["ca_income_tax"] - 5_000 - 2_000
        assert result["ca_balance_due"] == pytest.approx(expected)

    def test_effective_federal_rate(self):
        result = _calc()
        rate = result.get("effective_federal_rate", 0)
        assert 0 < rate < 1

    def test_marginal_federal_rate(self):
        result = _calc(w2_wages=200_000)
        brackets_2025 = [0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37]
        assert result.get("marginal_federal_rate") in brackets_2025
