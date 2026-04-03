"""Tests for authentication and tax year bootstrap — written before implementation (TDD)."""
import pytest
from werkzeug.security import generate_password_hash


def seed_user(app, username="testuser", password="testpass"):
    """Create the test user if it doesn't exist."""
    with app.app_context():
        from app import db
        from app.models import User
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(username=username, password_hash=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()


# ---------------------------------------------------------------------------
# Login / logout
# ---------------------------------------------------------------------------

class TestLoginPage:
    def test_login_page_returns_200(self, client):
        resp = client.get("/auth/login")
        assert resp.status_code == 200

    def test_login_page_contains_form(self, client):
        resp = client.get("/auth/login")
        assert b"<form" in resp.data


class TestLoginPost:
    def test_valid_credentials_redirect_to_dashboard(self, app, client):
        seed_user(app)
        resp = client.post(
            "/auth/login",
            data={"username": "testuser", "password": "testpass"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        loc = resp.headers["Location"]
        assert loc == "/" or "/dashboard" in loc

    def test_invalid_password_returns_200_with_error(self, app, client):
        seed_user(app)
        resp = client.post(
            "/auth/login",
            data={"username": "testuser", "password": "wrongpass"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Invalid" in resp.data or b"incorrect" in resp.data.lower() or b"wrong" in resp.data.lower()

    def test_nonexistent_user_returns_200_with_error(self, app, client):
        resp = client.post(
            "/auth/login",
            data={"username": "nobody", "password": "nopass"},
            follow_redirects=True,
        )
        assert resp.status_code == 200


class TestLogout:
    def test_logout_redirects_to_login(self, app, client):
        seed_user(app)
        client.post("/auth/login", data={"username": "testuser", "password": "testpass"})
        resp = client.get("/auth/logout", follow_redirects=False)
        assert resp.status_code == 302
        assert "login" in resp.headers["Location"]


# ---------------------------------------------------------------------------
# @login_required enforcement
# ---------------------------------------------------------------------------

class TestLoginRequired:
    def test_dashboard_redirects_unauthenticated(self, client):
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code == 302
        assert "login" in resp.headers["Location"]

    def test_dashboard_accessible_when_logged_in(self, app, client):
        seed_user(app)
        client.post("/auth/login", data={"username": "testuser", "password": "testpass"})
        resp = client.get("/", follow_redirects=True)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Current-year auto-creation on first login
# ---------------------------------------------------------------------------

class TestYearAutoCreate:
    def test_current_year_created_on_first_login(self, app, client):
        import datetime
        seed_user(app)

        # Clear any existing tax year for current year
        with app.app_context():
            from app import db
            from app.models import TaxYear
            current_year = datetime.date.today().year
            existing = TaxYear.query.filter_by(year=current_year).first()
            if existing:
                db.session.delete(existing)
                db.session.commit()

        client.post("/auth/login", data={"username": "testuser", "password": "testpass"})

        with app.app_context():
            from app.models import TaxYear
            import datetime
            ty = TaxYear.query.filter_by(year=datetime.date.today().year).first()
            assert ty is not None, "Current year TaxYear should be auto-created on login"

    def test_year_not_duplicated_on_second_login(self, app, client):
        import datetime
        seed_user(app)
        client.post("/auth/login", data={"username": "testuser", "password": "testpass"})
        client.get("/auth/logout")
        client.post("/auth/login", data={"username": "testuser", "password": "testpass"})

        with app.app_context():
            from app.models import TaxYear
            current_year = datetime.date.today().year
            count = TaxYear.query.filter_by(year=current_year).count()
            assert count == 1, f"Expected 1 TaxYear for {current_year}, found {count}"
