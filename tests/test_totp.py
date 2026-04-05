"""Tests for TOTP two-factor authentication — setup, login, and management."""
import pytest
import pyotp
from werkzeug.security import generate_password_hash


def seed_user_with_totp(app, username="totpuser", password="totppass", enabled=True):
    """Create a test user with TOTP enabled (or disabled)."""
    with app.app_context():
        from app import db
        from app.models import User
        user = User.query.filter_by(username=username).first()
        if not user:
            secret = pyotp.random_base32()
            user = User(
                username=username,
                password_hash=generate_password_hash(password),
                totp_secret=secret,
                totp_enabled=enabled,
            )
            db.session.add(user)
            db.session.commit()


def seed_user_no_totp(app, username="plainuser", password="plainpass"):
    """Create a test user without TOTP."""
    with app.app_context():
        from app import db
        from app.models import User
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(
                username=username,
                password_hash=generate_password_hash(password),
            )
            db.session.add(user)
            db.session.commit()


# ---------------------------------------------------------------------------
# Login with 2FA not enabled (existing behaviour preserved)
# ---------------------------------------------------------------------------

class TestLoginWithoutTOTP:
    def test_valid_credentials_redirect_to_dashboard(self, app, client):
        seed_user_no_totp(app)
        resp = client.post(
            "/auth/login",
            data={"username": "plainuser", "password": "plainpass"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        loc = resp.headers["Location"]
        assert loc == "/" or "/dashboard" in loc

    def test_does_not_redirect_to_totp_page(self, app, client):
        seed_user_no_totp(app)
        resp = client.post(
            "/auth/login",
            data={"username": "plainuser", "password": "plainpass"},
            follow_redirects=False,
        )
        assert "/totp" not in resp.headers["Location"]


# ---------------------------------------------------------------------------
# Login with 2FA enabled — redirects to TOTP verification page
# ---------------------------------------------------------------------------

class TestLoginWithTOTP:
    def test_redirects_to_totp_page_when_enabled(self, app, client):
        seed_user_with_totp(app)
        resp = client.post(
            "/auth/login",
            data={"username": "totpuser", "password": "totppass"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/auth/totp" in resp.headers["Location"]

    def test_totp_page_returns_200(self, app, client):
        seed_user_with_totp(app)
        client.post(
            "/auth/login",
            data={"username": "totpuser", "password": "totppass"},
        )
        resp = client.get("/auth/totp")
        assert resp.status_code == 200
        assert b"<form" in resp.data

    def test_valid_totp_code_completes_login(self, app, client):
        seed_user_with_totp(app)
        client.post(
            "/auth/login",
            data={"username": "totpuser", "password": "totppass"},
        )
        with app.app_context():
            from app.models import User
            user = User.query.filter_by(username="totpuser").first()
            code = pyotp.TOTP(user.totp_secret).now()
        resp = client.post(
            "/auth/totp",
            data={"totp_code": code},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        loc = resp.headers["Location"]
        assert loc == "/" or "/dashboard" in loc

    def test_invalid_totp_code_shows_error(self, app, client):
        seed_user_with_totp(app)
        client.post(
            "/auth/login",
            data={"username": "totpuser", "password": "totppass"},
        )
        resp = client.post(
            "/auth/totp",
            data={"totp_code": "000000"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Invalid" in resp.data

    def test_totp_page_without_pending_session_redirects_to_login(self, app, client):
        resp = client.get("/auth/totp", follow_redirects=False)
        assert resp.status_code == 302
        assert "login" in resp.headers["Location"]

    def test_wrong_password_does_not_reach_totp_page(self, app, client):
        seed_user_with_totp(app)
        resp = client.post(
            "/auth/login",
            data={"username": "totpuser", "password": "wrongpass"},
            follow_redirects=False,
        )
        assert "/totp" not in resp.headers.get("Location", "")


# ---------------------------------------------------------------------------
# 2FA setup page — GET /profile/totp/setup
# ---------------------------------------------------------------------------

class TestTOTPSetupPage:
    def _login(self, app, client, username="setupuser", password="setuppass"):
        seed_user_no_totp(app, username=username, password=password)
        client.post("/auth/login", data={"username": username, "password": password})

    def test_setup_page_returns_200(self, app, client):
        self._login(app, client)
        resp = client.get("/profile/totp/setup")
        assert resp.status_code == 200

    def test_setup_page_contains_qr_code(self, app, client):
        self._login(app, client)
        resp = client.get("/profile/totp/setup")
        assert b"data:image/png;base64," in resp.data

    def test_setup_page_contains_secret(self, app, client):
        self._login(app, client)
        resp = client.get("/profile/totp/setup")
        assert b"<code" in resp.data

    def test_setup_page_requires_login(self, client):
        resp = client.get("/profile/totp/setup", follow_redirects=False)
        assert resp.status_code == 302
        assert "login" in resp.headers["Location"]


# ---------------------------------------------------------------------------
# Enable 2FA — POST /profile/totp/enable
# ---------------------------------------------------------------------------

class TestTOTPEnable:
    def _login_and_get_setup_secret(self, app, client, username="enableuser", password="enablepass"):
        seed_user_no_totp(app, username=username, password=password)
        client.post("/auth/login", data={"username": username, "password": password})
        client.get("/profile/totp/setup")  # populates session secret
        with client.session_transaction() as sess:
            return sess.get("_totp_setup_secret")

    def test_valid_code_enables_totp(self, app, client):
        secret = self._login_and_get_setup_secret(app, client)
        assert secret is not None
        code = pyotp.TOTP(secret).now()
        resp = client.post(
            "/profile/totp/enable",
            data={"totp_code": code},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"enabled" in resp.data.lower()
        with app.app_context():
            from app.models import User
            user = User.query.filter_by(username="enableuser").first()
            assert user.totp_enabled is True
            assert user.totp_secret == secret

    def test_invalid_code_does_not_enable_totp(self, app, client):
        self._login_and_get_setup_secret(app, client, username="enableuser2", password="enablepass2")
        resp = client.post(
            "/profile/totp/enable",
            data={"totp_code": "000000"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        with app.app_context():
            from app.models import User
            user = User.query.filter_by(username="enableuser2").first()
            assert not user.totp_enabled


# ---------------------------------------------------------------------------
# Disable 2FA — POST /profile/totp/disable
# ---------------------------------------------------------------------------

class TestTOTPDisable:
    def _login_totp_user(self, app, client, username="disableuser", password="disablepass"):
        seed_user_with_totp(app, username=username, password=password)
        client.post("/auth/login", data={"username": username, "password": password})
        with app.app_context():
            from app.models import User
            user = User.query.filter_by(username=username).first()
            code = pyotp.TOTP(user.totp_secret).now()
        client.post("/auth/totp", data={"totp_code": code})

    def test_correct_password_disables_totp(self, app, client):
        self._login_totp_user(app, client)
        resp = client.post(
            "/profile/totp/disable",
            data={"password": "disablepass"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"disabled" in resp.data.lower()
        with app.app_context():
            from app.models import User
            user = User.query.filter_by(username="disableuser").first()
            assert not user.totp_enabled
            assert user.totp_secret is None

    def test_wrong_password_does_not_disable_totp(self, app, client):
        self._login_totp_user(app, client, username="disableuser2", password="disablepass2")
        resp = client.post(
            "/profile/totp/disable",
            data={"password": "wrongpass"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        with app.app_context():
            from app.models import User
            user = User.query.filter_by(username="disableuser2").first()
            assert user.totp_enabled is True
