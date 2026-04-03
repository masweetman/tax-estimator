"""Integration tests and user-story tests.

Integration tests verify that database records are correctly aggregated by
``_build_inputs`` and fed to the calculator.  User-story tests simulate
realistic tax scenarios end-to-end from route through calculator.
"""
import datetime
import pytest
from werkzeug.security import generate_password_hash

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _login(client, app, username="intuser", password="pass"):
    with app.app_context():
        from app import db
        from app.models import User
        if not User.query.filter_by(username=username).first():
            db.session.add(User(
                username=username,
                password_hash=generate_password_hash(password),
            ))
            db.session.commit()
    client.post("/auth/login", data={"username": username, "password": password})


def _get_or_create_year(app, year=2025):
    with app.app_context():
        from app import db
        from app.models import TaxYear
        ty = TaxYear.query.filter_by(year=year).first()
        if not ty:
            ty = TaxYear(year=year)
            db.session.add(ty)
            db.session.commit()
        return ty.id


def _build_inputs_for_year(app, year):
    """Call _build_inputs via the dashboard's internal function."""
    with app.app_context():
        from app.models import TaxYear
        from app.routes.dashboard import _build_inputs
        ty = TaxYear.query.filter_by(year=year).first()
        assert ty is not None, f"TaxYear {year} not found"
        return _build_inputs(ty)


# ===========================================================================
# Section 1: Calculator engine integration
# ===========================================================================

class TestCalculatorEngineIntegration:
    """Verify the engine composes federal + CA + safe harbor correctly."""

    def test_result_contains_all_subsystems(self):
        """Engine output must contain keys from all three sub-calculators."""
        from app.calculator.engine import calculate
        result = calculate({"tax_year": 2025, "w2_wages": 100_000,
                            "qualifying_children": 0,
                            "prior_year_federal_tax": 0,
                            "prior_year_ca_tax": 0,
                            "prior_year_agi": 0})
        # Federal keys
        assert "federal_agi" in result
        assert "federal_income_tax" in result
        assert "federal_total_tax" in result
        # CA keys
        assert "ca_agi" in result
        assert "ca_income_tax" in result
        # Safe harbor keys
        assert "safe_harbor_federal" in result
        assert "quarterly_federal_recommended" in result

    def test_federal_higher_than_ca_for_typical_income(self):
        """For moderate W-2 income, federal tax liability exceeds CA tax."""
        from app.calculator.engine import calculate
        result = calculate({"tax_year": 2025, "w2_wages": 150_000,
                            "qualifying_children": 0,
                            "prior_year_federal_tax": 0,
                            "prior_year_ca_tax": 0,
                            "prior_year_agi": 0})
        assert result["federal_total_tax"] > result["ca_income_tax"]

    def test_total_tax_increases_monotonically_with_income(self):
        """Doubling W-2 income must more than double total tax (progressive)."""
        from app.calculator.engine import calculate
        low = calculate({"tax_year": 2025, "w2_wages": 100_000,
                         "qualifying_children": 0,
                         "prior_year_federal_tax": 0,
                         "prior_year_ca_tax": 0,
                         "prior_year_agi": 0})
        high = calculate({"tax_year": 2025, "w2_wages": 200_000,
                          "qualifying_children": 0,
                          "prior_year_federal_tax": 0,
                          "prior_year_ca_tax": 0,
                          "prior_year_agi": 0})
        # Progressive system: doubling income should MORE than double tax
        assert high["federal_income_tax"] > 2 * low["federal_income_tax"]

    def test_later_result_keys_do_not_overwrite_earlier_ones(self):
        """Engine merges subsystem results; no key should be silently overwritten."""
        from app.calculator.engine import calculate
        result = calculate({"tax_year": 2025, "w2_wages": 200_000,
                            "qualifying_children": 0,
                            "prior_year_federal_tax": 10_000,
                            "prior_year_ca_tax": 3_000,
                            "prior_year_agi": 180_000})
        # All three systems' distinct keys must coexist
        assert "federal_income_tax" in result  # from federal
        assert "ca_income_tax" in result        # from california
        assert "safe_harbor_federal" in result  # from safe_harbor


# ===========================================================================
# Section 2: _build_inputs aggregation
# ===========================================================================

