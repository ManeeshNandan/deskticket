from django.conf import settings
import csv
from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q, Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify

from .forms import *
from .models import *
from .services.audit import audit
from .services.email import send_ticket_reply
from .services.imap import sync_account, test_connection
from .services.notifications import notify
from .services.tenant import current_org, membership_for

User = get_user_model()


STAFF_ROLES = {
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
    Membership.Role.MANAGER,
}
AGENT_ROLES = STAFF_ROLES | {Membership.Role.AGENT}


def staff_required(view_func):
    @wraps(view_func)
    def inner(request, *args, **kwargs):
        org = current_org(request)
        membership = membership_for(request.user, org)
        if request.user.is_staff or (membership and membership.role in STAFF_ROLES):
            return view_func(request, *args, **kwargs)
        messages.error(request, "You do not have permission to access that page.")
        return redirect("tickets:dashboard")
    return inner


def agent_required(request, org):
    membership = membership_for(request.user, org)
    return bool(
        request.user.is_staff
        or (membership and membership.role in AGENT_ROLES)
    )


def org_required(view_func):
    @wraps(view_func)
    def inner(request, *args, **kwargs):
        if not current_org(request):
            messages.info(request, "Please create or join a DeskTicket workspace first.")
            return redirect("tickets:signup")
        return view_func(request, *args, **kwargs)
    return inner


def landing(request):
    if request.user.is_authenticated:
        return redirect("tickets:dashboard")
    return render(request, "landing.html")


def signup(request):
    if request.user.is_authenticated:
        return redirect("tickets:dashboard")

    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cd = form.cleaned_data
        workspace_name = cd["organization"]
        workspace_slug = slugify(workspace_name)

        try:
            with transaction.atomic():
                # Re-check inside the transaction to handle concurrent signups.
                if Organization.objects.select_for_update().filter(slug=workspace_slug).exists():
                    form.add_error(
                        "organization",
                        "Workspace name is unavailable. Please choose a different name.",
                    )
                    raise ValueError("workspace_exists")

                user = form.save(commit=False)
                user.email = cd["email"]
                user.first_name = cd["first_name"]
                user.last_name = cd.get("last_name", "")
                user.save()

                org = Organization.objects.create(
                    name=workspace_name,
                    slug=workspace_slug,
                    email=cd["email"],
                )
                Membership.objects.create(
                    organization=org,
                    user=user,
                    role=Membership.Role.OWNER,
                )

                for name, code in [("IT Support", "IT"), ("General", "GEN")]:
                    Department.objects.create(
                        organization=org,
                        name=name,
                        code=code,
                    )

                for priority, first_response, resolution in [
                    ("URGENT", 15, 240),
                    ("HIGH", 30, 480),
                    ("MEDIUM", 120, 2880),
                    ("LOW", 240, 7200),
                ]:
                    SLAPolicy.objects.create(
                        organization=org,
                        name=f"{priority.title()} SLA",
                        priority=priority,
                        first_response_minutes=first_response,
                        resolution_minutes=resolution,
                    )

        except ValueError as exc:
            if str(exc) != "workspace_exists":
                raise
        except IntegrityError as exc:
            # Friendly production-facing validation for race conditions.
            if Organization.objects.filter(slug=workspace_slug).exists():
                form.add_error(
                    "organization",
                    "Workspace name is unavailable. Please choose a different name.",
                )
            elif User.objects.filter(username__iexact=cd["username"]).exists():
                form.add_error(
                    "username",
                    "Username is unavailable. Please choose another username.",
                )
            else:
                form.add_error(
                    None,
                    "We could not create the workspace. Please review the form and try again.",
                )
        else:
            login(request, user)
            request.session["desk_org_id"] = org.id
            messages.success(request, "Your DeskTicket workspace is ready.")
            return redirect("tickets:dashboard")

    return render(request, "registration/signup.html", {"form": form})


