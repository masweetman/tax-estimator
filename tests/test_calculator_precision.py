"""Precision, edge-case, and adversarial tests for the tax calculator.

Complements test_calculator.py by:
  1. Verifying exact computed values against hand-calculated expectations
  2. Testing boundary conditions precisely
  3. Testing adversarial / unexpected inputs
  4. Directly unit-testing the bracket engine

All tests use ``zero_inputs(**overrides)`` so every input is explicitly
controlled — there are no hidden defaults that could mask bugs.

Hand-calculated reference values are annotated inline.
"""
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def zero_inputs(**overrides):
    """All-zero base input dict — override only the fields you care about."""
    base = {
        "tax_year": 2025,
        "w2_wages": 0.0,
        "w2_wages_p1": 0.0,
        "w2_wages_p2": 0.0,
        "federal_income_withheld": 0.0,
        "ss_withheld": 0.0,
        "medicare_withheld": 0.0,
        "ca_income_withheld": 0.0,
        "ca_sdi_withheld": 0.0,
        "se_net_income_p1": 0.0,
        "se_net_income_p2": 0.0,
        "long_term_capital_gains": 0.0,
        "short_term_capital_gains": 0.0,
        "mortgage_interest": 0.0,
        "charitable": 0.0,
        "salt_taxes_paid": 0.0,
        "medical_expenses": 0.0,
        "pretax_401k_total": 0.0,
        "traditional_ira_total": 0.0,
        "sep_ira_total": 0.0,
        "hsa_total": 0.0,
        "se_health_insurance": 0.0,
        "child_care_expenses": 0.0,
        "qualifying_children": 0,
        "federal_estimated_paid": 0.0,
        "ca_estimated_paid": 0.0,
        "prior_year_federal_tax": 0.0,
        "prior_year_ca_tax": 0.0,
        "prior_year_agi": 0.0,
    }
    base.update(overrides)
    return base


def calc(**overrides):
    """Run the calculator with zero_inputs base plus overrides."""
    from app.calculator.engine import calculate
    return calculate(zero_inputs(**overrides))


# ===========================================================================
# Section 1: Bracket engine unit tests
# ===========================================================================

class TestBracketEngine:
    """Direct unit tests of the _apply_brackets function."""

    def _brackets(self):
        """2025 federal MFJ brackets."""
        from app.calculator.constants import FEDERAL_BRACKETS_MFJ
        return FEDERAL_BRACKETS_MFJ[2025]

    def test_zero_income_yields_zero_tax(self):
        from app.calculator.federal import _apply_brackets
        assert _apply_brackets(0, self._brackets()) == 0.0

    def test_income_within_first_bracket(self):
        """$10,000 is entirely in the 10% bracket → $1,000 tax."""
        from app.calculator.federal import _apply_brackets
        assert _apply_brackets(10_000, self._brackets()) == pytest.approx(1_000.0)

    def test_income_at_first_bracket_ceiling(self):
        """$23,850 fills the 10% bracket exactly → $2,385 tax."""
        from app.calculator.federal import _apply_brackets
        assert _apply_brackets(23_850, self._brackets()) == pytest.approx(2_385.0)

    def test_income_one_dollar_above_first_bracket(self):
        """$23,851: $23,850 at 10% + $1 at 12% = $2,385.12."""
        from app.calculator.federal import _apply_brackets
        assert _apply_brackets(23_851, self._brackets()) == pytest.approx(2_385.12)

    def test_income_spanning_two_brackets(self):
        """$50,000 spans 10% and 12% brackets.
        10% on $23,850 = $2,385
        12% on ($50,000 - $23,850) = $3,138
        Total = $5,523
        """
        from app.calculator.federal import _apply_brackets
        expected = 23_850 * 0.10 + (50_000 - 23_850) * 0.12
        assert _apply_brackets(50_000, self._brackets()) == pytest.approx(expected)

    def test_exact_value_at_150k(self):
        """$150,000 ordinary income — reference value for many other tests.
        10%: $23,850 → $2,385
        12%: $73,100 → $8,772
        22%: $53,050 → $11,671
        Total: $22,828
        """
        from app.calculator.federal import _apply_brackets
        expected = 2_385 + 8_772 + 11_671  # = 22_828
        assert _apply_brackets(150_000, self._brackets()) == pytest.approx(22_828.0)

    def test_marginal_rate_in_10pct_bracket(self):
        from app.calculator.federal import _marginal_rate
        assert _marginal_rate(23_000, self._brackets()) == 0.10

    def test_marginal_rate_in_22pct_bracket(self):
        from app.calculator.federal import _marginal_rate
        assert _marginal_rate(150_000, self._brackets()) == 0.22

    def test_marginal_rate_in_37pct_bracket(self):
        from app.calculator.federal import _marginal_rate
        assert _marginal_rate(800_000, self._brackets()) == 0.37


# ===========================================================================
# Section 2: Federal income tax — precision
# ===========================================================================

