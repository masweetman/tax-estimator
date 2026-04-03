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
    pay_period_start = db.Column(db.Date, nullable=False)
    pay_period_end = db.Column(db.Date, nullable=False)
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
    notes = db.Column(db.Text, nullable=True)

    employer = db.relationship("Employer", back_populates="paystubs")
    custom_field_values = db.relationship("PaystubCustomFieldValue", back_populates="paystub", cascade="all, delete-orphan")

    @property
    def pretax_benefit_total(self):
        """Total pre-tax benefit deductions that reduce Box 1 (taxable) wages."""
        return (
            self.medical_insurance + self.dental_insurance + self.vision_insurance
            + self.pretax_401k + self.dependent_care_fsa + self.healthcare_fsa
        )


class PaystubCustomFieldDef(db.Model):
    __tablename__ = "paystub_custom_field_def"

    id = db.Column(db.Integer, primary_key=True)
    employer_id = db.Column(db.Integer, db.ForeignKey("employer.id", ondelete="CASCADE"), nullable=False)
    field_name = db.Column(db.String(128), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

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

    tax_year = db.relationship("TaxYear", back_populates="se_income")


class SelfEmploymentExpense(db.Model):
    __tablename__ = "self_employment_expense"

    id = db.Column(db.Integer, primary_key=True)
    tax_year_id = db.Column(db.Integer, db.ForeignKey("tax_year.id", ondelete="CASCADE"), nullable=False)
    description = db.Column(db.String(256), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    date = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(64), nullable=False, default="other")
    notes = db.Column(db.Text, nullable=True)

    tax_year = db.relationship("TaxYear", back_populates="se_expenses")


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
    "mortgage_interest", "property_tax", "charitable", "medical", "other",
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

    tax_year = db.relationship("TaxYear", back_populates="vehicle_mileage")


# ---------------------------------------------------------------------------
# Retirement Contributions (IRA / SEP — 401k is via Paystub)
# ---------------------------------------------------------------------------

RETIREMENT_ACCOUNT_TYPES = [
    "traditional_ira", "roth_ira", "sep_ira",
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

    tax_year = db.relationship("TaxYear", back_populates="retirement_contributions")


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