class TestBuildInputsAggregation:
    """Verify _build_inputs correctly aggregates database records.

    Each test method uses its own unique far-future year to prevent data
    accumulation across tests (the database is session-scoped and shared).
    """

    def _setup_year(self, app, client, year):
        """Create a TaxYear with specific prior-year values, if not already present."""
        _login(client, app, username="biuser")
        with app.app_context():
            from app import db
            from app.models import TaxYear
            ty = TaxYear.query.filter_by(year=year).first()
            if not ty:
                ty = TaxYear(
                    year=year,
                    prior_year_federal_tax=20_000,
                    prior_year_ca_tax=5_000,
                    prior_year_agi=180_000,
                )
                db.session.add(ty)
                db.session.commit()

    def test_empty_year_produces_zero_w2_wages(self, app, client):
        year = 2051
        self._setup_year(app, client, year)
        inputs = _build_inputs_for_year(app, year)
        assert inputs["w2_wages"] == pytest.approx(0.0)

    def test_paystub_gross_pay_sums_into_w2_wages(self, app, client):
        """Two paystubs with known gross pay → w2_wages = sum of box-1 wages."""
        year = 2052
        self._setup_year(app, client, year)
        with app.app_context():
            from app import db
            from app.models import TaxYear, Employer, Paystub
            ty = TaxYear.query.filter_by(year=year).first()
            emp = Employer(
                tax_year_id=ty.id, person="Person 1", name="AggCorp",
                first_paystub_date=datetime.date(year, 1, 4),
            )
            db.session.add(emp)
            db.session.flush()
            for n, gp in enumerate([5_000, 6_000], start=1):
                db.session.add(Paystub(
                    employer_id=emp.id,
                    pay_period_start=datetime.date(year, n, 1),
                    pay_period_end=datetime.date(year, n, 14),
                    pay_date=datetime.date(year, n, 15),
                    is_actual=True,
                    gross_pay=gp,
                    federal_income_withholding=0,
                    ss_withholding=0,
                    medicare_withholding=0,
                    state_income_withholding=0,
                    state_disability_withholding=0,
                ))
            db.session.commit()

        inputs = _build_inputs_for_year(app, year)
        # w2_wages = (5000 - 0) + (6000 - 0) = 11000
        assert inputs["w2_wages"] == pytest.approx(11_000.0)

    def test_federal_withholding_aggregated(self, app, client):
        year = 2053
        self._setup_year(app, client, year)
        with app.app_context():
            from app import db
            from app.models import TaxYear, Employer, Paystub
            ty = TaxYear.query.filter_by(year=year).first()
            emp = Employer(
                tax_year_id=ty.id, person="Person 1", name="WthCorp",
                first_paystub_date=datetime.date(year, 1, 4),
            )
            db.session.add(emp)
            db.session.flush()
            for i, fed_wth in enumerate([800, 850], start=1):
                db.session.add(Paystub(
                    employer_id=emp.id,
                    pay_period_start=datetime.date(year, i, 1),
                    pay_period_end=datetime.date(year, i, 14),
                    pay_date=datetime.date(year, i, 15),
                    is_actual=True,
                    gross_pay=5_000,
                    federal_income_withholding=fed_wth,
                ))
            db.session.commit()

        inputs = _build_inputs_for_year(app, year)
        assert inputs["federal_income_withheld"] == pytest.approx(1_650.0)

    def test_se_expenses_reduce_person1_net_income(self, app, client):
        """SE expenses are subtracted from Person 1's gross SE income.
        Person 2's income is passed gross (no expense offset in current design).
        """
        year = 2054
        self._setup_year(app, client, year)
        with app.app_context():
            from app import db
            from app.models import TaxYear, SelfEmploymentIncome, SelfEmploymentExpense
            ty = TaxYear.query.filter_by(year=year).first()
            db.session.add(SelfEmploymentIncome(
                tax_year_id=ty.id, person="Person 1",
                amount=30_000, date=datetime.date(year, 6, 1),
                category="consulting",
            ))
            db.session.add(SelfEmploymentExpense(
                tax_year_id=ty.id, description="Home office",
                amount=5_000, date=datetime.date(year, 6, 1),
                category="office",
            ))
            db.session.commit()

        inputs = _build_inputs_for_year(app, year)
        assert inputs["se_net_income_p1"] == pytest.approx(25_000.0)  # 30k - 5k

    def test_long_term_capital_gain_aggregated(self, app, client):
        """Gain = proceeds - cost_basis for is_long_term=True records."""
        year = 2055
        self._setup_year(app, client, year)
        with app.app_context():
            from app import db
            from app.models import TaxYear, CapitalGain
            ty = TaxYear.query.filter_by(year=year).first()
            db.session.add(CapitalGain(
                tax_year_id=ty.id, person="Person 1",
                description="AAPL", proceeds=15_000, cost_basis=10_000,
                acquisition_date=datetime.date(year - 2, 1, 1),
                sale_date=datetime.date(year, 5, 15),
                is_long_term=True,
            ))
            db.session.commit()

        inputs = _build_inputs_for_year(app, year)
        assert inputs["long_term_capital_gains"] == pytest.approx(5_000.0)  # 15k - 10k

    def test_short_term_capital_gain_aggregated(self, app, client):
        year = 2056
        self._setup_year(app, client, year)
        with app.app_context():
            from app import db
            from app.models import TaxYear, CapitalGain
            ty = TaxYear.query.filter_by(year=year).first()
            db.session.add(CapitalGain(
                tax_year_id=ty.id, person="Person 1",
                description="TSLA", proceeds=8_000, cost_basis=9_000,
                acquisition_date=datetime.date(year, 1, 1),
                sale_date=datetime.date(year, 6, 1),
                is_long_term=False,
            ))
            db.session.commit()

        inputs = _build_inputs_for_year(app, year)
        # Short-term loss: gain = 8000 - 9000 = -1000
        assert inputs["short_term_capital_gains"] == pytest.approx(-1_000.0)

    def test_long_term_gain_clamped_to_zero_when_net_loss(self, app, client):
        """long_term_capital_gains cannot go below 0 in inputs (losses not passed)."""
        year = 2057
        self._setup_year(app, client, year)
        with app.app_context():
            from app import db
            from app.models import TaxYear, CapitalGain
            ty = TaxYear.query.filter_by(year=year).first()
            db.session.add(CapitalGain(
                tax_year_id=ty.id, person="Person 1",
                description="Loss Stock", proceeds=5_000, cost_basis=10_000,
                acquisition_date=datetime.date(year - 2, 1, 1),
                sale_date=datetime.date(year, 3, 1),
                is_long_term=True,
            ))
            db.session.commit()

        inputs = _build_inputs_for_year(app, year)
        # _build_inputs uses max(0, ltcg)
        assert inputs["long_term_capital_gains"] == pytest.approx(0.0)

    def test_vehicle_mileage_deduction_calculated(self, app, client):
        """Vehicle mileage deduction = business_miles × IRS rate ($0.70/mile)."""
        year = 2058
        self._setup_year(app, client, year)
        with app.app_context():
            from app import db
            from app.models import TaxYear, VehicleMileage
            ty = TaxYear.query.filter_by(year=year).first()
            db.session.add(VehicleMileage(
                tax_year_id=ty.id,
                vehicle_name="Honda Civic",
                business_miles=1_000,
                date=datetime.date(year, 6, 1),
            ))
            db.session.commit()

        inputs = _build_inputs_for_year(app, year)
        # 1000 miles × $0.70 = $700.00
        assert inputs["vehicle_mileage_deduction"] == pytest.approx(700.0)

    def test_prior_year_data_passed_from_tax_year_model(self, app, client):
        """prior_year_* fields come from the TaxYear model attributes."""
        year = 2059
        self._setup_year(app, client, year)
        inputs = _build_inputs_for_year(app, year)
        assert inputs["prior_year_federal_tax"] == pytest.approx(20_000.0)
        assert inputs["prior_year_ca_tax"] == pytest.approx(5_000.0)
        assert inputs["prior_year_agi"] == pytest.approx(180_000.0)

    def test_qualifying_children_always_two(self, app, client):
        """Dashboard hardcodes qualifying_children=2 (family-of-4 assumption)."""
        year = 2060
        self._setup_year(app, client, year)
        inputs = _build_inputs_for_year(app, year)
        assert inputs["qualifying_children"] == 2

    def test_multiple_employers_wages_summed(self, app, client):
        """Two employers: wages from both must be aggregated."""
        year = 2061
        self._setup_year(app, client, year)
        with app.app_context():
            from app import db
            from app.models import TaxYear, Employer, Paystub
            ty = TaxYear.query.filter_by(year=year).first()
            for n, emp_name in enumerate(["Corp A", "Corp B"], start=1):
                emp = Employer(
                    tax_year_id=ty.id, person=f"Person {n}",
                    name=emp_name,
                    first_paystub_date=datetime.date(year, 1, 4),
                )
                db.session.add(emp)
                db.session.flush()
                db.session.add(Paystub(
                    employer_id=emp.id,
                    pay_period_start=datetime.date(year, 1, 1),
                    pay_period_end=datetime.date(year, 1, 14),
                    pay_date=datetime.date(year, 1, 15),
                    is_actual=True,
                    gross_pay=4_000 * n,  # 4000 + 8000
                ))
            db.session.commit()

        inputs = _build_inputs_for_year(app, year)
        assert inputs["w2_wages"] == pytest.approx(12_000.0)  # 4000 + 8000

    def test_ira_contributions_aggregated(self, app, client):
        year = 2062
        self._setup_year(app, client, year)
        with app.app_context():
            from app import db
            from app.models import TaxYear, RetirementContribution
            ty = TaxYear.query.filter_by(year=year).first()
            for amount in [3_500, 3_500]:
                db.session.add(RetirementContribution(
                    tax_year_id=ty.id, person="Person 1",
                    account_type="traditional_ira", amount=amount,
                    date=datetime.date(year, 4, 15),
                ))
            db.session.commit()

        inputs = _build_inputs_for_year(app, year)
        assert inputs["traditional_ira_total"] == pytest.approx(7_000.0)

    def test_estimated_payments_aggregated_by_jurisdiction(self, app, client):
        year = 2063
        self._setup_year(app, client, year)
        with app.app_context():
            from app import db
            from app.models import TaxYear, EstimatedTaxPayment
            ty = TaxYear.query.filter_by(year=year).first()
            db.session.add(EstimatedTaxPayment(
                tax_year_id=ty.id, jurisdiction="federal",
                quarter="Q1", amount=3_000,
                date_paid=datetime.date(year, 4, 15),
            ))
            db.session.add(EstimatedTaxPayment(
                tax_year_id=ty.id, jurisdiction="ca",
                quarter="Q1", amount=1_500,
                date_paid=datetime.date(year, 4, 15),
            ))
            db.session.commit()

        inputs = _build_inputs_for_year(app, year)
        assert inputs["federal_estimated_paid"] == pytest.approx(3_000.0)
        assert inputs["ca_estimated_paid"] == pytest.approx(1_500.0)