class TestFederalPrecision:

    def test_exact_income_tax_at_150k_taxable(self):
        """W-2 wages $180k, standard deduction → $150k taxable → $22,828 tax."""
        result = calc(w2_wages=180_000)
        assert result["federal_taxable_income"] == pytest.approx(150_000.0)
        assert result["federal_income_tax"] == pytest.approx(22_828.0)

    def test_marginal_rate_22pct_at_150k_taxable(self):
        result = calc(w2_wages=180_000)
        assert result["marginal_federal_rate"] == 0.22

    def test_effective_rate_formula_holds(self):
        """effective_rate == federal_income_tax / federal_agi."""
        result = calc(w2_wages=180_000)
        rate = result["effective_federal_rate"]
        expected = result["federal_income_tax"] / result["federal_agi"]
        assert rate == pytest.approx(expected, abs=0.0001)

    def test_effective_rate_plausible_for_180k_w2(self):
        """180k single-earner, standard deduction: effective rate ~10–20%."""
        result = calc(w2_wages=180_000)
        assert 0.10 <= result["effective_federal_rate"] <= 0.20

    def test_ira_reduces_agi_exact(self):
        """$7,000 IRA deduction reduces AGI by exactly $7,000."""
        no_ira = calc(w2_wages=100_000)
        with_ira = calc(w2_wages=100_000, traditional_ira_total=7_000)
        assert with_ira["federal_agi"] == pytest.approx(no_ira["federal_agi"] - 7_000)

    def test_hsa_reduces_agi_exact(self):
        """$8,300 HSA contribution reduces AGI by exactly $8,300."""
        no_hsa = calc(w2_wages=100_000)
        with_hsa = calc(w2_wages=100_000, hsa_total=8_300)
        assert with_hsa["federal_agi"] == pytest.approx(no_hsa["federal_agi"] - 8_300)

    def test_sep_ira_reduces_agi_exact(self):
        """SEP-IRA contribution reduces AGI by the contribution amount."""
        no_sep = calc(w2_wages=100_000)
        with_sep = calc(w2_wages=100_000, sep_ira_total=20_000)
        assert with_sep["federal_agi"] == pytest.approx(no_sep["federal_agi"] - 20_000)

    def test_se_health_insurance_reduces_agi(self):
        """SE health insurance is an above-the-line deduction."""
        no_ins = calc(w2_wages=100_000)
        with_ins = calc(w2_wages=100_000, se_health_insurance=12_000)
        assert with_ins["federal_agi"] == pytest.approx(no_ins["federal_agi"] - 12_000)

    def test_short_term_gains_treated_as_ordinary_income(self):
        """STCG flows through ordinary income brackets (unlike LTCG)."""
        no_stcg = calc(w2_wages=100_000)
        with_stcg = calc(w2_wages=100_000, short_term_capital_gains=20_000)
        # STCG raises AGI and taxable income → higher ordinary income tax
        assert with_stcg["federal_agi"] == pytest.approx(no_stcg["federal_agi"] + 20_000)
        assert with_stcg["federal_income_tax"] > no_stcg["federal_income_tax"]

    def test_medical_expense_floor_7pt5pct(self):
        """Medical expenses below 7.5% AGI floor are not deductible."""
        # AGI = 100,000 → floor = 7,500
        # medical_expenses = 7,000 → deductible = 0
        # medical_expenses = 8,000 → deductible = 500
        no_medical = calc(w2_wages=100_000, mortgage_interest=40_000)
        below_floor = calc(w2_wages=100_000, mortgage_interest=40_000,
                           medical_expenses=7_000)
        above_floor = calc(w2_wages=100_000, mortgage_interest=40_000,
                           medical_expenses=8_000)
        # $7,000 medical below 7.5% floor: same as no_medical
        assert below_floor["federal_taxable_income"] == pytest.approx(
            no_medical["federal_taxable_income"])
        # $8,000 medical: $500 deductible → taxable income $500 lower
        assert above_floor["federal_taxable_income"] == pytest.approx(
            no_medical["federal_taxable_income"] - 500)

    def test_itemized_tie_with_standard_uses_standard(self):
        """When itemized == standard deduction, standard is chosen (not strictly greater)."""
        # mortgage_interest = 30,000 == FEDERAL_STANDARD_DEDUCTION_MFJ[2025]
        result = calc(w2_wages=100_000, mortgage_interest=30_000)
        assert result["deduction_type"] == "standard"

    def test_ctc_exact_at_two_children_below_phaseout(self):
        """2 children, AGI well below $400k phase-out → CTC = $4,000."""
        result = calc(w2_wages=150_000, qualifying_children=2)
        assert result["child_tax_credit"] == 4_000

    def test_ctc_begins_phasing_out_above_400k(self):
        """First dollar above $400k AGI: 1 unit = $50 reduction per child.
        AGI = $403,001: excess = $3,001 → 4 units → reduction = $200
        CTC = $4,000 - $200 = $3,800.
        """
        result = calc(w2_wages=403_001, qualifying_children=2)
        assert result["child_tax_credit"] == 3_800

    def test_ctc_zero_when_fully_phased_out(self):
        """AGI = $480,000: excess = $80,000 → 80 units × $50 = $4,000 reduction.
        2 children × $2,000 = $4,000 raw CTC; phase-out wipes it entirely → $0.
        """
        result = calc(w2_wages=480_000, qualifying_children=2)
        assert result["child_tax_credit"] == 0

    def test_ctc_one_child(self):
        result = calc(w2_wages=100_000, qualifying_children=1)
        assert result["child_tax_credit"] == 2_000

    def test_ctc_zero_children(self):
        result = calc(w2_wages=100_000, qualifying_children=0)
        assert result["child_tax_credit"] == 0

    def test_cdcc_at_minimum_rate_high_agi(self):
        """AGI well above $43k → CDCC rate floors at 20%.
        2 children, $6,000 expenses (CDCC max) → credit = $6,000 × 20% = $1,200.
        """
        result = calc(w2_wages=200_000,
                      child_care_expenses=6_000,
                      qualifying_children=2)
        assert result["child_care_credit"] == pytest.approx(1_200.0)

    def test_cdcc_at_maximum_rate_low_agi(self):
        """AGI ≤ $15,000 → CDCC rate = 35%.
        2 children, $6,000 expenses → credit = $6,000 × 35% = $2,100.
        """
        result = calc(w2_wages=14_000,
                      child_care_expenses=6_000,
                      qualifying_children=2)
        assert result["child_care_credit"] == pytest.approx(2_100.0)

    def test_cdcc_capped_at_one_child_maximum(self):
        """1 child → max eligible expenses = $3,000."""
        result = calc(w2_wages=14_000,
                      child_care_expenses=10_000,
                      qualifying_children=1)
        # Eligible = min(10000, 3000) = 3000; rate = 35% → credit = 1050
        assert result["child_care_credit"] == pytest.approx(1_050.0)

    def test_cdcc_zero_when_no_children(self):
        result = calc(w2_wages=100_000,
                      child_care_expenses=6_000,
                      qualifying_children=0)
        assert result["child_care_credit"] == 0.0

    def test_additional_medicare_tax_exact(self):
        """$150k above MFJ threshold ($250k) → 0.9% × $150k = $1,350."""
        result = calc(w2_wages=400_000)
        assert result["additional_medicare_tax"] == pytest.approx(1_350.0)

    def test_additional_medicare_zero_below_threshold(self):
        result = calc(w2_wages=200_000)
        assert result["additional_medicare_tax"] == 0.0

    def test_niit_exact(self):
        """LTCG = $20k, AGI = $320k → $70k above threshold.
        NIIT base = min(20000, 70000) = 20000 → NIIT = 20000 × 3.8% = $760.
        """
        result = calc(w2_wages=300_000, long_term_capital_gains=20_000)
        assert result["niit"] == pytest.approx(760.0)

    def test_niit_capped_at_nii_when_nii_is_smaller(self):
        """When NII < (AGI - $250k), NIIT base = NII (not the excess)."""
        # AGI = $500k → excess = $250k; NII (LTCG) = $5k → NIIT capped at NII
        result = calc(w2_wages=500_000, long_term_capital_gains=5_000)
        assert result["niit"] == pytest.approx(5_000 * 0.038)

    def test_niit_zero_when_below_threshold(self):
        """No NIIT when NII exists but MAGI is below $250k."""
        result = calc(w2_wages=100_000, long_term_capital_gains=30_000)
        # AGI = 130k < 250k threshold
        assert result["niit"] == 0.0

    def test_ltcg_taxed_at_zero_pct_when_ordinary_income_fills_first_two_brackets(self):
        """LTCG is 0% when stacked ordinary + LTCG still fits within 0% LTCG bracket.
        ordinary_taxable = $80k - $30k std = $50k;
        LTCG = $10k; total stack = $60k < $96,700 LTCG 0% boundary → 0% LTCG.
        """
        result = calc(w2_wages=80_000, long_term_capital_gains=10_000)
        # All LTCG in 0% bracket
        # ordinary_taxable = 50000, ltcg_base = 50000
        # _brackets(60000, ltcg) - _brackets(50000, ltcg) = 0 - 0 = 0
        # We verify by checking that LTCG addition does not raise income_tax
        no_ltcg = calc(w2_wages=80_000)
        with_ltcg = result
        assert with_ltcg["federal_income_tax"] == pytest.approx(no_ltcg["federal_income_tax"])

    def test_ltcg_taxed_at_15pct_above_0pct_bracket(self):
        """LTCG stacked on ordinary income entirely in 15% LTCG bracket.
        ordinary_taxable = 120k; LTCG = 50k; all 50k at 15% → $7,500.
        """
        # w2=150k, std=30k → ordinary_taxable=120k, LTCG stacks 120k→170k (in 15% bracket)
        result = calc(w2_wages=150_000, long_term_capital_gains=50_000)
        # ltcg_tax = _brackets(170000, ltcg) - _brackets(120000, ltcg)
        # = 0.15*(170000-96700) - 0.15*(120000-96700) = 0.15*73300 - 0.15*23300 = 7500
        # Note: income_tax includes LTCG tax in federal_income_tax_before_credits
        # We check the LTCG portion separately via total vs ordinary-only scenario
        no_ltcg = calc(w2_wages=150_000)  # same ordinary income, no LTCG
        ltcg_tax_portion = result["federal_income_tax_before_credits"] - \
                           no_ltcg["federal_income_tax_before_credits"]
        assert ltcg_tax_portion == pytest.approx(7_500.0)

    def test_ltcg_partially_at_20pct_bracket(self):
        """Large LTCG pushes into the 20% LTCG bracket (>$583,750 stacked)."""
        # ordinary_taxable = 370k, LTCG = 300k; some LTCG is above 583,750 boundary
        result = calc(w2_wages=400_000, long_term_capital_gains=300_000)
        no_ltcg = calc(w2_wages=400_000)
        ltcg_tax = result["federal_income_tax_before_credits"] - \
                   no_ltcg["federal_income_tax_before_credits"]
        # Part at 15%: 583750-370000 = 213750; part at 20%: 300000-213750 = 86250
        expected = 213_750 * 0.15 + 86_250 * 0.20
        assert ltcg_tax == pytest.approx(expected, abs=1.0)