@login_required
@org_required
def dashboard(request):
    org = current_org(request)
    base = Ticket.objects.filter(organization=org)
    mine = base.filter(assigned_to=request.user)
    active = base.exclude(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED])
    now = timezone.now()

    context = {
        "total": base.count(),
        "open_count": base.filter(status=Ticket.Status.OPEN).count(),
        "progress_count": base.filter(status=Ticket.Status.IN_PROGRESS).count(),
        "hold_count": base.filter(status=Ticket.Status.ON_HOLD).count(),
        "resolved_count": base.filter(status=Ticket.Status.RESOLVED).count(),
        "urgent_count": active.filter(priority=Ticket.Priority.URGENT).count(),
        "mine_count": mine.exclude(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED]).count(),
        "unassigned_count": active.filter(assigned_to__isnull=True).count(),
        "overdue_count": active.filter(
            Q(sla_resolution_due__lt=now)
            | Q(sla_first_response_due__lt=now, first_response_at__isnull=True)
        ).count(),
        "recent_tickets": base.select_related(
            "assigned_to", "department", "customer"
        )[:12],
    }

    membership = membership_for(request.user, org)
    if request.user.is_staff or (membership and membership.role in STAFF_ROLES):
        context["agent_load"] = (
            active.filter(assigned_to__isnull=False)
            .values("assigned_to__username")
            .annotate(count=Count("id"))
            .order_by("-count")[:8]
        )

    return render(request, "tickets/dashboard.html", context)


@login_required
@org_required
def ticket_list(request):
    org = current_org(request)
    qs = Ticket.objects.filter(organization=org).select_related(
        "assigned_to", "department", "category", "email_account", "customer"
    ).order_by("-created_at")

    membership = membership_for(request.user, org)
    if membership and membership.role == Membership.Role.CUSTOMER:
        qs = qs.filter(requester_email__iexact=request.user.email)

    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    priority = request.GET.get("priority", "").strip()
    assigned = request.GET.get("assigned", "").strip()

    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(subject__icontains=q)
            | Q(requester_email__icontains=q)
            | Q(description__icontains=q)
            | Q(category__name__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)
    if priority:
        qs = qs.filter(priority=priority)
    if assigned == "me":
        qs = qs.filter(assigned_to=request.user)
    elif assigned == "unassigned":
        qs = qs.filter(assigned_to__isnull=True)

    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(request, "tickets/ticket_list.html", {
        "tickets": page,
        "q": q,
        "status": status,
        "priority": priority,
        "assigned": assigned,
        "statuses": Ticket.Status.choices,
        "priorities": Ticket.Priority.choices,
    })


@login_required
@org_required
def ticket_create(request):
    org = current_org(request)
    form = TicketForm(request.POST or None, organization=org)

    if request.method == "POST" and form.is_valid():
        t = form.save(commit=False)
        t.organization = org
        t.created_by = request.user
        t.source = "MANUAL"
        t.sla_policy = SLAPolicy.objects.filter(
            organization=org,
            priority=t.priority,
            is_active=True,
        ).first()
        t.save()
        TicketHistory.objects.create(
            ticket=t,
            user=request.user,
            action="Created",
            new_value="Manual ticket",
        )
        if t.assigned_to:
            notify(
                t.assigned_to,
                t,
                "TICKET_ASSIGNED",
                "New ticket assigned",
                f"{t.number} has been assigned to you.",
            )
        messages.success(request, f"{t.number} created successfully.")
        return redirect("tickets:detail", t.pk)

    return render(request, "tickets/ticket_form.html", {
        "form": form,
        "title": "Create Ticket",
        "subtitle": "Capture the request and route it to the right team.",
    })


@login_required
@org_required
def ticket_detail(request, pk):
    org = current_org(request)
    t = get_object_or_404(
        Ticket.objects.select_related(
            "assigned_to", "department", "category", "email_account", "customer"
        ).prefetch_related("messages__attachments", "comments", "attachments"),
        pk=pk,
        organization=org,
    )
    membership = membership_for(request.user, org)
    if membership and membership.role == Membership.Role.CUSTOMER:
        if t.requester_email.lower() != request.user.email.lower():
            return redirect("tickets:customer_portal")
        return redirect("tickets:customer_detail", pk=t.pk)

    uf = TicketUpdateForm(instance=t, organization=org)
    return render(request, "tickets/ticket_detail.html", {
        "ticket": t,
        "update_form": uf,
        "comment_form": CommentForm(initial={"is_internal": True}),
        "attachment_form": AttachmentForm(),
        "reply_form": ReplyForm(),
    })


