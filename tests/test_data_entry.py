"""Tests for data entry routes — SE, deductions, payments, vehicles, retirement,
insurance premiums, and HSA contributions.  Written before implementation (TDD)."""
import datetime
import pytest
from werkzeug.security import generate_password_hash

YEAR = 2026


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _login(client, app, username="deuser", password="pass"):
    with app.app_context():
        from app import db
        from app.models import User
        if not User.query.filter_by(username=username).first():
            db.session.add(User(username=username, password_hash=generate_password_hash(password)))
            db.session.commit()
    client.post("/auth/login", data={"username": username, "password": password})


def _get_or_create_year(app, year=YEAR):
    with app.app_context():
        from app import db
        from app.models import TaxYear
        ty = TaxYear.query.filter_by(year=year).first()
        if not ty:
            ty = TaxYear(year=year)
            db.session.add(ty)
            db.session.commit()
        return ty.id


# ---------------------------------------------------------------------------
# Self-Employment Income
# ---------------------------------------------------------------------------

class TestSEIncome:
    def test_list_returns_200(self, app, client):
        _login(client, app)
        _get_or_create_year(app)
        resp = client.get(f"/se/{YEAR}/income")
        assert resp.status_code == 200

    def test_add_page_returns_200(self, app, client):
        _login(client, app)
        _get_or_create_year(app)
        resp = client.get(f"/se/{YEAR}/income/add")
        assert resp.status_code == 200

    def test_add_creates_record(self, app, client):
        _login(client, app)
        _get_or_create_year(app)
        resp = client.post(f"/se/{YEAR}/income/add", data={
            "person": "Person 1",
            "client": "Client X",
            "amount": "1500.00",
            "date": "2026-03-15",
            "category": "consulting",
            "notes": "",
        }, follow_redirects=False)
        assert resp.status_code == 302
        with app.app_context():
            from app.models import SelfEmploymentIncome, TaxYear
            ty = TaxYear.query.filter_by(year=YEAR).first()
            record = SelfEmploymentIncome.query.filter_by(
                tax_year_id=ty.id, client="Client X"
            ).first()
            assert record is not None
            assert float(record.amount) == 1500.00

    def test_edit_updates_record(self, app, client):
        _login(client, app)
        ty_id = _get_or_create_year(app)
        with app.app_context():
            from app import db
            from app.models import SelfEmploymentIncome
            rec = SelfEmploymentIncome(tax_year_id=ty_id, person="Person 1",
                client="EditClient", amount=500, date=datetime.date(2026, 1, 10),
                category="consulting")
            db.session.add(rec)
            db.session.commit()
            rec_id = rec.id
        resp = client.post(f"/se/income/{rec_id}/edit", data={
            "person": "Person 1", "client": "EditClient", "amount": "750.00",
            "date": "2026-01-10", "category": "consulting", "notes": "",
        }, follow_redirects=False)
        assert resp.status_code == 302
        with app.app_context():
            from app import db
            from app.models import SelfEmploymentIncome
            rec = db.session.get(SelfEmploymentIncome, rec_id)
            assert float(rec.amount) == 750.00

    def test_delete_removes_record(self, app, client):
        _login(client, app)
        ty_id = _get_or_create_year(app)
        with app.app_context():
            from app import db
            from app.models import SelfEmploymentIncome
            rec = SelfEmploymentIncome(tax_year_id=ty_id, person="Person 1",
                client="DelClient", amount=200, date=datetime.date(2026, 2, 1),
                category="other")
            db.session.add(rec)
            db.session.commit()
            rec_id = rec.id
        client.post(f"/se/income/{rec_id}/delete")
        with app.app_context():
            from app import db
            from app.models import SelfEmploymentIncome
            assert db.session.get(SelfEmploymentIncome, rec_id) is None

    def test_requires_login(self, client):
        resp = client.get(f"/se/{YEAR}/income", follow_redirects=False)
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Self-Employment Expenses
# ---------------------------------------------------------------------------