# ===========================================================================
# Section 3: Self-employment tax — precision
# ===========================================================================

class TestSEPrecision:

    def test_se_tax_exact_on_40k_net(self):
        """SE net = $40k; no W-2 wages.
        net_earnings = 40000 × 0.9235 = 36940
        SS: 36940 × 0.124 = 4580.56
        Medicare: 36940 × 0.029 = 1071.26
        SE tax = 5651.82; half_se deduction = 2825.91
        """
        result = calc(se_net_income_p1=40_000)
        assert result["federal_se_tax"] == pytest.approx(5_651.82, abs=0.02)
        assert result["se_deduction"] == pytest.approx(2_825.91, abs=0.02)

    def test_se_deduction_is_half_of_se_tax(self):
        result = calc(se_net_income_p1=60_000)
        assert result["se_deduction"] == pytest.approx(result["federal_se_tax"] / 2, abs=0.01)

    def test_se_deduction_reduces_agi(self):
        """Half of SE tax is an above-the-line AGI deduction."""
        no_se = calc(w2_wages=50_000)
        with_se = calc(w2_wages=50_000, se_net_income_p1=30_000)
        # SE income increases gross, but half-SE deduction partially offsets
        assert with_se["se_deduction"] > 0
        agi_from_se_income_only = with_se["federal_agi"] - no_se["federal_agi"]
        # SE net is not quite fully added to AGI because of the half-SE deduction
        assert agi_from_se_income_only == pytest.approx(
            30_000 - with_se["se_deduction"], abs=0.5)

    def test_se_no_ss_tax_when_w2_fills_base(self):
        """When W-2 wages already exceed the SS wage base for Person 1, SE income owes no SS.
        Only the Medicare portion of SE tax applies.
        w2_wages_p1=400k > SS_WAGE_BASE[2025]=176,100
        → ss_room=0 → ss_tax=0 for SE income.
        """
        result = calc(w2_wages=400_000, w2_wages_p1=400_000, se_net_income_p1=50_000)
        # Medicare-only SE tax: 50000 × 0.9235 × 0.029 = 46175 × 0.029 ≈ 1339.08
        expected_se_tax = 50_000 * 0.9235 * 0.029
        assert result["federal_se_tax"] == pytest.approx(expected_se_tax, abs=0.02)

    def test_person2_se_income_adds_to_total(self):
        """Both SE persons' income contributes to total SE tax."""
        p1_only = calc(se_net_income_p1=30_000)
        p2_only = calc(se_net_income_p2=30_000)
        both = calc(se_net_income_p1=30_000, se_net_income_p2=30_000)
        # With zero W-2 wages: each person has same SS room → taxes add linearly
        assert both["federal_se_tax"] == pytest.approx(
            p1_only["federal_se_tax"] + p2_only["federal_se_tax"], abs=0.05)


