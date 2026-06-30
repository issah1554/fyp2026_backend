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

## Email

By default, verification emails are printed to the terminal running `runserver`.
To send real emails, configure SMTP environment variables before starting Django:

```powershell
$env:EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend"
$env:EMAIL_HOST="smtp.example.com"
$env:EMAIL_PORT="587"
$env:EMAIL_USE_TLS="true"
$env:EMAIL_HOST_USER="your-smtp-username"
$env:EMAIL_HOST_PASSWORD="your-smtp-password"
$env:DEFAULT_FROM_EMAIL="Smart Market <noreply@example.com>"
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
