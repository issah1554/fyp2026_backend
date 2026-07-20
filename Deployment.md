# Django Deployment And Debugging Runbook

This guide covers the important deployment, restart, migration, static-file, admin-user, and debugging commands for this Django backend.

## Project Paths

Local Windows project:

```text
C:\Users\ISSAH\Desktop\Projects\DIT\fyp2026\fyp2026_backend
```

VPS project:

```bash
~/domains/kolinki.databenki.co.tz/fyp2026_backend
```

## 1. Enter The Project On VPS

```bash
cd ~/domains/kolinki.databenki.co.tz/fyp2026_backend
source venv/bin/activate
```

Confirm Python and Django are available:

```bash
python --version
python manage.py check
```

## 2. Pull Latest Code

```bash
cd ~/domains/kolinki.databenki.co.tz/fyp2026_backend
git status
git pull
```

If dependencies changed:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

## 3. Environment File

Edit the production environment file:

```bash
nano .env
```

Important production values:

```text
SECRET_KEY=your-real-secret-key
DEBUG=false
ALLOWED_HOSTS=kolinki.databenki.co.tz,127.0.0.1,localhost
STATIC_ROOT=staticfiles

DB_ENGINE=django.db.backends.postgresql
DB_NAME=fyp2026_backend
DB_USER=your-db-user
DB_PASSWORD=your-db-password
DB_HOST=127.0.0.1
DB_PORT=5432
DB_CONN_MAX_AGE=60
```

For frontend access, add the frontend URL:

```text
CORS_ALLOWED_ORIGINS=https://your-frontend-domain.com,http://localhost:3000
```

## 4. Database Migration

Check migration status:

```bash
python manage.py showmigrations
```

Apply migrations:

```bash
python manage.py migrate
```

Check for missing migration files before deploying from local:

```bash
python manage.py makemigrations --check --dry-run
```

Create new migrations after model changes:

```bash
python manage.py makemigrations
```

## 5. Static Files

Collect static files:

```bash
python manage.py collectstatic --noinput
```

If this fails with `STATIC_ROOT` missing, make sure `config/settings.py` has:

```python
STATIC_ROOT = os.environ.get("STATIC_ROOT", BASE_DIR / "staticfiles")
```

## 6. Run Gunicorn Manually

Use this to test the app before restarting the service:

```bash
gunicorn config.wsgi:application --bind 127.0.0.1:8000
```

For long-running requests, use a larger timeout:

```bash
gunicorn config.wsgi:application --bind 127.0.0.1:8000 --timeout 120
```

Stop manual Gunicorn with:

```bash
Ctrl+C
```

Correct WSGI module:

```bash
gunicorn config.wsgi:application
```

Wrong placeholder command:

```bash
gunicorn project_name.wsgi:application
```

The wrong command fails with:

```text
ModuleNotFoundError: No module named 'project_name'
```

## 7. Systemd Service

Check service status:

```bash
sudo systemctl status fyp2026-backend --no-pager
```

Restart the backend:

```bash
sudo systemctl restart fyp2026-backend
```

Reload systemd after editing the service file:

```bash
sudo systemctl daemon-reload
sudo systemctl restart fyp2026-backend
```

Enable service on boot:

```bash
sudo systemctl enable fyp2026-backend
```

View recent logs:

```bash
sudo journalctl -u fyp2026-backend -n 50 --no-pager
```

Follow live logs:

```bash
sudo journalctl -u fyp2026-backend -f
```

Example Gunicorn command for the service:

```bash
gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 2 --timeout 120
```

## 8. Nginx Checks

Test Nginx config:

```bash
sudo nginx -t
```

Reload Nginx:

```bash
sudo systemctl reload nginx
```

Restart Nginx:

```bash
sudo systemctl restart nginx
```

Check Nginx logs:

```bash
sudo tail -n 100 /var/log/nginx/error.log
sudo tail -n 100 /var/log/nginx/access.log
```

## 9. Admin User

Create a Django superuser:

```bash
python manage.py createsuperuser
```

Then visit:

```text
https://kolinki.databenki.co.tz/admin/
```

If the command fails because tables are missing:

```bash
python manage.py migrate
python manage.py createsuperuser
```

## 10. Health Checks

Check Django config:

```bash
python manage.py check
```

Check API docs:

```bash
curl -I https://kolinki.databenki.co.tz/api/docs
```

Check API schema:

```bash
curl -I https://kolinki.databenki.co.tz/api/schema
```

Check the local Gunicorn backend through localhost:

```bash
curl -I http://127.0.0.1:8000/api/docs
```

## 11. Common Errors And Fixes

### No module named project_name

Cause: Gunicorn is using a placeholder Django module.

Fix:

```bash
gunicorn config.wsgi:application --bind 127.0.0.1:8000
```

Update the systemd service Gunicorn command to:

```text
gunicorn config.wsgi:application
```

### STATIC_ROOT setting missing

Error:

```text
django.core.exceptions.ImproperlyConfigured: You're using the staticfiles app without having set the STATIC_ROOT setting
```

Fix:

```python
STATIC_ROOT = os.environ.get("STATIC_ROOT", BASE_DIR / "staticfiles")
```

Then run:

```bash
python manage.py collectstatic --noinput
sudo systemctl restart fyp2026-backend
```

### Worker exiting with SystemExit

Check logs:

```bash
sudo journalctl -u fyp2026-backend -n 100 --no-pager
```

If the worker exits during a long request, increase Gunicorn timeout:

```bash
gunicorn config.wsgi:application --bind 127.0.0.1:8000 --timeout 120
```

Then update the systemd service and restart:

```bash
sudo systemctl daemon-reload
sudo systemctl restart fyp2026-backend
```

If the stack trace points to database queries, run migrations and check slow endpoints:

```bash
python manage.py migrate
python manage.py check
```

### 400 Bad Request / DisallowedHost

Cause: current domain is not in `ALLOWED_HOSTS`.

Fix `.env`:

```text
ALLOWED_HOSTS=kolinki.databenki.co.tz,127.0.0.1,localhost
```

Restart:

```bash
sudo systemctl restart fyp2026-backend
```

### CORS error from frontend

Cause: frontend domain is not in `CORS_ALLOWED_ORIGINS`.

Fix `.env`:

```text
CORS_ALLOWED_ORIGINS=https://your-frontend-domain.com,http://localhost:3000
```

Restart:

```bash
sudo systemctl restart fyp2026-backend
```

### Database connection error

Check `.env` database values:

```bash
nano .env
```

Test Django database access:

```bash
python manage.py dbshell
```

If `dbshell` works, exit with:

```sql
\q
```

## 12. Full VPS Deployment Checklist

Run this after pushing new backend changes:

```bash
cd ~/domains/kolinki.databenki.co.tz/fyp2026_backend
source venv/bin/activate
git pull
pip install -r requirements.txt
python manage.py check
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart fyp2026-backend
sudo systemctl status fyp2026-backend --no-pager
sudo journalctl -u fyp2026-backend -n 50 --no-pager
```

If Nginx config changed:

```bash
sudo nginx -t
sudo systemctl reload nginx
```
