# External Integrations

## Core Sections (Required)

### 1) Integration Inventory

| System | Type (API/DB/Queue/etc) | Purpose | Auth model | Criticality | Evidence |
|--------|---------------------------|---------|------------|-------------|----------|
| SQLite (file-based) | Database | Sole system of record for all tax data, users, settings | OS file permissions only (no DB-level auth) | High | [config.py](../../config.py) |
| pyotp / TOTP authenticator apps | Local crypto, no network call | Second factor for login (2FA) | Shared secret (`totp_secret`) stored per user | Medium | [app/auth.py](../../app/auth.py) |
| Uploaded PDF paystubs (pdfplumber) | Local file parsing, not a network integration | Prefill paystub form fields from an employer-issued PDF | N/A (in-memory parse only) | Low | [app/pdf_parser.py](../../app/pdf_parser.py) |
| OpenLiteSpeed + Let's Encrypt/Certbot | Reverse proxy / TLS termination (deployment-only) | Serves the app over HTTPS via a Unix socket to gunicorn | Server-managed TLS certs | High (prod only) | [README.md](../../README.md) |

No third-party web APIs (payment processors, tax e-file services, analytics, email, etc.) are called anywhere in `app/`. `[TODO]` — confirm no external tax-rate lookup service is expected (rates are all hardcoded in [app/calculator/constants.py](../../app/calculator/constants.py) and overridable via `TaxYearSettings`).

### 2) Data Stores

| Store | Role | Access layer | Key risk | Evidence |
|-------|------|--------------|----------|----------|
| SQLite file at `instance/tax_estimator.db` (dev) or `DATABASE_URL` path (prod) | Single relational store for all app data (users, tax years, income, deductions, settings) | Flask-SQLAlchemy ORM (`app.db`) | Single-writer file DB — no concurrent-write scaling, no built-in backup/replication | [config.py](../../config.py) |
| `:memory:` SQLite | Ephemeral test database | Flask-SQLAlchemy, created/dropped per test session in [tests/conftest.py](../../tests/conftest.py) | N/A (test-only) | [tests/conftest.py](../../tests/conftest.py) |

### 3) Secrets and Credentials Handling

- Credential sources: `.env` file loaded via `python-dotenv`/Flask, read through `os.environ.get(...)` in [config.py](../../config.py). `SECRET_KEY` defaults to the literal string `"change-me-in-production"` if unset — a real risk if an operator forgets to set it (see [CONCERNS.md](CONCERNS.md)).
- Hardcoding checks: default application user is hardcoded (`username="mike"`, `password="change-me-now"`) and auto-created on first boot in [app/__init__.py](../../app/__init__.py). Passwords are hashed with Werkzeug's `generate_password_hash`/`check_password_hash` (salted, not stored in plaintext).
- TOTP secrets (`User.totp_secret`) are stored in plaintext in the `user` table (standard practice for TOTP, since the server must recompute codes) — protected only by DB file permissions.
- Rotation/lifecycle: no secret rotation mechanism exists; `[ASK USER]` whether `SECRET_KEY` rotation invalidates sessions (it does, since Flask session cookies are signed with it).

### 4) Reliability and Failure Behavior

- Retry/backoff: not applicable — there are no outbound network calls to retry.
- Timeout policy: none configured at the app level; gunicorn's default worker timeout applies (not overridden in [deploy/tax-estimator.service](../../deploy/tax-estimator.service) — `[TODO]` verify gunicorn CLI flags in the actual `ExecStart` line).
- Circuit-breaker/fallback: none needed/present (no external service dependency).
- DB-level resilience: `app/__init__.py` catches `OperationalError` during startup seeding specifically to tolerate a database that is mid-`flask db upgrade`, deferring seeding to the next normal boot.

### 5) Observability for Integrations

- Logging around external calls: none — no logging library is configured anywhere in the app (see [CONVENTIONS.md](CONVENTIONS.md)).
- Metrics/tracing: none present; gunicorn access/error logs and systemd journal are the only operational visibility (per [README.md](../../README.md) log locations section).
- Missing visibility gaps: no application-level logging of failed logins, failed 2FA attempts, or PDF parse failures beyond user-facing flash messages — an incident investigation would rely solely on gunicorn/OLS access logs. `[ASK USER]` whether basic security event logging (failed logins, 2FA disables) should be added.

### 6) Evidence

- [config.py](../../config.py)
- [app/__init__.py](../../app/__init__.py)
- [app/auth.py](../../app/auth.py)
- [README.md](../../README.md) (Log locations section)

## Extended Sections (Optional)

Not added — this app has no external API surface to catalog beyond what's listed above.