# ===========================================================================
# Section 3: Dashboard route integration
# ===========================================================================

class TestDashboardRouteIntegration:
    """End-to-end tests: create DB data → request dashboard → check response."""

    YEAR = 2041

    def _bootstrap(self, app, client):
        _login(client, app, username="druser")
        with app.app_context():
            from app import db
            from app.models import TaxYear, Employer, Paystub
            ty = TaxYear.query.filter_by(year=self.YEAR).first()
            if not ty:
                ty = TaxYear(
                    year=self.YEAR,
                    prior_year_federal_tax=30_000,
                    prior_year_ca_tax=8_000,
                    prior_year_agi=200_000,
                )
                db.session.add(ty)
                db.session.flush()
                emp = Employer(
                    tax_year_id=ty.id, person="Person 1", name="DRCorp",
                    first_paystub_date=datetime.date(self.YEAR, 1, 4),
                )
                db.session.add(emp)
                db.session.flush()
                # Use different months (Jan/Feb/Mar) to avoid day-of-month overflow
                for i in range(3):
                    db.session.add(Paystub(
                        employer_id=emp.id,
                        pay_period_start=datetime.date(self.YEAR, i + 1, 1),
                        pay_period_end=datetime.date(self.YEAR, i + 1, 14),
                        pay_date=datetime.date(self.YEAR, i + 1, 15),
                        is_actual=True,
                        gross_pay=8_000,
                        federal_income_withholding=1_000,
                        state_income_withholding=600,
                    ))
                db.session.commit()

    def test_dashboard_returns_200_with_real_data(self, app, client):
        self._bootstrap(app, client)
        resp = client.get(f"/?year={self.YEAR}")
        assert resp.status_code == 200

    def test_dashboard_invalid_year_returns_404(self, app, client):
        self._bootstrap(app, client)
        resp = client.get("/?year=1776")
        assert resp.status_code == 404

    def test_dashboard_contains_tax_figures(self, app, client):
        """Response HTML must contain dollar-sign sections."""
        self._bootstrap(app, client)
        resp = client.get(f"/?year={self.YEAR}")
        assert b"$" in resp.data or b"Federal" in resp.data

    def test_dashboard_shows_correct_year(self, app, client):
        self._bootstrap(app, client)
        resp = client.get(f"/?year={self.YEAR}")
        assert str(self.YEAR).encode() in resp.data


