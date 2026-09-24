# Codebase Concerns

## Core Sections (Required)

### 1) Top Risks (Prioritized)

| Severity | Concern | Evidence | Impact | Suggested action |
|----------|---------|----------|--------|------------------|
| Medium | `SECRET_KEY` falls back to the hardcoded literal `"change-me-in-production"` if the env var is unset, in both `DevelopmentConfig` and `ProductionConfig` | [config.py](../../config.py) | Session cookies and CSRF tokens are forgeable if `SECRET_KEY` is left unset at deploy time | Since this is a single personal install, set a real `SECRET_KEY` in `.env` once at deploy time (README already documents this); optionally fail fast in `ProductionConfig` as a safety net |
| Medium | A default user (`mike` / `change-me-now`) is auto-created with a known password on every fresh boot, in every non-testing config including production | [app/__init__.py](../../app/__init__.py) L96-118 | Brief window between first boot and the operator's first login where the account has a publicly-documented password | Change the password immediately after first login, as the README already instructs; low residual risk since only the owner ever installs/operates this app |
| Medium | No login attempt throttling/lockout on `/auth/login` or `/auth/2fa/verify` | [app/auth.py](../../app/auth.py) | Susceptible to online brute-force/credential-stuffing against the single internet-facing account (OWASP A07) | Add rate limiting (e.g., Flask-Limiter) on auth endpoints |
| Medium | No application logging anywhere (no `logging` module usage found in `app/`) | grep across `app/` found zero `logging`/`app.logger` usage | Failed logins, 2FA disables, and unhandled exceptions are invisible outside gunicorn's generic access/error logs | Add structured logging for auth events and unhandled exceptions |
| Low | No CI pipeline, linter, or formatter configured | scan output: "No CI/CD pipelines detected", "No linting or formatting config files found" | Style drift and regressions can land without automated checks; relies entirely on manually running pytest | Add a GitHub Actions workflow running `pytest` (and optionally `ruff`/`black`) on push/PR |

> Note: this app is confirmed to be a single-user, personal-installation tool (one owner/operator, installed once, who sets passwords and keys directly) — it will not be extended to support multiple users. The lack of per-user data isolation (all `TaxYear` records are global, not scoped by `user_id`, per [app/models.py](../../app/models.py)) is therefore an intentional design fit for purpose, not a risk to remediate.

### 2) Technical Debt

| Debt item | Why it exists | Where | Risk if ignored | Suggested fix |
|-----------|---------------|-------|-----------------|---------------|
| `_build_inputs()` in `dashboard.py` is a single large procedural function aggregating ~15 relationship types into a flat dict | Organic growth as new income/deduction categories were added over time | [app/routes/dashboard.py](../../app/routes/dashboard.py) | Hard to extend safely; easy to introduce a person-attribution bug (e.g., SE expense-to-person mapping already has a documented "rare" fallback) | Extract per-domain aggregator helpers (e.g., `_aggregate_w2()`, `_aggregate_se()`) that dashboard composes |
| `deductions.py` route module is the largest route file (20.2KB per code metrics) | Handles many deduction sub-types (itemized, capital gains, dividends, interest, child care, unemployment, insurance) in one blueprint | [app/routes/deductions.py](../../app/routes/deductions.py) | Same fragility/complexity concern as `dashboard.py` | Consider splitting into per-subtype blueprints if it keeps growing |
| No `pyproject.toml`/lint config despite a nontrivial codebase (~9,124 LOC, 40 Python files) | Project appears to have prioritized shipping features over tooling | scan output CODE METRICS section | Inconsistent style enforcement over time | Add `ruff`/`black` + pre-commit if the team wants enforced style |

### 3) Security Concerns