class TestSEExpenses:
    def test_list_returns_200(self, app, client):
        _login(client, app)
        _get_or_create_year(app)
        resp = client.get(f"/se/{YEAR}/expenses")
        assert resp.status_code == 200

    def test_add_creates_record(self, app, client):
        _login(client, app)
        _get_or_create_year(app)
        resp = client.post(f"/se/{YEAR}/expenses/add", data={
            "description": "Home Office Router",
            "amount": "89.99",
            "date": "2026-02-01",
            "category": "office",
            "notes": "",
        }, follow_redirects=False)
        assert resp.status_code == 302
        with app.app_context():
            from app.models import SelfEmploymentExpense, TaxYear
            ty = TaxYear.query.filter_by(year=YEAR).first()
            rec = SelfEmploymentExpense.query.filter_by(
                tax_year_id=ty.id, description="Home Office Router"
            ).first()
            assert rec is not None

    def test_delete_removes_record(self, app, client):
        _login(client, app)
        ty_id = _get_or_create_year(app)
        with app.app_context():
            from app import db
            from app.models import SelfEmploymentExpense
            rec = SelfEmploymentExpense(tax_year_id=ty_id, description="Old Laptop",
                amount=999, date=datetime.date(2026, 1, 5), category="supplies")
            db.session.add(rec)
            db.session.commit()
            rec_id = rec.id
        client.post(f"/se/expenses/{rec_id}/delete")
        with app.app_context():
            from app import db
            from app.models import SelfEmploymentExpense
            assert db.session.get(SelfEmploymentExpense, rec_id) is None


# ---------------------------------------------------------------------------
# Capital Gains
# ---------------------------------------------------------------------------

class TestCapitalGains:
    def test_list_returns_200(self, app, client):
        _login(client, app)
        _get_or_create_year(app)
        resp = client.get(f"/deductions/{YEAR}/capital-gains")
        assert resp.status_code == 200

    def test_add_creates_record(self, app, client):
        _login(client, app)
        _get_or_create_year(app)
        resp = client.post(f"/deductions/{YEAR}/capital-gains/add", data={
            "person": "Person 1",
            "description": "AAPL shares",
            "proceeds": "12000.00",
            "cost_basis": "9000.00",
            "acquisition_date": "2024-03-01",
            "sale_date": "2026-01-20",
            "is_long_term": "true",
            "notes": "",
        }, follow_redirects=False)
        assert resp.status_code == 302
        with app.app_context():
            from app.models import CapitalGain, TaxYear
            ty = TaxYear.query.filter_by(year=YEAR).first()
            rec = CapitalGain.query.filter_by(
                tax_year_id=ty.id, description="AAPL shares"
            ).first()
            assert rec is not None
            assert float(rec.proceeds) == 12000.00
            assert rec.is_long_term is True

    def test_delete_removes_record(self, app, client):
        _login(client, app)
        ty_id = _get_or_create_year(app)
        with app.app_context():
            from app import db
            from app.models import CapitalGain
            rec = CapitalGain(tax_year_id=ty_id, person="Person 1",
                description="TSLA", proceeds=5000, cost_basis=4000,
                acquisition_date=datetime.date(2025, 1, 1),
                sale_date=datetime.date(2026, 2, 1), is_long_term=True)
            db.session.add(rec)
            db.session.commit()
            rec_id = rec.id
        client.post(f"/deductions/capital-gains/{rec_id}/delete")
        with app.app_context():
            from app import db
            from app.models import CapitalGain
            assert db.session.get(CapitalGain, rec_id) is None


# ---------------------------------------------------------------------------
# Itemized Deductions
# ---------------------------------------------------------------------------

class TestDeductions:
    def test_list_returns_200(self, app, client):
        _login(client, app)
        _get_or_create_year(app)
        resp = client.get(f"/deductions/{YEAR}/itemized")
        assert resp.status_code == 200

    def test_add_creates_record(self, app, client):
        _login(client, app)
        _get_or_create_year(app)
        resp = client.post(f"/deductions/{YEAR}/itemized/add", data={
            "category": "mortgage_interest",
            "description": "Home mortgage",
            "amount": "18000.00",
            "date": "2026-12-31",
            "notes": "",
        }, follow_redirects=False)
        assert resp.status_code == 302
        with app.app_context():
            from app.models import Deduction, TaxYear
            ty = TaxYear.query.filter_by(year=YEAR).first()
            rec = Deduction.query.filter_by(
                tax_year_id=ty.id, description="Home mortgage"
            ).first()
            assert rec is not None
            assert float(rec.amount) == 18000.00

    def test_delete_removes_record(self, app, client):
        _login(client, app)
        ty_id = _get_or_create_year(app)
        with app.app_context():
            from app import db
            from app.models import Deduction
            rec = Deduction(tax_year_id=ty_id, category="charitable",
                description="Red Cross", amount=500, date=datetime.date(2026, 6, 1))
            db.session.add(rec)
            db.session.commit()
            rec_id = rec.id
        client.post(f"/deductions/itemized/{rec_id}/delete")
        with app.app_context():
            from app import db
            from app.models import Deduction
            assert db.session.get(Deduction, rec_id) is None


