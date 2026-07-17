# FYP 2026 Backend

Django REST backend for the Smart Market and Price Decision Support System.

## Setup

Create and activate a virtual environment:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

If PowerShell blocks activation scripts, run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Run The Project

Start the development server:

```powershell
python manage.py runserver
```

Or without activating the virtualenv:

```powershell
.\venv\Scripts\python.exe manage.py runserver
```

API base URL:

```text
http://127.0.0.1:8000/api/v1/
```

Swagger docs:

```text
http://127.0.0.1:8000/api/docs/
```

OpenAPI schema:

```text
http://127.0.0.1:8000/api/schema/
```

## Migrations

Create migrations after model changes:

```powershell
python manage.py makemigrations
```

Apply pending migrations:

```powershell
python manage.py migrate
```

Collect static files for production:

```powershell
python manage.py collectstatic --noinput
```

Show migration status:

```powershell
python manage.py showmigrations
```

Check if model changes need migrations without writing files:

```powershell
python manage.py makemigrations --check --dry-run
```

For this project, the auth app code lives in `apps/auth`, but its Django app label is `api` for migration compatibility. To inspect its migrations:

```powershell
python manage.py showmigrations api
```

## Environment And Database

Local settings are loaded from `.env`. The project is configured to use PostgreSQL by default through:

```text
DB_ENGINE=django.db.backends.postgresql
DB_NAME=fyp2026_backend
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=127.0.0.1
DB_PORT=5432
```

Install dependencies after pulling database changes:

```powershell
pip install -r requirements.txt
```

Create the PostgreSQL database before running migrations:

```sql
CREATE DATABASE fyp2026_backend;
```

Then apply migrations:

```powershell
python manage.py migrate
```

## Apps Structure

Project apps are grouped under the root `apps/` package.

Current app:

```text
apps/auth/
```

Auth is installed in `config/settings.py`:

```python
"apps.auth.apps.AuthConfig"
```

Create a new app inside `apps/`:

```powershell
python manage.py startapp app_name apps/app_name
```

Then add its config class to `INSTALLED_APPS` in `config/settings.py`.

## Tests And Checks

Run tests:

```powershell
python manage.py test
```

Run Django system checks:

```powershell
python manage.py check
```

Run tests without activating the virtualenv:

```powershell
.\venv\Scripts\python.exe manage.py test
```

## Render Deployment

The Django project module is `config`, so the Render web service Start Command must be:

```bash
gunicorn config.wsgi:application
```

Do not use `gunicorn project_name.wsgi:application`; `project_name` is only a placeholder and will fail with:

```text
ModuleNotFoundError: No module named 'project_name'
```

For a manual Render service, set these values in the Render dashboard:

```text
Build Command: pip install -r requirements.txt
Start Command: gunicorn config.wsgi:application
```

Set `DEBUG=false` and include your Render service host in `ALLOWED_HOSTS`, for example:

```text
ALLOWED_HOSTS=your-service-name.onrender.com
```

## Email

Verification emails are sent through the SMTP settings in `.env`.
For local development, use a real SMTP provider or temporarily set `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`.

```powershell
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=your-smtp-username
EMAIL_HOST_PASSWORD=your-smtp-password
DEFAULT_FROM_EMAIL=Smart Market <your-email@example.com>
```

For Gmail, use an app password, not your normal Google account password:

```text
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=your-address@gmail.com
EMAIL_HOST_PASSWORD=your-google-app-password
DEFAULT_FROM_EMAIL=Smart Market <your-address@gmail.com>
```

After updating `.env`, restart Django:

```powershell
.\venv\Scripts\python.exe manage.py runserver
```

## Admin

Create a superuser:

```powershell
python manage.py createsuperuser
```

Admin URL:

```text
http://127.0.0.1:8000/admin/
```

## Seed Sample System Users

Run migrations first, then seed verified sample users:

```powershell
python manage.py migrate
python manage.py seed_system_users
```

The default password for all seeded users is:

```text
StrongPass123
```

To set a different password:

```powershell
python manage.py seed_system_users --password YourPassword123
```

Seeded verified accounts:

```text
admin_sample           system.admin@user.com
farmer_sample          system.farmer@user.com
entrepreneur_sample    system.entrepreneur@user.com
buyer_sample           system.buyer@user.com
market_officer_sample  system.market_officer@user.com
researcher_sample      system.researcher@user.com
```

## Useful Django Shell Commands

Open the Django shell:

```powershell
python manage.py shell
```

Resolve an auth URL:

```powershell
python manage.py shell -c "from django.urls import reverse; print(reverse('auth:login'))"
```

## Auth Endpoints

```text
POST /api/v1/auth/register/
POST /api/v1/auth/login/
POST /api/v1/auth/token/refresh/
POST /api/v1/auth/email/verify/
POST /api/v1/auth/email/resend/
GET  /api/v1/auth/me/
POST /api/v1/auth/logout/
```

## Git

Check changed files:

```powershell
git status --short
```

View unstaged changes:

```powershell
git diff
```
