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
