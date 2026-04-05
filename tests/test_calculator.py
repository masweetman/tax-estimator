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
        assert CHILD_TAX_CREDIT[2025] == 2_000
        assert CHILD_TAX_CREDIT[2026] == 2_200

    def test_irs_mileage_rate(self):
        from app.calculator.constants import IRS_MILEAGE_RATE
        assert IRS_MILEAGE_RATE[2025] == 0.70
        assert IRS_MILEAGE_RATE[2026] == 0.725

    def test_salt_cap(self):
        from app.calculator.constants import SALT_CAP
        assert SALT_CAP[2025] == 10_000
        assert SALT_CAP[2026] == 40_400

    def test_ca_standard_deduction_mfj(self):
        from app.calculator.constants import CA_STANDARD_DEDUCTION_MFJ
        assert CA_STANDARD_DEDUCTION_MFJ[2025] == 11_392

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
        # w2_wages is Box-1 wages: pre-tax 401k is already excluded before Box-1
        # is computed, so a higher 401k contribution means lower Box-1 wages → lower AGI.
        result_no_401k = _calc(w2_wages=100_000, pretax_401k_total=0)
        result_with_401k = _calc(w2_wages=90_000, pretax_401k_total=10_000)
        # Box-1 wages differ by the 401k contribution → AGI is lower
        assert result_with_401k["federal_agi"] < result_no_401k["federal_agi"]

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
        # w2_wages=200_000 is Box-1 (401k already excluded). Taxable income ≈ 200000 - 30000 = 170000
        # MFJ tax on 170k: ~$27,000 +/- 25%
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
        """CA itemized when mortgage alone exceeds the tiny CA std deduction ($11,392).

        Importantly, the same mortgage is below the federal std deduction ($30,000),
        so federal uses standard while CA uses itemized.
        """
        result = _calc(
            mortgage_interest=15_000,
            charitable=0,
            salt_taxes_paid=0,
            ca_sdi_withheld=0,
        )
        assert result.get("ca_deduction_type") == "itemized"
        assert result.get("deduction_type") == "standard"

    def test_ca_sdi_not_a_deduction_for_ca(self):
        """SDI is deductible on federal Schedule A but NOT on CA return.

        Adding SDI withholding should not reduce CA income tax.  With a large
        enough mortgage to force itemizing on both federal and CA, the CA tax
        must be identical whether SDI is zero or non-zero.
        """
        base = dict(
            w2_wages=300_000,
            mortgage_interest=35_000,  # > federal AND CA std deductions
            charitable=0,
            salt_taxes_paid=0,
        )
        result_no_sdi = _calc(ca_sdi_withheld=0, **base)
        result_with_sdi = _calc(ca_sdi_withheld=6_000, **base)
        # CA return does not allow SDI deduction — tax must be identical
        assert result_no_sdi["ca_income_tax"] == result_with_sdi["ca_income_tax"]
        # Federal: SDI counts toward SALT — federal AGI must be same (AGI is before
        # itemized deductions), but SDI shifts which bracket itemized is in
        assert result_no_sdi["federal_agi"] == result_with_sdi["federal_agi"]

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
        """Prior-year AGI ≤ 150k → 100% multiplier; prior-year wins when it's smaller."""
        # prior_year_agi=100k → 100% × 10k = 10k < 90% of current-year tax → prior wins
        result = _calc(prior_year_federal_tax=10_000, prior_year_agi=100_000)
        assert result["safe_harbor_federal"] == pytest.approx(10_000.0)

    def test_safe_harbor_federal_110pct_above_150k(self):
        """Prior-year AGI > 150k → 110% multiplier; prior-year wins when it's smaller."""
        # 110% × 10k = 11k < 90% of current-year tax → prior wins
        result = _calc(prior_year_federal_tax=10_000, prior_year_agi=200_000)
        assert result["safe_harbor_federal"] == pytest.approx(11_000.0)

    def test_safe_harbor_federal_90pct_wins_when_smaller(self):
        """90% of current-year tax wins when prior-year basis is larger."""
        # 100% × 25k = 25k > 90% of ~17562 ≈ 15806 → 90% current wins
        result = _calc(prior_year_federal_tax=25_000, prior_year_agi=100_000)
        assert result["safe_harbor_federal"] == pytest.approx(result["federal_safe_harbor_90pct"])
        assert result["safe_harbor_federal"] < 25_000.0

    def test_safe_harbor_ca_100pct(self):
        """Prior-year AGI ≤ 150k → 100% CA multiplier; prior-year wins when it's smaller."""
        # Override prior_year_agi to 100k (default is 190k) and use low prior CA tax
        result = _calc(prior_year_ca_tax=4_500, prior_year_agi=100_000)
        assert result["safe_harbor_ca"] == pytest.approx(4_500.0)

    def test_safe_harbor_ca_110pct_high_income(self):
        """Prior-year AGI > 150k → 110% CA multiplier applied."""
        # 110% × 4k = 4400 < 90% of ~6710 ≈ 6039 → prior wins; verify multiplier
        result = _calc(prior_year_ca_tax=4_000, prior_year_agi=200_000)
        assert result["safe_harbor_ca"] == pytest.approx(4_400.0)
        assert result["ca_safe_harbor_prior"] == pytest.approx(4_400.0)

    def test_safe_harbor_ca_millionaire_exception(self):
        """CA millionaire exception: prior AGI >= $1M forces 90% of current year only."""
        result = _calc(
            prior_year_agi=1_500_000,
            prior_year_ca_tax=50_000,  # large prior; should be ignored
        )
        assert result["ca_millionaire_exception"] is True
        assert result["safe_harbor_ca"] == pytest.approx(result["ca_safe_harbor_90pct"])
        assert result["ca_safe_harbor_prior"] is None

    def test_safe_harbor_ca_millionaire_exception_current_year(self):
        """CA millionaire exception triggers when current-year CA AGI >= $1M."""
        # Push CA AGI over $1M by adding large SE income
        result = _calc(
            se_net_income_p1=2_000_000,
            prior_year_ca_tax=50_000,
            prior_year_agi=100_000,
        )
        assert result["ca_millionaire_exception"] is True
        assert result["safe_harbor_ca"] == pytest.approx(result["ca_safe_harbor_90pct"])

    def test_ca_quarterly_weighted_schedule(self):
        """CA uses FTB 30/40/0/30 schedule, not equal fourths."""
        result = _calc(
            prior_year_ca_tax=4_000,
            prior_year_agi=100_000,
            ca_income_withheld=0,
        )
        sh = result["safe_harbor_ca"]
        assert result["ca_q1_payment"] == pytest.approx(sh * 0.30, abs=0.02)
        assert result["ca_q2_payment"] == pytest.approx(sh * 0.40, abs=0.02)
        assert result["ca_q3_payment"] == 0.0
        assert result["ca_q4_payment"] == pytest.approx(sh * 0.30, abs=0.02)

    def test_ca_quarterly_q3_is_always_zero(self):
        """CA Q3 installment is always $0 regardless of safe harbor amount."""
        result = _calc(prior_year_ca_tax=20_000, ca_income_withheld=0)
        assert result["ca_q3_payment"] == 0.0

    def test_ca_quarterly_net_of_withholding(self):
        """Each CA installment is reduced by 25% of annual CA withholding."""
        # prior=5000 < 90% of current CA tax → safe_harbor_ca=5000; ca_paid_ytd=2000 < 5000
        result = _calc(
            prior_year_ca_tax=5_000,
            prior_year_agi=100_000,
            ca_income_withheld=2_000,
        )
        sh = result["safe_harbor_ca"]
        wh_per_q = 2_000 * 0.25
        assert result["ca_q1_payment"] == pytest.approx(max(0, sh * 0.30 - wh_per_q), abs=0.02)
        assert result["ca_q2_payment"] == pytest.approx(max(0, sh * 0.40 - wh_per_q), abs=0.02)

    def test_quarterly_federal_recommendation(self):
        """Each quarterly payment = (safe_harbor - withholding_ytd) / 4."""
        result = _calc(
            federal_income_withheld=5_000,
            federal_estimated_paid=0,
        )
        assert "quarterly_federal_recommended" in result

    def test_quarterly_federal_no_payment_needed_when_overpaid(self):
        """If already covered by withholding, no quarterly payment needed."""
        result = _calc(
            prior_year_federal_tax=10_000,
            prior_year_agi=100_000,  # 100% safe harbor = 10k; 90% current = ~15806
            federal_income_withheld=15_000,  # already exceeds safe harbor
            federal_estimated_paid=0,
        )
        # quarterly recommended should be 0 (can't be negative)
        assert result["quarterly_federal_recommended"] == 0

    def test_ca_quarterly_zero_when_safe_harbor_covered(self):
        """All CA quarterly amounts are $0 when ca_paid_ytd >= safe_harbor_ca."""
        result = _calc(
            prior_year_ca_tax=4_000,
            prior_year_agi=100_000,
            ca_income_withheld=10_000,  # withholding alone exceeds any safe harbor
            ca_estimated_paid=0,
        )
        assert result["ca_q1_payment"] == 0.0
        assert result["ca_q2_payment"] == 0.0
        assert result["ca_q3_payment"] == 0.0
        assert result["ca_q4_payment"] == 0.0
        assert result["quarterly_ca_recommended"] == 0.0


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
        """effective_federal_rate = federal_income_tax / federal_agi.

        Verify the formula holds, and that the rate is in a plausible range for
        a $200 k single-income W-2 household after standard deduction.
        """
        result = _calc(
            w2_wages=200_000,
            pretax_401k_total=0,
            traditional_ira_total=0,
            hsa_total=0,
            mortgage_interest=0,
            charitable=0,
            salt_taxes_paid=0,
            ca_sdi_withheld=0,
            qualifying_children=0,
            child_care_expenses=0,
            se_net_income_p1=0,
            se_net_income_p2=0,
            long_term_capital_gains=0,
            short_term_capital_gains=0,
        )
        rate = result["effective_federal_rate"]
        # Rough sanity: 200k W-2, $30k std deduction → ~10–20% effective rate
        assert 0.10 <= rate <= 0.20
        # Formula check: effective_rate = income_tax / AGI
        assert rate == pytest.approx(
            result["federal_income_tax"] / result["federal_agi"], abs=0.0001
        )

    def test_marginal_federal_rate(self):
        result = _calc(w2_wages=200_000)
        brackets_2025 = [0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37]
        assert result.get("marginal_federal_rate") in brackets_2025


