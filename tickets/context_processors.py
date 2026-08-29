from django.conf import settings

from .models import Notification, Membership
from .services.tenant import current_org, membership_for


def desk_context(request):
    org = current_org(request) if request.user.is_authenticated else None
    membership = membership_for(request.user, org) if org else None
    unread = (
        Notification.objects.filter(
            user=request.user,
            is_read=False,
            organization=org,
        ).count()
        if org
        else 0
    )
    can_manage = bool(
        request.user.is_authenticated
        and (
            request.user.is_staff
            or (
                membership
                and membership.role
                in {
                    Membership.Role.OWNER,
                    Membership.Role.ADMIN,
                    Membership.Role.MANAGER,
                }
            )
        )
    )
    return {
        "desk_org": org,
        "desk_membership": membership,
        "unread_notifications": unread,
        "desk_can_manage": can_manage,
        "APP_NAME": settings.APP_NAME,
        "DEMO_MODE": settings.DEMO_MODE,
    }
