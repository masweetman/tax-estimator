"""W-2 employer and paystub routes."""
import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required

from app import db
from app.models import Employer, Paystub, PaystubCustomFieldDef, PaystubCustomFieldValue, TaxYear

w2_bp = Blueprint("w2", __name__, url_prefix="/w2")

PAYSTUB_NUMERIC_FIELDS = [
    "gross_pay", "federal_income_withholding", "ss_withholding",
    "medicare_withholding", "state_income_withholding", "state_disability_withholding",
    "medical_insurance", "dental_insurance", "vision_insurance",
    "pretax_401k", "roth_401k", "dependent_care_fsa", "healthcare_fsa",
]


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _generate_biweekly_stubs(employer: Employer):
    """Create bi-weekly Paystub stubs (is_actual=False) for the tax year."""
    year = employer.tax_year.year
    current = employer.first_paystub_date

    while current.year == year:
        period_start = current - datetime.timedelta(days=13)
        period_end = current - datetime.timedelta(days=1)
        stub = Paystub(
            employer_id=employer.id,
            pay_period_start=period_start,
            pay_period_end=period_end,
            pay_date=current,
            is_actual=False,
        )
        db.session.add(stub)
        current += datetime.timedelta(weeks=2)

    db.session.commit()


def _propagate_from_actual(paystub: Paystub):
    """Copy numeric fields from this actual paystub to all later estimated stubs."""
    later_stubs = (
        Paystub.query
        .filter(
            Paystub.employer_id == paystub.employer_id,
            Paystub.pay_date > paystub.pay_date,
            Paystub.is_actual == False,  # noqa: E712
        )
        .all()
    )
    for stub in later_stubs:
        for field in PAYSTUB_NUMERIC_FIELDS:
            setattr(stub, field, getattr(paystub, field))
    db.session.commit()


def _get_tax_year_or_404(year: int) -> TaxYear:
    ty = TaxYear.query.filter_by(year=year).first_or_404(
        description=f"Tax year {year} not found."
    )
    return ty


# ---------------------------------------------------------------------------
# Employer routes
# ---------------------------------------------------------------------------

@w2_bp.route("/employers/<int:year>")
@login_required
def employer_list(year):
    ty = _get_tax_year_or_404(year)
    employers = Employer.query.filter_by(tax_year_id=ty.id).order_by(Employer.person, Employer.name).all()
    return render_template("w2/employers.html", tax_year=ty, employers=employers)


@w2_bp.route("/employers/<int:year>/add", methods=["GET", "POST"])
@login_required
def employer_add(year):
    ty = _get_tax_year_or_404(year)
    if request.method == "POST":
        emp = Employer(
            tax_year_id=ty.id,
            person=request.form["person"].strip(),
            name=request.form["name"].strip(),
            first_paystub_date=datetime.date.fromisoformat(request.form["first_paystub_date"]),
            is_covered_by_retirement_plan=request.form.get("is_covered_by_retirement_plan") in ("true", "on", "1", "yes"),
            notes=request.form.get("notes", "").strip() or None,
        )
        db.session.add(emp)
        db.session.flush()  # get emp.id before generating stubs
        _generate_biweekly_stubs(emp)
        flash(f"Employer '{emp.name}' added with {len(emp.paystubs)} pay periods.", "success")
        return redirect(url_for("w2.employer_list", year=year))

    return render_template("w2/employer_form.html", tax_year=ty, employer=None)


@w2_bp.route("/employers/<int:employer_id>/edit", methods=["GET", "POST"])
@login_required
def employer_edit(employer_id):
    emp = db.session.get(Employer, employer_id) or abort(404)
    year = emp.tax_year.year
    if request.method == "POST":
        emp.person = request.form["person"].strip()
        emp.name = request.form["name"].strip()
        emp.notes = request.form.get("notes", "").strip() or None
        emp.is_covered_by_retirement_plan = request.form.get("is_covered_by_retirement_plan") in ("true", "on", "1", "yes")
        db.session.commit()
        flash("Employer updated.", "success")
        return redirect(url_for("w2.employer_list", year=year))
    return render_template("w2/employer_form.html", tax_year=emp.tax_year, employer=emp)