# ---------------------------------------------------------------------------
# Child Care Expenses
# ---------------------------------------------------------------------------

class TestChildCare:
    def test_list_returns_200(self, app, client):
        _login(client, app)
        _get_or_create_year(app)
        resp = client.get(f"/deductions/{YEAR}/child-care")
        assert resp.status_code == 200

    def test_add_creates_record(self, app, client):
        _login(client, app)
        _get_or_create_year(app)
        resp = client.post(f"/deductions/{YEAR}/child-care/add", data={
            "provider": "Sunshine Daycare",
            "child_name": "Alice",
            "amount": "1200.00",
            "date": "2026-01-31",
            "notes": "",
        }, follow_redirects=False)
        assert resp.status_code == 302
        with app.app_context():
            from app.models import ChildCareExpense, TaxYear
            ty = TaxYear.query.filter_by(year=YEAR).first()
            rec = ChildCareExpense.query.filter_by(
                tax_year_id=ty.id, provider="Sunshine Daycare"
            ).first()
            assert rec is not None


# ---------------------------------------------------------------------------
# Self-Employed Insurance Premiums
# ---------------------------------------------------------------------------

class TestInsurancePremiums:
    def test_list_returns_200(self, app, client):
        _login(client, app)
        _get_or_create_year(app)
        resp = client.get(f"/deductions/{YEAR}/insurance")
        assert resp.status_code == 200

    def test_add_creates_record(self, app, client):
        _login(client, app)
        _get_or_create_year(app)
        resp = client.post(f"/deductions/{YEAR}/insurance/add", data={
            "person": "Person 1",
            "insurance_type": "health",
            "is_self_employed": "true",
            "amount": "450.00",
            "date": "2026-01-01",
            "notes": "",
        }, follow_redirects=False)
        assert resp.status_code == 302
        with app.app_context():
            from app.models import InsurancePremium, TaxYear
            ty = TaxYear.query.filter_by(year=YEAR).first()
            recs = InsurancePremium.query.filter_by(tax_year_id=ty.id).all()
            assert any(float(r.amount) == 450.00 for r in recs)

    def test_delete_removes_record(self, app, client):
        _login(client, app)
        ty_id = _get_or_create_year(app)
        with app.app_context():
            from app import db
            from app.models import InsurancePremium
            rec = InsurancePremium(tax_year_id=ty_id, person="Person 1",
                insurance_type="dental", is_self_employed=True,
                amount=50, date=datetime.date(2026, 1, 1))
            db.session.add(rec)
            db.session.commit()
            rec_id = rec.id
        client.post(f"/deductions/insurance/{rec_id}/delete")
        with app.app_context():
            from app import db
            from app.models import InsurancePremium
            assert db.session.get(InsurancePremium, rec_id) is None


# ---------------------------------------------------------------------------
# Estimated Tax Payments
# ---------------------------------------------------------------------------

class TestEstimatedPayments:
    def test_list_returns_200(self, app, client):
        _login(client, app)
        _get_or_create_year(app)
        resp = client.get(f"/payments/{YEAR}/estimated")
        assert resp.status_code == 200

    def test_add_creates_record(self, app, client):
        _login(client, app)
        _get_or_create_year(app)
        resp = client.post(f"/payments/{YEAR}/estimated/add", data={
            "jurisdiction": "federal",
            "quarter": "Q1",
            "amount": "3500.00",
            "date_paid": "2026-04-15",
            "notes": "",
        }, follow_redirects=False)
        assert resp.status_code == 302
        with app.app_context():
            from app.models import EstimatedTaxPayment, TaxYear
            ty = TaxYear.query.filter_by(year=YEAR).first()
            rec = EstimatedTaxPayment.query.filter_by(
                tax_year_id=ty.id, jurisdiction="federal", quarter="Q1"
            ).first()
            assert rec is not None
            assert float(rec.amount) == 3500.00

    def test_delete_removes_record(self, app, client):
        _login(client, app)
        ty_id = _get_or_create_year(app)
        with app.app_context():
            from app import db
            from app.models import EstimatedTaxPayment
            rec = EstimatedTaxPayment(tax_year_id=ty_id, jurisdiction="ca",
                quarter="Q2", amount=1000, date_paid=datetime.date(2026, 6, 15))
            db.session.add(rec)
            db.session.commit()
            rec_id = rec.id
        client.post(f"/payments/estimated/{rec_id}/delete")
        with app.app_context():
            from app import db
            from app.models import EstimatedTaxPayment
            assert db.session.get(EstimatedTaxPayment, rec_id) is None


