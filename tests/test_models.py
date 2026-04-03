"""Tests for database models — written before model implementation (TDD)."""
import pytest
from sqlalchemy import inspect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def table_names(app):
    with app.app_context():
        from app import db
        inspector = inspect(db.engine)
        return set(inspector.get_table_names())


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestTablesExist:
    EXPECTED_TABLES = {
        "user",
        "tax_year",
        "employer",
        "paystub",
        "paystub_custom_field_def",
        "paystub_custom_field_value",
        "self_employment_income",
        "self_employment_expense",
        "capital_gain",
        "deduction",
        "child_care_expense",
        "estimated_tax_payment",
        "vehicle_mileage",
        "retirement_contribution",
        "insurance_premium",
        "hsa_contribution",
    }

    def test_all_tables_created(self, app):
        names = table_names(app)
        missing = self.EXPECTED_TABLES - names
        assert not missing, f"Missing tables: {missing}"


class TestTaxYearFields:
    def test_has_prior_year_fields(self, app):
        with app.app_context():
            from app import db
            inspector = inspect(db.engine)
            cols = {c["name"] for c in inspector.get_columns("tax_year")}
        assert "prior_year_federal_tax" in cols
        assert "prior_year_ca_tax" in cols
        assert "prior_year_agi" in cols

    def test_prior_year_fields_nullable(self, app):
        with app.app_context():
            from app.models import TaxYear
            # prior_year fields must accept None; use a year no other test touches
            ty = TaxYear(year=9998)
            from app import db
            db.session.add(ty)
            db.session.commit()
            assert ty.prior_year_federal_tax is None
            assert ty.prior_year_ca_tax is None
            assert ty.prior_year_agi is None
            db.session.delete(ty)
            db.session.commit()


class TestEmployerFields:
    def test_has_retirement_plan_flag(self, app):
        with app.app_context():
            from app import db
            inspector = inspect(db.engine)
            cols = {c["name"]: c for c in inspector.get_columns("employer")}
        assert "is_covered_by_retirement_plan" in cols

    def test_retirement_plan_defaults_true(self, app):
        with app.app_context():
            from app import db
            from app.models import TaxYear, Employer
            import datetime
            ty = TaxYear(year=2099)
            db.session.add(ty)
            db.session.flush()
            emp = Employer(
                tax_year_id=ty.id,
                person="Person 1",
                name="Acme Corp",
                first_paystub_date=datetime.date(2099, 1, 3),
            )
            db.session.add(emp)
            db.session.commit()
            assert emp.is_covered_by_retirement_plan is True
            db.session.delete(ty)
            db.session.commit()


# ---------------------------------------------------------------------------
# Cascade delete tests
# ---------------------------------------------------------------------------

class TestCascadeDeletes:
    def test_delete_tax_year_cascades_to_employers(self, app):
        with app.app_context():
            from app import db
            from app.models import TaxYear, Employer
            import datetime
            ty = TaxYear(year=2098)
            db.session.add(ty)
            db.session.flush()
            emp = Employer(
                tax_year_id=ty.id,
                person="Person 1",
                name="Cascade Corp",
                first_paystub_date=datetime.date(2098, 1, 3),
            )
            db.session.add(emp)
            db.session.commit()
            emp_id = emp.id

            db.session.delete(ty)
            db.session.commit()
            assert db.session.get(Employer, emp_id) is None

    def test_delete_employer_cascades_to_paystubs(self, app):
        with app.app_context():
            from app import db
            from app.models import TaxYear, Employer, Paystub
            import datetime
            ty = TaxYear(year=2097)
            db.session.add(ty)
            db.session.flush()
            emp = Employer(
                tax_year_id=ty.id,
                person="Person 1",
                name="Stub Corp",
                first_paystub_date=datetime.date(2097, 1, 3),
            )
            db.session.add(emp)
            db.session.flush()
            stub = Paystub(
                employer_id=emp.id,
                pay_period_start=datetime.date(2097, 1, 3),
                pay_period_end=datetime.date(2097, 1, 16),
                pay_date=datetime.date(2097, 1, 17),
                is_actual=False,
            )
            db.session.add(stub)
            db.session.commit()
            stub_id = stub.id

            db.session.delete(ty)
            db.session.commit()
            assert db.session.get(Paystub, stub_id) is None

    def test_delete_tax_year_cascades_to_all_data_models(self, app):
        """Spot-check that TaxYear deletion removes child records across tables."""
        with app.app_context():
            from app import db
            from app.models import (
                TaxYear, SelfEmploymentIncome, CapitalGain,
                Deduction, EstimatedTaxPayment, HSAContribution,
            )
            import datetime
            ty = TaxYear(year=2096)
            db.session.add(ty)
            db.session.flush()

            sei = SelfEmploymentIncome(tax_year_id=ty.id, person="Person 1", client="Client A", amount=5000, date=datetime.date(2096, 3, 1), category="consulting")
            cg = CapitalGain(tax_year_id=ty.id, person="Person 1", description="AAPL", proceeds=10000, cost_basis=8000, acquisition_date=datetime.date(2095, 1, 1), sale_date=datetime.date(2096, 6, 1), is_long_term=True)
            ded = Deduction(tax_year_id=ty.id, category="mortgage_interest", description="Mortgage", amount=12000, date=datetime.date(2096, 12, 31))
            etp = EstimatedTaxPayment(tax_year_id=ty.id, jurisdiction="federal", quarter="Q1", amount=3000, date_paid=datetime.date(2096, 4, 15))
            hsa = HSAContribution(tax_year_id=ty.id, person="Person 1", amount=500, date=datetime.date(2096, 2, 1))

            db.session.add_all([sei, cg, ded, etp, hsa])
            db.session.commit()
            ids = (sei.id, cg.id, ded.id, etp.id, hsa.id)

            db.session.delete(ty)
            db.session.commit()

            assert db.session.get(SelfEmploymentIncome, ids[0]) is None
            assert db.session.get(CapitalGain, ids[1]) is None
            assert db.session.get(Deduction, ids[2]) is None
            assert db.session.get(EstimatedTaxPayment, ids[3]) is None
            assert db.session.get(HSAContribution, ids[4]) is None


# ---------------------------------------------------------------------------
# User model
# ---------------------------------------------------------------------------

class TestUserModel:
    def test_user_password_hash_stored(self, app):
        with app.app_context():
            from app import db
            from app.models import User
            from werkzeug.security import generate_password_hash, check_password_hash
            u = User(username="modeltest", password_hash=generate_password_hash("secret"))
            db.session.add(u)
            db.session.commit()
            fetched = User.query.filter_by(username="modeltest").first()
            assert fetched is not None
            assert check_password_hash(fetched.password_hash, "secret")
            db.session.delete(fetched)
            db.session.commit()

    def test_user_implements_flask_login_interface(self, app):
        with app.app_context():
            from app.models import User
            from flask_login import UserMixin
            assert issubclass(User, UserMixin)
