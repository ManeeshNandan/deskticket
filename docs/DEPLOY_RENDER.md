# Deploy DeskTicket to Render

This project is prepared for a public hobby/demo deployment on Render.

## Recommended architecture

- GitHub: public source repository
- Render: Django web service (Free)
- PostgreSQL: Neon Free plan (recommended for a demo that should not depend on Render's 30-day Free Postgres expiry)
- Redis/Celery: disabled for the public demo; enable separately if you need background mailbox polling

Render's Free web service is suitable for a hobby/demo project, but it can spin down after inactivity. Render's Free Postgres currently expires after 30 days, so the project is intentionally database-provider agnostic.

## 1. Push this project to GitHub

Do not commit `.env` or `db.sqlite3`.

```bash
git init
git add .
git status
git commit -m "Initial public release"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/deskticket.git
git push -u origin main
```

## 2. Create a PostgreSQL database

Create a free PostgreSQL database with Neon or another PostgreSQL provider. Copy its PostgreSQL connection string. It should look similar to:

```text
postgresql://user:password@host/dbname?sslmode=require
```

Do not commit this value to GitHub.

## 3. Deploy on Render

1. Sign in to Render with GitHub.
2. Choose **New → Web Service**.
3. Select the public `deskticket` repository.
4. Runtime: **Python**.
5. Build command: `./build.sh`.
6. Start command: `python -m gunicorn config.asgi:application -k uvicorn.workers.UvicornWorker`.
7. Choose **Free**.
8. Add these environment variables:

```text
DJANGO_SECRET_KEY=<Generate a secure value in Render>
DJANGO_DEBUG=False
DEMO_MODE=True
DEMO_USERNAME=demo
DEMO_PASSWORD=Demo@12345
MAILBOX_ENCRYPTION_KEY=<Generate a Fernet key>
DATABASE_URL=<your PostgreSQL connection string>
APP_URL=<your Render URL>
```

The Render dashboard automatically provides `RENDER_EXTERNAL_HOSTNAME`; the Django settings use it for `ALLOWED_HOSTS` and CSRF trusted origins.

## 4. Generate the mailbox encryption key

Locally:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

For the public demo, real mailbox secrets should not be entered. The key is present so the application remains compatible with the full mailbox feature set.

## 5. Deploy

Render runs:

```text
pip install -r requirements.txt
collectstatic
migrate
seed_demo
Gunicorn/Uvicorn
```

The demo user and synthetic tickets are created automatically.

## Demo credentials

```text
Username: demo
Password: Demo@12345
```

The account is an application Owner, but it is **not** a Django superuser.

## Demo safety

When `DEMO_MODE=True`:

- real outbound ticket email is disabled
- real mailbox test connections are disabled
- mailbox synchronization is disabled
- the demo reply workflow still records simulated outbound messages
- seed data is synthetic

## 6. Automatic deployments

After the first deployment, pushes to the connected GitHub branch trigger a new Render deployment.

## Important Free-tier limitations

Render Free web services can spin down after inactivity. Render Free Postgres is temporary and currently expires after 30 days. Use Neon Free or another persistent free PostgreSQL provider if you want to keep the demo database longer without moving to a paid Render database.
