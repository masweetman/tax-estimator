#!/usr/bin/env python3
"""Management CLI for Tax Estimator."""
import os
import sys
import json
import getpass
from sqlalchemy import text

# Ensure the app directory is on the path
sys.path.insert(0, os.path.dirname(__file__))


def get_app():
    from app import create_app
    return create_app(os.environ.get("FLASK_ENV", "development"))


def _seed_tax_years(db):
    """Seed default TaxYear + TaxYearSettings records for 2025 and 2026 (idempotent)."""
    from app.models import TaxYear, TaxYearSettings

    def _brackets_json(pairs):
        return json.dumps([{"rate": r, "upper": u} for r, u in pairs])

    TAX_YEAR_DATA = {
        2025: {
            # Federal scalars
            "federal_standard_deduction": 31_500,
            "ss_wage_base": 176_100,
            "salt_cap": 40_000,
            "child_tax_credit": 2_200,
            "ctc_phase_out_start": 400_000,
            "niit_rate": 0.038,
            "niit_threshold": 250_000,
            "additional_medicare_rate": 0.009,
            "additional_medicare_threshold": 250_000,
            "irs_mileage_rate": 0.70,
            # California scalars
            "ca_standard_deduction": 11_412,
            "ca_sdi_rate": 0.012,
            "ca_mental_health_surtax_rate": 0.01,
            "ca_mental_health_surtax_threshold": 1_000_000,
            "ca_personal_exemption": 306,
            "ca_dependent_credit": 475,
            "ca_young_child_credit": None,
            # Bracket arrays
            "federal_brackets_json": _brackets_json([
                (0.10,  23_850),
                (0.12,  96_950),
                (0.22, 206_700),
                (0.24, 394_600),
                (0.32, 501_050),
                (0.35, 751_600),
                (0.37,    None),
            ]),
            "ltcg_brackets_json": _brackets_json([
                (0.00,  96_700),
                (0.15, 583_750),
                (0.20,    None),
            ]),
            "ca_brackets_json": _brackets_json([
                (0.01,    22_158),
                (0.02,    52_528),
                (0.04,    82_904),
                (0.06,   115_084),
                (0.08,   145_448),
                (0.093,  742_958),
                (0.103,  891_542),
                (0.113, 1_485_906),
                (0.123,     None),
            ]),
        },
        2026: {
            # Federal scalars
            "federal_standard_deduction": 32_200,
            "ss_wage_base": 184_500,
            "salt_cap": 40_400,
            "child_tax_credit": 2_200,
            "ctc_phase_out_start": 400_000,
            "niit_rate": 0.038,
            "niit_threshold": 250_000,
            "additional_medicare_rate": 0.009,
            "additional_medicare_threshold": 250_000,
            "irs_mileage_rate": 0.725,
            # California scalars
            "ca_standard_deduction": 11_720,
            "ca_sdi_rate": 0.013,
            "ca_mental_health_surtax_rate": 0.01,
            "ca_mental_health_surtax_threshold": 1_000_000,
            "ca_personal_exemption": 314,
            "ca_dependent_credit": 488,
            "ca_young_child_credit": 1_117,
            # Bracket arrays
            "federal_brackets_json": _brackets_json([
                (0.10,  24_800),
                (0.12, 100_800),
                (0.22, 211_400),
                (0.24, 403_550),
                (0.32, 512_450),
                (0.35, 768_700),
                (0.37,    None),
            ]),
            "ltcg_brackets_json": _brackets_json([
                (0.00,  98_900),
                (0.15, 613_700),
                (0.20,    None),
            ]),
            "ca_brackets_json": _brackets_json([
                (0.01,    22_756),
                (0.02,    53_946),
                (0.04,    85_142),
                (0.06,   118_191),
                (0.08,   149_375),
                (0.093,  763_018),
                (0.103,  915_614),
                (0.113, 1_526_025),
                (0.123,     None),
            ]),
        },
    }

    for year, data in TAX_YEAR_DATA.items():
        ty = TaxYear.query.filter_by(year=year).first()
        if ty is None:
            ty = TaxYear(year=year)
            db.session.add(ty)
            db.session.flush()  # get ty.id
            print(f"Created tax year {year}.")
        else:
            print(f"Tax year {year} already exists.")

        if ty.settings is None:
            settings = TaxYearSettings(tax_year_id=ty.id, **data)
            db.session.add(settings)
            print(f"Seeded settings for tax year {year}.")
        else:
            print(f"Settings for tax year {year} already exist, skipping.")

    db.session.commit()


def cmd_init_db():
    """Create all database tables and seed default tax years."""
    app = get_app()
    with app.app_context():
        from app import db
        db.create_all()
        print("Database tables created.")
        _seed_tax_years(db)


def cmd_create_user():
    """Create or update the single app user."""
    from werkzeug.security import generate_password_hash
    username = input("Username [admin]: ").strip() or "admin"
    while True:
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password == confirm:
            break
        print("Passwords do not match. Try again.")

    app = get_app()
    with app.app_context():
        from app import db
        from app.models import User
        user = User.query.filter_by(username=username).first()
        if user:
            user.password_hash = generate_password_hash(password)
            print(f"Password updated for user '{username}'.")
        else:
            user = User(username=username, password_hash=generate_password_hash(password))
            db.session.add(user)
            print(f"User '{username}' created.")
        db.session.commit()


