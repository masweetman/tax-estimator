# Architecture

## Core Sections (Required)

### 1) Architectural Style

- Primary style: Classic server-rendered MVC-ish monolith using the Flask "application factory" + Blueprints pattern, with a distinct pure-calculation layer separated from routes/models.
- Why this classification: `create_app()` in [app/__init__.py](../../app/__init__.py) builds the Flask app, registers 13 feature blueprints, and injects Jinja context processors; each blueprint in `app/routes/` owns one feature's HTTP handlers and renders a matching template folder under `app/templates/`; `app/calculator/` is a framework-free module tree that only consumes/returns plain dicts.
- Primary constraints:
  - Single-tenant / single-household design: there is no per-user data partitioning — `TaxYear` and all child records are global, not scoped by `user_id`. Only the `User` table exists for login/2FA. Evidence: [app/models.py](../../app/models.py) has no `user_id` foreign key on `TaxYear` or any financial model.
  - SQLite as the only supported datastore (file-based, single-writer). Evidence: [config.py](../../config.py).
  - The app self-provisions its schema and a default admin user (`mike` / `change-me-now`) on every process start. Evidence: [app/__init__.py](../../app/__init__.py) lines ~96-115.

### 2) System Flow

```text
Browser request -> Flask routing (Blueprint) -> route handler (app/routes/*.py)
   -> SQLAlchemy queries build a flat "inputs" dict from DB rows
   -> app/tax_settings.get_settings_inputs() merges per-year rate overrides
   -> app/calculator/engine.calculate(inputs) -> federal.py + california.py + safe_harbor.py (pure functions)
   -> merged result dict returned to the route
   -> Jinja2 template (app/templates/...) renders HTML using the result dict + `currency` filter
```

Example trace: [app/routes/dashboard.py](../../app/routes/dashboard.py) `_build_inputs()` aggregates `Employer`/`Paystub`/`SelfEmploymentIncome`/etc. into one dict, then presumably calls `calculate()` from [app/calculator/engine.py](../../app/calculator/engine.py) before rendering `dashboard.html`. `[TODO]` — confirm the exact call site of `calculate()` in `dashboard.py` past line 120 (file not fully read).

### 3) Layer/Module Responsibilities

| Layer or module | Owns | Must not own | Evidence |
|-----------------|------|--------------|----------|
| `app/routes/*.py` | HTTP verbs, form parsing, auth guards (`@login_required`), DB reads/writes, redirects/flash messages | Tax bracket math | [app/routes/w2.py](../../app/routes/w2.py) |
| `app/calculator/engine.py` + `federal.py`/`california.py`/`safe_harbor.py` | Federal/CA tax computation, safe-harbor quarterly payment logic, all derived from a plain `inputs` dict | DB access, Flask request context | [app/calculator/engine.py](../../app/calculator/engine.py) |
| `app/calculator/constants.py` | Year-keyed tax law constants (brackets, standard deduction, SS wage base, etc.) | Per-user overrides (that's `tax_settings.py` + `TaxYearSettings` model) | [app/calculator/constants.py](../../app/calculator/constants.py) |
| `app/tax_settings.py` | Bridges DB-stored `TaxYearSettings` overrides into the calculator's input-override contract | Direct route/template logic | [app/tax_settings.py](../../app/tax_settings.py) |
| `app/models.py` | Schema + relationships + small computed properties (e.g., `Paystub.take_home_pay`) | Business rule branching beyond simple arithmetic | [app/models.py](../../app/models.py) |
| `app/auth.py` | Login/logout, TOTP-based 2FA setup/verify/disable, open-redirect guarding (`_is_safe_url`) | Data-entry business logic | [app/auth.py](../../app/auth.py) |
| `app/pdf_parser.py` | Best-effort regex extraction of paystub fields from an uploaded PDF | Persistence — returns a dict for the caller to save | [app/pdf_parser.py](../../app/pdf_parser.py) |

### 4) Reused Patterns

| Pattern | Where found | Why it exists |
|---------|-------------|---------------|
| Application factory | `create_app()` in [app/__init__.py](../../app/__init__.py) | Enables distinct `development`/`production`/`testing` configs (used heavily by `tests/conftest.py`) |
| Blueprint-per-feature | `app/routes/*.py`, each with its own `url_prefix` | Keeps each tax topic (W-2, SE, deductions, vehicles, LLC, etc.) isolated and independently testable |
| Deferred/local imports | e.g. `from app.models import User` inside `create_app()`, inside route functions | Avoids circular imports between `app/__init__.py`, `app/models.py`, and route modules |
| Aggregate-then-calculate | `_build_inputs()` in [app/routes/dashboard.py](../../app/routes/dashboard.py) | Converts normalized relational data into the flat dict contract the calculator expects |
| Settings-as-override | [app/tax_settings.py](../../app/tax_settings.py) merges DB `TaxYearSettings` over `constants.py` defaults via `inputs.get(key)` fallback | Lets a user tweak a single year's rates without code changes |
| Context processors for globals | `inject_person_names`, `inject_tax_years` in [app/__init__.py](../../app/__init__.py) | Makes person display names and the year-switcher nav available to every template without passing them explicitly |

### 5) Known Architectural Risks

- No multi-tenancy/authorization boundary: any authenticated user can read/write all `TaxYear` data — acceptable only because the app is designed for one household with likely one or two logins sharing the same account, but it is a risk if `[ASK USER]` more users are ever added.
- Auto-seeding logic runs `db.create_all()` and creates a default user with a publicly-known password (`change-me-now`) on every app boot, including in `production` config — relies entirely on the operator changing it promptly.
- `dashboard.py`'s `_build_inputs()` is a large, single function aggregating ~15 relationship types procedurally — high complexity/fragility risk if the data model grows further (see [CONCERNS.md](CONCERNS.md)).

### 6) Evidence

- [app/__init__.py](../../app/__init__.py)
- [app/routes/dashboard.py](../../app/routes/dashboard.py)
- [app/calculator/engine.py](../../app/calculator/engine.py)
- [app/tax_settings.py](../../app/tax_settings.py)
- [app/models.py](../../app/models.py)

## Extended Sections (Optional)

Not added — no background workers, queues, or async topology exist in this codebase.
