"""Tests for W-2 employer and paystub routes — written before implementation (TDD)."""
import datetime
import pytest
from werkzeug.security import generate_password_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIRST_PAYSTUB_2026 = datetime.date(2026, 1, 2)  # Friday; 26 bi-weekly pay dates in 2026


def _login(client, app):
    with app.app_context():
        from app import db
        from app.models import User
        if not User.query.filter_by(username="w2user").first():
            db.session.add(User(username="w2user", password_hash=generate_password_hash("pass")))
            db.session.commit()
    client.post("/auth/login", data={"username": "w2user", "password": "pass"})


def _make_tax_year(app, year=2026):
    with app.app_context():
        from app import db
        from app.models import TaxYear
        ty = TaxYear.query.filter_by(year=year).first()
        if not ty:
            ty = TaxYear(year=year)
            db.session.add(ty)
            db.session.commit()
        return ty.id


def _make_employer(app, tax_year_id, person="Person 1", name="Acme Corp",
                   first_date=FIRST_PAYSTUB_2026):
    with app.app_context():
        from app import db
        from app.models import Employer
        emp = Employer(
            tax_year_id=tax_year_id,
            person=person,
            name=name,
            first_paystub_date=first_date,
        )
        db.session.add(emp)
        db.session.commit()
        return emp.id


# ---------------------------------------------------------------------------
# Employer CRUD
# ---------------------------------------------------------------------------

