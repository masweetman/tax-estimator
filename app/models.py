"""SQLAlchemy models for Tax Estimator."""
from datetime import date
from flask_login import UserMixin
from app import db, login_manager


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    person1_name = db.Column(db.String(64), nullable=True)
    person2_name = db.Column(db.String(64), nullable=True)

    @property
    def display_person1(self):
        return self.person1_name or "Person 1"

    @property
    def display_person2(self):
        return self.person2_name or "Person 2"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ---------------------------------------------------------------------------
# Tax Year
# ---------------------------------------------------------------------------

class TaxYear(db.Model):
    __tablename__ = "tax_year"

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False, unique=True)
    notes = db.Column(db.Text, nullable=True)
    prior_year_federal_tax = db.Column(db.Numeric(12, 2), nullable=True)
    prior_year_ca_tax = db.Column(db.Numeric(12, 2), nullable=True)
    prior_year_agi = db.Column(db.Numeric(12, 2), nullable=True)
    taxable_state_refund = db.Column(db.Numeric(12, 2), nullable=True, default=0)
    ca_employer_hsa_contributions = db.Column(db.Numeric(12, 2), nullable=True, default=0)
    ca_hsa_earnings = db.Column(db.Numeric(12, 2), nullable=True, default=0)

    # Relationships (cascade delete children when TaxYear is deleted)
    employers = db.relationship("Employer", back_populates="tax_year", cascade="all, delete-orphan")
    se_income = db.relationship("SelfEmploymentIncome", back_populates="tax_year", cascade="all, delete-orphan")
    se_expenses = db.relationship("SelfEmploymentExpense", back_populates="tax_year", cascade="all, delete-orphan")
    capital_gains = db.relationship("CapitalGain", back_populates="tax_year", cascade="all, delete-orphan")
    deductions = db.relationship("Deduction", back_populates="tax_year", cascade="all, delete-orphan")
    child_care_expenses = db.relationship("ChildCareExpense", back_populates="tax_year", cascade="all, delete-orphan")
    estimated_tax_payments = db.relationship("EstimatedTaxPayment", back_populates="tax_year", cascade="all, delete-orphan")
    vehicle_mileage = db.relationship("VehicleMileage", back_populates="tax_year", cascade="all, delete-orphan")
    retirement_contributions = db.relationship("RetirementContribution", back_populates="tax_year", cascade="all, delete-orphan")
    insurance_premiums = db.relationship("InsurancePremium", back_populates="tax_year", cascade="all, delete-orphan")
    hsa_contributions = db.relationship("HSAContribution", back_populates="tax_year", cascade="all, delete-orphan")
    settings = db.relationship("TaxYearSettings", back_populates="tax_year", uselist=False, cascade="all, delete-orphan")
    llcs = db.relationship("SingleMemberLLC", back_populates="tax_year", cascade="all, delete-orphan", order_by="SingleMemberLLC.person")
    home_offices = db.relationship("HomeOffice", back_populates="tax_year", cascade="all, delete-orphan")
    interest_income = db.relationship("InterestIncome", back_populates="tax_year", cascade="all, delete-orphan", order_by="InterestIncome.payer")
    dividend_income = db.relationship("DividendIncome", back_populates="tax_year", cascade="all, delete-orphan", order_by="DividendIncome.payer")
    unemployment_compensation = db.relationship("UnemploymentCompensation", back_populates="tax_year", cascade="all, delete-orphan", order_by="UnemploymentCompensation.payer")


# ---------------------------------------------------------------------------
# W-2 / Paystub
# ---------------------------------------------------------------------------

class Employer(db.Model):
    __tablename__ = "employer"

    id = db.Column(db.Integer, primary_key=True)
    tax_year_id = db.Column(db.Integer, db.ForeignKey("tax_year.id", ondelete="CASCADE"), nullable=False)
    person = db.Column(db.String(64), nullable=False)  # "Person 1" or "Person 2"
    name = db.Column(db.String(128), nullable=False)
    first_paystub_date = db.Column(db.Date, nullable=False)
    is_covered_by_retirement_plan = db.Column(db.Boolean, nullable=False, default=True)
    notes = db.Column(db.Text, nullable=True)

    tax_year = db.relationship("TaxYear", back_populates="employers")
    paystubs = db.relationship("Paystub", back_populates="employer", cascade="all, delete-orphan", order_by="Paystub.pay_date")
    custom_field_defs = db.relationship("PaystubCustomFieldDef", back_populates="employer", cascade="all, delete-orphan", order_by="PaystubCustomFieldDef.sort_order")