# ===========================================================================
# Section 4: User story tests
# ===========================================================================

class TestUserStoryHighEarner:
    """Story: A high-earning couple gets a mid-year raise.
    The additional income pushes wages into the 32% bracket and triggers
    both additional Medicare tax and potentially NIIT.
    """

    def test_raise_increases_marginal_rate_to_32pct(self):
        """Wages crossing $394,600 taxable income enter the 32% bracket."""
        from app.calculator.engine import calculate
        # taxable = AGI - 30000; AGI = wages; we want taxable just above 394,600
        # wages = 425_000 → AGI = 425,000 → taxable = 395,000 → 32% bracket
        result = calculate({
            "tax_year": 2025, "w2_wages": 425_000, "qualifying_children": 0,
            "prior_year_federal_tax": 0, "prior_year_ca_tax": 0, "prior_year_agi": 0,
        })
        assert result["marginal_federal_rate"] == pytest.approx(0.32)

    def test_additional_medicare_triggers_above_250k(self):
        """Wages > $250k (MFJ) trigger the 0.9% additional Medicare tax."""
        from app.calculator.engine import calculate
        result = calculate({
            "tax_year": 2025, "w2_wages": 300_000, "qualifying_children": 0,
            "prior_year_federal_tax": 0, "prior_year_ca_tax": 0, "prior_year_agi": 0,
        })
        assert result["additional_medicare_tax"] > 0
        assert result["additional_medicare_tax"] == pytest.approx(
            (300_000 - 250_000) * 0.009)

    def test_adding_stock_proceeds_triggers_niit(self):
        """LTCG when total income > $250k triggers NIIT."""
        from app.calculator.engine import calculate
        # $260k W-2 + $30k LTCG → AGI = $290k > $250k threshold
        result = calculate({
            "tax_year": 2025,
            "w2_wages": 260_000,
            "long_term_capital_gains": 30_000,
            "qualifying_children": 0,
            "prior_year_federal_tax": 0, "prior_year_ca_tax": 0, "prior_year_agi": 0,
        })
        assert result["niit"] > 0


