"""Estimated tax payments, retirement contributions, and HSA contribution routes."""
import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required

from app import db
from app.models import (
    EstimatedTaxPayment, RetirementContribution, HSAContribution,
    TaxYear, SingleMemberLLC, RETIREMENT_ACCOUNT_TYPES,
)
from app.calculator.federal import calculate_solo_401k_max
from app.calculator.constants import IRS_MILEAGE_RATE

payments_bp = Blueprint("payments", __name__, url_prefix="/payments")

QUARTERS = ["Q1", "Q2", "Q3", "Q4"]
JURISDICTIONS = [("federal", "Federal"), ("ca", "California")]

# Federal and CA estimated payment due dates (quarter label → (month, day))
QUARTER_DUE_DATES = {
    "Q1": (4, 15),
    "Q2": (6, 15),
    "Q3": (9, 15),
    "Q4": (1, 15),  # following year
}


def _get_year_or_404(year):
    return TaxYear.query.filter_by(year=year).first_or_404()


# ---------------------------------------------------------------------------
# Estimated Tax Payments
# ---------------------------------------------------------------------------

@payments_bp.route("/<int:year>/estimated")
@login_required
def estimated_list(year):
    ty = _get_year_or_404(year)
    records = EstimatedTaxPayment.query.filter_by(tax_year_id=ty.id).order_by(
        EstimatedTaxPayment.date_paid).all()
    total_federal = sum(float(r.amount) for r in records if r.jurisdiction == "federal")
    total_ca = sum(float(r.amount) for r in records if r.jurisdiction == "ca")
    return render_template("payments/estimated_list.html",
                           tax_year=ty, records=records,
                           total_federal=total_federal, total_ca=total_ca,
                           quarters=QUARTERS, jurisdictions=JURISDICTIONS)


@payments_bp.route("/<int:year>/estimated/add", methods=["GET", "POST"])
@login_required
def estimated_add(year):
    ty = _get_year_or_404(year)
    if request.method == "POST":
        rec = EstimatedTaxPayment(
            tax_year_id=ty.id,
            jurisdiction=request.form["jurisdiction"],
            quarter=request.form["quarter"],
            amount=float(request.form["amount"]),
            date_paid=datetime.date.fromisoformat(request.form["date_paid"]),
            notes=request.form.get("notes", "").strip() or None,
        )
        db.session.add(rec)
        db.session.commit()
        flash("Estimated payment recorded.", "success")
        return redirect(url_for("payments.estimated_list", year=year))
    return render_template("payments/estimated_form.html", tax_year=ty, record=None,
                           quarters=QUARTERS, jurisdictions=JURISDICTIONS)


@payments_bp.route("/estimated/<int:rec_id>/edit", methods=["GET", "POST"])
@login_required
def estimated_edit(rec_id):
    rec = db.session.get(EstimatedTaxPayment, rec_id) or abort(404)
    year = rec.tax_year.year
    if request.method == "POST":
        rec.jurisdiction = request.form["jurisdiction"]
        rec.quarter = request.form["quarter"]
        rec.amount = float(request.form["amount"])
        rec.date_paid = datetime.date.fromisoformat(request.form["date_paid"])
        rec.notes = request.form.get("notes", "").strip() or None
        db.session.commit()
        flash("Estimated payment updated.", "success")
        return redirect(url_for("payments.estimated_list", year=year))
    return render_template("payments/estimated_form.html", tax_year=rec.tax_year, record=rec,
                           quarters=QUARTERS, jurisdictions=JURISDICTIONS)


@payments_bp.route("/estimated/<int:rec_id>/delete", methods=["POST"])
@login_required
def estimated_delete(rec_id):
    rec = db.session.get(EstimatedTaxPayment, rec_id) or abort(404)
    year = rec.tax_year.year
    db.session.delete(rec)
    db.session.commit()
    flash("Estimated payment deleted.", "info")
    return redirect(url_for("payments.estimated_list", year=year))


# ---------------------------------------------------------------------------
# Retirement Contributions
# ---------------------------------------------------------------------------

@payments_bp.route("/<int:year>/retirement")
@login_required
def retirement_list(year):
    ty = _get_year_or_404(year)
    records = RetirementContribution.query.filter_by(tax_year_id=ty.id).order_by(
        RetirementContribution.date).all()
    total = sum(float(r.amount) for r in records)

    # Build Solo 401(k) max-contribution data for each LLC with SE income
    llcs = SingleMemberLLC.query.filter_by(tax_year_id=ty.id).order_by(SingleMemberLLC.person).all()
    mileage_rate = IRS_MILEAGE_RATE.get(year, IRS_MILEAGE_RATE[2025])
    solo_401k_calcs = []
    for llc in llcs:
        gross_income = sum(float(r.amount) for r in llc.income)
        expenses = sum(float(r.amount) for r in llc.expenses)
        mileage_deduction = round(
            sum(float(r.business_miles) for r in llc.mileage) * mileage_rate, 2
        )
        net_profit = max(0.0, gross_income - expenses - mileage_deduction)
        if net_profit > 0:
            calc = calculate_solo_401k_max(net_profit, year)
            calc["llc_name"] = llc.name
            calc["llc_id"] = llc.id
            solo_401k_calcs.append(calc)

    return render_template("payments/retirement_list.html",
                           tax_year=ty, records=records, total=total,
                           account_types=RETIREMENT_ACCOUNT_TYPES,
                           llcs=llcs, solo_401k_calcs=solo_401k_calcs)


