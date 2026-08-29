from rest_framework import serializers, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .models import Ticket, TicketComment, TicketMessage, Department, Category, Customer, Notification, Membership
from .services.email import send_ticket_reply
from .services.notifications import notify
from .services.tenant import current_org


class IsAgentOrAdmin(permissions.BasePermission):
    def has_permission(self,request,view):
        if not request.user.is_authenticated: return False
        if request.method in permissions.SAFE_METHODS: return True
        org=current_org(request)
        m=__import__("tickets.services.tenant",fromlist=["membership_for"]).membership_for(request.user,org) if org else None
        return bool(request.user.is_staff or (m and m.role in ["OWNER","ADMIN","MANAGER","AGENT"]))

class TenantMixin:
    def org(self): return current_org(self.request)
    def get_queryset(self):
        qs=super().get_queryset(); org=self.org()
        return qs.filter(organization=org) if org else qs.none()

class TicketSerializer(serializers.ModelSerializer):
    class Meta: model=Ticket; fields=["id","number","subject","description","requester_name","requester_email","source","status","priority","department","category","assigned_to","customer","created_at","updated_at","resolved_at","closed_at","sla_first_response_due","sla_resolution_due","sla_first_breached","sla_resolution_breached"]; read_only_fields=["number","created_at","updated_at","resolved_at","closed_at"]

class CommentSerializer(serializers.ModelSerializer):
    class Meta: model=TicketComment; fields=["id","ticket","comment","is_internal","author","created_at"]; read_only_fields=["author","created_at"]
class DepartmentSerializer(serializers.ModelSerializer):
    class Meta: model=Department; fields=["id","name","code","is_active"]
class CategorySerializer(serializers.ModelSerializer):
    class Meta: model=Category; fields=["id","department","name","is_active"]
class CustomerSerializer(serializers.ModelSerializer):
    class Meta: model=Customer; fields=["id","name","email","phone","company","notes","created_at"]; read_only_fields=["created_at"]
class NotificationSerializer(serializers.ModelSerializer):
    class Meta: model=Notification; fields=["id","ticket","notification_type","title","message","is_read","created_at"]

class TicketViewSet(TenantMixin, viewsets.ModelViewSet):
    serializer_class=TicketSerializer; permission_classes=[IsAgentOrAdmin]; search_fields=["number","subject","requester_email","description"]; filterset_fields=["status","priority","department","category","assigned_to"]; ordering_fields=["created_at","updated_at","priority"]
    def get_queryset(self):
        org=self.org()
        if not org: return Ticket.objects.none()
        qs=Ticket.objects.select_related("department","category","assigned_to","customer").filter(organization=org)
        from .services.tenant import membership_for
        m=membership_for(self.request.user,org)
        if m and m.role=="CUSTOMER": qs=qs.filter(requester_email__iexact=self.request.user.email)
        return qs
    def perform_create(self,serializer):
        org=self.org(); data={"organization":org,"created_by":self.request.user,"source":"API"}
        from .services.tenant import membership_for
        m=membership_for(self.request.user,org)
        if m and m.role=="CUSTOMER": data.update({"requester_email":self.request.user.email,"requester_name":self.request.user.get_full_name() or self.request.user.username,"source":"PORTAL"})
        serializer.save(**data)
    @action(detail=True,methods=["post"])
    def reply(self,request,pk=None):
        t=self.get_object(); body=request.data.get("body","").strip()
        if not body: return Response({"detail":"body is required"},status=400)
        m=send_ticket_reply(t,request.user,body); t.first_response_at=t.first_response_at or m.received_at; t.status=Ticket.Status.IN_PROGRESS; t.save(update_fields=["first_response_at","status","updated_at"]); return Response({"message_id":m.message_id})
    @action(detail=True,methods=["post"])
    def assign(self,request,pk=None):
        t=self.get_object(); uid=request.data.get("user_id"); t.assigned_to_id=uid; t.save(update_fields=["assigned_to","updated_at"]); notify(t.assigned_to,t,"TICKET_ASSIGNED","New ticket assigned",f"{t.number} has been assigned to you."); return Response(TicketSerializer(t).data)

class SimpleTenantViewSet(TenantMixin, viewsets.ModelViewSet):
    permission_classes=[IsAgentOrAdmin]
class DepartmentViewSet(SimpleTenantViewSet): queryset=Department.objects.all(); serializer_class=DepartmentSerializer
class CategoryViewSet(SimpleTenantViewSet): queryset=Category.objects.all(); serializer_class=CategorySerializer
class CustomerViewSet(SimpleTenantViewSet): queryset=Customer.objects.all(); serializer_class=CustomerSerializer
class NotificationViewSet(SimpleTenantViewSet):
    queryset=Notification.objects.all(); serializer_class=NotificationSerializer; http_method_names=["get","patch","head","options"]
    def get_queryset(self): return Notification.objects.filter(organization=self.org(),user=self.request.user) if self.org() else Notification.objects.none()
    @action(detail=True,methods=["post"])
    def read(self,request,pk=None): n=self.get_object(); n.is_read=True; n.save(update_fields=["is_read"]); return Response({"ok":True})
