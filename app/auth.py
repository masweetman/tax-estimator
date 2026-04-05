import datetime
import io
import base64
from urllib.parse import urlparse

import pyotp
import qrcode
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_safe_url(target: str) -> bool:
    """Return True only for relative URL paths (no scheme or external host)."""
    if not target:
        return False
    parts = urlparse(target)
    return not parts.scheme and not parts.netloc


def _generate_qr_b64(uri: str) -> str:
    """Render a TOTP provisioning URI as a base64-encoded PNG."""
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ---------------------------------------------------------------------------
# Standard login / logout
# ---------------------------------------------------------------------------

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    from app.models import User
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            if user.totp_enabled:
                # Password is correct but 2FA is required.  Store the user id
                # in the session (not yet logged in) and send to TOTP verify.
                session["pending_2fa_user_id"] = user.id
                next_url = request.args.get("next", "")
                # Validate the next URL now so we don't carry an unsafe value.
                session["next_url"] = next_url if _is_safe_url(next_url) else ""
                return redirect(url_for("auth.totp_verify"))
            # No 2FA — log in immediately.
            login_user(user)
            _ensure_current_year_exists()
            return redirect(url_for("dashboard.index"))
        flash("Invalid username or password.", "danger")
    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


# ---------------------------------------------------------------------------
# 2FA setup (requires an already-authenticated session)
# ---------------------------------------------------------------------------

@auth_bp.route("/2fa/setup", methods=["GET", "POST"])
@login_required
def totp_setup():
    from app import db

    if request.method == "POST":
        token = request.form.get("token", "").strip()
        secret = current_user.totp_secret
        # Verify the submitted code against the stored secret.
        if secret and pyotp.TOTP(secret).verify(token, valid_window=1):
            current_user.totp_enabled = True
            db.session.commit()
            flash("Two-factor authentication has been enabled.", "success")
            return redirect(url_for("profile.profile"))
        flash("Invalid code — please try again.", "danger")
        return redirect(url_for("auth.totp_setup"))

    # GET: generate and persist a secret if the user doesn't have one yet.
    # The secret is saved immediately so the same QR is shown on page refresh.
    # totp_enabled stays False until the user successfully verifies a code.
    if current_user.totp_secret is None:
        current_user.totp_secret = pyotp.random_base32()
        db.session.commit()

    uri = pyotp.TOTP(current_user.totp_secret).provisioning_uri(
        name=current_user.username,
        issuer_name="Tax Estimator",
    )
    qr_b64 = _generate_qr_b64(uri)
    return render_template(
        "auth/2fa_setup.html",
        qr_b64=qr_b64,
        secret=current_user.totp_secret,
    )


# ---------------------------------------------------------------------------
# 2FA verify (called after password check, before login_user())
# ---------------------------------------------------------------------------

@auth_bp.route("/2fa/verify", methods=["GET", "POST"])
def totp_verify():
    from app import db
    from app.models import User

    # Guard: if there is no pending user in the session, send back to login.
    user_id = session.get("pending_2fa_user_id")
    if not user_id:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        token = request.form.get("token", "").strip()
        user = db.session.get(User, user_id)
        if user and pyotp.TOTP(user.totp_secret).verify(token, valid_window=1):
            # Code is correct — clean up the temporary session state and log in.
            next_url = session.pop("next_url", "")
            session.pop("pending_2fa_user_id", None)
            login_user(user)
            _ensure_current_year_exists()
            target = next_url if _is_safe_url(next_url) else url_for("dashboard.index")
            return redirect(target)
        # Wrong code — flash and stay on this page (session key is preserved
        # so the user can retry without re-entering their password).
        flash("Invalid code — please try again.", "danger")
        return redirect(url_for("auth.totp_verify"))

    return render_template("auth/2fa_verify.html")


# ---------------------------------------------------------------------------
# 2FA disable (requires an already-authenticated session)
# ---------------------------------------------------------------------------

@auth_bp.route("/2fa/disable", methods=["POST"])
@login_required
def totp_disable():
    from app import db

    if not current_user.totp_enabled:
        flash("Two-factor authentication is not currently enabled.", "warning")
        return redirect(url_for("profile.profile"))

    current_user.totp_enabled = False
    current_user.totp_secret = None
    db.session.commit()
    flash("Two-factor authentication has been disabled.", "success")
    return redirect(url_for("profile.profile"))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_current_year_exists():
    """Create a TaxYear for the current calendar year if one doesn't exist."""
    from app import db
    from app.models import TaxYear
    year = datetime.date.today().year
    if not TaxYear.query.filter_by(year=year).first():
        db.session.add(TaxYear(year=year))
        db.session.commit()