def cmd_migrate_db():
    """Add new columns to existing databases (safe to run multiple times)."""
    app = get_app()
    with app.app_context():
        from app import db
        with db.engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(user)"))
            existing_cols = {row[1] for row in result}
            added = []
            if "person1_name" not in existing_cols:
                conn.execute(text("ALTER TABLE user ADD COLUMN person1_name TEXT"))
                added.append("person1_name")
            if "person2_name" not in existing_cols:
                conn.execute(text("ALTER TABLE user ADD COLUMN person2_name TEXT"))
                added.append("person2_name")
            conn.commit()
        if added:
            print(f"Added columns: {', '.join(added)}")
        else:
            print("No changes needed — database already up to date.")


def cmd_migrate_llc():
    """Add LLC / home-office tables and llc_id columns to existing databases (safe to run multiple times)."""
    app = get_app()
    with app.app_context():
        from app import db
        # Create any new tables (single_member_llc, home_office) — skips existing ones
        db.create_all()

        added = []
        with db.engine.connect() as conn:
            for table, col, typedef in [
                ("self_employment_income",  "llc_id", "INTEGER REFERENCES single_member_llc(id) ON DELETE SET NULL"),
                ("self_employment_expense", "llc_id", "INTEGER REFERENCES single_member_llc(id) ON DELETE SET NULL"),
                ("vehicle_mileage",         "llc_id", "INTEGER REFERENCES single_member_llc(id) ON DELETE SET NULL"),
            ]:
                result = conn.execute(text(f"PRAGMA table_info({table})"))
                existing = {row[1] for row in result}
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}"))
                    added.append(f"{table}.{col}")
            conn.commit()

        if added:
            print(f"Added columns: {', '.join(added)}")
        else:
            print("No schema changes needed — database already up to date.")


def cmd_migrate_solo401k():
    """Add llc_id column to retirement_contribution table (safe to run multiple times)."""
    app = get_app()
    with app.app_context():
        from app import db
        added = []
        with db.engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(retirement_contribution)"))
            existing = {row[1] for row in result}
            if "llc_id" not in existing:
                conn.execute(text(
                    "ALTER TABLE retirement_contribution "
                    "ADD COLUMN llc_id INTEGER REFERENCES single_member_llc(id) ON DELETE SET NULL"
                ))
                added.append("retirement_contribution.llc_id")
            conn.commit()
        if added:
            print(f"Added columns: {', '.join(added)}")
        else:
            print("No schema changes needed — database already up to date.")


def cmd_migrate_quarterly_pl():
    """Create the llc_quarterly_pl table (safe to run multiple times)."""
    app = get_app()
    with app.app_context():
        from app import db
        db.create_all()
        print("llc_quarterly_pl table ensured.")


def cmd_migrate_investment_income():
    """Create interest_income and dividend_income tables and add taxable_state_refund to tax_year (idempotent)."""
    app = get_app()
    with app.app_context():
        from app import db
        # Create new tables
        db.create_all()
        # Add taxable_state_refund column if missing
        with db.engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(tax_year)"))
            existing = {row[1] for row in result}
            if "taxable_state_refund" not in existing:
                conn.execute(text(
                    "ALTER TABLE tax_year ADD COLUMN taxable_state_refund NUMERIC(12,2) DEFAULT 0"
                ))
                print("Added tax_year.taxable_state_refund")
            else:
                print("tax_year.taxable_state_refund already exists")
            conn.commit()
        print("interest_income and dividend_income tables ensured.")


def cmd_migrate_sstb():
    """Add sstb column to single_member_llc table (idempotent)."""
    app = get_app()
    with app.app_context():
        from app import db
        with db.engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(single_member_llc)"))
            existing = {row[1] for row in result}
            if "sstb" not in existing:
                conn.execute(text(
                    "ALTER TABLE single_member_llc ADD COLUMN sstb BOOLEAN NOT NULL DEFAULT 0"
                ))
                print("Added single_member_llc.sstb")
            else:
                print("single_member_llc.sstb already exists")
            conn.commit()


def cmd_migrate_unemployment():
    """Create unemployment_compensation table (idempotent)."""
    app = get_app()
    with app.app_context():
        from app import db
        db.create_all()
        print("unemployment_compensation table ensured.")


def cmd_seed_tax_years():
    """Seed default TaxYear and TaxYearSettings for 2025 and 2026 (idempotent)."""
    app = get_app()
    with app.app_context():
        from app import db
        _seed_tax_years(db)


COMMANDS = {
    "init-db": cmd_init_db,
    "create-user": cmd_create_user,
    "migrate-db": cmd_migrate_db,
    "migrate-llc": cmd_migrate_llc,
    "migrate-solo401k": cmd_migrate_solo401k,
    "migrate-quarterly-pl": cmd_migrate_quarterly_pl,
    "migrate-investment-income": cmd_migrate_investment_income,
    "migrate-sstb": cmd_migrate_sstb,
    "migrate-unemployment": cmd_migrate_unemployment,
    "seed-tax-years": cmd_seed_tax_years,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: python manage.py [{' | '.join(COMMANDS)}]")
        sys.exit(1)
    COMMANDS[sys.argv[1]]()
