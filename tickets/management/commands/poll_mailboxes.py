from django.core.management.base import BaseCommand
from django.conf import settings
from tickets.models import EmailAccount
from tickets.services.imap import sync_account

class Command(BaseCommand):
    help = "Poll all configured IMAP mailboxes and create/update tickets."

    def handle(self, *args, **options):
        if settings.DEMO_MODE:
            self.stdout.write(self.style.WARNING("Demo mode is enabled; mailbox polling is disabled."))
            return
        total = 0
        for account in EmailAccount.objects.filter(poll_enabled=True):
            try:
                count = sync_account(account)
                total += count
                self.stdout.write(self.style.SUCCESS(f"{account.email}: {count} new ticket(s)"))
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"{account.email}: {exc}"))
        self.stdout.write(self.style.SUCCESS(f"Done. {total} new ticket(s) created."))