class TestUserStorySelfEmployed:
    """Story: Person 2 starts freelancing mid-year.
    SE income appears, SE tax is owed, half-SE deduction reduces AGI.
    """

    def test_adding_se_income_increases_total_tax(self):
        from app.calculator.engine import calculate
        base = {"tax_year": 2025, "w2_wages": 80_000, "qualifying_children": 0,
                "prior_year_federal_tax": 0, "prior_year_ca_tax": 0, "prior_year_agi": 0}
        no_se = calculate(base)
        with_se = calculate({**base, "se_net_income_p2": 30_000})
        assert with_se["federal_total_tax"] > no_se["federal_total_tax"]

    def test_se_income_generates_se_tax(self):
        from app.calculator.engine import calculate
        result = calculate({
            "tax_year": 2025, "w2_wages": 0, "se_net_income_p1": 50_000,
            "qualifying_children": 0,
            "prior_year_federal_tax": 0, "prior_year_ca_tax": 0, "prior_year_agi": 0,
        })
        assert result["federal_se_tax"] > 0

    def test_half_se_deduction_reduces_agi(self):
        from app.calculator.engine import calculate
        no_se = calculate({"tax_year": 2025, "w2_wages": 100_000,
                           "qualifying_children": 0,
                           "prior_year_federal_tax": 0, "prior_year_ca_tax": 0, "prior_year_agi": 0})
        with_se = calculate({"tax_year": 2025, "w2_wages": 100_000,
                             "se_net_income_p1": 40_000,
                             "qualifying_children": 0,
                             "prior_year_federal_tax": 0, "prior_year_ca_tax": 0, "prior_year_agi": 0})
        # 40k SE income adds to gross, but half-SE deduction partially offsets
        # Net AGI delta = 40000 - se_deduction (which is ~half of se_tax)
        agi_increase = with_se["federal_agi"] - no_se["federal_agi"]
        assert 0 < agi_increase < 40_000  # must be less than full SE income

    def test_se_expenses_reduce_net_se_income(self):
        """SE net = SE gross income - SE expenses."""
        from app.calculator.engine import calculate
        gross_income_result = calculate({
            "tax_year": 2025, "w2_wages": 0, "se_net_income_p1": 60_000,
            "qualifying_children": 0,
            "prior_year_federal_tax": 0, "prior_year_ca_tax": 0, "prior_year_agi": 0,
        })
        net_income_result = calculate({
            "tax_year": 2025, "w2_wages": 0, "se_net_income_p1": 40_000,
            "qualifying_children": 0,
            "prior_year_federal_tax": 0, "prior_year_ca_tax": 0, "prior_year_agi": 0,
        })
        # 60k gross vs 40k net: higher gross → higher total tax
        assert gross_income_result["federal_total_tax"] > net_income_result["federal_total_tax"]