# ===========================================================================
# Section 4: California tax — precision
# ===========================================================================

class TestCaliforniaPrecision:

    def test_ca_standard_deduction_exact(self):
        from app.calculator.constants import CA_STANDARD_DEDUCTION_MFJ
        assert CA_STANDARD_DEDUCTION_MFJ[2025] == 11_392

    def test_ca_tax_in_first_bracket_only(self):
        """CA taxable income fully within the 1% bracket.
        w2=26,392 → ca_agi=26,392 → ca_taxable=26392-11392=15,000
        ca_tax_before_credits = 15000 × 1% = $150.00
        CA personal exemption ($314 MFJ) exceeds pre-credit tax → after-credit tax = $0.
        """
        result = calc(w2_wages=26_392)
        assert result["ca_taxable_income"] == pytest.approx(15_000.0)
        assert result["ca_income_tax_before_surtax"] == pytest.approx(150.0)
        assert result["ca_income_tax"] == pytest.approx(0.0)

    def test_ca_uses_itemized_when_mortgage_exceeds_ca_standard(self):
        """CA standard deduction ($11,392) is much lower than federal ($30,000).
        A $15,000 mortgage tips CA to itemized while federal remains standard.
        """
        result = calc(w2_wages=100_000, mortgage_interest=15_000)
        assert result["ca_deduction_type"] == "itemized"
        assert result["deduction_type"] == "standard"
        assert result["ca_deduction_amount"] == pytest.approx(15_000.0)

    def test_ca_uses_full_salt_no_cap(self):
        """CA does NOT cap SALT at $10k.  Federal caps it; CA uses the full amount."""
        result = calc(w2_wages=150_000,
                      salt_taxes_paid=25_000,
                      ca_sdi_withheld=0)
        # CA: 25,000 > 11,392 → itemized with full 25,000
        assert result["ca_deduction_type"] == "itemized"
        assert result["ca_deduction_amount"] == pytest.approx(25_000.0)
        # Federal: SALT capped at 10,000; itemized=10,000 < 30,000 → standard
        assert result["deduction_type"] == "standard"

    def test_ca_sdi_not_deductible_on_ca_return(self):
        """SDI withholding does NOT reduce CA itemized deductions."""
        base_kw = dict(w2_wages=200_000, mortgage_interest=35_000, ca_sdi_withheld=0)
        with_sdi = calc(**base_kw | {"ca_sdi_withheld": 6_000})
        without_sdi = calc(**base_kw)
        assert with_sdi["ca_income_tax"] == pytest.approx(without_sdi["ca_income_tax"])

    def test_ca_federal_agi_used_as_ca_agi(self):
        """CA AGI is derived from federal AGI (simplified conformity)."""
        result = calc(w2_wages=150_000, traditional_ira_total=7_000)
        assert result["ca_agi"] == pytest.approx(result["federal_agi"])

    def test_ca_ltcg_taxed_as_ordinary_income(self):
        """CA taxes LTCG at the same rates as ordinary income (no preferential rate)."""
        no_ltcg = calc(w2_wages=100_000)
        with_ltcg = calc(w2_wages=100_000, long_term_capital_gains=20_000)
        # CA AGI increases by 20k → CA tax increases
        assert with_ltcg["ca_agi"] > no_ltcg["ca_agi"]
        assert with_ltcg["ca_income_tax"] > no_ltcg["ca_income_tax"]

    def test_ca_mental_health_surtax_exact(self):
        """1% surtax on CA taxable income above $1M.
        ca_taxable = 1,100,000 - 11,392 = 1,088,608
        mh_base = 1,088,608 - 1,000,000 = 88,608
        surtax = 88,608 × 1% = $886.08
        """
        result = calc(w2_wages=1_100_000)
        assert result["ca_mental_health_surtax"] == pytest.approx(886.08, abs=0.02)
        assert result["ca_mental_health_surtax"] > 0

    def test_ca_mental_health_surtax_zero_at_exactly_1m(self):
        """No surtax when taxable income = exactly $1,000,000."""
        # Need ca_taxable = 1,000,000 → ca_agi = 1,000,000 + 11,392 = 1,011,392
        result = calc(w2_wages=1_011_392)
        assert result["ca_mental_health_surtax"] == pytest.approx(0.0, abs=0.01)


