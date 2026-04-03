"""Capital gains, itemized deductions, child care, and insurance premium routes."""
import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required

from app import db
from app.models import (
    CapitalGain, Deduction, ChildCareExpense, InsurancePremium,
    TaxYear, DEDUCTION_CATEGORIES, INSURANCE_TYPES,
)

deductions_bp = Blueprint("deductions", __name__, url_prefix="/deductions")


def _get_year_or_404(year):
    return TaxYear.query.filter_by(year=year).first_or_404()


# ---------------------------------------------------------------------------
# Capital Gains
# ---------------------------------------------------------------------------

@deductions_bp.route("/<int:year>/capital-gains")
@login_required
def capital_gains_list(year):
    ty = _get_year_or_404(year)
    records = CapitalGain.query.filter_by(tax_year_id=ty.id).order_by(CapitalGain.sale_date).all()
    total_lt = sum(float(r.gain) for r in records if r.is_long_term)
    total_st = sum(float(r.gain) for r in records if not r.is_long_term)
    return render_template("deductions/capital_gains_list.html",
                           tax_year=ty, records=records, total_lt=total_lt, total_st=total_st)


@deductions_bp.route("/<int:year>/capital-gains/add", methods=["GET", "POST"])
@login_required
def capital_gains_add(year):
    ty = _get_year_or_404(year)
    if request.method == "POST":
        rec = CapitalGain(
            tax_year_id=ty.id,
            person=request.form["person"].strip(),
            description=request.form["description"].strip(),
            proceeds=float(request.form["proceeds"]),
            cost_basis=float(request.form["cost_basis"]),
            acquisition_date=datetime.date.fromisoformat(request.form["acquisition_date"]),
            sale_date=datetime.date.fromisoformat(request.form["sale_date"]),
            is_long_term=request.form.get("is_long_term") in ("true", "on", "1", "yes"),
            notes=request.form.get("notes", "").strip() or None,
        )
        db.session.add(rec)
        db.session.commit()
        flash("Capital gain added.", "success")
        return redirect(url_for("deductions.capital_gains_list", year=year))
    return render_template("deductions/capital_gains_form.html", tax_year=ty, record=None)


@deductions_bp.route("/capital-gains/<int:rec_id>/edit", methods=["GET", "POST"])
@login_required
def capital_gains_edit(rec_id):
    rec = db.session.get(CapitalGain, rec_id) or abort(404)
    year = rec.tax_year.year
    if request.method == "POST":
        rec.person = request.form["person"].strip()
        rec.description = request.form["description"].strip()
        rec.proceeds = float(request.form["proceeds"])
        rec.cost_basis = float(request.form["cost_basis"])
        rec.acquisition_date = datetime.date.fromisoformat(request.form["acquisition_date"])
        rec.sale_date = datetime.date.fromisoformat(request.form["sale_date"])
        rec.is_long_term = request.form.get("is_long_term") in ("true", "on", "1", "yes")
        rec.notes = request.form.get("notes", "").strip() or None
        db.session.commit()
        flash("Capital gain updated.", "success")
        return redirect(url_for("deductions.capital_gains_list", year=year))
    return render_template("deductions/capital_gains_form.html", tax_year=rec.tax_year, record=rec)


@deductions_bp.route("/capital-gains/<int:rec_id>/delete", methods=["POST"])
@login_required
def capital_gains_delete(rec_id):
    rec = db.session.get(CapitalGain, rec_id) or abort(404)
    year = rec.tax_year.year
    db.session.delete(rec)
    db.session.commit()
    flash("Capital gain deleted.", "info")
    return redirect(url_for("deductions.capital_gains_list", year=year))


# ---------------------------------------------------------------------------
# Itemized Deductions
# ---------------------------------------------------------------------------

@deductions_bp.route("/<int:year>/itemized")
@login_required
def itemized_list(year):
    ty = _get_year_or_404(year)
    records = Deduction.query.filter_by(tax_year_id=ty.id).order_by(Deduction.date).all()
    total = sum(float(r.amount) for r in records)
    return render_template("deductions/itemized_list.html",
                           tax_year=ty, records=records, total=total,
                           categories=DEDUCTION_CATEGORIES)


@deductions_bp.route("/<int:year>/itemized/add", methods=["GET", "POST"])
@login_required
def itemized_add(year):
    ty = _get_year_or_404(year)
    if request.method == "POST":
        rec = Deduction(
            tax_year_id=ty.id,
            category=request.form["category"],
            description=request.form["description"].strip(),
            amount=float(request.form["amount"]),
            date=datetime.date.fromisoformat(request.form["date"]),
            notes=request.form.get("notes", "").strip() or None,
        )
        db.session.add(rec)
        db.session.commit()
        flash("Deduction added.", "success")
        return redirect(url_for("deductions.itemized_list", year=year))
    return render_template("deductions/itemized_form.html", tax_year=ty, record=None,
                           categories=DEDUCTION_CATEGORIES)


@deductions_bp.route("/itemized/<int:rec_id>/edit", methods=["GET", "POST"])
@login_required
def itemized_edit(rec_id):
    rec = db.session.get(Deduction, rec_id) or abort(404)
    year = rec.tax_year.year
    if request.method == "POST":
        rec.category = request.form["category"]
        rec.description = request.form["description"].strip()
        rec.amount = float(request.form["amount"])
        rec.date = datetime.date.fromisoformat(request.form["date"])
        rec.notes = request.form.get("notes", "").strip() or None
        db.session.commit()
        flash("Deduction updated.", "success")
        return redirect(url_for("deductions.itemized_list", year=year))
    return render_template("deductions/itemized_form.html", tax_year=rec.tax_year, record=rec,
                           categories=DEDUCTION_CATEGORIES)