# ---------------------------------------------------------------------------
# Retirement Contributions (IRA / SEP)
# ---------------------------------------------------------------------------

class TestRetirementContributions:
    def test_list_returns_200(self, app, client):
        _login(client, app)
        _get_or_create_year(app)
        resp = client.get(f"/payments/{YEAR}/retirement")
        assert resp.status_code == 200

    def test_add_creates_record(self, app, client):
        _login(client, app)
        _get_or_create_year(app)
        resp = client.post(f"/payments/{YEAR}/retirement/add", data={
            "person": "Person 1",
            "account_type": "traditional_ira",
            "amount": "7000.00",
            "date": "2026-04-15",
            "notes": "",
        }, follow_redirects=False)
        assert resp.status_code == 302
        with app.app_context():
            from app.models import RetirementContribution, TaxYear
            ty = TaxYear.query.filter_by(year=YEAR).first()
            rec = RetirementContribution.query.filter_by(
                tax_year_id=ty.id, account_type="traditional_ira"
            ).first()
            assert rec is not None
            assert float(rec.amount) == 7000.00

    def test_delete_removes_record(self, app, client):
        _login(client, app)
        ty_id = _get_or_create_year(app)
        with app.app_context():
            from app import db
            from app.models import RetirementContribution
            rec = RetirementContribution(tax_year_id=ty_id, person="Person 2",
                account_type="roth_ira", amount=7000,
                date=datetime.date(2026, 4, 15))
            db.session.add(rec)
            db.session.commit()
            rec_id = rec.id
        client.post(f"/payments/retirement/{rec_id}/delete")
        with app.app_context():
            from app import db
            from app.models import RetirementContribution
            assert db.session.get(RetirementContribution, rec_id) is None


# ---------------------------------------------------------------------------
# HSA Contributions
# ---------------------------------------------------------------------------

class TestHSAContributions:
    def test_list_returns_200(self, app, client):
        _login(client, app)
        _get_or_create_year(app)
        resp = client.get(f"/payments/{YEAR}/hsa")
        assert resp.status_code == 200

    def test_add_creates_record(self, app, client):
        _login(client, app)
        _get_or_create_year(app)
        resp = client.post(f"/payments/{YEAR}/hsa/add", data={
            "person": "Person 1",
            "amount": "500.00",
            "date": "2026-02-01",
            "notes": "",
        }, follow_redirects=False)
        assert resp.status_code == 302
        with app.app_context():
            from app.models import HSAContribution, TaxYear
            ty = TaxYear.query.filter_by(year=YEAR).first()
            recs = HSAContribution.query.filter_by(tax_year_id=ty.id).all()
            assert any(float(r.amount) == 500.00 for r in recs)

    def test_delete_removes_record(self, app, client):
        _login(client, app)
        ty_id = _get_or_create_year(app)
        with app.app_context():
            from app import db
            from app.models import HSAContribution
            rec = HSAContribution(tax_year_id=ty_id, person="Person 1",
                amount=300, date=datetime.date(2026, 3, 1))
            db.session.add(rec)
            db.session.commit()
            rec_id = rec.id
        client.post(f"/payments/hsa/{rec_id}/delete")
        with app.app_context():
            from app import db
            from app.models import HSAContribution
            assert db.session.get(HSAContribution, rec_id) is None


# ---------------------------------------------------------------------------
# Vehicle Mileage
# ---------------------------------------------------------------------------

