from django.shortcuts import get_object_or_404
from ..models import Membership, Organization

def membership_for(user, org=None):
    if not user.is_authenticated: return None
    qs=Membership.objects.select_related("organization").filter(user=user,is_active=True,organization__is_active=True)
    return qs.filter(organization=org).first() if org else qs.first()

def current_org(request):
    if getattr(request,"_desk_org",None): return request._desk_org
    mid=request.session.get("desk_org_id")
    if mid and request.user.is_authenticated:
        m=Membership.objects.filter(user=request.user,organization_id=mid,is_active=True).select_related("organization").first()
        if m: request._desk_org=m.organization; return m.organization
    m=membership_for(request.user)
    if m: request.session["desk_org_id"]=m.organization_id; request._desk_org=m.organization; return m.organization
    if request.user.is_superuser:
        o=Organization.objects.filter(is_active=True).first()
        if o: request._desk_org=o; return o
    return None
