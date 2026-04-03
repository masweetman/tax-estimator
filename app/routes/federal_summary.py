"""Federal Tax Summary — 1040-style read-only view."""
from flask import Blueprint, render_template, abort
from flask_login import login_required

from app.models import TaxYear
from app.routes.dashboard import _build_inputs
from app.calculator.engine import calculate

federal_summary_bp = Blueprint("federal_summary", __name__, url_prefix="/federal-summary")


@federal_summary_bp.route("/<int:year>/")
@login_required
def summary(year):
    ty = TaxYear.query.filter_by(year=year).first_or_404()
    inputs = _build_inputs(ty)
    result = calculate(inputs)
    return render_template("federal_summary.html", tax_year=ty, inputs=inputs, result=result)