class Paystub(db.Model):
    __tablename__ = "paystub"

    id = db.Column(db.Integer, primary_key=True)
    employer_id = db.Column(db.Integer, db.ForeignKey("employer.id", ondelete="CASCADE"), nullable=False)
    pay_period_start = db.Column(db.Date, nullable=True)
    pay_period_end = db.Column(db.Date, nullable=True)
    pay_date = db.Column(db.Date, nullable=False)
    is_actual = db.Column(db.Boolean, nullable=False, default=False)

    # Standard withholding / deduction fields (default 0)
    gross_pay = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    federal_income_withholding = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    ss_withholding = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    medicare_withholding = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    state_income_withholding = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    state_disability_withholding = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    medical_insurance = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    dental_insurance = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    vision_insurance = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    pretax_401k = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    roth_401k = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    dependent_care_fsa = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    healthcare_fsa = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    employer_hsa_contribution = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    notes = db.Column(db.Text, nullable=True)

    employer = db.relationship("Employer", back_populates="paystubs")
    custom_field_values = db.relationship("PaystubCustomFieldValue", back_populates="paystub", cascade="all, delete-orphan")

    @property
    def pretax_benefit_total(self):
        """Total pre-tax benefit deductions that reduce Box 1 (taxable) wages."""
        standard = (
            self.medical_insurance + self.dental_insurance + self.vision_insurance
            + self.pretax_401k + self.dependent_care_fsa + self.healthcare_fsa
        )
        custom = sum(
            v.amount for v in self.custom_field_values
            if v.field_def.field_type == "pre_tax_deduct"
        )
        return standard + custom

    @property
    def custom_pretax_adder_total(self):
        """Sum of custom pre-tax addition fields (increase taxable wages)."""
        return sum(
            v.amount for v in self.custom_field_values
            if v.field_def.field_type == "pre_tax_adder"
        )

    @property
    def take_home_pay(self):
        """Net pay after all withholdings and payroll deductions."""
        custom_posttax_deduct = sum(
            v.amount for v in self.custom_field_values
            if v.field_def.field_type == "post_tax_deduct"
        )
        custom_posttax_adder = sum(
            v.amount for v in self.custom_field_values
            if v.field_def.field_type == "post_tax_adder"
        )
        return (
            self.gross_pay
            - self.federal_income_withholding
            - self.ss_withholding
            - self.medicare_withholding
            - self.state_income_withholding
            - self.state_disability_withholding
            - self.roth_401k
            - self.pretax_benefit_total
            + self.custom_pretax_adder_total
            - custom_posttax_deduct
            + custom_posttax_adder
        )


CUSTOM_FIELD_TYPES = [
    ("pre_tax_deduct",  "Pre-tax deduction (reduces taxable wages)"),
    ("pre_tax_adder",   "Pre-tax addition (increases taxable wages)"),
    ("post_tax_deduct", "Post-tax deduction"),
    ("post_tax_adder",  "Post-tax addition"),
]