@deductions_bp.route("/itemized/<int:rec_id>/delete", methods=["POST"])
@login_required
def itemized_delete(rec_id):
    rec = db.session.get(Deduction, rec_id) or abort(404)
    year = rec.tax_year.year
    db.session.delete(rec)
    db.session.commit()
    flash("Deduction deleted.", "info")
    return redirect(url_for("deductions.itemized_list", year=year))


# ---------------------------------------------------------------------------
# Child Care Expenses
# ---------------------------------------------------------------------------

@deductions_bp.route("/<int:year>/child-care")
@login_required
def child_care_list(year):
    ty = _get_year_or_404(year)
    records = ChildCareExpense.query.filter_by(tax_year_id=ty.id).order_by(ChildCareExpense.date).all()
    total = sum(float(r.amount) for r in records)
    return render_template("deductions/child_care_list.html", tax_year=ty, records=records, total=total)


@deductions_bp.route("/<int:year>/child-care/add", methods=["GET", "POST"])
@login_required
def child_care_add(year):
    ty = _get_year_or_404(year)
    if request.method == "POST":
        rec = ChildCareExpense(
            tax_year_id=ty.id,
            provider=request.form["provider"].strip(),
            child_name=request.form.get("child_name", "").strip() or None,
            amount=float(request.form["amount"]),
            date=datetime.date.fromisoformat(request.form["date"]),
            notes=request.form.get("notes", "").strip() or None,
        )
        db.session.add(rec)
        db.session.commit()
        flash("Child care expense added.", "success")
        return redirect(url_for("deductions.child_care_list", year=year))
    return render_template("deductions/child_care_form.html", tax_year=ty, record=None)


@deductions_bp.route("/child-care/<int:rec_id>/edit", methods=["GET", "POST"])
@login_required
def child_care_edit(rec_id):
    rec = db.session.get(ChildCareExpense, rec_id) or abort(404)
    year = rec.tax_year.year
    if request.method == "POST":
        rec.provider = request.form["provider"].strip()
        rec.child_name = request.form.get("child_name", "").strip() or None
        rec.amount = float(request.form["amount"])
        rec.date = datetime.date.fromisoformat(request.form["date"])
        rec.notes = request.form.get("notes", "").strip() or None
        db.session.commit()
        flash("Child care expense updated.", "success")
        return redirect(url_for("deductions.child_care_list", year=year))
    return render_template("deductions/child_care_form.html", tax_year=rec.tax_year, record=rec)


@deductions_bp.route("/child-care/<int:rec_id>/delete", methods=["POST"])
@login_required
def child_care_delete(rec_id):
    rec = db.session.get(ChildCareExpense, rec_id) or abort(404)
    year = rec.tax_year.year
    db.session.delete(rec)
    db.session.commit()
    flash("Child care expense deleted.", "info")
    return redirect(url_for("deductions.child_care_list", year=year))


# ---------------------------------------------------------------------------
# Self-Employed Insurance Premiums
# ---------------------------------------------------------------------------

@deductions_bp.route("/<int:year>/insurance")
@login_required
def insurance_list(year):
    ty = _get_year_or_404(year)
    records = InsurancePremium.query.filter_by(tax_year_id=ty.id).order_by(InsurancePremium.date).all()
    total = sum(float(r.amount) for r in records)
    return render_template("deductions/insurance_list.html",
                           tax_year=ty, records=records, total=total,
                           insurance_types=INSURANCE_TYPES)


@deductions_bp.route("/<int:year>/insurance/add", methods=["GET", "POST"])
@login_required
def insurance_add(year):
    ty = _get_year_or_404(year)
    if request.method == "POST":
        rec = InsurancePremium(
            tax_year_id=ty.id,
            person=request.form["person"].strip(),
            insurance_type=request.form["insurance_type"],
            is_self_employed=request.form.get("is_self_employed") in ("true", "on", "1", "yes"),
            amount=float(request.form["amount"]),
            date=datetime.date.fromisoformat(request.form["date"]),
            notes=request.form.get("notes", "").strip() or None,
        )
        db.session.add(rec)
        db.session.commit()
        flash("Insurance premium added.", "success")
        return redirect(url_for("deductions.insurance_list", year=year))
    return render_template("deductions/insurance_form.html", tax_year=ty, record=None,
                           insurance_types=INSURANCE_TYPES)


@deductions_bp.route("/insurance/<int:rec_id>/edit", methods=["GET", "POST"])
@login_required
def insurance_edit(rec_id):
    rec = db.session.get(InsurancePremium, rec_id) or abort(404)
    year = rec.tax_year.year
    if request.method == "POST":
        rec.person = request.form["person"].strip()
        rec.insurance_type = request.form["insurance_type"]
        rec.is_self_employed = request.form.get("is_self_employed") in ("true", "on", "1", "yes")
        rec.amount = float(request.form["amount"])
        rec.date = datetime.date.fromisoformat(request.form["date"])
        rec.notes = request.form.get("notes", "").strip() or None
        db.session.commit()
        flash("Insurance premium updated.", "success")
        return redirect(url_for("deductions.insurance_list", year=year))
    return render_template("deductions/insurance_form.html", tax_year=rec.tax_year, record=rec,
                           insurance_types=INSURANCE_TYPES)


@deductions_bp.route("/insurance/<int:rec_id>/delete", methods=["POST"])
@login_required
def insurance_delete(rec_id):
    rec = db.session.get(InsurancePremium, rec_id) or abort(404)
    year = rec.tax_year.year
    db.session.delete(rec)
    db.session.commit()
    flash("Insurance premium deleted.", "info")
    return redirect(url_for("deductions.insurance_list", year=year))