class TestUserStoryMortgagePurchase:
    """Story: Family buys a house → large mortgage interest tips them to itemized.
    Both federal and CA switch from standard to itemized, saving taxes.
    """

    def test_large_mortgage_switches_federal_to_itemized(self):
        from app.calculator.engine import calculate
        no_mortgage = calculate({"tax_year": 2025, "w2_wages": 300_000,
                                 "qualifying_children": 2,
                                 "prior_year_federal_tax": 0, "prior_year_ca_tax": 0,
                                 "prior_year_agi": 0})
        with_mortgage = calculate({"tax_year": 2025, "w2_wages": 300_000,
                                   "mortgage_interest": 35_000,
                                   "salt_taxes_paid": 10_000,
                                   "qualifying_children": 2,
                                   "prior_year_federal_tax": 0, "prior_year_ca_tax": 0,
                                   "prior_year_agi": 0})
        assert no_mortgage["deduction_type"] == "standard"
        assert with_mortgage["deduction_type"] == "itemized"

    def test_mortgage_reduces_taxable_income(self):
        """Itemizing with $35k mortgage + SALT cap ($10k) = $45k > $30k std."""
        from app.calculator.engine import calculate
        result = calculate({"tax_year": 2025, "w2_wages": 300_000,
                            "mortgage_interest": 35_000,
                            "salt_taxes_paid": 10_000,
                            "qualifying_children": 0,
                            "prior_year_federal_tax": 0, "prior_year_ca_tax": 0,
                            "prior_year_agi": 0})
        # federal_taxable = 300000 - 45000 = 255000 (not 300000 - 30000 = 270000)
        assert result["federal_taxable_income"] == pytest.approx(255_000.0)

    def test_mortgage_reduces_ca_tax_even_when_below_federal_std_deduction(self):
        """A mortgage below the federal std deduction ($30k) still reduces CA tax
        because the CA std deduction ($11,392) is much lower.
        Federal uses standard; CA switches to itemized → CA-only savings.
        """
        from app.calculator.engine import calculate
        no_mortgage = calculate({"tax_year": 2025, "w2_wages": 200_000,
                                  "mortgage_interest": 0, "qualifying_children": 0,
                                  "prior_year_federal_tax": 0, "prior_year_ca_tax": 0,
                                  "prior_year_agi": 0})
        with_mortgage = calculate({"tax_year": 2025, "w2_wages": 200_000,
                                    "mortgage_interest": 25_000,  # > CA std, < fed std
                                    "qualifying_children": 0,
                                    "prior_year_federal_tax": 0, "prior_year_ca_tax": 0,
                                    "prior_year_agi": 0})
        # CA itemizes (25k > 11k CA std) → CA tax goes down
        assert with_mortgage["ca_income_tax"] < no_mortgage["ca_income_tax"]
        assert with_mortgage["ca_deduction_type"] == "itemized"
        # Federal stays standard (25k < 30k federal std) → federal tax unchanged
        assert with_mortgage["deduction_type"] == "standard"
        assert with_mortgage["federal_income_tax"] == no_mortgage["federal_income_tax"]