@login_required
@org_required
def ticket_update(request, pk):
    org = current_org(request)
    t = get_object_or_404(Ticket, pk=pk, organization=org)
    if not agent_required(request, org):
        return redirect("tickets:customer_detail", pk)

    old_status = t.status
    old_assigned = t.assigned_to_id

    if request.method == "POST":
        form = TicketUpdateForm(request.POST, instance=t, organization=org)
        if form.is_valid():
            t = form.save(commit=False)
            if not t.sla_policy:
                t.sla_policy = SLAPolicy.objects.filter(
                    organization=t.organization,
                    priority=t.priority,
                    is_active=True,
                ).first()
            if t.status == Ticket.Status.RESOLVED and old_status != Ticket.Status.RESOLVED:
                t.resolved_at = timezone.now()
            if t.status != Ticket.Status.RESOLVED and old_status == Ticket.Status.RESOLVED:
                t.resolved_at = None
            if t.status == Ticket.Status.CLOSED and old_status != Ticket.Status.CLOSED:
                t.closed_at = timezone.now()
            if t.status != Ticket.Status.CLOSED and old_status == Ticket.Status.CLOSED:
                t.closed_at = None
            t.save()

            if old_status != t.status:
                TicketHistory.objects.create(
                    ticket=t, user=request.user, action="Status changed",
                    old_value=old_status, new_value=t.status,
                )
                audit(request, t.organization, "STATUS_CHANGED", t, {
                    "old": old_status, "new": t.status,
                })

            if old_assigned != t.assigned_to_id:
                TicketHistory.objects.create(
                    ticket=t, user=request.user, action="Assignment changed",
                    old_value=str(old_assigned or ""),
                    new_value=str(t.assigned_to_id or ""),
                )
                if t.assigned_to:
                    notify(
                        t.assigned_to,
                        t,
                        "TICKET_ASSIGNED",
                        "New ticket assigned",
                        f"{t.number} has been assigned to you.",
                    )
                audit(request, t.organization, "ASSIGNED", t, {
                    "old_user_id": old_assigned,
                    "new_user_id": t.assigned_to_id,
                })
            messages.success(request, "Ticket updated successfully.")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.replace('_', ' ').title()}: {error}")

    return redirect("tickets:detail", pk)


@login_required
@org_required
def add_comment(request, pk):
    org = current_org(request)
    t = get_object_or_404(Ticket, pk=pk, organization=org)
    if not agent_required(request, org):
        return redirect("tickets:customer_detail", pk)
    form = CommentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        c = form.save(commit=False)
        c.ticket = t
        c.author = request.user
        c.save()
        TicketHistory.objects.create(
            ticket=t, user=request.user, action="Comment added"
        )
        messages.success(request, "Internal note added.")
    return redirect("tickets:detail", pk)


@login_required
@org_required
def add_attachment(request, pk):
    org = current_org(request)
    t = get_object_or_404(Ticket, pk=pk, organization=org)
    if not agent_required(request, org):
        return redirect("tickets:customer_detail", pk)
    form = AttachmentForm(request.POST, request.FILES)
    if request.method == "POST" and form.is_valid():
        a = form.save(commit=False)
        a.ticket = t
        a.original_name = a.file.name
        a.save()
        messages.success(request, "Attachment uploaded.")
    return redirect("tickets:detail", pk)


@login_required
@org_required
def ticket_reply(request, pk):
    org = current_org(request)
    t = get_object_or_404(Ticket, pk=pk, organization=org)
    if not agent_required(request, org):
        return redirect("tickets:customer_detail", pk)
    form = ReplyForm(request.POST)
    if request.method == "POST" and form.is_valid():
        try:
            m = send_ticket_reply(t, request.user, form.cleaned_data["body"])
            t.first_response_at = t.first_response_at or m.received_at
            t.status = Ticket.Status.IN_PROGRESS
            t.save(update_fields=["first_response_at", "status", "updated_at"])
            TicketHistory.objects.create(
                ticket=t, user=request.user, action="Email reply sent"
            )
            messages.success(request, "Reply sent to the customer.")
        except Exception as exc:
            messages.error(request, f"Reply failed: {exc}")
    return redirect("tickets:detail", pk)


