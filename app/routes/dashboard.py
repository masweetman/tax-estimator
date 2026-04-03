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
    InsurancePremium, VehicleMileage, HomeOffice,
    InterestIncome, DividendIncome,
)
from app.calculator.engine import calculate
from app.calculator.constants import IRS_MILEAGE_RATE
from app.tax_settings import get_settings_inputs

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
            w2_wages += (
                float(stub.gross_pay)
                - float(stub.pretax_benefit_total)
                + float(stub.custom_pretax_adder_total)
            )
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

    # --- LLC quarterly P&L grid (additive with per-item SE records) ---
    for llc in ty.llcs:
        for q in llc.quarterly_pl:
            q_income = float(q.income or 0) + float(q.other_income or 0)
            q_deductions = float(q.cogs or 0) + float(q.expenses or 0)
            if llc.person == "Person 1":
                se_p1 += q_income
            else:
                se_p2 += q_income
            se_expenses += q_deductions

    # --- Home office deductions (SMLLC) ---
    # Business portion is added to se_expenses; personal property tax and
    # mortgage interest portions are added to their respective itemized deduction buckets.
    ho_se_addition = 0.0
    ho_mortgage_personal = 0.0
    ho_property_tax_personal = 0.0
    for ho in ty.home_offices:
        biz_pct = ho.business_pct
        for field in ("property_taxes", "mortgage_interest", "home_insurance",
                      "utilities", "garbage", "hoa_dues"):
            ho_se_addition += ho.business_amount(field)
        if ho.depreciation:
            ho_se_addition += float(ho.depreciation)
        ho_mortgage_personal += ho.personal_amount("mortgage_interest")
        ho_property_tax_personal += ho.personal_amount("property_taxes")
    se_expenses += ho_se_addition

    # --- Capital gains ---
    ltcg = sum(float(r.gain) for r in ty.capital_gains if r.is_long_term)
    stcg = sum(float(r.gain) for r in ty.capital_gains if not r.is_long_term)

    # --- Interest and dividend income ---
    interest_income = sum(float(r.amount) for r in ty.interest_income)
    ordinary_dividends = sum(float(r.ordinary_dividends) for r in ty.dividend_income)
    qualified_dividends = sum(float(r.qualified_dividends) for r in ty.dividend_income)

    # --- Deductions ---
    mortgage_interest = sum(float(r.amount) for r in ty.deductions
                            if r.category == "mortgage_interest")
    mortgage_interest += ho_mortgage_personal
    charitable = sum(float(r.amount) for r in ty.deductions
                     if r.category == "charitable")
    salt_paid = sum(float(r.amount) for r in ty.deductions
                    if r.category in ("property_tax", "state_tax", "local_tax"))
    salt_paid += ho_property_tax_personal
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
    solo_401k_total = sum(float(r.amount) for r in ty.retirement_contributions
                          if r.account_type in ("solo_401k_employee", "solo_401k_employer"))

    # --- HSA ---
    hsa_total = sum(float(r.amount) for r in ty.hsa_contributions)

    # --- Vehicle mileage deduction ---
    settings_overrides = get_settings_inputs(ty)
    mileage_rate = settings_overrides.get("irs_mileage_rate") or IRS_MILEAGE_RATE.get(year, IRS_MILEAGE_RATE[2025])
    total_miles = sum(float(r.business_miles) for r in ty.vehicle_mileage)
    mileage_deduction = round(total_miles * mileage_rate, 2)

    inputs = {
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
        "interest_income": interest_income,
        "ordinary_dividends": ordinary_dividends,
        "qualified_dividends": qualified_dividends,
        "taxable_state_refund": float(ty.taxable_state_refund or 0),
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
        "solo_401k_total": solo_401k_total,
        "hsa_total": hsa_total,
        "vehicle_mileage_deduction": mileage_deduction,
        "qualifying_children": 2,  # family of 4: 2 children
        "qualifying_children_under_6": settings_overrides.get("qualifying_children_under_6", 0),
        "prior_year_federal_tax": float(ty.prior_year_federal_tax or 0),
        "prior_year_ca_tax": float(ty.prior_year_ca_tax or 0),
        "prior_year_agi": float(ty.prior_year_agi or 0),
    }
    inputs.update(settings_overrides)
    return inputs


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