| Risk | OWASP category (if applicable) | Evidence | Current mitigation | Gap |
|------|--------------------------------|----------|--------------------|-----|
| Weak default credentials shipped in source/README | A07:2021 – Identification and Authentication Failures | [app/__init__.py](../../app/__init__.py), [README.md](../../README.md) | README instructs the owner to change the password immediately after first login; since installation is performed once by the sole user, the exposure window is short and self-controlled | No enforcement — app doesn't force a password change or expire the default credential |
| `SECRET_KEY` default fallback | A02:2021 – Cryptographic Failures | [config.py](../../config.py) | `.env.example` documents setting a real value, and the owner sets this directly during personal install | No runtime validation that a non-default key is set in production |
| No brute-force protection on auth endpoints | A07:2021 | [app/auth.py](../../app/auth.py) | 2FA (TOTP) mitigates for the account once enabled, but it's opt-in (`totp_enabled` default `False`); relevant even for a single-user app since the login endpoint is internet-facing (per the OpenLiteSpeed/Let's Encrypt deployment) | No rate limiting, no account lockout |
| CSRF protection is global via Flask-WTF (`csrf.init_app(app)`) | A01/A05 mitigation already in place | [app/__init__.py](../../app/__init__.py) | `WTF_CSRF_ENABLED = True` by default (disabled only in `TestingConfig`) | None identified — this is a positive control |
| PDF upload endpoint accepts arbitrary files without size/type validation before passing to `pdfplumber` | A03:2021 – adjacent (resource exhaustion / malformed input) | [app/routes/w2.py](../../app/routes/w2.py) `paystub_import` | `pdf_parser.py` wraps parsing in a best-effort try/except | No explicit file size cap or MIME/type check before parsing; large/malicious PDFs could cause resource exhaustion (`[TODO]` verify pdfplumber's own safeguards) |

### 4) Performance and Scaling Concerns

| Concern | Evidence | Current symptom | Scaling risk | Suggested improvement |
|---------|----------|------------------|--------------|-----------------------|
| SQLite as sole datastore | [config.py](../../config.py) | None observed (single-user app) | None — SQLite's single-writer model is a non-issue since the app is confirmed to be single-user/single-install by design, not a growth path to multi-tenant | No action needed |
| `_build_inputs()` iterates every child collection per request with Python-side loops rather than SQL aggregation | [app/routes/dashboard.py](../../app/routes/dashboard.py) | Not currently a symptom at small data volumes (one family/year) | Could become slow if paystub/transaction counts grow very large (years of biweekly data) | Consider DB-side `SUM()`/`GROUP BY` queries if dashboard load time becomes noticeable |

### 5) Fragile/High-Churn Areas

- Git history is shallow (18 commits total, all on 2026-04-05 per `git log`), so the scan's 90-day churn heuristic returned no signal (`[TODO]` — churn analysis is not meaningful for this repo's history depth).
- By file size and responsibility breadth, the most fragile areas are:
  - [app/routes/dashboard.py](../../app/routes/dashboard.py) — largest/most complex route module, central aggregation point for nearly every model.
  - [app/routes/deductions.py](../../app/routes/deductions.py) — largest route file (20.2KB), covers 6+ deduction sub-types in one blueprint.
  - [app/calculator/federal.py](../../app/calculator/federal.py) — dense tax-law logic (16.7KB); any bracket/rule change here has wide blast radius across federal + safe-harbor calculations.
  - [app/models.py](../../app/models.py) — largest single file (28.3KB), touched whenever any new data field is added; schema changes require a corresponding Alembic migration (only 2 migrations exist so far).

### 6) `[ASK USER]` Questions

Resolved: single-tenant design (no `user_id` scoping) is confirmed intentional — this is a personal, single-install, single-user application and will not be extended to multiple users.

1. [ASK USER] Should the auto-created default user (`mike`/`change-me-now`) be replaced with a forced first-run setup flow instead of a fixed literal credential, or is the current "change it after first login" approach acceptable given the owner controls the install?
2. [ASK USER] Is a CI pipeline (running pytest on push/PR) and/or a linter/formatter desired, given none currently exist?
3. [ASK USER] Should basic security event logging (failed logins, 2FA disable events, unhandled exceptions) be added given no logging library is currently used?
4. [ASK USER] Is `wsgi.py` hardcoding `create_app("production")` intentional for local `flask run --debug` usage too, or should it read config name from `FLASK_ENV`?

### 7) Evidence

- `.codebase-scan.txt` (CODE METRICS, TODO/FIXME, CI/CD, SECURITY & COMPLIANCE sections)
- [app/__init__.py](../../app/__init__.py)
- [config.py](../../config.py)
- [app/routes/dashboard.py](../../app/routes/dashboard.py)
- [app/routes/w2.py](../../app/routes/w2.py)

## Extended Sections (Optional)

Not added — the top risks and debt items above are comprehensive for this repo's current size.