class TestVehicleMileage:
    def test_list_returns_200(self, app, client):
        _login(client, app)
        _get_or_create_year(app)
        resp = client.get(f"/vehicles/{YEAR}/mileage")
        assert resp.status_code == 200

    def test_add_creates_record(self, app, client):
        _login(client, app)
        _get_or_create_year(app)
        resp = client.post(f"/vehicles/{YEAR}/mileage/add", data={
            "vehicle_name": "Honda CR-V",
            "date": "2026-03-10",
            "odometer_start": "45000",
            "odometer_end": "45037",
            "business_miles": "37.0",
            "purpose": "Client meeting",
            "notes": "",
        }, follow_redirects=False)
        assert resp.status_code == 302
        with app.app_context():
            from app.models import VehicleMileage, TaxYear
            ty = TaxYear.query.filter_by(year=YEAR).first()
            rec = VehicleMileage.query.filter_by(
                tax_year_id=ty.id, vehicle_name="Honda CR-V"
            ).first()
            assert rec is not None
            assert float(rec.business_miles) == 37.0

    def test_delete_removes_record(self, app, client):
        _login(client, app)
        ty_id = _get_or_create_year(app)
        with app.app_context():
            from app import db
            from app.models import VehicleMileage
            rec = VehicleMileage(tax_year_id=ty_id, vehicle_name="Toyota RAV4",
                date=datetime.date(2026, 1, 15),
                odometer_start=10000, odometer_end=10050, business_miles=50,
                purpose="Office supply run")
            db.session.add(rec)
            db.session.commit()
            rec_id = rec.id
        client.post(f"/vehicles/mileage/{rec_id}/delete")
        with app.app_context():
            from app import db
            from app.models import VehicleMileage
            assert db.session.get(VehicleMileage, rec_id) is None

    def test_mileage_deduction_preview_shown(self, app, client):
        """List page should show the IRS mileage deduction total."""
        _login(client, app)
        # Use an isolated year so no other test's mileage records contaminate the total
        CLEAN_YEAR = 9999
        ty_id = _get_or_create_year(app, year=CLEAN_YEAR)
        with app.app_context():
            from app import db
            from app.models import VehicleMileage
            rec = VehicleMileage(tax_year_id=ty_id, vehicle_name="Subaru",
                date=datetime.date(CLEAN_YEAR, 4, 1),
                odometer_start=20000, odometer_end=20100, business_miles=100,
                purpose="Client site")
            db.session.add(rec)
            db.session.commit()
        resp = client.get(f"/vehicles/{CLEAN_YEAR}/mileage")
        # 100 miles × $0.70 = $70.00 deduction should appear somewhere on the page
        assert b"70.00" in resp.data or b"$70" in resp.data


# ---------------------------------------------------------------------------
# 404 on missing IDs
# ---------------------------------------------------------------------------

class TestMissingIds:
    def test_edit_se_income_404(self, app, client):
        _login(client, app)
        resp = client.get("/se/income/999999/edit")
        assert resp.status_code == 404

    def test_edit_capital_gain_404(self, app, client):
        _login(client, app)
        resp = client.get("/deductions/capital-gains/999999/edit")
        assert resp.status_code == 404

    def test_edit_mileage_404(self, app, client):
        _login(client, app)
        resp = client.get("/vehicles/mileage/999999/edit")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# HSA Earnings (TaxYear-level CA-only field)
# ---------------------------------------------------------------------------

class TestHSAEarnings:
    def test_save_hsa_earnings_updates_tax_year(self, app, client):
        _login(client, app)
        _get_or_create_year(app)
        resp = client.post(f"/payments/{YEAR}/hsa/earnings", data={
            "ca_hsa_earnings": "375.00",
        }, follow_redirects=False)
        assert resp.status_code == 302
        with app.app_context():
            from app.models import TaxYear
            ty = TaxYear.query.filter_by(year=YEAR).first()
            assert float(ty.ca_hsa_earnings) == pytest.approx(375.0)

    def test_save_hsa_earnings_zero(self, app, client):
        _login(client, app)
        _get_or_create_year(app)
        resp = client.post(f"/payments/{YEAR}/hsa/earnings", data={
            "ca_hsa_earnings": "0",
        }, follow_redirects=False)
        assert resp.status_code == 302
        with app.app_context():
            from app.models import TaxYear
            ty = TaxYear.query.filter_by(year=YEAR).first()
            assert float(ty.ca_hsa_earnings) == pytest.approx(0.0)

    def test_save_hsa_earnings_requires_login(self, client):
        resp = client.post(f"/payments/{YEAR}/hsa/earnings",
                           data={"ca_hsa_earnings": "100"},
                           follow_redirects=False)
        assert resp.status_code == 302
