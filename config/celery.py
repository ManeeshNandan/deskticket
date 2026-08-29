import os
from celery import Celery
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
app=Celery("deskticket"); app.config_from_object("django.conf:settings",namespace="CELERY_"); app.autodiscover_tasks()
app.conf.beat_schedule={"poll-mailboxes-every-minute":{"task":"tickets.tasks.poll_all_mailboxes","schedule":60.0},"sla-watch-every-minute":{"task":"tickets.tasks.check_sla","schedule":60.0}}
