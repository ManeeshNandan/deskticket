from django.core.management.base import BaseCommand, CommandError
from tickets.models import EmailAccount
from tickets.services.imap import test_connection

class Command(BaseCommand):
    help = "Test an EmailAccount IMAP connection."

    def add_arguments(self, parser):
        parser.add_argument("account_id", type=int)

    def handle(self, *args, **opts):
        try:
            account = EmailAccount.objects.get(pk=opts["account_id"])
            test_connection(account)
            self.stdout.write(self.style.SUCCESS(f"Connection successful: {account.email}"))
        except Exception as exc:
            raise CommandError(str(exc))