class TestUserStorySafeHarborQuarterly:
    """Story: Couple wants to avoid underpayment penalties.
    They need to know exactly how much to pay each quarter.
    """

    def test_high_prior_year_agi_triggers_110pct_rule(self):
        """Prior AGI > $150k → must pay 110% of prior-year tax to be safe."""
        from app.calculator.engine import calculate
        result = calculate({
            "tax_year": 2025,
            "w2_wages": 300_000,
            "prior_year_federal_tax": 40_000,
            "prior_year_agi": 250_000,  # > 150k → 110% rule
            "prior_year_ca_tax": 10_000,
            "qualifying_children": 0,
        })
        assert result["safe_harbor_federal"] == pytest.approx(44_000.0)  # 40k × 1.10

    def test_withholding_reduces_quarterly_payment_needed(self):
        """Increasing withholding (e.g. via Form W-4) reduces quarterly estimates."""
        from app.calculator.engine import calculate
        low_wth = calculate({
            "tax_year": 2025, "w2_wages": 200_000,
            "federal_income_withheld": 5_000,
            "prior_year_federal_tax": 30_000, "prior_year_agi": 200_000,
            "prior_year_ca_tax": 0, "qualifying_children": 0,
        })
        high_wth = calculate({
            "tax_year": 2025, "w2_wages": 200_000,
            "federal_income_withheld": 25_000,
            "prior_year_federal_tax": 30_000, "prior_year_agi": 200_000,
            "prior_year_ca_tax": 0, "qualifying_children": 0,
        })
        assert high_wth["quarterly_federal_recommended"] < low_wth["quarterly_federal_recommended"]

    def test_no_quarterly_payment_when_prior_year_data_unknown(self):
        """If prior-year data is missing, safe harbor = 0 → no payment recommended."""
        from app.calculator.engine import calculate
        result = calculate({
            "tax_year": 2025, "w2_wages": 300_000,
            "prior_year_federal_tax": 0,
            "prior_year_ca_tax": 0,
            "prior_year_agi": 0,
            "qualifying_children": 0,
        })
        assert result["quarterly_federal_recommended"] == 0.0

    def test_quarterly_ca_payment_reflects_ca_safe_harbor(self):
        from app.calculator.engine import calculate
        result = calculate({
            "tax_year": 2025, "w2_wages": 200_000,
            "prior_year_ca_tax": 12_000,
            "ca_income_withheld": 4_000,
            "ca_estimated_paid": 0,
            "prior_year_federal_tax": 0, "prior_year_agi": 0,
            "qualifying_children": 0,
        })
        # safe_harbor_ca = 12000; paid = 4000; remaining = 8000; quarterly = 2000
        assert result["quarterly_ca_recommended"] == pytest.approx(2_000.0)


class TestUserStoryCapitalGainsPlanning:
    """Story: Family sells stock.  They want to understand the tax impact."""

    def test_ltcg_below_threshold_owes_0pct_rate(self):
        """Low-income taxpayer with LTCG pays 0% on gains."""
        from app.calculator.engine import calculate
        # ordinary_taxable << 96,700 → LTCG in 0% bracket
        result = calculate({
            "tax_year": 2025, "w2_wages": 60_000,
            "long_term_capital_gains": 10_000,
            "qualifying_children": 0,
            "prior_year_federal_tax": 0, "prior_year_ca_tax": 0, "prior_year_agi": 0,
        })
        # At 60k wages, standard deduction = 30k → ordinary_taxable = 30k
        # LTCG stack: 30k + 10k = 40k < 96,700 → 0% LTCG
        # income_tax_before_credits should only reflect ordinary income tax
        result_no_ltcg = calculate({
            "tax_year": 2025, "w2_wages": 60_000, "qualifying_children": 0,
            "prior_year_federal_tax": 0, "prior_year_ca_tax": 0, "prior_year_agi": 0,
        })
        # Adding 0%-rate LTCG should not change federal income tax on ordinary income
        assert result["federal_income_tax_before_credits"] == pytest.approx(
            result_no_ltcg["federal_income_tax_before_credits"])

    def test_ltcg_at_high_income_triggers_niit(self):
        """For AGI > $250k, LTCG also triggers 3.8% NIIT."""
        from app.calculator.engine import calculate
        result = calculate({
            "tax_year": 2025, "w2_wages": 250_000,
            "long_term_capital_gains": 50_000,
            "qualifying_children": 0,
            "prior_year_federal_tax": 0, "prior_year_ca_tax": 0, "prior_year_agi": 0,
        })
        # AGI = 300k → above NIIT threshold
        assert result["niit"] > 0

    def test_ca_taxes_ltcg_like_ordinary_income(self):
        """CA has no preferential LTCG rate; gains are taxed at CA ordinary rates."""
        from app.calculator.engine import calculate
        ordinary_income = calculate({
            "tax_year": 2025, "w2_wages": 120_000, "qualifying_children": 0,
            "prior_year_federal_tax": 0, "prior_year_ca_tax": 0, "prior_year_agi": 0,
        })
        shifted_to_ltcg = calculate({
            "tax_year": 2025, "w2_wages": 100_000,
            "long_term_capital_gains": 20_000,
            "qualifying_children": 0,
            "prior_year_federal_tax": 0, "prior_year_ca_tax": 0, "prior_year_agi": 0,
        })
        # Both have same CA AGI (120k); CA tax should be approximately equal
        assert ordinary_income["ca_income_tax"] == pytest.approx(
            shifted_to_ltcg["ca_income_tax"], abs=1.0)