class TestInterestAndDividends:
    """Tests for interest income, ordinary dividends, and qualified dividends."""

    def test_interest_income_raises_agi(self):
        base = _calc(w2_wages=100_000)
        with_interest = _calc(w2_wages=100_000, interest_income=5_000)
        assert with_interest["federal_agi"] == pytest.approx(
            base["federal_agi"] + 5_000, abs=1
        )

    def test_ordinary_dividends_non_qualified_are_ordinary_income(self):
        """Non-qualified portion raises ordinary taxable income."""
        base = _calc(w2_wages=100_000)
        with_divs = _calc(
            w2_wages=100_000,
            ordinary_dividends=10_000,
            qualified_dividends=0,  # all non-qualified
        )
        assert with_divs["federal_agi"] == pytest.approx(
            base["federal_agi"] + 10_000, abs=1
        )

    def test_qualified_dividends_taxed_at_ltcg_rate(self):
        """Fully qualified dividends should produce lower tax than the same
        amount as ordinary (non-qualified) dividends."""
        ordinary_only = _calc(
            w2_wages=100_000,
            ordinary_dividends=20_000,
            qualified_dividends=0,
        )
        fully_qualified = _calc(
            w2_wages=100_000,
            ordinary_dividends=20_000,
            qualified_dividends=20_000,
        )
        # Both should have the same AGI (all dividends included in gross income)
        assert ordinary_only["federal_agi"] == pytest.approx(
            fully_qualified["federal_agi"], abs=1
        )
        # Qualified version should produce less or equal income tax before credits
        assert fully_qualified["federal_income_tax_before_credits"] <= (
            ordinary_only["federal_income_tax_before_credits"] + 1
        )

    def test_niit_includes_interest_and_dividends(self):
        """NIIT base should include interest and dividend income."""
        # High AGI to trigger NIIT; use 2025 NIIT threshold = $250k
        result = _calc(
            w2_wages=200_000,
            interest_income=10_000,
            ordinary_dividends=10_000,
            qualified_dividends=5_000,
            long_term_capital_gains=0,
            short_term_capital_gains=0,
            traditional_ira_total=0,
        )
        # AGI = 200k + 10k interest + 10k ordinary divs = 220k < 250k threshold
        # So NIIT should be 0 in this scenario
        assert result["niit"] == 0.0

        # Now push over the threshold
        high_income = _calc(
            w2_wages=230_000,
            interest_income=10_000,
            ordinary_dividends=10_000,
            qualified_dividends=5_000,
            long_term_capital_gains=0,
            short_term_capital_gains=0,
            traditional_ira_total=0,
        )
        # AGI = 230k + 20k = 250k = exactly at threshold, NIIT base = 0
        # Use 260k wages + no 401k to ensure AGI exceeds the $250k threshold:
        over_threshold = _calc(
            w2_wages=250_000,
            interest_income=5_000,
            ordinary_dividends=5_000,
            qualified_dividends=5_000,
            long_term_capital_gains=0,
            short_term_capital_gains=0,
            traditional_ira_total=0,
            pretax_401k_total=0,  # remove so AGI stays over threshold
        )
        assert over_threshold["niit"] > 0

    def test_taxable_state_refund_in_agi(self):
        base = _calc(w2_wages=100_000)
        with_refund = _calc(w2_wages=100_000, taxable_state_refund=3_000)
        assert with_refund["federal_agi"] == pytest.approx(
            base["federal_agi"] + 3_000, abs=1
        )

    def test_qualified_dividends_capped_at_ordinary(self):
        """Qualified dividends > ordinary dividends are capped at ordinary amount."""
        result = _calc(
            w2_wages=100_000,
            ordinary_dividends=5_000,
            qualified_dividends=10_000,  # exceeds ordinary — should be clamped
        )
        # AGI should only reflect 5k in dividends (ordinary), not 10k
        base = _calc(w2_wages=100_000)
        assert result["federal_agi"] == pytest.approx(base["federal_agi"] + 5_000, abs=1)