# ===========================================================================
# Section 5: Safe harbor — precision
# ===========================================================================

class TestSafeHarborPrecision:

    def test_safe_harbor_federal_100pct_below_150k_agi(self):
        """Prior-year AGI ≤ $150k → safe harbor = 100% of prior-year tax."""
        result = calc(prior_year_federal_tax=18_000, prior_year_agi=140_000)
        assert result["safe_harbor_federal"] == pytest.approx(18_000.0)

    def test_safe_harbor_federal_110pct_above_150k_agi(self):
        """Prior-year AGI > $150k → safe harbor = 110% of prior-year tax."""
        result = calc(prior_year_federal_tax=24_000, prior_year_agi=160_000)
        assert result["safe_harbor_federal"] == pytest.approx(26_400.0)  # 24,000 × 1.10

    def test_safe_harbor_federal_at_exactly_150k_threshold_uses_100pct(self):
        """Prior-year AGI = exactly $150,000 uses 100% (threshold is strictly >)."""
        result = calc(prior_year_federal_tax=20_000, prior_year_agi=150_000)
        assert result["safe_harbor_federal"] == pytest.approx(20_000.0)

    def test_safe_harbor_ca_equals_100pct_of_prior_year_ca_tax(self):
        """CA safe harbor = exactly 100% of prior-year CA tax."""
        result = calc(prior_year_ca_tax=7_500)
        assert result["safe_harbor_ca"] == pytest.approx(7_500.0)

    def test_quarterly_federal_exact_math(self):
        """Verify the quarterly recommendation arithmetic.
        prior_year_federal_tax=32,000; prior_year_agi=200,000 (>150k → 110%)
        safe_harbor = 32,000 × 1.10 = 35,200
        wthheld+estimated = 20,000+4,000 = 24,000
        remaining = 35,200 - 24,000 = 11,200
        quarterly = 11,200 / 4 = 2,800.00
        """
        result = calc(
            prior_year_federal_tax=32_000,
            prior_year_agi=200_000,
            federal_income_withheld=20_000,
            federal_estimated_paid=4_000,
        )
        assert result["safe_harbor_federal"] == pytest.approx(35_200.0)
        assert result["quarterly_federal_recommended"] == pytest.approx(2_800.0)

    def test_quarterly_ca_exact_math(self):
        """CA quarterly payment arithmetic."""
        result = calc(
            prior_year_ca_tax=8_000,
            ca_income_withheld=5_000,
            ca_estimated_paid=1_000,
        )
        # safe_harbor_ca = 8000; paid = 6000; remaining = 2000; quarterly = 500
        assert result["quarterly_ca_recommended"] == pytest.approx(500.0)

    def test_quarterly_zero_when_payments_exceed_safe_harbor(self):
        """If payments already satisfy safe harbor, recommended quarterly = 0."""
        result = calc(
            prior_year_federal_tax=10_000,
            prior_year_agi=100_000,
            federal_income_withheld=12_000,  # already > safe_harbor (10,000)
            federal_estimated_paid=0,
        )
        assert result["quarterly_federal_recommended"] == 0.0

    def test_federal_balance_due_can_be_negative_refund(self):
        """Negative balance_due = refund owed to taxpayer."""
        result = calc(
            w2_wages=50_000,
            federal_income_withheld=40_000,
            qualifying_children=0,
        )
        assert result["federal_balance_due"] < 0

    def test_balance_due_formula_federal(self):
        """federal_balance_due = federal_total_tax - (withheld + estimated)."""
        result = calc(
            w2_wages=200_000,
            federal_income_withheld=15_000,
            federal_estimated_paid=5_000,
        )
        expected = result["federal_total_tax"] - 15_000 - 5_000
        assert result["federal_balance_due"] == pytest.approx(expected)

    def test_balance_due_formula_ca(self):
        """ca_balance_due = ca_income_tax - (withheld + estimated)."""
        result = calc(
            w2_wages=200_000,
            ca_income_withheld=8_000,
            ca_estimated_paid=2_000,
        )
        expected = result["ca_income_tax"] - 8_000 - 2_000
        assert result["ca_balance_due"] == pytest.approx(expected)


