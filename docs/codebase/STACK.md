# Technology Stack

## Core Sections (Required)

### 1) Runtime Summary

| Area | Value | Evidence |
|------|-------|----------|
| Primary language | Python 3 (README states "Python 3+"; deployment targets Python 3.11+) | [README.md](../../README.md), [.python-version](../../.python-version) |
| Runtime + version | CPython, exact pinned version in `.python-version` | [.python-version](../../.python-version) |
| Package manager | pip (`requirements.txt` / `requirements-dev.txt`) | [requirements.txt](../../requirements.txt), [requirements-dev.txt](../../requirements-dev.txt) |
| Module/build system | None (plain pip install, no `pyproject.toml`/`setup.py`) | repo root listing |

### 2) Production Frameworks and Dependencies

| Dependency | Version | Role in system | Evidence |
|------------|---------|----------------|----------|
| Flask | >=3.1,<4 | Web framework / app factory | [app/__init__.py](../../app/__init__.py) |
| Flask-SQLAlchemy | >=3.1,<4 | ORM / DB access layer | [app/models.py](../../app/models.py) |
| Flask-Migrate | >=4.0,<5 | Alembic-based schema migrations | [migrations/env.py](../../migrations/env.py) |
| Flask-Login | >=0.6,<1 | Session-based auth, `login_required` | [app/auth.py](../../app/auth.py) |
| Flask-WTF | >=1.2,<2 | CSRF protection, form helpers | [app/__init__.py](../../app/__init__.py) |
| WTForms | >=3.2,<4 | Form validation (used with Flask-WTF) | [requirements.txt](../../requirements.txt) |
| Werkzeug | >=3.1,<4 | WSGI utilities, password hashing | [app/auth.py](../../app/auth.py) |
| python-dotenv | >=1.0,<2 | Loads `.env` into environment | [requirements.txt](../../requirements.txt) |
| gunicorn | >=23,<24 | Production WSGI server | [deploy/tax-estimator.service](../../deploy/tax-estimator.service) |
| email-validator | >=2.2,<3 | Email field validation for WTForms | [requirements.txt](../../requirements.txt) |
| pdfplumber | >=0.11,<1 | Parses uploaded PDF paystubs | [app/pdf_parser.py](../../app/pdf_parser.py) |
| pyotp | >=2.9 | TOTP generation/verification for 2FA | [app/auth.py](../../app/auth.py) |
| qrcode[pil] | >=7.4 | Renders 2FA setup QR codes | [app/auth.py](../../app/auth.py) |

Database: SQLite (file-based), via `SQLALCHEMY_DATABASE_URI` — no separate DB server. [config.py](../../config.py)

### 3) Development Toolchain

| Tool | Purpose | Evidence |
|------|---------|----------|
| pytest | Test runner | [requirements-dev.txt](../../requirements-dev.txt), [pytest.ini](../../pytest.ini) |
| pytest-flask | Flask-aware test fixtures | [requirements-dev.txt](../../requirements-dev.txt) |
| coverage | Test coverage reporting | [requirements-dev.txt](../../requirements-dev.txt) |

No linter or formatter config (no `.flake8`, `pyproject.toml`, `.pylintrc`, or `pre-commit` config) was found in the repo. `[TODO]` — confirm whether one is used outside the repo.

### 4) Key Commands

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
flask --app wsgi:app run --debug
python -m pytest tests/ -v
python -m pytest tests/ --cov=app --cov-report=term-missing
flask --app wsgi:app db migrate -m "message"
flask --app wsgi:app db upgrade
```

Evidence: [README.md](../../README.md)

### 5) Environment and Config

- Config sources: [config.py](../../config.py) (class-based `DevelopmentConfig`/`ProductionConfig`/`TestingConfig`), `.env` loaded via `python-dotenv`.
- Required env vars: `SECRET_KEY`, `FLASK_APP`, `FLASK_ENV`; optional `DATABASE_URL` (defaults to `instance/tax_estimator.db` SQLite). See [.env.example](../../.env.example).
- Deployment/runtime constraints: Production served by gunicorn over a Unix socket behind OpenLiteSpeed on Ubuntu 22.04, managed via systemd unit ([deploy/tax-estimator.service](../../deploy/tax-estimator.service)). `wsgi.py` hardcodes `create_app("production")`.

### 6) Evidence

- [requirements.txt](../../requirements.txt)
- [requirements-dev.txt](../../requirements-dev.txt)
- [config.py](../../config.py)
- [wsgi.py](../../wsgi.py)
- [deploy/tax-estimator.service](../../deploy/tax-estimator.service)

## Extended Sections (Optional)

Not added — repo is a single small monolithic Flask app; the core sections are sufficient.
