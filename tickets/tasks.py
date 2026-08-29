from celery import shared_task
from django.utils import timezone
from django.conf import settings
from django.db.models import Q
from .models import EmailAccount, Ticket
from .services.imap import sync_account
from .services.notifications import notify

@shared_task
def poll_all_mailboxes():
    if settings.DEMO_MODE:
        return []
    results=[]
    for account in EmailAccount.objects.filter(poll_enabled=True,organization__is_active=True):
        try: results.append((account.email,sync_account(account)))
        except Exception as exc: results.append((account.email,f"ERROR: {exc}"))
    return results

@shared_task
def check_sla():
    now=timezone.now(); qs=Ticket.objects.exclude(status__in=["RESOLVED","CLOSED"])
    for t in qs.select_related("assigned_to"):
        if t.sla_first_response_due and not t.first_response_at and not t.sla_first_breached and now>=t.sla_first_response_due:
            t.sla_first_breached=True; t.save(update_fields=["sla_first_breached","updated_at"]); notify(t.assigned_to,t,"SLA_BREACH","First response SLA breached",f"{t.number} has breached its first-response SLA.")
        if t.sla_resolution_due and not t.sla_resolution_breached and now>=t.sla_resolution_due:
            t.sla_resolution_breached=True; t.save(update_fields=["sla_resolution_breached","updated_at"]); notify(t.assigned_to,t,"SLA_BREACH","Resolution SLA breached",f"{t.number} has breached its resolution SLA.")