@login_required
@org_required
def my_tickets(request):
    return customer_portal(request)


@login_required
@org_required
def notifications(request):
    qs = Notification.objects.filter(
        organization=current_org(request), user=request.user
    )
    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(request, "tickets/notifications.html", {"notifications": page})


@login_required
@org_required
def notification_read(request, pk):
    n = get_object_or_404(
        Notification,
        pk=pk,
        organization=current_org(request),
        user=request.user,
    )
    n.is_read = True
    n.save(update_fields=["is_read"])
    return redirect(request.META.get("HTTP_REFERER") or "tickets:notifications")


@login_required
@org_required
def customer_ticket_detail(request, pk):
    org = current_org(request)
    t = get_object_or_404(
        Ticket.objects.prefetch_related("messages__attachments"),
        pk=pk,
        organization=org,
        requester_email__iexact=request.user.email,
    )
    return render(request, "tickets/customer_ticket_detail.html", {
        "ticket": t,
        "form": ReplyForm(),
    })


@login_required
@org_required
def customer_reply(request, pk):
    org = current_org(request)
    t = get_object_or_404(
        Ticket,
        pk=pk,
        organization=org,
        requester_email__iexact=request.user.email,
    )
    form = ReplyForm(request.POST)
    if request.method == "POST" and form.is_valid():
        m = TicketMessage.objects.create(
            ticket=t,
            direction="IN",
            sender=request.user.email,
            recipients=t.email_account.email if t.email_account else "",
            subject=t.subject,
            body=form.cleaned_data["body"],
            received_at=timezone.now(),
        )
        t.status = Ticket.Status.OPEN if t.status in [Ticket.Status.RESOLVED, Ticket.Status.CLOSED] else t.status
        t.save(update_fields=["status", "updated_at"])
        TicketHistory.objects.create(
            ticket=t, user=request.user, action="Customer portal reply"
        )
        if t.assigned_to:
            notify(
                t.assigned_to,
                t,
                "CUSTOMER_REPLY",
                "Customer replied",
                f"{t.number} has a new customer reply.",
            )
        messages.success(request, "Your reply has been sent to the support team.")
    return redirect("tickets:customer_detail", pk)


@login_required
@org_required
def customer_portal(request):
    org = current_org(request)
    qs = Ticket.objects.filter(
        organization=org,
        requester_email__iexact=request.user.email,
    ).select_related("assigned_to", "department", "category")
    return render(request, "tickets/customer_portal.html", {"tickets": qs[:50]})


@login_required
@org_required
def customer_create_ticket(request):
    org = current_org(request)
    form = CustomerTicketForm(request.POST or None, organization=org)
    if request.method == "POST" and form.is_valid():
        customer = Customer.objects.filter(
            organization=org, email__iexact=request.user.email
        ).first()
        t = form.save(commit=False)
        t.organization = org
        t.customer = customer
        t.requester_email = request.user.email
        t.requester_name = request.user.get_full_name() or request.user.username
        t.source = "PORTAL"
        t.sla_policy = SLAPolicy.objects.filter(
            organization=org, priority=t.priority, is_active=True
        ).first()
        t.save()
        TicketHistory.objects.create(
            ticket=t, user=request.user, action="Created", new_value="Customer portal"
        )
        messages.success(request, f"{t.number} created successfully.")
        return redirect("tickets:customer_portal")
    return render(request, "tickets/ticket_form.html", {
        "form": form,
        "title": "Create Support Request",
        "subtitle": "Tell the support team what you need help with.",
    })


@login_required
@org_required
@staff_required
def mailbox_list(request):
    return render(request, "tickets/mailbox_list.html", {
        "mailboxes": EmailAccount.objects.filter(
            organization=current_org(request)
        ).order_by("email")
    })


@login_required
@org_required
@staff_required
def mailbox_create(request):
    form = EmailAccountForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            obj = form.save(commit=False)
            obj.organization = current_org(request)
            obj.save()
            messages.success(request, f"Mailbox {obj.email} saved successfully.")
            return redirect("tickets:mailboxes")
        except IntegrityError:
            form.add_error("email", "A mailbox with this email already exists in this workspace.")
    return render(request, "tickets/mailbox_form.html", {
        "form": form, "title": "Add Email Mailbox"
    })


