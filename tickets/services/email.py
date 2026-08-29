from email.utils import make_msgid

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from ..models import TicketMessage


def send_ticket_reply(ticket, user, body):
    """Send a real email in normal mode, or record a simulated reply in demo mode."""
    mailbox = ticket.email_account
    from_email = mailbox.email if mailbox else settings.DEFAULT_FROM_EMAIL
    recipients = [ticket.requester_email]
    subject = f"Re: [{ticket.number}] {ticket.subject}"
    last = ticket.messages.order_by("-received_at").first()
    headers = {"X-DeskTicket-Ticket": ticket.number}
    if last and last.message_id:
        headers["In-Reply-To"] = last.message_id
        headers["References"] = (last.references + " " + last.message_id).strip()
    msgid = make_msgid(domain="demo.deskticket.local" if settings.DEMO_MODE else from_email.split("@")[-1])
    headers["Message-ID"] = msgid
    text = body
    html = (
        "<div style='font-family:Arial,sans-serif;white-space:pre-wrap'>"
        + body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        + "</div>"
    )

    if not settings.DEMO_MODE:
        mail = EmailMultiAlternatives(
            subject, text, from_email, recipients, headers=headers
        )
        mail.attach_alternative(html, "text/html")
        mail.send(fail_silently=False)

    return TicketMessage.objects.create(
        ticket=ticket,
        direction="OUT",
        sender=from_email,
        recipients=", ".join(recipients),
        subject=subject,
        body=body,
        body_html=html,
        message_id=msgid,
        received_at=timezone.now(),
    )
