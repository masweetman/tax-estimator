# Coding Conventions

## Core Sections (Required)

### 1) Naming Rules

| Item | Rule | Example | Evidence |
|------|------|---------|----------|
| Files | `snake_case.py`, one blueprint/module per feature | `federal_summary.py`, `pdf_parser.py` | [app/routes/](../../app/routes) |
| Functions/methods | `snake_case`, private/internal helpers prefixed with `_` | `_build_inputs`, `_is_safe_url`, `_generate_qr_b64` | [app/routes/dashboard.py](../../app/routes/dashboard.py), [app/auth.py](../../app/auth.py) |
| Classes / models | `PascalCase`, matches DB entity name | `SelfEmploymentIncome`, `PaystubCustomFieldDef` | [app/models.py](../../app/models.py) |
| Blueprint variables | `<name>_bp` | `w2_bp`, `dashboard_bp`, `auth_bp` | [app/auth.py](../../app/auth.py) |
| Constants / module-level data | `UPPER_SNAKE_CASE` | `FEDERAL_BRACKETS_MFJ`, `SE_INCOME_CATEGORIES`, `CUSTOM_FIELD_TYPES` | [app/calculator/constants.py](../../app/calculator/constants.py), [app/models.py](../../app/models.py) |
| Env vars | `UPPER_SNAKE_CASE` | `SECRET_KEY`, `DATABASE_URL`, `FLASK_ENV` | [.env.example](../../.env.example) |

### 2) Formatting and Linting

- Formatter: none configured — no `pyproject.toml`, `.black`, or `ruff` config found in the repo root.
- Linter: none configured — no `.flake8`, `.pylintrc`, or `pre-commit-config.yaml` found.
- `[TODO]` — no enforced style rules are verifiable from the repo; observed style is 4-space indentation, double-quoted strings, and section-divider comments (`# --- ... ---`) grouping related code within a file (e.g. [app/models.py](../../app/models.py), [app/routes/dashboard.py](../../app/routes/dashboard.py)).
- Run commands: none defined (no `Makefile`, no lint/format scripts in any manifest).

### 3) Import and Module Conventions

- Import grouping: standard library first, then third-party (Flask/Flask extensions), then local `app.*` imports — observed consistently, e.g. [app/auth.py](../../app/auth.py) (`datetime, io, base64, urllib.parse` → `pyotp, qrcode, flask, flask_login, werkzeug` → local model imports).
- Alias vs relative import policy: no `tsconfig`-style aliases (Python project); intra-package imports use relative dots only inside `app/calculator/` (`from .federal import calculate_federal`), everywhere else absolute `app.*` imports are used.
- Deferred/local imports are a deliberate, repeated convention to avoid circular imports — e.g. `from app.models import User` inside `create_app()` and inside several route handlers ([app/__init__.py](../../app/__init__.py), [app/auth.py](../../app/auth.py)).
- No barrel/`__init__.py` re-exports: `app/routes/__init__.py` and `app/calculator/__init__.py` are empty; blueprints are imported directly from their module path in `app/__init__.py`.

### 4) Error and Logging Conventions

- No logging library is used anywhere in `app/` (no `import logging`, no `app.logger` calls found in a full-codebase search).
- Error strategy is per-layer and inconsistent:
  - Routes: user-facing errors surface via Flask `flash()` messages + redirect (e.g. [app/auth.py](../../app/auth.py) `flash("Invalid username or password.", "danger")`); malformed request data is caught with narrow `except ValueError`/`except FileNotFoundError` blocks and silently ignored or defaulted (e.g. [app/routes/settings.py](../../app/routes/settings.py), [app/routes/tax_years.py](../../app/routes/tax_years.py)).
  - DB bootstrap: `app/__init__.py` catches `IntegrityError`/`OperationalError` around the default-user seed and silently rolls back rather than logging.
  - `app/pdf_parser.py` is fully best-effort: parse failures return an empty dict with a `_warnings` list instead of raising.
  - 404s are raised via Flask's `abort(404)` idiom (`db.session.get(...) or abort(404)`), e.g. [app/routes/w2.py](../../app/routes/w2.py).
- Sensitive-data redaction: no explicit redaction logic exists; there is no logging to redact from. `[TODO]` — confirm gunicorn/OLS access logs don't capture sensitive form data (they log request lines only, not bodies, per default gunicorn behavior).

### 5) Testing Conventions

- Test file naming/location: `tests/test_<area>.py`, matching `pytest.ini`'s `python_files = test_*.py`. See [pytest.ini](../../pytest.ini).
- Fixtures: shared fixtures (`app`, `db`, `client`, `auth_client`) are centralized in [tests/conftest.py](../../tests/conftest.py); `auth_client` logs in by directly writing Flask-Login session keys rather than posting to `/auth/login`.
- Mocking strategy: no mocking library is used — tests exercise the real Flask app + a `testing`-config SQLite in-memory DB, with per-test rollback via the `db` fixture's explicit transaction.
- Coverage expectation: `[TODO]` — `coverage` is installed as a dev dependency and README documents a `--cov=app` command, but no minimum threshold is enforced in `pytest.ini` or CI (no CI exists).

### 6) Evidence

- [app/models.py](../../app/models.py)
- [app/auth.py](../../app/auth.py)
- [app/routes/dashboard.py](../../app/routes/dashboard.py)
- [tests/conftest.py](../../tests/conftest.py)
- [pytest.ini](../../pytest.ini)

## Extended Sections (Optional)

Not added — codebase is small/consistent enough that the core sections capture the conventions in full.
