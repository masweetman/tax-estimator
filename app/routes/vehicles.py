"""Vehicle mileage log routes."""
import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required

from app import db
from app.models import VehicleMileage, TaxYear, SingleMemberLLC


def _get_llcs(ty):
    return SingleMemberLLC.query.filter_by(tax_year_id=ty.id).order_by(SingleMemberLLC.person).all()

vehicles_bp = Blueprint("vehicles", __name__, url_prefix="/vehicles")

# IRS standard mileage rate — stored in constants too, but needed here for the preview
IRS_MILEAGE_RATE = 0.70  # 2025


def _get_year_or_404(year):
    return TaxYear.query.filter_by(year=year).first_or_404()


@vehicles_bp.route("/<int:year>/mileage")
@login_required
def mileage_list(year):
    ty = _get_year_or_404(year)
    records = VehicleMileage.query.filter_by(tax_year_id=ty.id).order_by(VehicleMileage.date).all()
    total_miles = sum(float(r.business_miles) for r in records)
    total_deduction = round(total_miles * IRS_MILEAGE_RATE, 2)
    return render_template("vehicles/mileage_list.html",
                           tax_year=ty, records=records,
                           total_miles=total_miles,
                           total_deduction=total_deduction,
                           mileage_rate=IRS_MILEAGE_RATE,
                           llcs=_get_llcs(ty))


@vehicles_bp.route("/<int:year>/mileage/add", methods=["GET", "POST"])
@login_required
def mileage_add(year):
    ty = _get_year_or_404(year)
    if request.method == "POST":
        odo_start = request.form.get("odometer_start", "").strip()
        odo_end = request.form.get("odometer_end", "").strip()
        llc_id_raw = request.form.get("llc_id", "").strip()
        rec = VehicleMileage(
            tax_year_id=ty.id,
            vehicle_name=request.form["vehicle_name"].strip(),
            date=datetime.date.fromisoformat(request.form["date"]),
            odometer_start=int(odo_start) if odo_start else None,
            odometer_end=int(odo_end) if odo_end else None,
            business_miles=float(request.form["business_miles"]),
            purpose=request.form.get("purpose", "").strip() or None,
            notes=request.form.get("notes", "").strip() or None,
            llc_id=int(llc_id_raw) if llc_id_raw else None,
        )
        db.session.add(rec)
        db.session.commit()
        flash("Mileage entry added.", "success")
        return redirect(url_for("vehicles.mileage_list", year=year))
    return render_template("vehicles/mileage_form.html", tax_year=ty, record=None, llcs=_get_llcs(ty))


@vehicles_bp.route("/mileage/<int:rec_id>/edit", methods=["GET", "POST"])
@login_required
def mileage_edit(rec_id):
    rec = db.session.get(VehicleMileage, rec_id) or abort(404)
    year = rec.tax_year.year
    if request.method == "POST":
        odo_start = request.form.get("odometer_start", "").strip()
        odo_end = request.form.get("odometer_end", "").strip()
        llc_id_raw = request.form.get("llc_id", "").strip()
        rec.vehicle_name = request.form["vehicle_name"].strip()
        rec.date = datetime.date.fromisoformat(request.form["date"])
        rec.odometer_start = int(odo_start) if odo_start else None
        rec.odometer_end = int(odo_end) if odo_end else None
        rec.business_miles = float(request.form["business_miles"])
        rec.purpose = request.form.get("purpose", "").strip() or None
        rec.notes = request.form.get("notes", "").strip() or None
        rec.llc_id = int(llc_id_raw) if llc_id_raw else None
        db.session.commit()
        flash("Mileage entry updated.", "success")
        return redirect(url_for("vehicles.mileage_list", year=year))
    return render_template("vehicles/mileage_form.html", tax_year=rec.tax_year, record=rec, llcs=_get_llcs(rec.tax_year))


@vehicles_bp.route("/mileage/<int:rec_id>/delete", methods=["POST"])
@login_required
def mileage_delete(rec_id):
    rec = db.session.get(VehicleMileage, rec_id) or abort(404)
    year = rec.tax_year.year
    db.session.delete(rec)
    db.session.commit()
    flash("Mileage entry deleted.", "info")
    return redirect(url_for("vehicles.mileage_list", year=year))

