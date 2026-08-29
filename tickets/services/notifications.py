from django.core.mail import send_mail
from django.conf import settings
from ..models import Notification

def notify(user, ticket, notification_type, title, message, email=True):
    if not user: return None
    n=Notification.objects.create(organization=ticket.organization if ticket else None,user=user,ticket=ticket,notification_type=notification_type,title=title,message=message)
    if email and user.email and not settings.DEMO_MODE:
        try: send_mail(f"{title} | DeskTicket",message,settings.DEFAULT_FROM_EMAIL,[user.email],fail_silently=True)
        except Exception: pass
    return n
