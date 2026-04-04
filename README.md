# Tax Estimator

A Flask-based federal + California income tax estimator for a family of four (MFJ, 2 children).
Tracks W-2 income, self-employment income, investments, deductions, and estimated payments throughout
the year. Calculates safe harbor thresholds and recommends quarterly payment amounts.

**Stack:** Python 3+, Flask 3.x, Flask-SQLAlchemy, Flask-Migrate, Flask-Login, SQLite, Bootstrap 5, gunicorn

---

## Local development

### 1. Clone and set up the virtual environment

```bash
git clone <repo-url> tax-estimator
cd tax-estimator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 2. Configure environment

```bash
cp .env.example .env   # or create manually
```

`.env` (development):

```
FLASK_ENV=development
SECRET_KEY=dev-secret-change-me
```

### 3. Run the dev server

On first startup the app automatically creates the database and a default user
(`mike`, password `change-me-now`). Change the password after first login.

```bash
flask --app wsgi:app run --debug
```

App is available at `http://127.0.0.1:5000`.

---

## Database migrations

This project uses [Flask-Migrate](https://flask-migrate.readthedocs.io/) (Alembic) to manage schema changes.

### After changing `models.py`

```bash
# Generate a migration file
flask --app wsgi:app db migrate -m "describe the change"

# Review the generated file in migrations/versions/
# Then apply it locally
flask --app wsgi:app db upgrade

# Commit both the model change and the migration file
git add app/models.py migrations/versions/
git commit -m "describe the change"
```

On production, `flask db upgrade` runs automatically via `ExecStartPre` in the systemd service
before gunicorn starts — so a `git pull` + `systemctl restart` is all that's needed to deploy
schema changes.

### Checking migration status

```bash
flask --app wsgi:app db current   # current revision of the DB
flask --app wsgi:app db history   # full migration history
```

---

## Running the tests

Tests use an in-memory SQLite database and pytest-flask. No server needs to be running.

```bash
source .venv/bin/activate

# Run the full suite
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_calculator.py -v

# Run with coverage
python -m pytest tests/ --cov=app --cov-report=term-missing
```

**Test files:**

| File | What it covers |
|------|---------------|
| `tests/test_models.py` | SQLAlchemy model fields and constraints |
| `tests/test_auth.py` | Login / logout / access control |
| `tests/test_w2.py` | Employer + paystub CRUD routes |
| `tests/test_data_entry.py` | SE income, deductions, payments, mileage |
| `tests/test_calculator.py` | Federal, CA, and safe harbor calculations |
| `tests/test_calculator_precision.py` | Precision and edge cases for tax calculations |
| `tests/test_dashboard.py` | Dashboard route + template rendering |
| `tests/test_integration.py` | End-to-end multi-route integration flows |

All 279 tests should pass:

```
279 passed in ~8s
```

---

## Deployment on Ubuntu with OpenLiteSpeed

Target: **Ubuntu 22.04 LTS**, OpenLiteSpeed, Python 3.11+, gunicorn over a Unix socket.

### Prerequisites

```bash
# Python and SQLite
sudo apt update && sudo apt install -y python3 python3-venv python3-pip sqlite3

# OpenLiteSpeed (if not already installed)
wget -O - https://repo.litespeed.sh | sudo bash
sudo apt install -y openlitespeed

# Certbot for Let's Encrypt
sudo apt install -y certbot
```

Verify DNS: an A record must point to the server's public IP before
requesting a TLS certificate.

---

### 1. Upload the application

Clone directly on the server:

```bash
sudo mkdir -p /srv/tax-estimator
sudo chown www-data:www-data /srv/tax-estimator
sudo -u www-data git clone <repo-url> /srv/tax-estimator
```

---

### 2. Server-side setup

```bash
ssh deploy-user@<server-ip>

# Hand ownership to www-data (the gunicorn service user)
sudo chown -R www-data:www-data /srv/tax-estimator
sudo chmod 750 /srv/tax-estimator

# Create the virtual environment as www-data
sudo -u www-data python3 -m venv /srv/tax-estimator/.venv
sudo -u www-data /srv/tax-estimator/.venv/bin/pip install -r /srv/tax-estimator/requirements.txt

# Create the instance directory (SQLite database lives here)
sudo -u www-data mkdir -p /srv/tax-estimator/instance
sudo chmod 750 /srv/tax-estimator/instance
```

Create `/srv/tax-estimator/.env`:

```bash
sudo -u www-data tee /srv/tax-estimator/.env > /dev/null <<'EOF'
FLASK_ENV=production
SECRET_KEY=<paste output of: python3 -c "import secrets; print(secrets.token_hex(32))">
DATABASE_URL=sqlite:////srv/tax-estimator/instance/tax_estimator.db
EOF
sudo chmod 600 /srv/tax-estimator/.env
```

The database and default user (`mike`, password `change-me-now`) are created
automatically on first startup. Change the password after first login.

---

### 3. Install the systemd service

```bash
sudo cp /srv/tax-estimator/deploy/tax-estimator.service \
        /etc/systemd/system/tax-estimator.service

sudo systemctl daemon-reload
sudo systemctl enable tax-estimator
sudo systemctl start tax-estimator

# Confirm it is running and the socket exists
sudo systemctl status tax-estimator
ls -la /run/tax-estimator/gunicorn.sock
```

The service runs `flask db upgrade` automatically before gunicorn starts (`ExecStartPre`),
so schema migrations are applied on every restart without manual intervention.

---

### 4. Configure OpenLiteSpeed

#### 4a. Register the virtual host

In the **OLS Admin console** (`https://<server-ip>:7080`):

1. Go to **Virtual Hosts → Add**.
2. Fill in:
   - **Virtual Host Name:** `YOUR-URL`
   - **Virtual Host Root:** `/srv/tax-estimator`
   - **Config File:** `$SERVER_ROOT/conf/vhosts/YOUR-URL/vhconf.conf`
   - **Enable Scripts/ExtApps:** Yes
3. Save.

#### 4b. Install the vhost config

```bash
sudo mkdir -p /usr/local/lsws/conf/vhosts/YOUR-URL
sudo cp /srv/tax-estimator/deploy/ols-vhost.conf \
        /usr/local/lsws/conf/vhosts/YOUR-URL/vhconf.conf
sudo chown lsadm:lsadm \
        /usr/local/lsws/conf/vhosts/YOUR-URL/vhconf.conf
```

#### 4c. Add an HTTPS listener

In OLS Admin → **Listeners → Add**:

- **Name:** `HTTPS`
- **IP Address:** `*`
- **Port:** `443`
- **Secure:** Yes
- **Private Key File:** `/etc/letsencrypt/live/YOUR-URL/privkey.pem`
- **Certificate File:** `/etc/letsencrypt/live/YOUR-URL/fullchain.pem`

Map this listener to the `YOUR-URL` virtual host.

#### 4d. Graceful restart

Click **Graceful Restart** in the OLS Admin console, or:

```bash
sudo /usr/local/lsws/bin/lswsctrl restart
```

---

### 5. TLS certificate (Let's Encrypt)

Obtain the certificate *before* enabling the HTTPS listener (HTTP must be reachable on port 80):

```bash
sudo certbot certonly --webroot \
    --webroot-path /srv/tax-estimator/app/static \
    -d YOUR-URL
```

Set up auto-renewal hook so OLS reloads after renewal:

```bash
sudo tee /etc/letsencrypt/renewal-hooks/deploy/restart-ols.sh > /dev/null <<'EOF'
#!/bin/sh
/usr/local/lsws/bin/lswsctrl restart
EOF
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/restart-ols.sh
```

---

### 6. Updating the application

```bash
ssh deploy-user@<server-ip>

cd /srv/tax-estimator
sudo -u www-data git pull

# Reinstall dependencies only if requirements.txt changed
sudo -u www-data /srv/tax-estimator/.venv/bin/pip install -r requirements.txt

sudo systemctl restart tax-estimator
```

The service will automatically run `flask db upgrade` before starting gunicorn,
applying any new migrations included in the pull.

---

### 7. Bootstrapping Flask-Migrate on an existing installation

If adding Flask-Migrate to a server that was previously running without it, stamp
the current database as the baseline before the first restart:

```bash
sudo -u www-data /srv/tax-estimator/.venv/bin/pip install -r /srv/tax-estimator/requirements.txt
sudo -u www-data /srv/tax-estimator/.venv/bin/flask --app wsgi:app db stamp head
sudo systemctl daemon-reload
sudo systemctl restart tax-estimator
```

---

### 8. Log locations

| Log | Path |
|-----|------|
| gunicorn stdout/stderr | `journalctl -u tax-estimator -f` |
| gunicorn access | `/var/log/tax-estimator/access.log` |
| gunicorn errors | `/var/log/tax-estimator/error.log` |
| OLS access | `/var/log/tax-estimator/ols-access.log` |
| OLS errors | `/var/log/tax-estimator/ols-error.log` |
