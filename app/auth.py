import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash
import pyotp

from app import db

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

_TOTP_PENDING_KEY = "_totp_pending_user_id"


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    from app.models import User
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            if user.totp_enabled:
                session[_TOTP_PENDING_KEY] = user.id
                return redirect(url_for("auth.totp_verify"))
            login_user(user)
            _ensure_current_year_exists()
            return redirect(url_for("dashboard.index"))
        flash("Invalid username or password.", "danger")
    return render_template("auth/login.html")


@auth_bp.route("/totp", methods=["GET", "POST"])
def totp_verify():
    from app.models import User
    user_id = session.get(_TOTP_PENDING_KEY)
    if not user_id:
        return redirect(url_for("auth.login"))
    user = db.session.get(User, user_id)
    if not user or not user.totp_enabled:
        session.pop(_TOTP_PENDING_KEY, None)
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        code = request.form.get("totp_code", "").strip()
        totp = pyotp.TOTP(user.totp_secret)
        if totp.verify(code, valid_window=1):
            session.pop(_TOTP_PENDING_KEY, None)
            login_user(user)
            _ensure_current_year_exists()
            return redirect(url_for("dashboard.index"))
        flash("Invalid verification code. Please try again.", "danger")
    return render_template("auth/totp.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


def _ensure_current_year_exists():
    """Create a TaxYear for the current calendar year if one doesn't exist."""
    from app.models import TaxYear
    year = datetime.date.today().year
    if not TaxYear.query.filter_by(year=year).first():
        db.session.add(TaxYear(year=year))
        db.session.commit()
