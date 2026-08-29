import email
import imaplib
import nh3
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
from html import unescape
from django.db import transaction, IntegrityError
from django.conf import settings
from django.utils import timezone
from tickets.models import EmailAccount, Ticket, TicketMessage, TicketAttachment, Customer, SLAPolicy
from .security import decrypt
from .notifications import notify
from .oauth import refresh_access_token
from bs4 import BeautifulSoup

def decode_mime_header(value):
    if not value: return ""
    out = ""
    for part, enc in decode_header(value):
        if isinstance(part, bytes):
            out += part.decode(enc or "utf-8", errors="replace")
        else: out += part
    return out


def get_email_bodies(msg):
    """
    Extract both plain-text and HTML email bodies.
    Returns:
        {
            "text": "...",
            "html": "..."
        }
    """

    text_parts = []
    html_parts = []

    if msg.is_multipart():

        for part in msg.walk():

            if part.get_content_disposition() == "attachment":
                continue

            content_type = part.get_content_type()

            try:
                payload = part.get_payload(decode=True)

                if not payload:
                    continue

                charset = part.get_content_charset() or "utf-8"

                content = payload.decode(
                    charset,
                    errors="replace"
                )

            except Exception:
                continue

            if content_type == "text/plain":
                text_parts.append(content)

            elif content_type == "text/html":
                html_parts.append(content)

    else:

        try:
            payload = msg.get_payload(decode=True)

            if payload:

                charset = msg.get_content_charset() or "utf-8"

                content = payload.decode(
                    charset,
                    errors="replace"
                )

                if msg.get_content_type() == "text/html":
                    html_parts.append(content)

                else:
                    text_parts.append(content)

        except Exception:
            pass

    # ---------------------------------------------------------
    # Prefer plain text
    # ---------------------------------------------------------

    text = "\n\n".join(text_parts).strip()

    # ---------------------------------------------------------
    # If no plain text exists, convert HTML to text
    # ---------------------------------------------------------

    if not text and html_parts:

        soup = BeautifulSoup(
            "\n".join(html_parts),
            "html.parser"
        )

        # Remove scripts/styles
        for tag in soup(
            ["script", "style", "head"]
        ):
            tag.decompose()

        text = soup.get_text(
            separator="\n",
            strip=True
        )

    html = "\n".join(html_parts).strip()

    return {
        "text": text,
        "html": html,
    }


def thread_key(msg):
    refs = msg.get("References", "").strip()
    irt = msg.get("In-Reply-To", "").strip()
    return refs.split()[0] if refs else irt


def find_existing_ticket(msg):
    mid = msg.get("Message-ID", "").strip()
    if mid:
        existing = Ticket.objects.filter(message_id=mid).first()
        if existing: return existing
    refs = (msg.get("References", "") + " " + msg.get("In-Reply-To", "")).split()
    for ref in refs:
        existing = Ticket.objects.filter(message_id=ref).first()
        if existing: return existing
    tk = thread_key(msg)
    if tk:
        existing = Ticket.objects.filter(thread_key=tk).first()
        if existing: return existing
    return None


