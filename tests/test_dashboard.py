"""Tests for the dashboard route — TDD, written before implementation."""
import pytest
from werkzeug.security import generate_password_hash
import datetime

YEAR = 2025  # use a unique year to avoid contamination


def _login(client, app, username="dashuser", password="pass"):
    with app.app_context():
        from app import db
        from app.models import User
        if not User.query.filter_by(username=username).first():
            db.session.add(User(username=username, password_hash=generate_password_hash(password)))
            db.session.commit()
    client.post("/auth/login", data={"username": username, "password": password})


def _bootstrap(app):
    """Create a minimal but realistic TaxYear(2025) with some data."""
    with app.app_context():
        from app import db
        from app.models import (
            TaxYear, Employer, Paystub, SelfEmploymentIncome,
            EstimatedTaxPayment, RetirementContribution,
        )
        ty = TaxYear.query.filter_by(year=YEAR).first()
        if not ty:
            ty = TaxYear(
                year=YEAR,
                prior_year_federal_tax=28_000,
                prior_year_ca_tax=7_000,
                prior_year_agi=185_000,
            )
            db.session.add(ty)
            db.session.flush()

            # W-2 employer for Person 1
            emp = Employer(
                tax_year_id=ty.id,
                person="Person 1",
                name="Acme Corp",
                first_paystub_date=datetime.date(YEAR, 1, 3),
            )
            db.session.add(emp)
            db.session.flush()

            # One actual paystub
            stub = Paystub(
                employer_id=emp.id,
                pay_period_start=datetime.date(YEAR, 1, 1),
                pay_period_end=datetime.date(YEAR, 1, 14),
                pay_date=datetime.date(YEAR, 1, 17),
                is_actual=True,
                gross_pay=8_000,
                federal_income_withholding=1_200,
                ss_withholding=496,
                medicare_withholding=116,
                state_income_withholding=480,
                state_disability_withholding=72,
            )
            db.session.add(stub)

            # SE income
            se = SelfEmploymentIncome(
                tax_year_id=ty.id,
                person="Person 2",
                amount=10_000,
                date=datetime.date(YEAR, 3, 1),
                category="consulting",
            )
            db.session.add(se)

            # Estimated Q1 federal payment
            ep = EstimatedTaxPayment(
                tax_year_id=ty.id,
                jurisdiction="federal",
                quarter="Q1",
                amount=3_000,
                date_paid=datetime.date(YEAR, 4, 15),
            )
            db.session.add(ep)

            # Retirement contribution
            rc = RetirementContribution(
                tax_year_id=ty.id,
                person="Person 1",
                account_type="traditional_ira",
                amount=7_000,
                date=datetime.date(YEAR, 4, 15),
            )
            db.session.add(rc)
            db.session.commit()
        return ty.id


class TestDashboard:
    def test_requires_login(self, client):
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code == 302

    def test_redirects_when_no_year(self, app, client):
        """When logged in but current-year bucket doesn't exist, redirect to first available or show empty."""
        _login(client, app, username="noyruser")
        # Should still return 200 (auth created current year on login)
        resp = client.get("/", follow_redirects=True)
        assert resp.status_code == 200

    def test_dashboard_200_with_data(self, app, client):
        _login(client, app)
        _bootstrap(app)
        resp = client.get(f"/?year={YEAR}")
        assert resp.status_code == 200

    def test_dashboard_shows_year(self, app, client):
        _login(client, app)
        _bootstrap(app)
        resp = client.get(f"/?year={YEAR}")
        assert str(YEAR).encode() in resp.data

    def test_dashboard_shows_w2_section(self, app, client):
        _login(client, app)
        _bootstrap(app)
        resp = client.get(f"/?year={YEAR}")
        assert b"W-2" in resp.data or b"w2" in resp.data or b"Acme" in resp.data

    def test_dashboard_shows_federal_tax_estimate(self, app, client):
        _login(client, app)
        _bootstrap(app)
        resp = client.get(f"/?year={YEAR}")
        # Some dollar amount should be present
        assert b"Federal" in resp.data or b"federal" in resp.data

    def test_dashboard_shows_california_tax(self, app, client):
        _login(client, app)
        _bootstrap(app)
        resp = client.get(f"/?year={YEAR}")
        assert b"California" in resp.data or b"CA" in resp.data

    def test_dashboard_shows_safe_harbor_panel(self, app, client):
        _login(client, app)
        _bootstrap(app)
        resp = client.get(f"/?year={YEAR}")
        assert b"safe harbor" in resp.data.lower() or b"Safe Harbor" in resp.data

    def test_dashboard_shows_quarterly_recommendation(self, app, client):
        _login(client, app)
        _bootstrap(app)
        resp = client.get(f"/?year={YEAR}")
        # Should mention quarterly payment recommendation
        assert b"Quarterly" in resp.data or b"quarterly" in resp.data

    def test_dashboard_year_selector_links(self, app, client):
        _login(client, app)
        _bootstrap(app)
        resp = client.get(f"/?year={YEAR}")
        assert b"year" in resp.data.lower()

    def test_dashboard_shows_total_income(self, app, client):
        _login(client, app)
        _bootstrap(app)
        resp = client.get(f"/?year={YEAR}")
        # The dashboard should show some income figures
        assert b"Income" in resp.data or b"income" in resp.data

    def test_invalid_year_404(self, app, client):
        _login(client, app)
        resp = client.get("/?year=1800")
        assert resp.status_code == 404


class TestSummaryRoutes:
    """Smoke tests for /federal-summary and /ca-summary pages."""

    YEAR = 2043

    def _bootstrap(self, app, client):
        _login(client, app, username="sumuser")
        with app.app_context():
            from app import db
            from app.models import TaxYear
            ty = TaxYear.query.filter_by(year=self.YEAR).first()
            if not ty:
                ty = TaxYear(
                    year=self.YEAR,
                    prior_year_federal_tax=20_000,
                    prior_year_ca_tax=5_000,
                    prior_year_agi=150_000,
                )
                db.session.add(ty)
                db.session.commit()

    def test_federal_summary_returns_200(self, app, client):
        self._bootstrap(app, client)
        resp = client.get(f"/federal-summary/{self.YEAR}/")
        assert resp.status_code == 200

    def test_ca_summary_returns_200(self, app, client):
        self._bootstrap(app, client)
        resp = client.get(f"/ca-summary/{self.YEAR}/")
        assert resp.status_code == 200

    def test_federal_summary_requires_login(self, client):
        resp = client.get(f"/federal-summary/{self.YEAR}/", follow_redirects=False)
        assert resp.status_code == 302

    def test_ca_summary_requires_login(self, client):
        resp = client.get(f"/ca-summary/{self.YEAR}/", follow_redirects=False)
        assert resp.status_code == 302

    def test_federal_summary_shows_agi(self, app, client):
        self._bootstrap(app, client)
        resp = client.get(f"/federal-summary/{self.YEAR}/")
        assert b"Adjusted Gross Income" in resp.data or b"AGI" in resp.data

    def test_ca_summary_shows_ca_agi(self, app, client):
        self._bootstrap(app, client)
        resp = client.get(f"/ca-summary/{self.YEAR}/")
        assert b"California" in resp.data
