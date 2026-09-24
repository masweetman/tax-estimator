# Codebase Structure

## Core Sections (Required)

### 1) Top-Level Map

| Path | Purpose | Evidence |
|------|---------|----------|
| `app/` | Flask application package: factory, models, auth, calculator, routes, templates, static assets | [app/__init__.py](../../app/__init__.py) |
| `app/calculator/` | Pure-function tax calculation engine (federal, CA, safe harbor) | [app/calculator/engine.py](../../app/calculator/engine.py) |
| `app/routes/` | Flask blueprints, one module per feature area (dashboard, w2, se, deductions, payments, vehicles, profile, tax_years, settings, llc, federal_summary, ca_summary) | [app/routes/dashboard.py](../../app/routes/dashboard.py) |
| `app/templates/` | Jinja2 templates, mirrors `app/routes/` feature grouping (subfolders per blueprint) | [app/templates/base.html](../../app/templates/base.html) |
| `app/static/` | CSS assets (Bootstrap-based) | [app/static/css/app.css](../../app/static/css/app.css) |
| `migrations/` | Alembic migration environment and versioned migration scripts (Flask-Migrate) | [migrations/env.py](../../migrations/env.py) |
| `tests/` | pytest test suite, one file per feature/concern | [tests/conftest.py](../../tests/conftest.py) |
| `llm/` | Plain-text tax reference material (rates, instructions) — reference data, not executed code | [llm/2025_Tax_Rates_Reference.txt](../../llm/2025_Tax_Rates_Reference.txt) |
| `deploy/` | systemd service unit for production deployment | [deploy/tax-estimator.service](../../deploy/tax-estimator.service) |
| `config.py` | Environment-specific Flask config classes | [config.py](../../config.py) |
| `manage.py` | CLI script to seed `TaxYear`/`TaxYearSettings` defaults | [manage.py](../../manage.py) |
| `wsgi.py` | Production WSGI entry point (gunicorn target) | [wsgi.py](../../wsgi.py) |

### 2) Entry Points

- Main runtime entry: [wsgi.py](../../wsgi.py) — calls `create_app("production")`; gunicorn is pointed at `wsgi:app` in the systemd unit.
- Development entry: `flask --app wsgi:app run --debug` (per [README.md](../../README.md)), which still loads `wsgi.py` and thus `production` config unless `FLASK_ENV`/config name is overridden — `[ASK USER]` confirm whether local dev is expected to run under `production` config given `wsgi.py` hardcodes it.
- Secondary entry points: [manage.py](../../manage.py) is a standalone CLI (not a Flask CLI command) for idempotently seeding `TaxYear`/`TaxYearSettings` rows for 2025/2026.
- App is also self-bootstrapping: `create_app()` in [app/__init__.py](../../app/__init__.py) auto-runs `db.create_all()` and seeds a default `mike` user on every startup unless `app.testing` is set.

### 3) Module Boundaries

| Boundary | What belongs here | What must not be here |
|----------|-------------------|------------------------|
| `app/calculator/` | Pure tax-rule math (federal, CA, safe harbor) taking a plain `dict` and returning a plain `dict`; no Flask/DB imports | Flask request/session access, DB queries |
| `app/routes/*.py` | Blueprint route handlers: request/form handling, DB reads/writes, calling into `app/calculator` | Tax-law constants or bracket math (belongs in `calculator/constants.py`) |
| `app/models.py` | SQLAlchemy model/schema definitions and simple computed `@property` helpers | Route logic, HTTP concerns |
| `app/tax_settings.py` | Translates `TaxYearSettings` DB rows into the calculator's input-override dict | Direct route handling |
| `app/pdf_parser.py` | Best-effort text extraction/regex parsing of uploaded paystub PDFs | DB writes (returns a dict; caller persists it) |
| `app/templates/` | Presentation only (Jinja2) | Business logic beyond simple display formatting/filters |

### 4) Naming and Organization Rules

- File naming pattern: all Python modules use `snake_case.py` (e.g., `federal_summary.py`, `pdf_parser.py`). Evidence: [app/routes/](../../app/routes) directory listing.
- Directory organization pattern: feature-based for routes/templates (one file/folder per domain area: `w2`, `se`, `deductions`, `payments`, `vehicles`, `llc`), layer-based for the calculator (`federal.py`, `california.py`, `safe_harbor.py`, `engine.py`, `constants.py`).
- Import aliasing: none — no path aliases; imports use plain package paths (`from app.models import ...`, `from app.calculator.engine import calculate`). Many route/model modules use deferred (function-local) imports to avoid circular imports (e.g., `from app.models import User` inside `create_app`). Evidence: [app/__init__.py](../../app/__init__.py).

### 5) Evidence

- [app/__init__.py](../../app/__init__.py)
- [app/routes/dashboard.py](../../app/routes/dashboard.py)
- [app/calculator/engine.py](../../app/calculator/engine.py)
- `.codebase-scan.txt` directory tree output

## Extended Sections (Optional)

Not added — flat two-level structure (`app/<area>/`) is simple enough that a deeper map isn't needed.
