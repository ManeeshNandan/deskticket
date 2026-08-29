from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from tickets.models import (
    AuditLog,
    Category,
    Customer,
    Department,
    Membership,
    Notification,
    Organization,
    SLAPolicy,
    Ticket,
    TicketComment,
    TicketHistory,
    TicketMessage,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Create or refresh the synthetic DeskTicket demo account and sample data."

    def handle(self, *args, **options):
        if not settings.DEMO_MODE:
            self.stdout.write(self.style.WARNING("DEMO_MODE is not enabled; demo data was not changed."))
            return

        username = settings.DEMO_USERNAME
        password = settings.DEMO_PASSWORD

        demo_user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": "demo@deskticket.local",
                "first_name": "Demo",
                "last_name": "Agent",
            },
        )
        demo_user.email = "demo@deskticket.local"
        demo_user.first_name = "Demo"
        demo_user.last_name = "Agent"
        demo_user.is_active = True
        demo_user.is_staff = False
        demo_user.is_superuser = False
        demo_user.set_password(password)
        demo_user.save()

        org, _ = Organization.objects.get_or_create(
            slug="deskticket-demo",
            defaults={
                "name": "DeskTicket Demo Workspace",
                "email": "demo@deskticket.local",
                "timezone": "Asia/Kolkata",
            },
        )
        org.name = "DeskTicket Demo Workspace"
        org.email = "demo@deskticket.local"
        org.is_active = True
        org.save(update_fields=["name", "email", "is_active"])

        Membership.objects.update_or_create(
            organization=org,
            user=demo_user,
            defaults={"role": Membership.Role.OWNER, "is_active": True},
        )

        departments = {}
        for name, code in [
            ("IT Support", "IT"),
            ("Customer Service", "CS"),
            ("Billing", "BILL"),
            ("Technical Support", "TECH"),
        ]:
            departments[code], _ = Department.objects.get_or_create(
                organization=org,
                code=code,
                defaults={"name": name, "is_active": True},
            )
            departments[code].name = name
            departments[code].is_active = True
            departments[code].save(update_fields=["name", "is_active"])

        categories = {}
        category_map = {
            "IT": ["Login & Access", "Hardware", "Software"],
            "CS": ["General Enquiry", "Account Support", "Service Request"],
            "BILL": ["Invoice Query", "Payment Issue"],
            "TECH": ["Bug Report", "Integration", "Performance"],
        }
        for code, names in category_map.items():
            for name in names:
                categories[(code, name)], _ = Category.objects.get_or_create(
                    organization=org,
                    department=departments[code],
                    name=name,
                    defaults={"is_active": True},
                )

        sla_values = {
            "URGENT": (15, 240),
            "HIGH": (30, 480),
            "MEDIUM": (120, 2880),
            "LOW": (240, 7200),
        }
        slas = {}
        for priority, (first_response, resolution) in sla_values.items():
            slas[priority], _ = SLAPolicy.objects.get_or_create(
                organization=org,
                priority=priority,
                defaults={
                    "name": f"{priority.title()} SLA",
                    "first_response_minutes": first_response,
                    "resolution_minutes": resolution,
                    "warning_percent": 80,
                    "is_active": True,
                },
            )

        customer_specs = [
            ("Aarav Menon", "aarav@example.test", "Acme Retail"),
            ("Meera Nair", "meera@example.test", "Northstar Labs"),
            ("Rahul Das", "rahul@example.test", "BluePeak Services"),
            ("Ananya Iyer", "ananya@example.test", "Orbit Systems"),
            ("Vivek Kumar", "vivek@example.test", "Greenline Foods"),
            ("Diya Thomas", "diya@example.test", "Summit Finance"),
        ]
        customers = []
        for name, email, company in customer_specs:
            customer, _ = Customer.objects.get_or_create(
                organization=org,
                email=email,
                defaults={
                    "name": name,
                    "company": company,
                    "phone": "+91 90000 00000",
                    "notes": "Synthetic demo customer data.",
                },
            )
            customer.name = name
            customer.company = company
            customer.notes = "Synthetic demo customer data."
            customer.save(update_fields=["name", "company", "notes"])
            customers.append(customer)

        samples = [
            ("Unable to sign in to the employee portal", "OPEN", "HIGH", "IT", "Login & Access"),
            ("Invoice amount needs clarification", "IN_PROGRESS", "MEDIUM", "BILL", "Invoice Query"),
            ("API integration returning intermittent 500 errors", "OPEN", "URGENT", "TECH", "Integration"),
            ("Request for new laptop setup", "ON_HOLD", "LOW", "IT", "Hardware"),
            ("Customer profile update request", "RESOLVED", "MEDIUM", "CS", "Account Support"),
            ("Dashboard page loads slowly", "OPEN", "HIGH", "TECH", "Performance"),
            ("Payment confirmation not received", "IN_PROGRESS", "HIGH", "BILL", "Payment Issue"),
            ("General service enquiry", "CLOSED", "LOW", "CS", "General Enquiry"),
            ("Bug in CSV export", "OPEN", "MEDIUM", "TECH", "Bug Report"),
            ("Software installation request", "RESOLVED", "LOW", "IT", "Software"),
            ("Service request status update", "OPEN", "MEDIUM", "CS", "Service Request"),
            ("Account access after role change", "IN_PROGRESS", "HIGH", "IT", "Login & Access"),
        ]

        now = timezone.now()
        for index, (subject, status, priority, dept_code, category_name) in enumerate(samples):
            customer = customers[index % len(customers)]
            created_at = now - timedelta(days=(index % 14), hours=(index * 2) % 12)
            ticket, created_ticket = Ticket.objects.get_or_create(
                organization=org,
                subject=subject,
                defaults={
                    "customer": customer,
                    "description": self._description(subject),
                    "requester_name": customer.name,
                    "requester_email": customer.email,
                    "source": "EMAIL" if index % 3 == 0 else "PORTAL",
                    "status": status,
                    "priority": priority,
                    "department": departments[dept_code],
                    "category": categories[(dept_code, category_name)],
                    "assigned_to": demo_user if index % 4 != 0 else None,
                    "created_by": demo_user,
                    "sla_policy": slas[priority],
                    "created_at": created_at,
                },
            )
            if not created_ticket:
                ticket.customer = customer
                ticket.description = self._description(subject)
                ticket.requester_name = customer.name
                ticket.requester_email = customer.email
                ticket.status = status
                ticket.priority = priority
                ticket.department = departments[dept_code]
                ticket.category = categories[(dept_code, category_name)]
                ticket.assigned_to = demo_user if index % 4 != 0 else None
                ticket.created_by = demo_user
                ticket.sla_policy = slas[priority]
                ticket.save()

            if status in {Ticket.Status.RESOLVED, Ticket.Status.CLOSED}:
                Ticket.objects.filter(pk=ticket.pk).update(
                    resolved_at=created_at + timedelta(hours=3)
                    if status == Ticket.Status.RESOLVED
                    else None,
                    closed_at=created_at + timedelta(hours=5)
                    if status == Ticket.Status.CLOSED
                    else None,
                )
                ticket.refresh_from_db()

            TicketMessage.objects.get_or_create(
                message_id=f"<demo-{ticket.id}-incoming@deskticket.local>",
                defaults={
                    "ticket": ticket,
                    "direction": "IN",
                    "sender": customer.email,
                    "recipients": "support@deskticket.local",
                    "subject": ticket.subject,
                    "body": self._description(subject),
                    "received_at": created_at,
                },
            )
            TicketComment.objects.get_or_create(
                ticket=ticket,
                author=demo_user,
                comment="Demo internal note: synthetic data for public demonstration.",
                defaults={"is_internal": True},
            )
            TicketHistory.objects.get_or_create(
                ticket=ticket,
                user=demo_user,
                action="Demo ticket created",
                defaults={"new_value": "Synthetic demo ticket"},
            )

        for ticket in Ticket.objects.filter(organization=org).order_by("id")[:5]:
            Notification.objects.get_or_create(
                organization=org,
                user=demo_user,
                ticket=ticket,
                notification_type="DEMO",
                defaults={
                    "title": "Demo activity",
                    "message": f"{ticket.number} is available to explore in the demo workspace.",
                    "is_read": False,
                },
            )

        AuditLog.objects.get_or_create(
            organization=org,
            user=demo_user,
            action="DEMO_DATA_SEEDED",
            model_name="Demo",
            object_id="deskticket-demo",
            defaults={"details": {"synthetic": True}},
        )

        self.stdout.write(self.style.SUCCESS("DeskTicket demo data is ready."))
        self.stdout.write(f"Username: {username}")
        self.stdout.write(f"Password: {password}")
        self.stdout.write("Workspace: DeskTicket Demo Workspace")

    @staticmethod
    def _description(subject):
        return (
            f"This is synthetic data created for the DeskTicket public demo.\n\n"
            f"Example request: {subject}.\n"
            "No real customer, patient, company, or production information is used."
        )
