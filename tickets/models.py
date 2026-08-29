from django.conf import settings
from django.db import models
from django.utils import timezone
from datetime import timedelta

class Organization(models.Model):
    name=models.CharField(max_length=150); slug=models.SlugField(unique=True); email=models.EmailField(blank=True); logo=models.FileField(upload_to="organizations/",blank=True,null=True)
    is_active=models.BooleanField(default=True); timezone=models.CharField(max_length=64,default="Asia/Kolkata"); created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.name

class Membership(models.Model):
    class Role(models.TextChoices): OWNER="OWNER","Owner"; ADMIN="ADMIN","Admin"; MANAGER="MANAGER","Manager"; AGENT="AGENT","Agent"; CUSTOMER="CUSTOMER","Customer"
    organization=models.ForeignKey(Organization,on_delete=models.CASCADE,related_name="memberships")
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="memberships")
    role=models.CharField(max_length=20,choices=Role.choices,default=Role.AGENT); is_active=models.BooleanField(default=True); joined_at=models.DateTimeField(auto_now_add=True)
    class Meta: constraints=[models.UniqueConstraint(fields=["organization","user"],name="uniq_org_user")]
    def __str__(self): return f"{self.organization} / {self.user} / {self.role}"

class Customer(models.Model):
    organization=models.ForeignKey(Organization,on_delete=models.CASCADE,related_name="customers")
    name=models.CharField(max_length=150); email=models.EmailField(); phone=models.CharField(max_length=50,blank=True); company=models.CharField(max_length=150,blank=True); notes=models.TextField(blank=True); user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name="customer_profile")
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: constraints=[models.UniqueConstraint(fields=["organization","email"],name="uniq_customer_email_org")]
    def __str__(self): return f"{self.name} <{self.email}>"

class Department(models.Model):
    organization=models.ForeignKey(Organization,on_delete=models.CASCADE,related_name="departments",null=True,blank=True)
    name=models.CharField(max_length=100); code=models.CharField(max_length=30); is_active=models.BooleanField(default=True)
    class Meta: constraints=[models.UniqueConstraint(fields=["organization","code"],name="uniq_department_code_org")]
    def __str__(self): return self.name

class Category(models.Model):
    organization=models.ForeignKey(Organization,on_delete=models.CASCADE,related_name="categories",null=True,blank=True)
    department=models.ForeignKey(Department,on_delete=models.CASCADE,related_name="categories"); name=models.CharField(max_length=100); is_active=models.BooleanField(default=True)
    class Meta: constraints=[models.UniqueConstraint(fields=["department","name"],name="uniq_category_department_name")]
    def __str__(self): return f"{self.department.code} - {self.name}"

class EmailAccount(models.Model):
    class Provider(models.TextChoices): GMAIL="GMAIL","Gmail"; OUTLOOK="OUTLOOK","Outlook / Microsoft 365"; YAHOO="YAHOO","Yahoo"; CUSTOM="CUSTOM","Custom"
    class AuthMethod(models.TextChoices): PASSWORD="PASSWORD","Password / App Password"; OAUTH2="OAUTH2","OAuth2"
    organization=models.ForeignKey(Organization,on_delete=models.CASCADE,related_name="email_accounts",null=True,blank=True)
    email=models.EmailField(); display_name=models.CharField(max_length=150,blank=True); provider=models.CharField(max_length=20,choices=Provider.choices); imap_host=models.CharField(max_length=255); imap_port=models.PositiveIntegerField(default=993); imap_ssl=models.BooleanField(default=True); username=models.CharField(max_length=255); auth_method=models.CharField(max_length=20,choices=AuthMethod.choices,default=AuthMethod.PASSWORD); secret_encrypted=models.TextField(blank=True); oauth_refresh_token_encrypted=models.TextField(blank=True); oauth_client_id_encrypted=models.TextField(blank=True); oauth_client_secret_encrypted=models.TextField(blank=True); folder=models.CharField(max_length=255,default="INBOX"); poll_enabled=models.BooleanField(default=True); mark_as_seen=models.BooleanField(default=True); create_ticket_from_replies=models.BooleanField(default=True); last_uid=models.BigIntegerField(default=0); last_checked_at=models.DateTimeField(null=True,blank=True); last_error=models.TextField(blank=True); created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
    class Meta: constraints=[models.UniqueConstraint(fields=["organization","email"],name="uniq_mailbox_org_email")]
    def __str__(self): return f"{self.email} ({self.get_provider_display()})"

class SLAPolicy(models.Model):
    organization=models.ForeignKey(Organization,on_delete=models.CASCADE,related_name="sla_policies")
    name=models.CharField(max_length=100); priority=models.CharField(max_length=10); first_response_minutes=models.PositiveIntegerField(default=120); resolution_minutes=models.PositiveIntegerField(default=2880); warning_percent=models.PositiveIntegerField(default=80); is_active=models.BooleanField(default=True)
    def __str__(self): return self.name