class PaystubCustomFieldDef(db.Model):
    __tablename__ = "paystub_custom_field_def"

    id = db.Column(db.Integer, primary_key=True)
    employer_id = db.Column(db.Integer, db.ForeignKey("employer.id", ondelete="CASCADE"), nullable=False)
    field_name = db.Column(db.String(128), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    field_type = db.Column(db.String(32), nullable=False, server_default="post_tax_deduct")

    employer = db.relationship("Employer", back_populates="custom_field_defs")
    values = db.relationship("PaystubCustomFieldValue", back_populates="field_def", cascade="all, delete-orphan")


class PaystubCustomFieldValue(db.Model):
    __tablename__ = "paystub_custom_field_value"

    id = db.Column(db.Integer, primary_key=True)
    paystub_id = db.Column(db.Integer, db.ForeignKey("paystub.id", ondelete="CASCADE"), nullable=False)
    field_def_id = db.Column(db.Integer, db.ForeignKey("paystub_custom_field_def.id", ondelete="CASCADE"), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    paystub = db.relationship("Paystub", back_populates="custom_field_values")
    field_def = db.relationship("PaystubCustomFieldDef", back_populates="values")


# ---------------------------------------------------------------------------
# Self-Employment
# ---------------------------------------------------------------------------

SE_INCOME_CATEGORIES = [
    "consulting", "freelance", "rental", "royalties", "other",
]

SE_EXPENSE_CATEGORIES = [
    "office", "vehicle", "supplies", "software", "professional_services",
    "meals", "travel", "other",
]


class SelfEmploymentIncome(db.Model):
    __tablename__ = "self_employment_income"

    id = db.Column(db.Integer, primary_key=True)
    tax_year_id = db.Column(db.Integer, db.ForeignKey("tax_year.id", ondelete="CASCADE"), nullable=False)
    person = db.Column(db.String(64), nullable=False)
    client = db.Column(db.String(128), nullable=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    date = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(64), nullable=False, default="consulting")
    notes = db.Column(db.Text, nullable=True)
    llc_id = db.Column(db.Integer, db.ForeignKey("single_member_llc.id", ondelete="SET NULL"), nullable=True)

    tax_year = db.relationship("TaxYear", back_populates="se_income")
    llc = db.relationship("SingleMemberLLC", back_populates="income")


class SelfEmploymentExpense(db.Model):
    __tablename__ = "self_employment_expense"

    id = db.Column(db.Integer, primary_key=True)
    tax_year_id = db.Column(db.Integer, db.ForeignKey("tax_year.id", ondelete="CASCADE"), nullable=False)
    description = db.Column(db.String(256), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    date = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(64), nullable=False, default="other")
    notes = db.Column(db.Text, nullable=True)
    llc_id = db.Column(db.Integer, db.ForeignKey("single_member_llc.id", ondelete="SET NULL"), nullable=True)

    tax_year = db.relationship("TaxYear", back_populates="se_expenses")
    llc = db.relationship("SingleMemberLLC", back_populates="expenses")


# ---------------------------------------------------------------------------
# Capital Gains
# ---------------------------------------------------------------------------

class CapitalGain(db.Model):
    __tablename__ = "capital_gain"

    id = db.Column(db.Integer, primary_key=True)
    tax_year_id = db.Column(db.Integer, db.ForeignKey("tax_year.id", ondelete="CASCADE"), nullable=False)
    person = db.Column(db.String(64), nullable=False)
    description = db.Column(db.String(256), nullable=False)
    proceeds = db.Column(db.Numeric(12, 2), nullable=False)
    cost_basis = db.Column(db.Numeric(12, 2), nullable=False)
    acquisition_date = db.Column(db.Date, nullable=False)
    sale_date = db.Column(db.Date, nullable=False)
    is_long_term = db.Column(db.Boolean, nullable=False, default=True)
    notes = db.Column(db.Text, nullable=True)

    tax_year = db.relationship("TaxYear", back_populates="capital_gains")

    @property
    def gain(self):
        return self.proceeds - self.cost_basis


# ---------------------------------------------------------------------------
# Deductions
# ---------------------------------------------------------------------------

DEDUCTION_CATEGORIES = [
    "mortgage_interest", "property_tax", "state_tax", "charitable", "medical", "other",
]


class Deduction(db.Model):
    __tablename__ = "deduction"

    id = db.Column(db.Integer, primary_key=True)
    tax_year_id = db.Column(db.Integer, db.ForeignKey("tax_year.id", ondelete="CASCADE"), nullable=False)
    category = db.Column(db.String(64), nullable=False)
    description = db.Column(db.String(256), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text, nullable=True)

    tax_year = db.relationship("TaxYear", back_populates="deductions")


class ChildCareExpense(db.Model):
    __tablename__ = "child_care_expense"

    id = db.Column(db.Integer, primary_key=True)
    tax_year_id = db.Column(db.Integer, db.ForeignKey("tax_year.id", ondelete="CASCADE"), nullable=False)
    provider = db.Column(db.String(128), nullable=False)
    child_name = db.Column(db.String(128), nullable=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text, nullable=True)

    tax_year = db.relationship("TaxYear", back_populates="child_care_expenses")


# ---------------------------------------------------------------------------
# Estimated Tax Payments
# ---------------------------------------------------------------------------

class EstimatedTaxPayment(db.Model):
    __tablename__ = "estimated_tax_payment"

    id = db.Column(db.Integer, primary_key=True)
    tax_year_id = db.Column(db.Integer, db.ForeignKey("tax_year.id", ondelete="CASCADE"), nullable=False)
    jurisdiction = db.Column(db.String(16), nullable=False)   # "federal" or "ca"
    quarter = db.Column(db.String(4), nullable=False)          # "Q1" – "Q4"
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    date_paid = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text, nullable=True)

    tax_year = db.relationship("TaxYear", back_populates="estimated_tax_payments")


# ---------------------------------------------------------------------------
# Vehicle Mileage
# ---------------------------------------------------------------------------

class VehicleMileage(db.Model):
    __tablename__ = "vehicle_mileage"

    id = db.Column(db.Integer, primary_key=True)
    tax_year_id = db.Column(db.Integer, db.ForeignKey("tax_year.id", ondelete="CASCADE"), nullable=False)
    vehicle_name = db.Column(db.String(128), nullable=False)
    date = db.Column(db.Date, nullable=False)
    odometer_start = db.Column(db.Integer, nullable=True)
    odometer_end = db.Column(db.Integer, nullable=True)
    business_miles = db.Column(db.Numeric(8, 1), nullable=False)
    purpose = db.Column(db.String(256), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    llc_id = db.Column(db.Integer, db.ForeignKey("single_member_llc.id", ondelete="SET NULL"), nullable=True)

    tax_year = db.relationship("TaxYear", back_populates="vehicle_mileage")
    llc = db.relationship("SingleMemberLLC", back_populates="mileage")


# ---------------------------------------------------------------------------
# Retirement Contributions (IRA / SEP / Solo 401k)
# ---------------------------------------------------------------------------

RETIREMENT_ACCOUNT_TYPES = [
    "traditional_ira", "roth_ira", "sep_ira",
    "solo_401k_employee", "solo_401k_employer",
]


class RetirementContribution(db.Model):
    __tablename__ = "retirement_contribution"

    id = db.Column(db.Integer, primary_key=True)
    tax_year_id = db.Column(db.Integer, db.ForeignKey("tax_year.id", ondelete="CASCADE"), nullable=False)
    person = db.Column(db.String(64), nullable=False)
    account_type = db.Column(db.String(32), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    llc_id = db.Column(db.Integer, db.ForeignKey("single_member_llc.id", ondelete="SET NULL"), nullable=True)

    tax_year = db.relationship("TaxYear", back_populates="retirement_contributions")
    llc = db.relationship("SingleMemberLLC", back_populates="retirement_contributions")


# ---------------------------------------------------------------------------
# Insurance Premiums (self-employed only — W-2 premiums are via Paystub)
# ---------------------------------------------------------------------------

INSURANCE_TYPES = ["health", "dental", "vision"]


class InsurancePremium(db.Model):
    __tablename__ = "insurance_premium"

    id = db.Column(db.Integer, primary_key=True)
    tax_year_id = db.Column(db.Integer, db.ForeignKey("tax_year.id", ondelete="CASCADE"), nullable=False)
    person = db.Column(db.String(64), nullable=False)
    insurance_type = db.Column(db.String(16), nullable=False)
    is_self_employed = db.Column(db.Boolean, nullable=False, default=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text, nullable=True)

    tax_year = db.relationship("TaxYear", back_populates="insurance_premiums")


# ---------------------------------------------------------------------------
# HSA Contributions
# ---------------------------------------------------------------------------

class HSAContribution(db.Model):
    __tablename__ = "hsa_contribution"

    id = db.Column(db.Integer, primary_key=True)
    tax_year_id = db.Column(db.Integer, db.ForeignKey("tax_year.id", ondelete="CASCADE"), nullable=False)
    person = db.Column(db.String(64), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text, nullable=True)

    tax_year = db.relationship("TaxYear", back_populates="hsa_contributions")


# ---------------------------------------------------------------------------
# Per-Year Tax Rate Settings (overrides constants.py defaults)
# ---------------------------------------------------------------------------

class TaxYearSettings(db.Model):
    __tablename__ = "tax_year_settings"

    id = db.Column(db.Integer, primary_key=True)
    tax_year_id = db.Column(db.Integer, db.ForeignKey("tax_year.id", ondelete="CASCADE"),
                            nullable=False, unique=True)

    # Federal scalars (nullable = use constants.py default)
    federal_standard_deduction = db.Column(db.Numeric(12, 2), nullable=True)
    ss_wage_base = db.Column(db.Numeric(12, 2), nullable=True)
    salt_cap = db.Column(db.Numeric(12, 2), nullable=True)
    child_tax_credit = db.Column(db.Numeric(10, 2), nullable=True)
    ctc_phase_out_start = db.Column(db.Numeric(12, 2), nullable=True)
    niit_rate = db.Column(db.Numeric(8, 6), nullable=True)
    niit_threshold = db.Column(db.Numeric(12, 2), nullable=True)
    additional_medicare_rate = db.Column(db.Numeric(8, 6), nullable=True)
    additional_medicare_threshold = db.Column(db.Numeric(12, 2), nullable=True)
    irs_mileage_rate = db.Column(db.Numeric(8, 4), nullable=True)
    solo_401k_employee_limit = db.Column(db.Numeric(10, 2), nullable=True)
    solo_401k_total_limit = db.Column(db.Numeric(10, 2), nullable=True)
    qbi_threshold = db.Column(db.Numeric(12, 2), nullable=True)

    # California scalars
    ca_standard_deduction = db.Column(db.Numeric(12, 2), nullable=True)
    ca_sdi_rate = db.Column(db.Numeric(8, 6), nullable=True)
    ca_mental_health_surtax_rate = db.Column(db.Numeric(8, 6), nullable=True)
    ca_mental_health_surtax_threshold = db.Column(db.Numeric(12, 2), nullable=True)
    ca_personal_exemption = db.Column(db.Numeric(10, 2), nullable=True)
    ca_dependent_credit = db.Column(db.Numeric(10, 2), nullable=True)
    ca_young_child_credit = db.Column(db.Numeric(10, 2), nullable=True)
    qualifying_children_under_6 = db.Column(db.Integer, nullable=True)

    # Bracket arrays (JSON-encoded; null = use constants.py default)
    # Format: [{"rate": 0.10, "upper": 24800}, ..., {"rate": 0.37, "upper": null}]
    federal_brackets_json = db.Column(db.Text, nullable=True)
    ltcg_brackets_json = db.Column(db.Text, nullable=True)
    ca_brackets_json = db.Column(db.Text, nullable=True)

    tax_year = db.relationship("TaxYear", back_populates="settings")


# ---------------------------------------------------------------------------
# Single-Member LLC (Disregarded Entity)
# ---------------------------------------------------------------------------

class SingleMemberLLC(db.Model):
    __tablename__ = "single_member_llc"
    __table_args__ = (db.UniqueConstraint("tax_year_id", "person", name="uq_llc_year_person"),)

    id = db.Column(db.Integer, primary_key=True)
    tax_year_id = db.Column(db.Integer, db.ForeignKey("tax_year.id", ondelete="CASCADE"), nullable=False)
    person = db.Column(db.String(64), nullable=False)  # "Person 1" or "Person 2"
    name = db.Column(db.String(128), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    sstb = db.Column(db.Boolean, nullable=False, default=False)

    tax_year = db.relationship("TaxYear", back_populates="llcs")
    home_office = db.relationship("HomeOffice", back_populates="llc", uselist=False, cascade="all, delete-orphan")
    income = db.relationship("SelfEmploymentIncome", back_populates="llc")
    expenses = db.relationship("SelfEmploymentExpense", back_populates="llc")
    mileage = db.relationship("VehicleMileage", back_populates="llc")
    retirement_contributions = db.relationship("RetirementContribution", back_populates="llc")
    quarterly_pl = db.relationship("LLCQuarterlyPL", back_populates="llc",
                                   cascade="all, delete-orphan",
                                   order_by="LLCQuarterlyPL.quarter")


# ---------------------------------------------------------------------------
# LLC Quarterly P&L Grid
# ---------------------------------------------------------------------------

class LLCQuarterlyPL(db.Model):
    __tablename__ = "llc_quarterly_pl"
    __table_args__ = (db.UniqueConstraint("llc_id", "quarter", name="uq_llc_quarter"),)

    id = db.Column(db.Integer, primary_key=True)
    llc_id = db.Column(db.Integer, db.ForeignKey("single_member_llc.id", ondelete="CASCADE"), nullable=False)
    quarter = db.Column(db.Integer, nullable=False)  # 1–4

    income       = db.Column(db.Numeric(12, 2), nullable=True)
    cogs         = db.Column(db.Numeric(12, 2), nullable=True)
    expenses     = db.Column(db.Numeric(12, 2), nullable=True)
    other_income = db.Column(db.Numeric(12, 2), nullable=True)

    llc = db.relationship("SingleMemberLLC", back_populates="quarterly_pl")


# ---------------------------------------------------------------------------
# Home Office Deduction (tied to a Single-Member LLC)
# ---------------------------------------------------------------------------

HOME_OFFICE_DEDUCTION_TYPES = [
    ("property_taxes",    "Property Taxes"),
    ("mortgage_interest", "Mortgage Interest"),
    ("home_insurance",    "Home Insurance"),
    ("utilities",         "Utilities"),
    ("garbage",           "Garbage"),
    ("hoa_dues",          "HOA Dues"),
    ("depreciation",      "Depreciation (Business % Only)"),
]


class HomeOffice(db.Model):
    __tablename__ = "home_office"

    id = db.Column(db.Integer, primary_key=True)
    tax_year_id = db.Column(db.Integer, db.ForeignKey("tax_year.id", ondelete="CASCADE"), nullable=False)
    llc_id = db.Column(db.Integer, db.ForeignKey("single_member_llc.id", ondelete="CASCADE"), nullable=False, unique=True)

    home_sqft = db.Column(db.Numeric(10, 1), nullable=False)
    business_sqft = db.Column(db.Numeric(10, 1), nullable=False)

    # Deduction amounts entered by user (whole-home totals except depreciation)
    property_taxes = db.Column(db.Numeric(12, 2), nullable=True)
    mortgage_interest = db.Column(db.Numeric(12, 2), nullable=True)
    home_insurance = db.Column(db.Numeric(12, 2), nullable=True)
    utilities = db.Column(db.Numeric(12, 2), nullable=True)
    garbage = db.Column(db.Numeric(12, 2), nullable=True)
    hoa_dues = db.Column(db.Numeric(12, 2), nullable=True)
    depreciation = db.Column(db.Numeric(12, 2), nullable=True)  # full business amount

    notes = db.Column(db.Text, nullable=True)

    tax_year = db.relationship("TaxYear", back_populates="home_offices")
    llc = db.relationship("SingleMemberLLC", back_populates="home_office")

    @property
    def business_pct(self):
        if not self.home_sqft or float(self.home_sqft) == 0:
            return 0.0
        return float(self.business_sqft) / float(self.home_sqft)

    def business_amount(self, field):
        """Return the business portion of a deduction field."""
        val = getattr(self, field)
        if val is None:
            return 0.0
        if field == "depreciation":
            return float(val)
        return float(val) * self.business_pct

    def personal_amount(self, field):
        """Return the personal (non-business) portion of a deduction field.
        Only applicable for property_taxes and mortgage_interest.
        Other fields have no personal deduction."""
        val = getattr(self, field)
        if val is None or field not in ("property_taxes", "mortgage_interest"):
            return 0.0
        return float(val) * (1.0 - self.business_pct)


# ---------------------------------------------------------------------------
# Interest Income (1099-INT)
# ---------------------------------------------------------------------------

class InterestIncome(db.Model):
    __tablename__ = "interest_income"

    id = db.Column(db.Integer, primary_key=True)
    tax_year_id = db.Column(db.Integer, db.ForeignKey("tax_year.id", ondelete="CASCADE"), nullable=False)
    payer = db.Column(db.String(128), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    notes = db.Column(db.Text, nullable=True)

    tax_year = db.relationship("TaxYear", back_populates="interest_income")


# ---------------------------------------------------------------------------
# Dividend Income (1099-DIV)
# ---------------------------------------------------------------------------

class DividendIncome(db.Model):
    __tablename__ = "dividend_income"

    id = db.Column(db.Integer, primary_key=True)
    tax_year_id = db.Column(db.Integer, db.ForeignKey("tax_year.id", ondelete="CASCADE"), nullable=False)
    payer = db.Column(db.String(128), nullable=False)
    ordinary_dividends = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    qualified_dividends = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    notes = db.Column(db.Text, nullable=True)

    tax_year = db.relationship("TaxYear", back_populates="dividend_income")


# ---------------------------------------------------------------------------
# Unemployment Compensation (1099-G)
# ---------------------------------------------------------------------------

class UnemploymentCompensation(db.Model):
    __tablename__ = "unemployment_compensation"

    id = db.Column(db.Integer, primary_key=True)
    tax_year_id = db.Column(db.Integer, db.ForeignKey("tax_year.id", ondelete="CASCADE"), nullable=False)
    payer = db.Column(db.String(128), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    notes = db.Column(db.Text, nullable=True)

    tax_year = db.relationship("TaxYear", back_populates="unemployment_compensation")
