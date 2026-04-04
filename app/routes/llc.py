"""Single-Member LLC routes."""
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import (
    TaxYear, SingleMemberLLC, HomeOffice, LLCQuarterlyPL,
    HOME_OFFICE_DEDUCTION_TYPES,
)
from app.calculator.constants import IRS_MILEAGE_RATE

llc_bp = Blueprint("llc", __name__, url_prefix="/llc")


def _get_year_or_404(year):
    return TaxYear.query.filter_by(year=year).first_or_404()


def _get_llc_or_404(llc_id):
    return db.session.get(SingleMemberLLC, llc_id) or abort(404)


# ---------------------------------------------------------------------------
# LLC List
# ---------------------------------------------------------------------------

@llc_bp.route("/<int:year>/")
@login_required
def llc_list(year):
    ty = _get_year_or_404(year)
    return render_template("llc/list.html", tax_year=ty, llcs=ty.llcs)


# ---------------------------------------------------------------------------
# LLC Add / Edit
# ---------------------------------------------------------------------------

@llc_bp.route("/<int:year>/add", methods=["GET", "POST"])
@login_required
def llc_add(year):
    ty = _get_year_or_404(year)
    if request.method == "POST":
        person = request.form["person"].strip()
        # Enforce uniqueness: one LLC per person per year
        existing = SingleMemberLLC.query.filter_by(
            tax_year_id=ty.id, person=person
        ).first()
        if existing:
            flash(f"An LLC for that person already exists for {year}.", "danger")
            return render_template("llc/form.html", tax_year=ty, record=None)

        llc = SingleMemberLLC(
            tax_year_id=ty.id,
            person=person,
            name=request.form["name"].strip(),
            notes=request.form.get("notes", "").strip() or None,
            sstb="sstb" in request.form,
        )
        db.session.add(llc)
        db.session.commit()
        flash(f"LLC '{llc.name}' added.", "success")
        return redirect(url_for("llc.llc_list", year=year))
    return render_template("llc/form.html", tax_year=ty, record=None)


@llc_bp.route("/<int:llc_id>/edit", methods=["GET", "POST"])
@login_required
def llc_edit(llc_id):
    llc = _get_llc_or_404(llc_id)
    year = llc.tax_year.year
    if request.method == "POST":
        person = request.form["person"].strip()
        # Check uniqueness only if person changed
        if person != llc.person:
            existing = SingleMemberLLC.query.filter_by(
                tax_year_id=llc.tax_year_id, person=person
            ).first()
            if existing:
                flash(f"An LLC for that person already exists for {year}.", "danger")
                return render_template("llc/form.html", tax_year=llc.tax_year, record=llc)
        llc.person = person
        llc.name = request.form["name"].strip()
        llc.notes = request.form.get("notes", "").strip() or None
        llc.sstb = "sstb" in request.form
        db.session.commit()
        flash("LLC updated.", "success")
        return redirect(url_for("llc.llc_list", year=year))
    return render_template("llc/form.html", tax_year=llc.tax_year, record=llc)


@llc_bp.route("/<int:llc_id>/delete", methods=["POST"])
@login_required
def llc_delete(llc_id):
    llc = _get_llc_or_404(llc_id)
    year = llc.tax_year.year
    name = llc.name
    db.session.delete(llc)
    db.session.commit()
    flash(f"LLC '{name}' deleted.", "info")
    return redirect(url_for("llc.llc_list", year=year))


# ---------------------------------------------------------------------------
# LLC Dashboard (P&L)
# ---------------------------------------------------------------------------

