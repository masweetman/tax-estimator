import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    from app.models import User
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
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


def _ensure_current_year_exists():
    """Create a TaxYear for the current calendar year if one doesn't exist."""
    from app import db
    from app.models import TaxYear
    year = datetime.date.today().year
    if not TaxYear.query.filter_by(year=year).first():
        db.session.add(TaxYear(year=year))
        db.session.commit()
