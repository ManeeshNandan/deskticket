from ..models import AuditLog

def audit(request, organization, action, obj, details=None):
    x_forwarded=request.META.get("HTTP_X_FORWARDED_FOR","")
    ip=x_forwarded.split(",")[0].strip() if x_forwarded else request.META.get("REMOTE_ADDR")
    return AuditLog.objects.create(organization=organization,user=request.user if request.user.is_authenticated else None,action=action,model_name=obj.__class__.__name__,object_id=str(obj.pk),details=details or {},ip_address=ip)