class Ticket(models.Model):
    class Status(models.TextChoices): OPEN="OPEN","Open"; IN_PROGRESS="IN_PROGRESS","In Progress"; ON_HOLD="ON_HOLD","On Hold"; RESOLVED="RESOLVED","Resolved"; CLOSED="CLOSED","Closed"
    class Priority(models.TextChoices): LOW="LOW","Low"; MEDIUM="MEDIUM","Medium"; HIGH="HIGH","High"; URGENT="URGENT","Urgent"
    organization=models.ForeignKey(Organization,on_delete=models.CASCADE,related_name="tickets",null=True,blank=True)
    customer=models.ForeignKey(Customer,on_delete=models.SET_NULL,null=True,blank=True,related_name="tickets")
    number=models.CharField(max_length=30,unique=True,editable=False); subject=models.CharField(max_length=255); description=models.TextField(); requester_name=models.CharField(max_length=150,blank=True); requester_email=models.EmailField(); source=models.CharField(max_length=20,choices=[("EMAIL","Email"),("PORTAL","Portal"),("MANUAL","Manual"),("API","API")],default="MANUAL"); email_account=models.ForeignKey(EmailAccount,null=True,blank=True,on_delete=models.SET_NULL,related_name="tickets"); message_id=models.CharField(max_length=998,blank=True,null=True,unique=True); thread_key=models.CharField(max_length=998,blank=True,db_index=True); status=models.CharField(max_length=20,choices=Status.choices,default=Status.OPEN); priority=models.CharField(max_length=10,choices=Priority.choices,default=Priority.MEDIUM); department=models.ForeignKey(Department,null=True,blank=True,on_delete=models.SET_NULL,related_name="tickets"); category=models.ForeignKey(Category,null=True,blank=True,on_delete=models.SET_NULL,related_name="tickets"); assigned_to=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="assigned_tickets"); created_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="created_tickets"); sla_policy=models.ForeignKey(SLAPolicy,null=True,blank=True,on_delete=models.SET_NULL,related_name="tickets"); first_response_at=models.DateTimeField(null=True,blank=True); sla_first_response_due=models.DateTimeField(null=True,blank=True); sla_resolution_due=models.DateTimeField(null=True,blank=True); sla_first_breached=models.BooleanField(default=False); sla_resolution_breached=models.BooleanField(default=False); created_at=models.DateTimeField(default=timezone.now); updated_at=models.DateTimeField(auto_now=True); resolved_at=models.DateTimeField(null=True,blank=True); closed_at=models.DateTimeField(null=True,blank=True)
    class Meta: ordering=["-created_at"]; indexes=[models.Index(fields=["organization","status","-created_at"]),models.Index(fields=["thread_key"])]
    def save(self,*args,**kwargs):
        if not self.number:
            last=Ticket.objects.order_by("-id").first(); self.number=f"TKT-{((last.id+1) if last else 1):06d}"
        if self.status==self.Status.RESOLVED and not self.resolved_at: self.resolved_at=timezone.now()
        if self.status==self.Status.CLOSED and not self.closed_at: self.closed_at=timezone.now()
        if self.sla_policy and self.created_at and not self.sla_resolution_due: self.sla_resolution_due=self.created_at+timedelta(minutes=self.sla_policy.resolution_minutes)
        if self.sla_policy and self.created_at and not self.sla_first_response_due: self.sla_first_response_due=self.created_at+timedelta(minutes=self.sla_policy.first_response_minutes)
        super().save(*args,**kwargs)
    def __str__(self): return f"{self.number} - {self.subject}"

class TicketMessage(models.Model):
    ticket=models.ForeignKey(Ticket,on_delete=models.CASCADE,related_name="messages"); direction=models.CharField(max_length=10,choices=[("IN","Incoming"),("OUT","Outgoing")]); sender=models.EmailField(); recipients=models.TextField(blank=True); subject=models.CharField(max_length=255,blank=True); body=models.TextField(blank=True); message_id=models.CharField(max_length=998,blank=True,null=True,unique=True); in_reply_to=models.CharField(max_length=998,blank=True); references=models.TextField(blank=True); received_at=models.DateTimeField(default=timezone.now); body_html=models.TextField(blank=True,default="")
    class Meta: ordering=["received_at"]

class TicketComment(models.Model):
    ticket=models.ForeignKey(Ticket,on_delete=models.CASCADE,related_name="comments"); author=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL); comment=models.TextField(); is_internal=models.BooleanField(default=True); created_at=models.DateTimeField(default=timezone.now)
    class Meta: ordering=["created_at"]

class TicketAttachment(models.Model):
    ticket=models.ForeignKey(Ticket,on_delete=models.CASCADE,related_name="attachments"); message=models.ForeignKey(TicketMessage,null=True,blank=True,on_delete=models.SET_NULL,related_name="attachments"); file=models.FileField(upload_to="ticket_attachments/%Y/%m/"); original_name=models.CharField(max_length=255); created_at=models.DateTimeField(default=timezone.now)

class TicketHistory(models.Model):
    ticket=models.ForeignKey(Ticket,on_delete=models.CASCADE,related_name="history"); user=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL); action=models.CharField(max_length=100); old_value=models.TextField(blank=True); new_value=models.TextField(blank=True); created_at=models.DateTimeField(default=timezone.now)
    class Meta: ordering=["-created_at"]

class Notification(models.Model):
    organization=models.ForeignKey(Organization,on_delete=models.CASCADE,related_name="notifications",null=True,blank=True); user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="notifications"); ticket=models.ForeignKey(Ticket,null=True,blank=True,on_delete=models.CASCADE,related_name="notifications"); notification_type=models.CharField(max_length=50); title=models.CharField(max_length=255); message=models.TextField(); is_read=models.BooleanField(default=False); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=["-created_at"]

class AuditLog(models.Model):
    organization=models.ForeignKey(Organization,on_delete=models.CASCADE,related_name="audit_logs",null=True,blank=True); user=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL); action=models.CharField(max_length=100); model_name=models.CharField(max_length=100); object_id=models.CharField(max_length=100); details=models.JSONField(default=dict,blank=True); ip_address=models.GenericIPAddressField(null=True,blank=True); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=["-created_at"]