@transaction.atomic
def process_message(account, uid, raw):
    msg = email.message_from_bytes(raw)

    sender_name, sender_email = parseaddr(msg.get("From", ""))

    subject = decode_mime_header(
        msg.get("Subject", "(No Subject)")
    )[:255]

    message_id = msg.get("Message-ID", "").strip() or None
    bodies = get_email_bodies(msg)

    body_text = bodies["text"]
    body_html = bodies["html"]
    

    body_html = nh3.clean(
        body_html,
        tags={
            "a",
            "p",
            "div",
            "span",
            "br",
            "table",
            "thead",
            "tbody",
            "tr",
            "th",
            "td",
            "strong",
            "b",
            "i",
            "u",
            "ul",
            "ol",
            "li",
        },
        attributes={
            "a": {"href", "title", "target"},
            "td": {"colspan", "rowspan"},
            "th": {"colspan", "rowspan"},
        },
    )
    # ---------------------------------------------------------
    # 1. Prevent duplicate email processing
    # ---------------------------------------------------------
    if message_id:
        existing_message = TicketMessage.objects.filter(
            message_id=message_id
        ).select_related("ticket").first()

        if existing_message:
            return existing_message.ticket, False

    # ---------------------------------------------------------
    # 2. Find existing ticket by email threading headers
    # ---------------------------------------------------------
    existing_ticket = find_existing_ticket(msg)
    was_new_ticket = existing_ticket is None

    if existing_ticket and account.create_ticket_from_replies:
        ticket = existing_ticket

    elif existing_ticket:
        return existing_ticket, False

    else:
        # -----------------------------------------------------
        # 3. Create a completely new ticket
        # -----------------------------------------------------
        customer = None
        if account.organization and sender_email:
            customer, _ = Customer.objects.get_or_create(
                organization=account.organization,
                email=sender_email,
                defaults={"name": decode_mime_header(sender_name) or sender_email},
            )
        sla = SLAPolicy.objects.filter(organization=account.organization,priority="MEDIUM",is_active=True).first() if account.organization else None
        ticket = Ticket.objects.create(
            organization=account.organization,
            customer=customer,
            sla_policy=sla,
            subject=subject or "(No Subject)",
            description=body_text or "(No message body)",
            requester_name=decode_mime_header(sender_name),
            requester_email=sender_email,
            source="EMAIL",
            email_account=account,
            message_id=message_id,
            thread_key=thread_key(msg),
            status=Ticket.Status.OPEN,
        )

    # ---------------------------------------------------------
    # 4. Get received date
    # ---------------------------------------------------------
    received = timezone.now()

    try:
        if msg.get("Date"):
            received = parsedate_to_datetime(
                msg.get("Date")
            )
    except Exception:
        pass

    # ---------------------------------------------------------
    # 5. Extra safety check before creating TicketMessage
    # ---------------------------------------------------------
    if message_id:
        existing_message = TicketMessage.objects.filter(
            message_id=message_id
        ).first()

        if existing_message:
            return existing_message.ticket, False

    # ---------------------------------------------------------
    # 6. Create incoming ticket message
    # ---------------------------------------------------------
    try:
        with transaction.atomic():
            tm = TicketMessage.objects.create(
                ticket=ticket, direction="IN", sender=sender_email, recipients=msg.get("To", ""),
                subject=subject, body=body_text, body_html=body_html, message_id=message_id,
                in_reply_to=msg.get("In-Reply-To", ""), references=msg.get("References", ""), received_at=received,
            )
    except IntegrityError:
        if message_id:
            existing_message=TicketMessage.objects.filter(message_id=message_id).select_related("ticket").first()
            if existing_message: return existing_message.ticket, False
        raise

    if ticket.assigned_to:
        notify(ticket.assigned_to,ticket,"CUSTOMER_REPLY" if not was_new_ticket else "TICKET_CREATED","New customer email",f"{ticket.number} has a new customer email.")

    # ---------------------------------------------------------
    # 7. Save attachments
    # ---------------------------------------------------------
    for part in msg.walk():

        if part.is_multipart():
            continue

        filename = decode_mime_header(
            part.get_filename() or ""
        )

        if not filename:
            continue

        data = part.get_payload(decode=True)

        if not data:
            continue

        from django.core.files.base import ContentFile

        attachment = TicketAttachment(
            ticket=ticket,
            message=tm,
            original_name=filename,
        )

        attachment.file.save(
            filename,
            ContentFile(data),
            save=True,
        )

    return ticket, was_new_ticket


def test_connection(account):
    if settings.DEMO_MODE:
        raise RuntimeError("Real mailbox connections are disabled in demo mode.")
    mail = imaplib.IMAP4_SSL(account.imap_host, account.imap_port) if account.imap_ssl else imaplib.IMAP4(account.imap_host, account.imap_port)
    if account.auth_method == EmailAccount.AuthMethod.PASSWORD:
        mail.login(account.username, decrypt(account.secret_encrypted))
    else:
        token=refresh_access_token(account)
        auth_string=f"user={account.username}\x01auth=Bearer {token}\x01\x01"
        mail.authenticate("XOAUTH2", lambda _: auth_string.encode())
    mail.select(account.folder)
    mail.logout()
    return True


def sync_account(account):
    if settings.DEMO_MODE:
        return 0
    if not account.poll_enabled: return 0
    mail = imaplib.IMAP4_SSL(account.imap_host, account.imap_port) if account.imap_ssl else imaplib.IMAP4(account.imap_host, account.imap_port)
    try:
        if account.auth_method == EmailAccount.AuthMethod.PASSWORD:
            mail.login(account.username, decrypt(account.secret_encrypted))
        else:
            token=refresh_access_token(account)
            auth_string=f"user={account.username}\x01auth=Bearer {token}\x01\x01"
            mail.authenticate("XOAUTH2", lambda _: auth_string.encode())
        mail.select(account.folder)
        typ, data = mail.uid("search", None, "ALL")
        if typ != "OK": return 0
        uids = [int(x) for x in data[0].split()]
        new_uids = [u for u in uids if u > account.last_uid]
        created = 0
        for uid in new_uids:
            typ, msg_data = mail.uid("fetch", str(uid), "(RFC822)")
            if typ != "OK": continue
            raw = next((x[1] for x in msg_data if isinstance(x, tuple)), None)
            if not raw: continue
            ticket, was_new_ticket = process_message(account, uid, raw)
            if was_new_ticket:
                created += 1
            if account.mark_as_seen:
                mail.uid("store", str(uid), "+FLAGS", "(\\Seen)")
            account.last_uid = max(account.last_uid, uid)
            account.save(update_fields=["last_uid", "updated_at"])
        account.last_checked_at = timezone.now()
        account.last_error = ""
        account.save(update_fields=["last_checked_at", "last_error", "updated_at"])
        return created
    except Exception as exc:
        account.last_error = str(exc)
        account.last_checked_at = timezone.now()
        account.save(update_fields=["last_error", "last_checked_at", "updated_at"])
        raise
    finally:
        try: mail.logout()
        except Exception: pass