@login_required
@org_required
@staff_required
def mailbox_edit(request, pk):
    obj = get_object_or_404(
        EmailAccount, pk=pk, organization=current_org(request)
    )
    form = EmailAccountForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        try:
            form.save()
            messages.success(request, "Mailbox updated successfully.")
            return redirect("tickets:mailboxes")
        except IntegrityError:
            form.add_error("email", "A mailbox with this email already exists in this workspace.")
    return render(request, "tickets/mailbox_form.html", {
        "form": form, "title": "Edit Email Mailbox", "mailbox": obj
    })


@login_required
@org_required
@staff_required
def mailbox_test(request, pk):
    if settings.DEMO_MODE:
        messages.info(request, "Demo mode: real mailbox connections are disabled.")
        return redirect("tickets:mailboxes")
    obj = get_object_or_404(
        EmailAccount, pk=pk, organization=current_org(request)
    )
    try:
        test_connection(obj)
        messages.success(request, "IMAP connection successful.")
    except Exception as exc:
        messages.error(request, f"Connection failed: {exc}")
    return redirect("tickets:mailboxes")


@login_required
@org_required
@staff_required
def mailbox_sync(request, pk):
    if settings.DEMO_MODE:
        messages.info(request, "Demo mode: mailbox synchronization is disabled.")
        return redirect("tickets:mailboxes")
    obj = get_object_or_404(
        EmailAccount, pk=pk, organization=current_org(request)
    )
    try:
        count = sync_account(obj)
        messages.success(request, f"Sync complete. {count} new ticket(s).")
    except Exception as exc:
        messages.error(request, f"Sync failed: {exc}")
    return redirect("tickets:mailboxes")


@login_required
@org_required
@staff_required
def reports(request):
    org = current_org(request)
    qs = Ticket.objects.filter(organization=org)
    now = timezone.now()
    context = {
        "total": qs.count(),
        "resolved": qs.filter(status=Ticket.Status.RESOLVED).count(),
        "closed": qs.filter(status=Ticket.Status.CLOSED).count(),
        "overdue": qs.exclude(
            status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED]
        ).filter(sla_resolution_due__lt=now).count(),
        "by_status": qs.values("status").annotate(count=Count("id")),
        "by_priority": qs.values("priority").annotate(count=Count("id")),
        "by_department": qs.values("department__name").annotate(count=Count("id")).order_by("-count"),
    }
    return render(request, "tickets/reports.html", context)


@login_required
@org_required
@staff_required
def report_csv(request):
    org = current_org(request)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="deskticket-report.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "Ticket", "Subject", "Requester", "Status", "Priority",
        "Assigned", "Created", "Resolution Due",
    ])
    for t in Ticket.objects.filter(organization=org).select_related("assigned_to"):
        writer.writerow([
            t.number, t.subject, t.requester_email, t.get_status_display(),
            t.get_priority_display(), t.assigned_to or "", t.created_at,
            t.sla_resolution_due or "",
        ])
    return response


@login_required
@org_required
@staff_required
def members(request):
    org = current_org(request)
    form = MemberForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cd = form.cleaned_data
        if User.objects.filter(username__iexact=cd["username"]).exists():
            form.add_error("username", "Username is unavailable. Please choose another username.")
        elif User.objects.filter(email__iexact=cd["email"]).exists():
            form.add_error("email", "Email is already associated with another user.")
        else:
            u = User.objects.create_user(
                username=cd["username"],
                email=cd["email"],
                password=cd["password"],
                first_name=cd["first_name"],
            )
            Membership.objects.create(
                organization=org,
                user=u,
                role=cd["role"],
            )
            messages.success(request, f"{u.username} added to the workspace.")
            return redirect("tickets:members")
    return render(request, "tickets/members.html", {
        "members": Membership.objects.filter(
            organization=org, is_active=True
        ).select_related("user").order_by("user__first_name", "user__username"),
        "form": form,
    })