# ===========================================================================
# Section 6: SALT cap — precision
# ===========================================================================

class TestSALTCap:

    def test_salt_capped_at_10k_federal_with_sdi(self):
        """Federal SALT = min(salt_paid + ca_sdi + ca_income_withheld, 10,000)."""
        # Both total 15,000 which exceeds the cap
        low = calc(w2_wages=200_000, mortgage_interest=40_000,
                   salt_taxes_paid=8_000, ca_sdi_withheld=2_000)
        high = calc(w2_wages=200_000, mortgage_interest=40_000,
                    salt_taxes_paid=20_000, ca_sdi_withheld=5_000)
        # Both capped at 10,000 → same taxable income
        assert low["federal_taxable_income"] == pytest.approx(
            high["federal_taxable_income"])

    def test_ca_income_withheld_included_in_salt(self):
        """CA state income tax withheld feeds into SALT (alongside SDI and manual amounts).
        mortgage = 40,000 → definitely itemizing.
        salt_taxes_paid = 4,000; ca_sdi_withheld = 0; ca_income_withheld = 4,000
        → combined = 8,000 < 10,000 cap → full 8,000 allowed.
        Compare against ca_income_withheld = 0 → only 4,000 SALT allowed.
        Difference in taxable income should be 4,000.
        """
        without_ca_income = calc(w2_wages=200_000, mortgage_interest=40_000,
                                 salt_taxes_paid=4_000, ca_sdi_withheld=0,
                                 ca_income_withheld=0)
        with_ca_income = calc(w2_wages=200_000, mortgage_interest=40_000,
                              salt_taxes_paid=4_000, ca_sdi_withheld=0,
                              ca_income_withheld=4_000)
        # SALT allowed: 4k vs 8k → taxable income 4k lower when ca_income included
        assert without_ca_income["federal_taxable_income"] == pytest.approx(
            with_ca_income["federal_taxable_income"] + 4_000)
        # Verify the new return keys exist
        assert with_ca_income["salt_total"] == pytest.approx(8_000.0)
        assert with_ca_income["salt_cap_applied"] == pytest.approx(10_000.0)
        assert with_ca_income["itemized_total"] == pytest.approx(
            40_000 + 0 + 8_000 + 0)  # mortgage + charitable + salt + medical

    def test_ca_income_withheld_still_capped_at_salt_limit(self):
        """Even with large ca_income_withheld, SALT is capped at 10,000 for 2025."""
        result = calc(w2_wages=200_000, mortgage_interest=40_000,
                      salt_taxes_paid=5_000, ca_sdi_withheld=2_000,
                      ca_income_withheld=10_000)
        # combined = 17,000 > cap of 10,000 → capped
        assert result["salt_total"] == pytest.approx(10_000.0)

    def test_salt_below_cap_not_rounded_up(self):
        """SALT below $10k is deducted in full (not rounded to cap)."""
        result = calc(w2_wages=200_000, mortgage_interest=40_000,
                      salt_taxes_paid=6_000, ca_sdi_withheld=0)
        # itemized = 40,000 + 6,000 = 46,000
        assert result["deduction_type"] == "itemized"
        assert result["deduction_amount"] == pytest.approx(46_000.0)


