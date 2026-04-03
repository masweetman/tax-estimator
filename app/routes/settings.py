"""Per-year tax rate settings route."""
import json
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required

from app import db
from app.models import TaxYear, TaxYearSettings
from app.calculator.constants import (
    FEDERAL_STANDARD_DEDUCTION_MFJ,
    FEDERAL_BRACKETS_MFJ,
    LTCG_BRACKETS_MFJ,
    SS_WAGE_BASE,
    CHILD_TAX_CREDIT,
    CHILD_TAX_CREDIT_PHASE_OUT_START_MFJ,
    NIIT_RATE, NIIT_THRESHOLD_MFJ,
    ADDITIONAL_MEDICARE_RATE, ADDITIONAL_MEDICARE_THRESHOLD_MFJ,
    SALT_CAP, IRS_MILEAGE_RATE,
    CA_STANDARD_DEDUCTION_MFJ,
    CA_BRACKETS_MFJ,
    CA_SDI_RATE,
    CA_MENTAL_HEALTH_SURTAX_RATE, CA_MENTAL_HEALTH_SURTAX_THRESHOLD,
    CA_PERSONAL_EXEMPTION_MFJ, CA_DEPENDENT_CREDIT, CA_YOUNG_CHILD_TAX_CREDIT,
)

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


def _brackets_to_json(brackets):
    """Convert a list of (rate, upper) tuples to the JSON format for the template."""
    return json.dumps([{"rate": r, "upper": u} for r, u in brackets])


def _get_defaults(year):
    """Return a dict of constants.py defaults for the given year, for display."""
    y = year
    return {
        "federal_standard_deduction": FEDERAL_STANDARD_DEDUCTION_MFJ.get(y, FEDERAL_STANDARD_DEDUCTION_MFJ[2025]),
        "ss_wage_base": SS_WAGE_BASE.get(y, SS_WAGE_BASE[2025]),
        "salt_cap": SALT_CAP.get(y, SALT_CAP[2025]),
        "child_tax_credit": CHILD_TAX_CREDIT.get(y, CHILD_TAX_CREDIT[2025]),
        "ctc_phase_out_start": CHILD_TAX_CREDIT_PHASE_OUT_START_MFJ,
        "niit_rate": NIIT_RATE,
        "niit_threshold": NIIT_THRESHOLD_MFJ,
        "additional_medicare_rate": ADDITIONAL_MEDICARE_RATE,
        "additional_medicare_threshold": ADDITIONAL_MEDICARE_THRESHOLD_MFJ,
        "irs_mileage_rate": IRS_MILEAGE_RATE.get(y, IRS_MILEAGE_RATE[2025]),
        "ca_standard_deduction": CA_STANDARD_DEDUCTION_MFJ.get(y, CA_STANDARD_DEDUCTION_MFJ[2025]),
        "ca_sdi_rate": CA_SDI_RATE.get(y, CA_SDI_RATE[2025]),
        "ca_mental_health_surtax_rate": CA_MENTAL_HEALTH_SURTAX_RATE,
        "ca_mental_health_surtax_threshold": CA_MENTAL_HEALTH_SURTAX_THRESHOLD,
        "ca_personal_exemption": CA_PERSONAL_EXEMPTION_MFJ,
        "ca_dependent_credit": CA_DEPENDENT_CREDIT,
        "ca_young_child_credit": CA_YOUNG_CHILD_TAX_CREDIT,
        "qualifying_children_under_6": 0,
        "federal_brackets_json": _brackets_to_json(FEDERAL_BRACKETS_MFJ.get(y, FEDERAL_BRACKETS_MFJ[2025])),
        "ltcg_brackets_json": _brackets_to_json(LTCG_BRACKETS_MFJ.get(y, LTCG_BRACKETS_MFJ[2025])),
        "ca_brackets_json": _brackets_to_json(CA_BRACKETS_MFJ.get(y, CA_BRACKETS_MFJ[2025])),
    }


def _parse_float(val, default=None):
    if val is None or str(val).strip() == "":
        return None
    try:
        return float(str(val).strip())
    except ValueError:
        return default


@settings_bp.route("/<int:year>", methods=["GET", "POST"])
@login_required
def settings_page(year):
    ty = TaxYear.query.filter_by(year=year).first_or_404()
    s = ty.settings  # may be None

    defaults = _get_defaults(year)

    if request.method == "POST":
        if request.form.get("action") == "reset":
            if s:
                db.session.delete(s)
                db.session.commit()
            flash("Settings reset to defaults.", "info")
            return redirect(url_for("settings.settings_page", year=year))

        if s is None:
            s = TaxYearSettings(tax_year_id=ty.id)
            db.session.add(s)

        s.federal_standard_deduction = _parse_float(request.form.get("federal_standard_deduction"))
        s.ss_wage_base = _parse_float(request.form.get("ss_wage_base"))
        s.salt_cap = _parse_float(request.form.get("salt_cap"))
        s.child_tax_credit = _parse_float(request.form.get("child_tax_credit"))
        s.ctc_phase_out_start = _parse_float(request.form.get("ctc_phase_out_start"))
        s.niit_rate = _parse_float(request.form.get("niit_rate"))
        s.niit_threshold = _parse_float(request.form.get("niit_threshold"))
        s.additional_medicare_rate = _parse_float(request.form.get("additional_medicare_rate"))
        s.additional_medicare_threshold = _parse_float(request.form.get("additional_medicare_threshold"))
        s.irs_mileage_rate = _parse_float(request.form.get("irs_mileage_rate"))
        s.ca_standard_deduction = _parse_float(request.form.get("ca_standard_deduction"))
        s.ca_sdi_rate = _parse_float(request.form.get("ca_sdi_rate"))
        s.ca_mental_health_surtax_rate = _parse_float(request.form.get("ca_mental_health_surtax_rate"))
        s.ca_mental_health_surtax_threshold = _parse_float(request.form.get("ca_mental_health_surtax_threshold"))
        s.ca_personal_exemption = _parse_float(request.form.get("ca_personal_exemption"))
        s.ca_dependent_credit = _parse_float(request.form.get("ca_dependent_credit"))
        s.ca_young_child_credit = _parse_float(request.form.get("ca_young_child_credit"))
        qc6 = request.form.get("qualifying_children_under_6", "").strip()
        s.qualifying_children_under_6 = int(qc6) if qc6 else None

        # Bracket JSON is submitted as-is from hidden inputs updated by JS
        def _clean_brackets_json(key):
            raw = request.form.get(key, "").strip()
            if not raw or raw == "[]":
                return None
            try:
                json.loads(raw)  # validate
                return raw
            except ValueError:
                return None

        s.federal_brackets_json = _clean_brackets_json("federal_brackets_json")
        s.ltcg_brackets_json = _clean_brackets_json("ltcg_brackets_json")
        s.ca_brackets_json = _clean_brackets_json("ca_brackets_json")

        db.session.commit()
        flash("Settings saved.", "success")
        return redirect(url_for("settings.settings_page", year=year))

    return render_template(
        "settings/settings.html",
        tax_year=ty,
        s=s,
        defaults=defaults,
    )