@w2_bp.route("/employers/<int:employer_id>/delete", methods=["POST"])
@login_required
def employer_delete(employer_id):
    emp = db.session.get(Employer, employer_id) or abort(404)
    year = emp.tax_year.year
    db.session.delete(emp)
    db.session.commit()
    flash("Employer deleted.", "info")
    return redirect(url_for("w2.employer_list", year=year))


# ---------------------------------------------------------------------------
# Custom field def routes
# ---------------------------------------------------------------------------

@w2_bp.route("/employers/<int:employer_id>/custom-fields/add", methods=["POST"])
@login_required
def custom_field_add(employer_id):
    emp = db.session.get(Employer, employer_id) or abort(404)
    fd = PaystubCustomFieldDef(
        employer_id=employer_id,
        field_name=request.form["field_name"].strip(),
        sort_order=int(request.form.get("sort_order", 0)),
    )
    db.session.add(fd)
    db.session.commit()
    flash(f"Custom field '{fd.field_name}' added.", "success")
    return redirect(url_for("w2.employer_edit", employer_id=employer_id))


@w2_bp.route("/employers/<int:employer_id>/custom-fields/<int:fd_id>/delete", methods=["POST"])
@login_required
def custom_field_delete(employer_id, fd_id):
    fd = db.session.get(PaystubCustomFieldDef, fd_id) or abort(404)
    db.session.delete(fd)
    db.session.commit()
    flash("Custom field deleted.", "info")
    return redirect(url_for("w2.employer_edit", employer_id=employer_id))


# ---------------------------------------------------------------------------
# Paystub routes
# ---------------------------------------------------------------------------

@w2_bp.route("/employers/<int:employer_id>/paystubs")
@login_required
def paystub_list(employer_id):
    emp = db.session.get(Employer, employer_id) or abort(404)
    stubs = emp.paystubs  # already ordered by pay_date via relationship

    # Build YTD running totals
    ytd_gross = 0
    ytd_federal = 0
    ytd_state = 0
    rows = []
    for stub in stubs:
        ytd_gross += float(stub.gross_pay)
        ytd_federal += float(stub.federal_income_withholding)
        ytd_state += float(stub.state_income_withholding)
        rows.append({
            "stub": stub,
            "ytd_gross": ytd_gross,
            "ytd_federal": ytd_federal,
            "ytd_state": ytd_state,
        })

    return render_template("w2/paystubs.html", employer=emp, rows=rows)


@w2_bp.route("/paystubs/<int:stub_id>/edit", methods=["GET", "POST"])
@login_required
def paystub_edit(stub_id):
    stub = db.session.get(Paystub, stub_id) or abort(404)
    emp = stub.employer
    custom_defs = emp.custom_field_defs

    if request.method == "POST":
        for field in PAYSTUB_NUMERIC_FIELDS:
            val = request.form.get(field, "0") or "0"
            setattr(stub, field, float(val))

        stub.is_actual = request.form.get("is_actual") in ("true", "on", "1", "yes")
        stub.notes = request.form.get("notes", "").strip() or None

        # Save custom field values
        for fd in custom_defs:
            raw = request.form.get(f"custom_{fd.id}", "0") or "0"
            existing = PaystubCustomFieldValue.query.filter_by(
                paystub_id=stub.id, field_def_id=fd.id
            ).first()
            if existing:
                existing.amount = float(raw)
            else:
                db.session.add(PaystubCustomFieldValue(
                    paystub_id=stub.id, field_def_id=fd.id, amount=float(raw)
                ))

        db.session.commit()

        if stub.is_actual:
            _propagate_from_actual(stub)

        flash("Paystub saved.", "success")
        return redirect(url_for("w2.paystub_list", employer_id=emp.id))

    # Build custom field value map {fd_id: amount}
    cf_values = {
        v.field_def_id: v.amount
        for v in stub.custom_field_values
    }
    return render_template(
        "w2/paystub_form.html",
        stub=stub,
        employer=emp,
        custom_defs=custom_defs,
        cf_values=cf_values,
    )
