"""Tax year creation route."""
import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required

from app import db
from app.models import TaxYear

tax_years_bp = Blueprint("tax_years", __name__, url_prefix="/tax-years")

_EARLIEST_YEAR = 2010


@tax_years_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    current_year = datetime.date.today().year

    if request.method == "POST":
        year_str = request.form.get("year", "").strip()
        try:
            year = int(year_str)
        except (ValueError, TypeError):
            flash("Please enter a valid year.", "danger")
            return render_template("tax_years/new.html", current_year=current_year)

        if year < _EARLIEST_YEAR or year > current_year:
            flash(f"Year must be between {_EARLIEST_YEAR} and {current_year}.", "danger")
            return render_template("tax_years/new.html", current_year=current_year)

        existing = TaxYear.query.filter_by(year=year).first()
        if existing:
            flash(
                f"{year} already exists.",
                "warning",
            )
            return render_template(
                "tax_years/new.html",
                current_year=current_year,
                existing_year=year,
            )

        ty = TaxYear(
            year=year,
            prior_year_federal_tax=_parse_decimal(request.form.get("prior_year_federal_tax", "")),
            prior_year_ca_tax=_parse_decimal(request.form.get("prior_year_ca_tax", "")),
            prior_year_agi=_parse_decimal(request.form.get("prior_year_agi", "")),
            notes=request.form.get("notes", "").strip() or None,
        )
        db.session.add(ty)
        db.session.commit()
        flash(f"Tax year {year} created.", "success")
        return redirect(url_for("dashboard.index") + f"?year={year}")

    return render_template("tax_years/new.html", current_year=current_year)


def _parse_decimal(val: str):
    """Parse an optional decimal form value; returns None if empty or invalid."""
    if not val or not val.strip():
        return None
    try:
        return float(val.strip().replace(",", ""))
    except ValueError:
        return None


@tax_years_bp.route("/<int:year>/delete", methods=["POST"])
@login_required
def delete(year):
    ty = TaxYear.query.filter_by(year=year).first_or_404()
    db.session.delete(ty)
    db.session.commit()
    flash(f"Tax year {year} and all associated data deleted.", "success")
    return redirect(url_for("dashboard.index"))


@tax_years_bp.route("/<int:year>/update-basic", methods=["POST"])
@login_required
def update_basic(year):
    """Update basic TaxYear fields (prior-year figures and state refund)."""
    ty = TaxYear.query.filter_by(year=year).first_or_404()
    ty.prior_year_federal_tax = _parse_decimal(request.form.get("prior_year_federal_tax", ""))
    ty.prior_year_ca_tax = _parse_decimal(request.form.get("prior_year_ca_tax", ""))
    ty.prior_year_agi = _parse_decimal(request.form.get("prior_year_agi", ""))
    ty.taxable_state_refund = _parse_decimal(request.form.get("taxable_state_refund", "")) or 0
    ty.ca_hsa_earnings = _parse_decimal(request.form.get("ca_hsa_earnings", "")) or 0
    db.session.commit()
    flash("Tax year figures updated.", "success")
    return redirect(url_for("settings.settings_page", year=year))