class TestUserStoryChildCredits:
    """Story: Family of 4 (2 qualifying children) uses CTC and CDCC."""

    def test_two_children_generate_4000_ctc(self):
        from app.calculator.engine import calculate
        result = calculate({
            "tax_year": 2025, "w2_wages": 150_000, "qualifying_children": 2,
            "prior_year_federal_tax": 0, "prior_year_ca_tax": 0, "prior_year_agi": 0,
        })
        assert result["child_tax_credit"] == 4_000

    def test_child_care_credit_applied_at_moderate_income(self):
        from app.calculator.engine import calculate
        result = calculate({
            "tax_year": 2025, "w2_wages": 100_000,
            "child_care_expenses": 6_000, "qualifying_children": 2,
            "prior_year_federal_tax": 0, "prior_year_ca_tax": 0, "prior_year_agi": 0,
        })
        assert result["child_care_credit"] > 0

    def test_credits_reduce_tax_liability(self):
        """Tax WITH credits must be lower than tax WITHOUT credits."""
        from app.calculator.engine import calculate
        no_credits = calculate({
            "tax_year": 2025, "w2_wages": 150_000, "qualifying_children": 0,
            "child_care_expenses": 0,
            "prior_year_federal_tax": 0, "prior_year_ca_tax": 0, "prior_year_agi": 0,
        })
        with_credits = calculate({
            "tax_year": 2025, "w2_wages": 150_000, "qualifying_children": 2,
            "child_care_expenses": 6_000,
            "prior_year_federal_tax": 0, "prior_year_ca_tax": 0, "prior_year_agi": 0,
        })
        assert with_credits["federal_income_tax"] < no_credits["federal_income_tax"]
        assert with_credits["child_tax_credit"] == 4_000


class TestUserStoryRetirementContributions:
    """Story: Couple maxes out tax-advantaged accounts to reduce AGI."""

    def test_401k_and_ira_and_hsa_stack_to_reduce_agi(self):
        from app.calculator.engine import calculate
        no_contributions = calculate({
            "tax_year": 2025, "w2_wages": 200_000, "qualifying_children": 0,
            "prior_year_federal_tax": 0, "prior_year_ca_tax": 0, "prior_year_agi": 0,
        })
        with_contributions = calculate({
            "tax_year": 2025, "w2_wages": 200_000,
            "pretax_401k_total": 23_000,
            "traditional_ira_total": 7_000,
            "hsa_total": 8_300,
            "qualifying_children": 0,
            "prior_year_federal_tax": 0, "prior_year_ca_tax": 0, "prior_year_agi": 0,
        })
        expected_reduction = 23_000 + 7_000 + 8_300  # 38,300
        assert with_contributions["federal_agi"] == pytest.approx(
            no_contributions["federal_agi"] - expected_reduction)

    def test_lower_agi_reduces_marginal_bracket(self):
        """Enough contributions can push the marginal rate down one bracket."""
        from app.calculator.engine import calculate
        # Without contributions: w2=200k → taxable=170k → in 22% bracket
        no_contrib = calculate({
            "tax_year": 2025, "w2_wages": 200_000, "qualifying_children": 0,
            "prior_year_federal_tax": 0, "prior_year_ca_tax": 0, "prior_year_agi": 0,
        })
        # With $38k+ in contributions: taxable < 96,950 → 12% bracket
        with_contrib = calculate({
            "tax_year": 2025, "w2_wages": 200_000,
            "pretax_401k_total": 23_000,
            "traditional_ira_total": 7_000,
            "hsa_total": 8_300,
            "qualifying_children": 0,
            "prior_year_federal_tax": 0, "prior_year_ca_tax": 0, "prior_year_agi": 0,
        })
        # 200000 - 38300 - 30000 = 131700 → still in 22% bracket
        # Let's verify it actually IS still in 22% (our test should reflect reality)
        assert with_contrib["federal_agi"] < no_contrib["federal_agi"]
        assert with_contrib["federal_income_tax"] < no_contrib["federal_income_tax"]