# ===========================================================================
# Section 7: Edge cases
# ===========================================================================

class TestEdgeCases:

    def test_all_zero_inputs_yield_zero_taxes(self):
        """Taxpayer with zero income owes zero tax."""
        result = calc()
        assert result["federal_total_tax"] == 0.0
        assert result["ca_income_tax"] == 0.0
        assert result["federal_balance_due"] == 0.0
        assert result["ca_balance_due"] == 0.0

    def test_all_zero_inputs_no_quarterly_recommendation(self):
        """No prior-year tax and no current tax → no quarterly payment needed."""
        result = calc()
        assert result["quarterly_federal_recommended"] == 0.0
        assert result["quarterly_ca_recommended"] == 0.0

    def test_income_at_bracket_boundary_22pct(self):
        """Income exactly at $206,700 (top of 22% bracket) uses 22% marginal rate."""
        # taxable = 206,700 → in 22% bracket ceiling; marginal should be 22%
        # Need AGI = 206,700 + 30,000 = 236,700
        result = calc(w2_wages=236_700)
        assert result["marginal_federal_rate"] == 0.22

    def test_income_one_dollar_above_22pct_bracket_enters_24pct(self):
        """$1 above 22% ceiling → marginal rate jumps to 24%."""
        result = calc(w2_wages=236_701)
        assert result["marginal_federal_rate"] == 0.24

    def test_income_at_ss_wage_base_boundary(self):
        """W-2 wages per person exactly matching SS wage base → no SS tax on any SE."""
        # P1 W-2 = exactly SS wage base → P1 SS room = 0 → SE income for P1: Medicare only
        result = calc(w2_wages=352_200,    # total household W-2 (for AMT/NIIT calculations)
                      w2_wages_p1=176_100, # P1 W-2 exactly fills P1 SS base
                      se_net_income_p1=30_000)
        # Only Medicare SE tax ≈ 30,000 × 0.9235 × 0.029
        expected = 30_000 * 0.9235 * 0.029
        assert result["federal_se_tax"] == pytest.approx(expected, abs=0.05)

    def test_refundable_credit_does_not_make_tax_negative(self):
        """CTC + CDCC are non-refundable; federal_income_tax cannot go below 0."""
        result = calc(w2_wages=5_000,
                      qualifying_children=3,
                      child_care_expenses=50_000)
        assert result["federal_income_tax"] >= 0.0

    def test_very_high_income_no_crash(self):
        """$10M single-earner should not crash, and should hit top brackets."""
        result = calc(w2_wages=10_000_000)
        assert result["marginal_federal_rate"] == 0.37
        assert result["federal_total_tax"] > 0
        assert result["ca_income_tax"] > 0

    def test_prior_year_agi_at_exactly_150k_threshold(self):
        """AGI = exactly $150,000 uses 100% safe harbor multiplier (not 110%)."""
        result_at = calc(prior_year_federal_tax=20_000, prior_year_agi=150_000)
        result_over = calc(prior_year_federal_tax=20_000, prior_year_agi=150_001)
        assert result_at["safe_harbor_federal"] == pytest.approx(20_000.0)
        assert result_over["safe_harbor_federal"] == pytest.approx(22_000.0)

    def test_no_children_no_credits(self):
        """Taxpayer with no children has no CTC or CDCC regardless of expenses."""
        result = calc(w2_wages=100_000,
                      qualifying_children=0,
                      child_care_expenses=10_000)
        assert result["child_tax_credit"] == 0
        assert result["child_care_credit"] == 0.0

    def test_ltcg_only_income_no_ordinary_income(self):
        """Pure LTCG income (no W-2): all in low LTCG brackets."""
        result = calc(long_term_capital_gains=50_000)
        # AGI = 50,000; taxable = 50,000 - 30,000 = 20,000 → 0% LTCG rate
        assert result["ltcg_tax"] if "ltcg_tax" in result else True  # key may not exist
        assert result["federal_income_tax_before_credits"] == pytest.approx(0.0)

    def test_standard_deduction_used_when_itemized_lower(self):
        """Small SALT + zero mortgage → itemized < standard → standard wins."""
        result = calc(w2_wages=100_000, salt_taxes_paid=3_000)
        assert result["deduction_type"] == "standard"

    def test_ca_income_tax_exists_for_moderate_income(self):
        """Basic sanity: CA should tax moderate W-2 income."""
        result = calc(w2_wages=100_000)
        assert result["ca_income_tax"] > 0