@llc_bp.route("/<int:llc_id>/dashboard")
@login_required
def llc_dashboard(llc_id):
    llc = _get_llc_or_404(llc_id)
    year = llc.tax_year.year

    income_records = sorted(llc.income, key=lambda r: r.date)
    expense_records = sorted(llc.expenses, key=lambda r: r.date)
    mileage_records = sorted(llc.mileage, key=lambda r: r.date)

    total_income = sum(float(r.amount) for r in income_records)
    total_expenses = sum(float(r.amount) for r in expense_records)

    # Mileage deduction
    mileage_rate = IRS_MILEAGE_RATE.get(year, IRS_MILEAGE_RATE.get(2025, 0.70))
    total_miles = sum(float(r.business_miles) for r in mileage_records)
    mileage_deduction = round(total_miles * mileage_rate, 2)

    # Home office breakdown
    ho = llc.home_office
    ho_lines = []
    if ho:
        for field, label in HOME_OFFICE_DEDUCTION_TYPES:
            total_val = getattr(ho, field)
            if total_val is None:
                continue
            biz = ho.business_amount(field)
            personal = ho.personal_amount(field)
            ho_lines.append({
                "label": label,
                "total": float(total_val),
                "business": biz,
                "personal": personal,
            })

    ho_business_total = sum(line["business"] for line in ho_lines)

    # Quarterly P&L grid
    pl_by_quarter = {q.quarter: q for q in llc.quarterly_pl}
    pl_rows = [
        ("income",       "Income"),
        ("cogs",         "Cost of Goods Sold"),
        ("expenses",     "Expenses"),
        ("other_income", "Other Income"),
    ]
    pl_totals = {}
    for field, _ in pl_rows:
        pl_totals[field] = sum(float(getattr(pl_by_quarter[q], field) or 0) for q in range(1, 5) if q in pl_by_quarter)
    grid_total_income = pl_totals.get("income", 0) + pl_totals.get("other_income", 0)
    grid_total_deductions = pl_totals.get("cogs", 0) + pl_totals.get("expenses", 0)

    net_profit = (total_income + grid_total_income) - (total_expenses + grid_total_deductions) - mileage_deduction - ho_business_total

    return render_template(
        "llc/dashboard.html",
        llc=llc,
        tax_year=llc.tax_year,
        income_records=income_records,
        expense_records=expense_records,
        mileage_records=mileage_records,
        total_income=total_income,
        total_expenses=total_expenses,
        total_miles=total_miles,
        mileage_deduction=mileage_deduction,
        mileage_rate=mileage_rate,
        home_office=ho,
        ho_lines=ho_lines,
        ho_business_total=ho_business_total,
        net_profit=net_profit,
        pl_by_quarter=pl_by_quarter,
        pl_rows=pl_rows,
        pl_totals=pl_totals,
        grid_total_income=grid_total_income,
        grid_total_deductions=grid_total_deductions,
    )


@llc_bp.route("/<int:llc_id>/pl-grid", methods=["POST"])
@login_required
def pl_grid_save(llc_id):
    llc = _get_llc_or_404(llc_id)

    def _parse(name):
        v = request.form.get(name, "").strip()
        return float(v) if v else None

    for q in range(1, 5):
        record = LLCQuarterlyPL.query.filter_by(llc_id=llc_id, quarter=q).first()
        if record is None:
            record = LLCQuarterlyPL(llc_id=llc_id, quarter=q)
            db.session.add(record)
        record.income       = _parse(f"income_{q}")
        record.cogs         = _parse(f"cogs_{q}")
        record.expenses     = _parse(f"expenses_{q}")
        record.other_income = _parse(f"other_income_{q}")

    db.session.commit()
    flash("P&L saved.", "success")
    return redirect(url_for("llc.llc_dashboard", llc_id=llc_id))


# ---------------------------------------------------------------------------
# Home Office (create / edit for an LLC)
# ---------------------------------------------------------------------------

def _parse_home_office_form():
    """Parse HomeOffice fields from the current POST form."""
    def _f(name):
        v = request.form.get(name, "").strip()
        return float(v) if v else None

    return dict(
        home_sqft=float(request.form["home_sqft"]),
        business_sqft=float(request.form["business_sqft"]),
        property_taxes=_f("property_taxes"),
        mortgage_interest=_f("mortgage_interest"),
        home_insurance=_f("home_insurance"),
        utilities=_f("utilities"),
        garbage=_f("garbage"),
        hoa_dues=_f("hoa_dues"),
        depreciation=_f("depreciation"),
        notes=request.form.get("notes", "").strip() or None,
    )


@llc_bp.route("/<int:llc_id>/home-office", methods=["GET", "POST"])
@login_required
def home_office(llc_id):
    llc = _get_llc_or_404(llc_id)
    ho = llc.home_office  # may be None

    if request.method == "POST":
        data = _parse_home_office_form()
        if ho is None:
            ho = HomeOffice(tax_year_id=llc.tax_year_id, llc_id=llc.id, **data)
            db.session.add(ho)
        else:
            for k, v in data.items():
                setattr(ho, k, v)
        db.session.commit()
        flash("Home office deduction saved.", "success")
        return redirect(url_for("llc.llc_dashboard", llc_id=llc_id))

    return render_template(
        "llc/home_office_form.html",
        llc=llc,
        tax_year=llc.tax_year,
        home_office=ho,
        deduction_types=HOME_OFFICE_DEDUCTION_TYPES,
    )