@payments_bp.route("/<int:year>/retirement/add", methods=["GET", "POST"])
@login_required
def retirement_add(year):
    ty = _get_year_or_404(year)
    if request.method == "POST":
        llc_id_raw = request.form.get("llc_id", "").strip()
        rec = RetirementContribution(
            tax_year_id=ty.id,
            person=request.form["person"].strip(),
            account_type=request.form["account_type"],
            amount=float(request.form["amount"]),
            date=datetime.date.fromisoformat(request.form["date"]),
            notes=request.form.get("notes", "").strip() or None,
            llc_id=int(llc_id_raw) if llc_id_raw else None,
        )
        db.session.add(rec)
        db.session.commit()
        flash("Retirement contribution added.", "success")
        return redirect(url_for("payments.retirement_list", year=year))
    llcs = SingleMemberLLC.query.filter_by(tax_year_id=ty.id).order_by(SingleMemberLLC.person).all()
    return render_template("payments/retirement_form.html", tax_year=ty, record=None,
                           account_types=RETIREMENT_ACCOUNT_TYPES, llcs=llcs)


@payments_bp.route("/retirement/<int:rec_id>/edit", methods=["GET", "POST"])
@login_required
def retirement_edit(rec_id):
    rec = db.session.get(RetirementContribution, rec_id) or abort(404)
    year = rec.tax_year.year
    if request.method == "POST":
        llc_id_raw = request.form.get("llc_id", "").strip()
        rec.person = request.form["person"].strip()
        rec.account_type = request.form["account_type"]
        rec.amount = float(request.form["amount"])
        rec.date = datetime.date.fromisoformat(request.form["date"])
        rec.notes = request.form.get("notes", "").strip() or None
        rec.llc_id = int(llc_id_raw) if llc_id_raw else None
        db.session.commit()
        flash("Retirement contribution updated.", "success")
        return redirect(url_for("payments.retirement_list", year=year))
    llcs = SingleMemberLLC.query.filter_by(tax_year_id=rec.tax_year_id).order_by(SingleMemberLLC.person).all()
    return render_template("payments/retirement_form.html", tax_year=rec.tax_year, record=rec,
                           account_types=RETIREMENT_ACCOUNT_TYPES, llcs=llcs)


@payments_bp.route("/retirement/<int:rec_id>/delete", methods=["POST"])
@login_required
def retirement_delete(rec_id):
    rec = db.session.get(RetirementContribution, rec_id) or abort(404)
    year = rec.tax_year.year
    db.session.delete(rec)
    db.session.commit()
    flash("Retirement contribution deleted.", "info")
    return redirect(url_for("payments.retirement_list", year=year))


# ---------------------------------------------------------------------------
# HSA Contributions
# ---------------------------------------------------------------------------

@payments_bp.route("/<int:year>/hsa")
@login_required
def hsa_list(year):
    ty = _get_year_or_404(year)
    records = HSAContribution.query.filter_by(tax_year_id=ty.id).order_by(
        HSAContribution.date).all()
    total = sum(float(r.amount) for r in records)
    return render_template("payments/hsa_list.html", tax_year=ty, records=records, total=total)


@payments_bp.route("/<int:year>/hsa/add", methods=["GET", "POST"])
@login_required
def hsa_add(year):
    ty = _get_year_or_404(year)
    if request.method == "POST":
        rec = HSAContribution(
            tax_year_id=ty.id,
            person=request.form["person"].strip(),
            amount=float(request.form["amount"]),
            date=datetime.date.fromisoformat(request.form["date"]),
            notes=request.form.get("notes", "").strip() or None,
        )
        db.session.add(rec)
        db.session.commit()
        flash("HSA contribution added.", "success")
        return redirect(url_for("payments.hsa_list", year=year))
    return render_template("payments/hsa_form.html", tax_year=ty, record=None)


@payments_bp.route("/hsa/<int:rec_id>/edit", methods=["GET", "POST"])
@login_required
def hsa_edit(rec_id):
    rec = db.session.get(HSAContribution, rec_id) or abort(404)
    year = rec.tax_year.year
    if request.method =="POST":
        rec.person = request.form["person"].strip()
        rec.amount = float(request.form["amount"])
        rec.date = datetime.date.fromisoformat(request.form["date"])
        rec.notes = request.form.get("notes", "").strip() or None
        db.session.commit()
        flash("HSA contribution updated.", "success")
        return redirect(url_for("payments.hsa_list", year=year))
    return render_template("payments/hsa_form.html", tax_year=rec.tax_year, record=rec)


@payments_bp.route("/hsa/<int:rec_id>/delete", methods=["POST"])
@login_required
def hsa_delete(rec_id):
    rec = db.session.get(HSAContribution, rec_id) or abort(404)
    year = rec.tax_year.year
    db.session.delete(rec)
    db.session.commit()
    flash("HSA contribution deleted.", "info")
    return redirect(url_for("payments.hsa_list", year=year))


@payments_bp.route("/<int:year>/hsa/earnings", methods=["POST"])
@login_required
def hsa_earnings_save(year):
    ty = _get_year_or_404(year)
    raw = request.form.get("ca_hsa_earnings", "0").strip()
    try:
        ty.ca_hsa_earnings = float(raw) if raw else 0.0
    except ValueError:
        flash("Invalid earnings amount.", "danger")
        return redirect(url_for("payments.hsa_list", year=year))
    db.session.commit()
    flash("HSA earnings updated.", "success")
    return redirect(url_for("payments.hsa_list", year=year))