@login_required
@org_required
@staff_required
def customers(request):
    org = current_org(request)
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cd = form.cleaned_data
        if Customer.objects.filter(organization=org, email__iexact=cd["email"]).exists():
            form.add_error("email", "A customer with this email already exists in this workspace.")
        else:
            username = cd.get("username") or cd["email"].split("@")[0]
            base = username
            suffix = 1
            while User.objects.filter(username__iexact=username).exists():
                suffix += 1
                username = f"{base}{suffix}"
            u = User.objects.create_user(
                username=username,
                email=cd["email"],
                password=cd["password"],
                first_name=cd["name"],
            )
            Membership.objects.create(
                organization=org, user=u, role=Membership.Role.CUSTOMER
            )
            c = Customer.objects.create(
                organization=org,
                name=cd["name"],
                email=cd["email"],
                phone=cd["phone"],
                company=cd["company"],
                notes=cd["notes"],
                user=u,
            )
            messages.success(
                request,
                f"Customer {c.name} created. Portal username: {username}",
            )
            return redirect("tickets:customers")
    return render(request, "tickets/customers.html", {
        "customers": Customer.objects.filter(organization=org).order_by("name"),
        "form": form,
    })


@login_required
@org_required
@staff_required
def settings_home(request):
    return render(request, "tickets/settings.html", {
        "organization": current_org(request)
    })


@login_required
@org_required
@staff_required
def departments(request):
    org = current_org(request)
    form = DepartmentForm(request.POST or None, organization=org)
    if request.method == "POST" and form.is_valid():
        try:
            obj = form.save(commit=False)
            obj.organization = org
            obj.save()
            messages.success(request, f"Department '{obj.name}' created.")
            return redirect("tickets:departments")
        except IntegrityError:
            form.add_error("code", "Department code is already in use in this workspace.")
    return render(request, "tickets/departments.html", {
        "departments": Department.objects.filter(organization=org).order_by("name"),
        "form": form,
    })


@login_required
@org_required
@staff_required
def sla_policies(request):
    org = current_org(request)
    form = SLAForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.organization = org
        obj.save()
        messages.success(request, f"SLA policy '{obj.name}' created.")
        return redirect("tickets:sla")
    return render(request, "tickets/sla.html", {
        "policies": SLAPolicy.objects.filter(organization=org).order_by("priority", "name"),
        "form": form,
    })


@login_required
@org_required
@staff_required
def category_list(request):
    org = current_org(request)
    categories = Category.objects.filter(
        organization=org
    ).select_related("department").order_by("department__name", "name")
    return render(request, "tickets/category_list.html", {
        "categories": categories,
    })


@login_required
@org_required
@staff_required
def category_create(request):
    org = current_org(request)
    form = CategoryForm(request.POST or None, organization=org)

    if request.method == "POST" and form.is_valid():
        category = form.save(commit=False)
        category.organization = org
        category.save()
        messages.success(request, f"Category '{category.name}' created successfully.")
        return redirect("tickets:categories")

    return render(request, "tickets/category_form.html", {
        "form": form,
        "title": "Create Category",
        "subtitle": "Create a category for a department in this workspace.",
    })


@login_required
@org_required
@staff_required
def category_edit(request, pk):
    org = current_org(request)
    category = get_object_or_404(Category, pk=pk, organization=org)
    form = CategoryForm(request.POST or None, instance=category, organization=org)

    if request.method == "POST" and form.is_valid():
        category = form.save(commit=False)
        category.organization = org
        category.save()
        messages.success(request, f"Category '{category.name}' updated successfully.")
        return redirect("tickets:categories")

    return render(request, "tickets/category_form.html", {
        "form": form,
        "title": "Edit Category",
        "subtitle": "Update the category and its department.",
        "category": category,
    })


@login_required
@org_required
@staff_required
def category_delete(request, pk):
    org = current_org(request)
    category = get_object_or_404(Category, pk=pk, organization=org)

    if request.method == "POST":
        name = category.name
        category.delete()
        messages.success(request, f"Category '{name}' deleted.")
        return redirect("tickets:categories")

    return render(request, "tickets/category_confirm_delete.html", {
        "category": category,
    })