class TestEmployerRoutes:
    def test_employer_list_requires_login(self, client):
        resp = client.get("/w2/employers/2026", follow_redirects=False)
        assert resp.status_code == 302

    def test_employer_list_returns_200(self, app, client):
        _login(client, app)
        _make_tax_year(app)
        resp = client.get("/w2/employers/2026")
        assert resp.status_code == 200

    def test_add_employer_page_returns_200(self, app, client):
        _login(client, app)
        _make_tax_year(app)
        resp = client.get("/w2/employers/2026/add")
        assert resp.status_code == 200

    def test_add_employer_creates_record_and_redirects(self, app, client):
        _login(client, app)
        _make_tax_year(app)
        resp = client.post(
            "/w2/employers/2026/add",
            data={
                "person": "Person 1",
                "name": "Test Corp",
                "first_paystub_date": "2026-01-02",
                "is_covered_by_retirement_plan": "true",
                "notes": "",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        with app.app_context():
            from app.models import Employer, TaxYear
            ty = TaxYear.query.filter_by(year=2026).first()
            emp = Employer.query.filter_by(tax_year_id=ty.id, name="Test Corp").first()
            assert emp is not None

    def test_delete_employer_removes_record(self, app, client):
        _login(client, app)
        ty_id = _make_tax_year(app)
        emp_id = _make_employer(app, ty_id, name="Delete Me")
        resp = client.post(f"/w2/employers/{emp_id}/delete", follow_redirects=False)
        assert resp.status_code == 302
        with app.app_context():
            from app import db
            from app.models import Employer
            assert db.session.get(Employer, emp_id) is None


# ---------------------------------------------------------------------------
# Paystub auto-generation
# ---------------------------------------------------------------------------

class TestPaystubGeneration:
    def test_26_stubs_generated_for_full_year(self, app, client):
        """Starting Jan 2 2026 bi-weekly → 26 pay dates within 2026."""
        _login(client, app)
        ty_id = _make_tax_year(app)
        client.post(
            "/w2/employers/2026/add",
            data={
                "person": "Person 1",
                "name": "GenCorp",
                "first_paystub_date": "2026-01-02",
                "is_covered_by_retirement_plan": "true",
                "notes": "",
            },
        )
        with app.app_context():
            from app.models import Employer, Paystub, TaxYear
            ty = TaxYear.query.filter_by(year=2026).first()
            emp = Employer.query.filter_by(tax_year_id=ty.id, name="GenCorp").first()
            assert emp is not None
            stubs = Paystub.query.filter_by(employer_id=emp.id).all()
            assert len(stubs) == 26, f"Expected 26 stubs, got {len(stubs)}"

    def test_all_generated_stubs_are_estimated(self, app, client):
        _login(client, app)
        ty_id = _make_tax_year(app)
        emp_id = _make_employer(app, ty_id, name="EstCorp2")
        # Trigger generation via the route (employer already created via helper; use route too)
        client.post(
            "/w2/employers/2026/add",
            data={
                "person": "Person 2",
                "name": "EstCorp",
                "first_paystub_date": "2026-01-02",
                "is_covered_by_retirement_plan": "false",
                "notes": "",
            },
        )
        with app.app_context():
            from app.models import Employer, Paystub, TaxYear
            ty = TaxYear.query.filter_by(year=2026).first()
            emp = Employer.query.filter_by(tax_year_id=ty.id, name="EstCorp").first()
            stubs = Paystub.query.filter_by(employer_id=emp.id).all()
            assert all(not s.is_actual for s in stubs)

    def test_all_stubs_have_zero_amounts(self, app, client):
        _login(client, app)
        ty_id = _make_tax_year(app)
        client.post(
            "/w2/employers/2026/add",
            data={
                "person": "Person 1",
                "name": "ZeroCorp",
                "first_paystub_date": "2026-01-02",
                "is_covered_by_retirement_plan": "true",
                "notes": "",
            },
        )
        with app.app_context():
            from app.models import Employer, Paystub, TaxYear
            ty = TaxYear.query.filter_by(year=2026).first()
            emp = Employer.query.filter_by(tax_year_id=ty.id, name="ZeroCorp").first()
            for stub in emp.paystubs:
                assert float(stub.gross_pay) == 0.0


# ---------------------------------------------------------------------------
# Paystub propagation
# ---------------------------------------------------------------------------

class TestPaystubPropagation:
    def _setup_employer_with_stubs(self, app, client, name="PropCorp"):
        _login(client, app)
        ty_id = _make_tax_year(app)
        client.post(
            "/w2/employers/2026/add",
            data={
                "person": "Person 1",
                "name": name,
                "first_paystub_date": "2026-01-02",
                "is_covered_by_retirement_plan": "true",
                "notes": "",
            },
        )
        with app.app_context():
            from app.models import Employer, TaxYear
            ty = TaxYear.query.filter_by(year=2026).first()
            emp = Employer.query.filter_by(tax_year_id=ty.id, name=name).first()
            stub_ids = [s.id for s in emp.paystubs]
        return stub_ids

    def test_saving_actual_paystub_propagates_to_later_estimated_stubs(self, app, client):
        stub_ids = self._setup_employer_with_stubs(app, client, name="PropA")
        first_id = stub_ids[0]

        resp = client.post(
            f"/w2/paystubs/{first_id}/edit",
            data={
                "gross_pay": "5000.00",
                "federal_income_withholding": "600.00",
                "ss_withholding": "310.00",
                "medicare_withholding": "72.50",
                "state_income_withholding": "250.00",
                "state_disability_withholding": "50.00",
                "medical_insurance": "100.00",
                "dental_insurance": "20.00",
                "vision_insurance": "5.00",
                "pretax_401k": "200.00",
                "roth_401k": "0.00",
                "dependent_care_fsa": "0.00",
                "healthcare_fsa": "0.00",
                "notes": "",
                "is_actual": "true",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302

        with app.app_context():
            from app import db
            from app.models import Paystub
            # First stub: actual
            first = db.session.get(Paystub, first_id)
            assert first.is_actual is True
            assert float(first.gross_pay) == 5000.00

            # All subsequent stubs: estimated, copied values
            for sid in stub_ids[1:]:
                stub = db.session.get(Paystub, sid)
                assert stub.is_actual is False
                assert float(stub.gross_pay) == 5000.00, f"Stub {sid} gross_pay not propagated"

    def test_earlier_stubs_not_affected_by_propagation(self, app, client):
        stub_ids = self._setup_employer_with_stubs(app, client, name="PropB")

        # Mark stub[0] actual with $5000
        client.post(
            f"/w2/paystubs/{stub_ids[0]}/edit",
            data={
                "gross_pay": "5000.00",
                "federal_income_withholding": "600.00",
                "ss_withholding": "310.00",
                "medicare_withholding": "72.50",
                "state_income_withholding": "250.00",
                "state_disability_withholding": "50.00",
                "medical_insurance": "100.00",
                "dental_insurance": "20.00",
                "vision_insurance": "5.00",
                "pretax_401k": "200.00",
                "roth_401k": "0.00",
                "dependent_care_fsa": "0.00",
                "healthcare_fsa": "0.00",
                "notes": "",
                "is_actual": "true",
            },
        )
        # Mark stub[2] actual with $6000
        client.post(
            f"/w2/paystubs/{stub_ids[2]}/edit",
            data={
                "gross_pay": "6000.00",
                "federal_income_withholding": "700.00",
                "ss_withholding": "372.00",
                "medicare_withholding": "87.00",
                "state_income_withholding": "300.00",
                "state_disability_withholding": "60.00",
                "medical_insurance": "100.00",
                "dental_insurance": "20.00",
                "vision_insurance": "5.00",
                "pretax_401k": "200.00",
                "roth_401k": "0.00",
                "dependent_care_fsa": "0.00",
                "healthcare_fsa": "0.00",
                "notes": "",
                "is_actual": "true",
            },
        )

        with app.app_context():
            from app import db
            from app.models import Paystub
            # stub[1] was estimated with $5000 from first propagation; stub[2] is now actual $6000
            # stub[1] should still be $5000 (not overwritten by stub[2] propagation)
            stub1 = db.session.get(Paystub, stub_ids[1])
            assert float(stub1.gross_pay) == 5000.00, "Earlier stub should not be retroactively changed"
            # stubs[3+] should now reflect $6000
            stub3 = db.session.get(Paystub, stub_ids[3])
            assert float(stub3.gross_pay) == 6000.00

    def test_paystub_list_returns_200(self, app, client):
        stub_ids = self._setup_employer_with_stubs(app, client, name="ListCorp")
        with app.app_context():
            from app import db
            from app.models import Paystub
            stub = db.session.get(Paystub, stub_ids[0])
            emp_id = stub.employer_id
        resp = client.get(f"/w2/employers/{emp_id}/paystubs")
        assert resp.status_code == 200

    def test_paystub_edit_page_returns_200(self, app, client):
        stub_ids = self._setup_employer_with_stubs(app, client, name="EditCorp")
        resp = client.get(f"/w2/paystubs/{stub_ids[0]}/edit")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Custom fields
# ---------------------------------------------------------------------------

class TestCustomFields:
    def test_add_custom_field_def(self, app, client):
        _login(client, app)
        ty_id = _make_tax_year(app)
        emp_id = _make_employer(app, ty_id, name="CustomCorp")
        resp = client.post(
            f"/w2/employers/{emp_id}/custom-fields/add",
            data={"field_name": "Commuter Benefit", "sort_order": "0"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        with app.app_context():
            from app.models import PaystubCustomFieldDef
            fd = PaystubCustomFieldDef.query.filter_by(employer_id=emp_id, field_name="Commuter Benefit").first()
            assert fd is not None

    def test_custom_field_value_saved_with_paystub(self, app, client):
        _login(client, app)
        ty_id = _make_tax_year(app)
        client.post(
            "/w2/employers/2026/add",
            data={
                "person": "Person 1",
                "name": "CFCorp",
                "first_paystub_date": "2026-01-02",
                "is_covered_by_retirement_plan": "true",
                "notes": "",
            },
        )
        with app.app_context():
            from app.models import Employer, TaxYear, PaystubCustomFieldDef
            ty = TaxYear.query.filter_by(year=2026).first()
            emp = Employer.query.filter_by(tax_year_id=ty.id, name="CFCorp").first()
            emp_id = emp.id
            stub_id = emp.paystubs[0].id

        # Add a custom field def
        client.post(
            f"/w2/employers/{emp_id}/custom-fields/add",
            data={"field_name": "Parking", "sort_order": "0"},
        )
        with app.app_context():
            from app.models import PaystubCustomFieldDef
            fd = PaystubCustomFieldDef.query.filter_by(employer_id=emp_id).first()
            fd_id = fd.id

        # Save paystub with custom field value
        resp = client.post(
            f"/w2/paystubs/{stub_id}/edit",
            data={
                "gross_pay": "5000.00",
                "federal_income_withholding": "600.00",
                "ss_withholding": "310.00",
                "medicare_withholding": "72.50",
                "state_income_withholding": "250.00",
                "state_disability_withholding": "50.00",
                "medical_insurance": "100.00",
                "dental_insurance": "20.00",
                "vision_insurance": "5.00",
                "pretax_401k": "200.00",
                "roth_401k": "0.00",
                "dependent_care_fsa": "0.00",
                "healthcare_fsa": "0.00",
                "notes": "",
                "is_actual": "true",
                f"custom_{fd_id}": "75.00",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        with app.app_context():
            from app.models import PaystubCustomFieldValue
            val = PaystubCustomFieldValue.query.filter_by(
                paystub_id=stub_id, field_def_id=fd_id
            ).first()
            assert val is not None
            assert float(val.amount) == 75.00