# ===========================================================================
# Section 7: Excess Social Security withholding
# ===========================================================================

class TestExcessSocialSecurity:
    """Tests for the excess SS calculation (Schedule 3, Line 11).

    Two-job households (or single high earners) may over-withhold SS when
    total wages > $176,100.  Each employer withholds independently, so the
    excess is refundable on the federal return.
    """

    _MAX_SS = 176_100 * 0.062  # $10,918.20 for 2025

    def test_no_excess_ss_when_within_wage_base(self):
        """Withholding exactly at the cap → zero excess."""
        result = _calc(ss_withheld_p1=self._MAX_SS, ss_withheld_p2=0)
        assert result.get("excess_ss", 0) == pytest.approx(0.0)

    def test_no_excess_ss_when_below_wage_base(self):
        """Withholding below the cap → zero excess."""
        result = _calc(ss_withheld_p1=5_000, ss_withheld_p2=0)
        assert result.get("excess_ss", 0) == pytest.approx(0.0)

    def test_excess_ss_single_person_over_cap(self):
        """One person withheld beyond max → excess = withheld - max_ss."""
        withheld = self._MAX_SS + 300.00
        result = _calc(ss_withheld_p1=withheld, ss_withheld_p2=0)
        assert result["excess_ss"] == pytest.approx(300.0, abs=0.01)

    def test_excess_ss_two_persons_accumulates(self):
        """Both persons over the cap → excess is the sum of both overages."""
        result = _calc(
            ss_withheld_p1=self._MAX_SS + 200.0,
            ss_withheld_p2=self._MAX_SS + 150.0,
        )
        assert result["excess_ss"] == pytest.approx(350.0, abs=0.01)

    def test_excess_ss_not_included_in_federal_total_tax(self):
        """Excess SS is a payment/credit, not part of the tax liability itself."""
        result_no_excess = _calc(ss_withheld_p1=0, ss_withheld_p2=0)
        result_with_excess = _calc(
            ss_withheld_p1=self._MAX_SS + 500.0,
            ss_withheld_p2=0,
        )
        # federal_total_tax should be identical regardless of SS withholding
        assert result_no_excess["federal_total_tax"] == pytest.approx(
            result_with_excess["federal_total_tax"], abs=0.01
        )


