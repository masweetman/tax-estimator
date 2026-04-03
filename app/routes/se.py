"""Self-employment income and expense routes."""
import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required

from app import db
from app.models import SelfEmploymentIncome, SelfEmploymentExpense, TaxYear, SingleMemberLLC, SE_INCOME_CATEGORIES, SE_EXPENSE_CATEGORIES


def _get_llcs(ty):
    return SingleMemberLLC.query.filter_by(tax_year_id=ty.id).order_by(SingleMemberLLC.person).all()

se_bp = Blueprint("se", __name__, url_prefix="/se")


def _get_year_or_404(year):
    return TaxYear.query.filter_by(year=year).first_or_404()


# ---------------------------------------------------------------------------
# SE Income
# ---------------------------------------------------------------------------

@se_bp.route("/<int:year>/income")
@login_required
def income_list(year):
    ty = _get_year_or_404(year)
    records = SelfEmploymentIncome.query.filter_by(tax_year_id=ty.id).order_by(SelfEmploymentIncome.date).all()
    total = sum(float(r.amount) for r in records)
    return render_template("se/income_list.html", tax_year=ty, records=records, total=total,
                           categories=SE_INCOME_CATEGORIES, llcs=_get_llcs(ty))


@se_bp.route("/<int:year>/income/add", methods=["GET", "POST"])
@login_required
def income_add(year):
    ty = _get_year_or_404(year)
    if request.method == "POST":
        llc_id_raw = request.form.get("llc_id", "").strip()
        rec = SelfEmploymentIncome(
            tax_year_id=ty.id,
            person=request.form["person"].strip(),
            client=request.form.get("client", "").strip() or None,
            amount=float(request.form["amount"]),
            date=datetime.date.fromisoformat(request.form["date"]),
            category=request.form.get("category", "consulting"),
            notes=request.form.get("notes", "").strip() or None,
            llc_id=int(llc_id_raw) if llc_id_raw else None,
        )
        db.session.add(rec)
        db.session.commit()
        flash("SE income entry added.", "success")
        return redirect(url_for("se.income_list", year=year))
    return render_template("se/income_form.html", tax_year=ty, record=None,
                           categories=SE_INCOME_CATEGORIES, llcs=_get_llcs(ty))


@se_bp.route("/income/<int:rec_id>/edit", methods=["GET", "POST"])
@login_required
def income_edit(rec_id):
    rec = db.session.get(SelfEmploymentIncome, rec_id) or abort(404)
    year = rec.tax_year.year
    if request.method == "POST":
        llc_id_raw = request.form.get("llc_id", "").strip()
        rec.person = request.form["person"].strip()
        rec.client = request.form.get("client", "").strip() or None
        rec.amount = float(request.form["amount"])
        rec.date = datetime.date.fromisoformat(request.form["date"])
        rec.category = request.form.get("category", "consulting")
        rec.notes = request.form.get("notes", "").strip() or None
        rec.llc_id = int(llc_id_raw) if llc_id_raw else None
        db.session.commit()
        flash("SE income entry updated.", "success")
        return redirect(url_for("se.income_list", year=year))
    return render_template("se/income_form.html", tax_year=rec.tax_year, record=rec,
                           categories=SE_INCOME_CATEGORIES, llcs=_get_llcs(rec.tax_year))


@se_bp.route("/income/<int:rec_id>/delete", methods=["POST"])
@login_required
def income_delete(rec_id):
    rec = db.session.get(SelfEmploymentIncome, rec_id) or abort(404)
    year = rec.tax_year.year
    db.session.delete(rec)
    db.session.commit()
    flash("SE income entry deleted.", "info")
    return redirect(url_for("se.income_list", year=year))


# ---------------------------------------------------------------------------
# SE Expenses
# ---------------------------------------------------------------------------

@se_bp.route("/<int:year>/expenses")
@login_required
def expense_list(year):
    ty = _get_year_or_404(year)
    records = SelfEmploymentExpense.query.filter_by(tax_year_id=ty.id).order_by(SelfEmploymentExpense.date).all()
    total = sum(float(r.amount) for r in records)
    return render_template("se/expense_list.html", tax_year=ty, records=records, total=total,
                           categories=SE_EXPENSE_CATEGORIES, llcs=_get_llcs(ty))


@se_bp.route("/<int:year>/expenses/add", methods=["GET", "POST"])
@login_required
def expense_add(year):
    ty = _get_year_or_404(year)
    if request.method == "POST":
        llc_id_raw = request.form.get("llc_id", "").strip()
        rec = SelfEmploymentExpense(
            tax_year_id=ty.id,
            description=request.form["description"].strip(),
            amount=float(request.form["amount"]),
            date=datetime.date.fromisoformat(request.form["date"]),
            category=request.form.get("category", "other"),
            notes=request.form.get("notes", "").strip() or None,
            llc_id=int(llc_id_raw) if llc_id_raw else None,
        )
        db.session.add(rec)
        db.session.commit()
        flash("SE expense added.", "success")
        return redirect(url_for("se.expense_list", year=year))
    return render_template("se/expense_form.html", tax_year=ty, record=None,
                           categories=SE_EXPENSE_CATEGORIES, llcs=_get_llcs(ty))


@se_bp.route("/expenses/<int:rec_id>/edit", methods=["GET", "POST"])
@login_required
def expense_edit(rec_id):
    rec = db.session.get(SelfEmploymentExpense, rec_id) or abort(404)
    year = rec.tax_year.year
    if request.method == "POST":
        llc_id_raw = request.form.get("llc_id", "").strip()
        rec.description = request.form["description"].strip()
        rec.amount = float(request.form["amount"])
        rec.date = datetime.date.fromisoformat(request.form["date"])
        rec.category = request.form.get("category", "other")
        rec.notes = request.form.get("notes", "").strip() or None
        rec.llc_id = int(llc_id_raw) if llc_id_raw else None
        db.session.commit()
        flash("SE expense updated.", "success")
        return redirect(url_for("se.expense_list", year=year))
    return render_template("se/expense_form.html", tax_year=rec.tax_year, record=rec,
                           categories=SE_EXPENSE_CATEGORIES, llcs=_get_llcs(rec.tax_year))


@se_bp.route("/expenses/<int:rec_id>/delete", methods=["POST"])
@login_required
def expense_delete(rec_id):
    rec = db.session.get(SelfEmploymentExpense, rec_id) or abort(404)
    year = rec.tax_year.year
    db.session.delete(rec)
    db.session.commit()
    flash("SE expense deleted.", "info")
    return redirect(url_for("se.expense_list", year=year))