# ===========================================================================
# Section 8: Adversarial / chaos inputs
# ===========================================================================

class TestAdversarialInputs:

    def test_string_numeric_values_coerced(self):
        """Input values as strings should be coerced via float()/int()."""
        result = calc(w2_wages="100000", qualifying_children="2")
        assert result["federal_agi"] == pytest.approx(100_000.0)
        assert result["child_tax_credit"] == 4_000

    def test_extra_unknown_keys_ignored(self):
        """Unknown fields in the input dict must not raise an error."""
        from app.calculator.engine import calculate
        inputs = zero_inputs(w2_wages=100_000)
        inputs["phantom_field"] = "should_be_ignored"
        inputs["another_unknown"] = 999_999
        result = calculate(inputs)
        assert result["federal_agi"] == pytest.approx(100_000.0)

    def test_negative_wages_clamped_to_zero_agi(self):
        """Negative w2_wages must not produce negative AGI or crash."""
        result = calc(w2_wages=-50_000)
        assert result["federal_agi"] >= 0
        assert result["federal_total_tax"] >= 0

    def test_negative_mortgage_interest_does_not_inflate_deduction(self):
        """Negative itemized deduction input must not exceed standard deduction."""
        result = calc(w2_wages=100_000, mortgage_interest=-10_000)
        # Negative mortgage: itemized = -10k → standard wins
        assert result["deduction_type"] == "standard"

    def test_huge_salt_still_capped_at_10k(self):
        """Once SALT ≥ $10k the cap applies and additional SALT has no effect.
        SALT=$10k and SALT=$500k both produce the same itemized deduction.
        """
        at_cap = calc(w2_wages=200_000, mortgage_interest=40_000,
                      salt_taxes_paid=10_000)  # exactly at cap
        huge_salt = calc(w2_wages=200_000, mortgage_interest=40_000,
                         salt_taxes_paid=500_000)  # far above cap
        assert at_cap["federal_taxable_income"] == pytest.approx(
            huge_salt["federal_taxable_income"])

    def test_se_income_zero_produces_no_se_tax(self):
        result = calc(se_net_income_p1=0.0, se_net_income_p2=0.0)
        assert result["federal_se_tax"] == 0.0
        assert result["se_deduction"] == 0.0

    def test_zero_prior_year_data_produces_zero_safe_harbor(self):
        """No prior-year data → safe_harbor = 0 → no quarterly payment needed."""
        result = calc(w2_wages=200_000,
                      prior_year_federal_tax=0,
                      prior_year_ca_tax=0,
                      prior_year_agi=0)
        assert result["safe_harbor_federal"] == 0.0
        assert result["safe_harbor_ca"] == 0.0
        assert result["quarterly_federal_recommended"] == 0.0

    def test_extremely_high_child_care_capped_at_maximum(self):
        """CDCC eligible expenses are capped; $100k input uses the $6k cap."""
        result = calc(w2_wages=14_000,
                      qualifying_children=2,
                      child_care_expenses=100_000)
        # max eligible = CDCC_MAX_EXPENSES_2_PLUS = 6,000; rate = 35% → 2100
        assert result["child_care_credit"] == pytest.approx(2_100.0)

    def test_result_always_has_required_output_keys(self):
        """The calculator must always return a complete set of output keys."""
        REQUIRED_KEYS = {
            "federal_agi", "federal_taxable_income", "deduction_type",
            "deduction_amount", "federal_income_tax_before_credits",
            "child_tax_credit", "child_care_credit", "federal_income_tax",
            "se_deduction", "federal_se_tax", "additional_medicare_tax",
            "niit", "federal_total_tax", "effective_federal_rate",
            "marginal_federal_rate",
            "ca_agi", "ca_taxable_income", "ca_deduction_type",
            "ca_income_tax", "ca_mental_health_surtax",
            "safe_harbor_federal", "safe_harbor_ca",
            "quarterly_federal_recommended", "quarterly_ca_recommended",
            "federal_balance_due", "ca_balance_due",
        }
        result = calc()
        missing = REQUIRED_KEYS - set(result.keys())
        assert not missing, f"Calculator missing output keys: {missing}"

    def test_missing_optional_keys_default_to_zero(self):
        """A minimal input dict (only required keys) must not crash."""
        from app.calculator.engine import calculate
        minimal = {
            "tax_year": 2025,
            "w2_wages": 80_000,
            "qualifying_children": 0,
            "prior_year_federal_tax": 0,
            "prior_year_ca_tax": 0,
            "prior_year_agi": 0,
        }
        result = calculate(minimal)
        assert result["federal_total_tax"] > 0  # should still calculate tax
        assert result["federal_se_tax"] == 0.0  # missing SE fields default to 0