# ===========================================================================
# Section 8: California additions and subtractions
# ===========================================================================

class TestCAAdditionsAndSubtractions:
    """Tests for CA-specific adjustments to federal AGI."""

    def test_hsa_contributions_added_back_to_ca_agi(self):
        """Employee HSA deduction (federal above-the-line) is added back to CA AGI.

        CA does not recognise the HSA deduction, so the addback offsets the
        federal reduction: ca_agi = federal_agi + hsa_addback.
        """
        result = _calc(hsa_total=8_300)
        assert result["ca_additions_hsa_addback"] == pytest.approx(8_300, abs=1)
        assert result["ca_agi"] == pytest.approx(
            result["federal_agi"] + 8_300, abs=1
        )

    def test_employer_hsa_increases_ca_agi(self):
        """Employer HSA contributions (W-2 Box 12W) are excluded from federal
        gross income but taxable in CA (R&TC § 17215.4)."""
        base = _calc()
        with_employer_hsa = _calc(ca_employer_hsa_contributions=4_650)
        assert with_employer_hsa["ca_agi"] == pytest.approx(
            base["ca_agi"] + 4_650, abs=1
        )
        assert with_employer_hsa["ca_additions_employer_hsa"] == pytest.approx(4_650, abs=1)

    def test_hsa_earnings_increase_ca_agi(self):
        """HSA investment earnings are taxable in CA but not federally."""
        base = _calc()
        with_earnings = _calc(ca_hsa_earnings=375)
        assert with_earnings["ca_agi"] == pytest.approx(base["ca_agi"] + 375, abs=1)
        assert with_earnings["ca_additions_hsa_earnings"] == pytest.approx(375, abs=1)

    def test_employer_hsa_does_not_affect_federal_agi(self):
        """Employer HSA is a pre-tax W-2 exclusion — no impact on federal AGI."""
        base = _calc()
        with_employer_hsa = _calc(ca_employer_hsa_contributions=4_650)
        assert with_employer_hsa["federal_agi"] == pytest.approx(base["federal_agi"], abs=1)

    def test_hsa_earnings_do_not_affect_federal_agi(self):
        """HSA earnings are not federally taxable."""
        base = _calc()
        with_earnings = _calc(ca_hsa_earnings=1_000)
        assert with_earnings["federal_agi"] == pytest.approx(base["federal_agi"], abs=1)

    def test_unemployment_compensation_in_federal_agi(self):
        """Unemployment compensation is taxable federally (ARPA exclusion expired)."""
        base = _calc(unemployment_compensation=0)
        with_unemp = _calc(unemployment_compensation=5_000)
        assert with_unemp["federal_agi"] == pytest.approx(
            base["federal_agi"] + 5_000, abs=1
        )

    def test_unemployment_compensation_subtracted_from_ca_agi(self):
        """CA does not tax unemployment compensation (R&TC § 17083)."""
        base = _calc(unemployment_compensation=0)
        with_unemp = _calc(unemployment_compensation=5_000)
        # Federal AGI is 5k higher, but CA subtracts it → CA AGI unchanged
        assert with_unemp["ca_agi"] == pytest.approx(base["ca_agi"], abs=1)
        assert with_unemp["ca_subtractions_unemployment"] == pytest.approx(5_000, abs=1)

    def test_ca_additions_total_sums_all_components(self):
        """ca_additions_total = addback + employer_hsa + hsa_earnings."""
        result = _calc(
            hsa_total=8_300,
            ca_employer_hsa_contributions=4_650,
            ca_hsa_earnings=375,
        )
        expected_total = 8_300 + 4_650 + 375
        assert result["ca_additions_total"] == pytest.approx(expected_total, abs=1)
