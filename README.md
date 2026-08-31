# DeskTicket

> **Django Help Desk & Email Ticketing Platform**

[![Django](https://img.shields.io/badge/Django-4.2-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![REST API](https://img.shields.io/badge/API-Django%20REST%20Framework-red)](https://www.django-rest-framework.org/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

DeskTicket is a self-hosted, multi-tenant help desk application built with Django. It combines ticket management, customer support workflows, SLA tracking, email/IMAP ingestion, notifications, reporting, a customer portal, and a REST API in one application.


## Highlights

- Multi-tenant workspaces
- Ticket lifecycle management
- Priorities and statuses
- Agent assignment
- Departments and categories
- SLA policies and breach tracking
- Customer portal
- Email/IMAP ingestion architecture
- Gmail, Outlook/Microsoft 365, Yahoo and custom mailbox support
- Encrypted mailbox secrets
- Internal comments and ticket history
- Attachments
- Notifications
- CSV reporting
- REST API
- JWT authentication
- Celery/Redis background processing
- Docker support
- PostgreSQL and SQLite support
- Demo-mode safeguards for public hosting

## Technology

| Component | Technology |
|---|---|
| Backend | Python / Django 4.2 |
| API | Django REST Framework |
| Authentication | Django sessions + JWT |
| Database | PostgreSQL / SQLite |
| Background jobs | Celery |
| Queue | Redis |
| Email | IMAP / SMTP architecture |
| Security | Fernet encrypted mailbox secrets |
| Frontend | Django Templates + Bootstrap |
| Deployment | Render / Docker |

## Architecture

```text
                    ┌─────────────────────┐
                    │      Browser/API     │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Django / DRF      │
                    │   DeskTicket        │
                    └──────┬───────┬──────┘
                           │       │
                ┌──────────┘       └────────────┐
                ▼                               ▼
       ┌────────────────┐              ┌────────────────┐
       │   PostgreSQL   │              │ Redis / Celery │
       └────────────────┘              └───────┬────────┘
                                               │
                                               ▼
                                      ┌────────────────┐
                                      │ Mailbox/Jobs   │
                                      └────────────────┘
```

## Project structure

```text
.
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── tickets/
│   ├── models.py
│   ├── views.py
│   ├── forms.py
│   ├── api.py
│   ├── services/
│   ├── management/commands/seed_demo.py
│   └── migrations/
├── templates/
├── static/
├── docs/
│   ├── API.md
│   └── DEPLOY_RENDER.md
├── build.sh
├── render.yaml
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Local setup

DeskTicket supports SQLite locally so the project can be run without PostgreSQL during development.

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create environment configuration:

```bash
copy .env.example .env
```

Linux/macOS:

```bash
cp .env.example .env
```

Generate a mailbox encryption key if you need the mailbox features:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Then:

```bash
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/`.

## Populate demo data locally

Enable:

```env
DEMO_MODE=True
```

Then run:

```bash
python manage.py seed_demo
```

The command is idempotent and creates synthetic customers, tickets, SLA policies, departments, categories, comments, history and notifications.

## Render deployment

See **[docs/DEPLOY_RENDER.md](docs/DEPLOY_RENDER.md)** for the complete deployment procedure.

The repository includes `render.yaml` and `build.sh` so the project is ready for a Render deployment.

### Recommended free demo architecture

```text
GitHub
   │
   ▼
Render Free Web Service
   │
   ▼
Neon Free PostgreSQL
```

Render's Free web service is suitable for hobby/demo projects but can spin down after inactivity. Render's Free PostgreSQL currently expires after 30 days, so a separate free PostgreSQL provider is recommended when the demo database should persist longer.

## API documentation

See **[docs/API.md](docs/API.md)**.

API base path:

```text
/api/v1/
```

JWT endpoints:

```text
POST /api/v1/token/
POST /api/v1/token/refresh/
```

## Email integration

DeskTicket is designed around mailbox integrations rather than a single provider. The data model supports:

- Gmail
- Outlook / Microsoft 365
- Yahoo
- Custom IMAP mailboxes
- Password/app-password authentication
- OAuth2 credential fields

Mailbox credentials are encrypted before storage using Fernet.

### Public demo protection

When `DEMO_MODE=True`:

- outbound email is not sent
- IMAP connection tests are disabled
- mailbox synchronization is disabled
- ticket replies are recorded as simulated outbound messages

This allows the ticket workflow to be demonstrated without exposing or using real mailbox credentials.

## Docker

Start the local stack:

```bash
docker compose up --build
```

The Docker stack includes PostgreSQL, Redis, Django, Celery worker and Celery beat.

## Security notes

Never commit:

```text
.env
db.sqlite3
production database dumps
mailbox passwords
OAuth secrets
Fernet encryption keys
API tokens
```

Use `.env.example` as the public configuration template.

## License

MIT. See `LICENSE` when included by the repository owner.
