# Testing Patterns

## Core Sections (Required)

### 1) Test Stack and Commands

- Primary test framework: pytest `>=8,<9` with `pytest-flask >=1.3,<2`. See [requirements-dev.txt](../../requirements-dev.txt).
- Assertion/mocking tools: plain `assert` statements (pytest style); no mocking library is used anywhere in `tests/`.
- Commands (from [README.md](../../README.md)):

```bash
python -m pytest tests/ -v
python -m pytest tests/test_calculator.py -v
python -m pytest tests/ --cov=app --cov-report=term-missing
```

### 2) Test Layout

- Test file placement: all tests live in the top-level `tests/` folder (not co-located with source), one file per concern: `test_models.py`, `test_auth.py`, `test_w2.py`, `test_data_entry.py`, `test_calculator.py`, `test_calculator_precision.py`, `test_dashboard.py`, `test_integration.py`. See [tests/](../../tests) and [README.md](../../README.md) test table.
- Naming convention enforced by [pytest.ini](../../pytest.ini): `python_files = test_*.py`, `python_classes = Test*`, `python_functions = test_*`.
- Setup/fixtures: [tests/conftest.py](../../tests/conftest.py) defines session-scoped `app` (testing config, in-memory SQLite created once) and function-scoped `db` (wraps each test in a transaction that's rolled back), `client`, and `auth_client` (pre-authenticated test client via direct session manipulation).

### 3) Test Scope Matrix

| Scope | Covered? | Typical target | Notes |
|-------|----------|----------------|-------|
| Unit | Yes | `app/calculator/*` pure functions (`test_calculator.py`, `test_calculator_precision.py`) | Largest test files by size (29–40KB), heavy focus on tax-math correctness/edge cases |
| Integration | Yes | Flask routes + DB via `pytest-flask` test client (`test_w2.py`, `test_data_entry.py`, `test_dashboard.py`, `test_auth.py`) | Uses real SQLite (`:memory:`), no HTTP mocking needed since there are no external calls |
| End-to-end (multi-route flows) | Yes | `test_integration.py` — largest test file (41.8KB per scan), exercises full user journeys across blueprints | README confirms "End-to-end multi-route integration flows" |
| E2E (browser/UI) | No | N/A | No Selenium/Playwright/Cypress config found |

### 4) Mocking and Isolation Strategy

- Main approach: no mocking — tests run against the real Flask app instance and a real (in-memory) SQLite database, isolated per test via SQLAlchemy transaction rollback (the `db` fixture in [tests/conftest.py](../../tests/conftest.py)).
- Isolation guarantees: the `app` fixture is session-scoped (one Flask app/schema for the whole test run); the `db` fixture opens a connection + transaction per test function and rolls it back afterward, so writes don't leak between tests as long as tests use the `db` fixture rather than the app's own `db.session` directly. `[TODO]` — verify whether all test files consistently route through the `db` fixture vs. importing `app.db` directly, since a mismatch would break isolation.
- Common failure mode: `auth_client` creates a `testuser` user if one doesn't already exist and reuses it across tests within the session scope, since `app` is session-scoped — could cause cross-test coupling if a test mutates the shared `testuser` record.

### 5) Coverage and Quality Signals

- Coverage tool: `coverage` (dev dependency); no threshold enforced in `pytest.ini` or any CI config (none exists).
- Current reported coverage: `[TODO]` — not captured by this scan; run `python -m pytest tests/ --cov=app --cov-report=term-missing` to obtain it.
- README states "All 279 tests should pass" as of the last update — `[TODO]` confirm current pass count matches by running the suite.
- Known gaps/flaky areas: none documented; no skipped/xfail markers were found in a directory-tree scan (`[TODO]` — a full grep for `@pytest.mark.skip`/`xfail` was not performed).

### 6) Evidence

- [pytest.ini](../../pytest.ini)
- [tests/conftest.py](../../tests/conftest.py)
- [requirements-dev.txt](../../requirements-dev.txt)
- [README.md](../../README.md) (Running the tests section)

## Extended Sections (Optional)

Not added — the test suite uses one consistent, simple strategy (real app + real in-memory DB) with no framework-specific nuance needing separate documentation.
