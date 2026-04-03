"""Dashboard route — full tax summary for a given year."""
from flask import Blueprint, render_template, request, abort
from flask_login import login_required

from app import db
from app.models import (
    TaxYear,
    Employer, Paystub,
    SelfEmploymentIncome, SelfEmploymentExpense,
    CapitalGain, Deduction, ChildCareExpense,
    EstimatedTaxPayment, RetirementContribution, HSAContribution,
    InsurancePremium, VehicleMileage,
)
from app.calculator.engine import calculate
from app.calculator.constants import IRS_MILEAGE_RATE

dashboard_bp = Blueprint("dashboard", __name__)


def _build_inputs(ty: TaxYear) -> dict:
    """Aggregate all DB data for `ty` into the flat dict the calculator expects."""
    year = ty.year

    # --- W-2 wages & withholdings ---
    w2_wages = 0.0
    fed_withheld = 0.0
    ss_withheld = 0.0
    medicare_withheld = 0.0
    ca_withheld = 0.0
    ca_sdi_withheld = 0.0
    pretax_401k_total = 0.0

    for emp in ty.employers:
        for stub in emp.paystubs:
            w2_wages += float(stub.gross_pay) - float(stub.pretax_benefit_total)
            fed_withheld += float(stub.federal_income_withholding)
            ss_withheld += float(stub.ss_withholding)
            medicare_withheld += float(stub.medicare_withholding)
            ca_withheld += float(stub.state_income_withholding)
            ca_sdi_withheld += float(stub.state_disability_withholding)
            pretax_401k_total += float(stub.pretax_401k)

    # --- SE income / expenses ---
    se_p1 = sum(float(r.amount) for r in ty.se_income if r.person == "Person 1")
    se_p2 = sum(float(r.amount) for r in ty.se_income if r.person == "Person 2")
    se_expenses = sum(float(r.amount) for r in ty.se_expenses)

    # --- Capital gains ---
    ltcg = sum(float(r.gain) for r in ty.capital_gains if r.is_long_term)
    stcg = sum(float(r.gain) for r in ty.capital_gains if not r.is_long_term)

    # --- Deductions ---
    mortgage_interest = sum(float(r.amount) for r in ty.deductions
                            if r.category == "mortgage_interest")
    charitable = sum(float(r.amount) for r in ty.deductions
                     if r.category == "charitable")
    salt_paid = sum(float(r.amount) for r in ty.deductions
                    if r.category in ("property_tax", "state_tax", "local_tax"))
    medical_expenses = sum(float(r.amount) for r in ty.deductions
                           if r.category == "medical")

    # --- Child care ---
    child_care = sum(float(r.amount) for r in ty.child_care_expenses)

    # --- Self-employed insurance ---
    se_health = sum(float(r.amount) for r in ty.insurance_premiums
                    if r.is_self_employed)

    # --- Estimated payments ---
    fed_est = sum(float(r.amount) for r in ty.estimated_tax_payments
                  if r.jurisdiction == "federal")
    ca_est = sum(float(r.amount) for r in ty.estimated_tax_payments
                 if r.jurisdiction == "ca")

    # --- Retirement ---
    ira_total = sum(float(r.amount) for r in ty.retirement_contributions
                    if r.account_type == "traditional_ira")
    sep_total = sum(float(r.amount) for r in ty.retirement_contributions
                    if r.account_type == "sep_ira")

    # --- HSA ---
    hsa_total = sum(float(r.amount) for r in ty.hsa_contributions)

    # --- Vehicle mileage deduction ---
    total_miles = sum(float(r.business_miles) for r in ty.vehicle_mileage)
    mileage_deduction = round(total_miles * IRS_MILEAGE_RATE, 2)

    return {
        "tax_year": year,
        "w2_wages": w2_wages,
        "federal_income_withheld": fed_withheld,
        "ss_withheld": ss_withheld,
        "medicare_withheld": medicare_withheld,
        "ca_income_withheld": ca_withheld,
        "ca_sdi_withheld": ca_sdi_withheld,
        "pretax_401k_total": pretax_401k_total,
        "se_net_income_p1": max(0.0, se_p1 - se_expenses),
        "se_net_income_p2": se_p2,
        "long_term_capital_gains": max(0.0, ltcg),
        "short_term_capital_gains": stcg,
        "mortgage_interest": mortgage_interest,
        "charitable": charitable,
        "salt_taxes_paid": salt_paid,
        "medical_expenses": medical_expenses,
        "child_care_expenses": child_care,
        "se_health_insurance": se_health,
        "federal_estimated_paid": fed_est,
        "ca_estimated_paid": ca_est,
        "traditional_ira_total": ira_total,
        "sep_ira_total": sep_total,
        "hsa_total": hsa_total,
        "vehicle_mileage_deduction": mileage_deduction,
        "qualifying_children": 2,  # family of 4: 2 children
        "prior_year_federal_tax": float(ty.prior_year_federal_tax or 0),
        "prior_year_ca_tax": float(ty.prior_year_ca_tax or 0),
        "prior_year_agi": float(ty.prior_year_agi or 0),
    }


@dashboard_bp.route("/")
@login_required
def index():
    # Allow ?year=XXXX override; default to most recent TaxYear
    year_param = request.args.get("year", type=int)
    all_years = TaxYear.query.order_by(TaxYear.year.desc()).all()

    if not all_years:
        return render_template("dashboard.html", tax_year=None, result=None,
                               all_years=[], inputs=None)

    if year_param:
        ty = TaxYear.query.filter_by(year=year_param).first_or_404()
    else:
        ty = all_years[0]

    inputs = _build_inputs(ty)
    result = calculate(inputs)

    return render_template(
        "dashboard.html",
        tax_year=ty,
        all_years=all_years,
        inputs=inputs,
        result=result,
    )

