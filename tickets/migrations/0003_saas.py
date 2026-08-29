from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_legacy_org(apps, schema_editor):
    Organization=apps.get_model("tickets","Organization")
    Membership=apps.get_model("tickets","Membership")
    User=apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    org=Organization.objects.order_by("id").first()
    if not org:
        org=Organization.objects.create(name="Default Workspace",slug="default-workspace",email="")
    user=User.objects.order_by("id").first()
    if user and not Membership.objects.filter(organization=org,user=user).exists():
        Membership.objects.create(organization=org,user=user,role="OWNER")
    for model_name in ["Department","Category","EmailAccount","Ticket"]:
        Model=apps.get_model("tickets",model_name)
        if "organization" in [f.name for f in Model._meta.fields]:
            Model.objects.filter(organization__isnull=True).update(organization=org)
    Department=apps.get_model("tickets","Department")
    SLAPolicy=apps.get_model("tickets","SLAPolicy")
    if not Department.objects.filter(organization=org).exists():
        Department.objects.create(organization=org,name="IT Support",code="IT")
        Department.objects.create(organization=org,name="General",code="GEN")
    if not SLAPolicy.objects.filter(organization=org).exists():
        for priority,fr,res in [("URGENT",15,240),("HIGH",30,480),("MEDIUM",120,2880),("LOW",240,7200)]:
            SLAPolicy.objects.create(organization=org,name=f"{priority.title()} SLA",priority=priority,first_response_minutes=fr,resolution_minutes=res)

def reverse_legacy_org(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies=[("tickets","0002_ticketmessage_body_html")]
    operations=[
        migrations.CreateModel(name="Organization",fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("name",models.CharField(max_length=150)),("slug",models.SlugField(unique=True)),("email",models.EmailField(blank=True,max_length=254)),("logo",models.FileField(blank=True,null=True,upload_to="organizations/")),("is_active",models.BooleanField(default=True)),("timezone",models.CharField(default="Asia/Kolkata",max_length=64)),("created_at",models.DateTimeField(auto_now_add=True))]),
        migrations.CreateModel(name="SLAPolicy",fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("name",models.CharField(max_length=100)),("priority",models.CharField(max_length=10)),("first_response_minutes",models.PositiveIntegerField(default=120)),("resolution_minutes",models.PositiveIntegerField(default=2880)),("warning_percent",models.PositiveIntegerField(default=80)),("is_active",models.BooleanField(default=True)),("organization",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="sla_policies",to="tickets.organization"))]),
        migrations.CreateModel(name="Membership",fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("role",models.CharField(choices=[("OWNER","Owner"),("ADMIN","Admin"),("MANAGER","Manager"),("AGENT","Agent"),("CUSTOMER","Customer")],default="AGENT",max_length=20)),("is_active",models.BooleanField(default=True)),("joined_at",models.DateTimeField(auto_now_add=True)),("organization",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="memberships",to="tickets.organization")),("user",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="memberships",to=settings.AUTH_USER_MODEL))],options={"constraints":[models.UniqueConstraint(fields=["organization","user"],name="uniq_org_user")]}),
        migrations.CreateModel(name="Customer",fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("name",models.CharField(max_length=150)),("email",models.EmailField(max_length=254)),("phone",models.CharField(blank=True,max_length=50)),("company",models.CharField(blank=True,max_length=150)),("notes",models.TextField(blank=True)),("created_at",models.DateTimeField(auto_now_add=True)),("organization",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="customers",to="tickets.organization")),("user",models.OneToOneField(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="customer_profile",to=settings.AUTH_USER_MODEL))],options={"constraints":[models.UniqueConstraint(fields=["organization","email"],name="uniq_customer_email_org")]}),
        migrations.AddField(model_name="department",name="organization",field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.CASCADE,related_name="departments",to="tickets.organization")),
        migrations.AlterField(model_name="department",name="name",field=models.CharField(max_length=100)),
        migrations.AlterField(model_name="department",name="code",field=models.CharField(max_length=30)),
        migrations.AddField(model_name="category",name="organization",field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.CASCADE,related_name="categories",to="tickets.organization")),
        migrations.AddField(model_name="emailaccount",name="organization",field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.CASCADE,related_name="email_accounts",to="tickets.organization")),
        migrations.AlterField(model_name="emailaccount",name="email",field=models.EmailField(max_length=254)),
        migrations.AddField(model_name="ticket",name="organization",field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.CASCADE,related_name="tickets",to="tickets.organization")),
        migrations.AddField(model_name="ticket",name="customer",field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="tickets",to="tickets.customer")),
        migrations.AddField(model_name="ticket",name="sla_policy",field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="tickets",to="tickets.slapolicy")),
        migrations.AddField(model_name="ticket",name="first_response_at",field=models.DateTimeField(blank=True,null=True)),
        migrations.AddField(model_name="ticket",name="sla_first_response_due",field=models.DateTimeField(blank=True,null=True)),
        migrations.AddField(model_name="ticket",name="sla_resolution_due",field=models.DateTimeField(blank=True,null=True)),
        migrations.AddField(model_name="ticket",name="sla_first_breached",field=models.BooleanField(default=False)),
        migrations.AddField(model_name="ticket",name="sla_resolution_breached",field=models.BooleanField(default=False)),
        migrations.AlterField(model_name="ticketmessage",name="message_id",field=models.CharField(blank=True,max_length=998,null=True,unique=True)),
        migrations.CreateModel(name="Notification",fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("notification_type",models.CharField(max_length=50)),("title",models.CharField(max_length=255)),("message",models.TextField()),("is_read",models.BooleanField(default=False)),("created_at",models.DateTimeField(auto_now_add=True)),("organization",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.CASCADE,related_name="notifications",to="tickets.organization")),("ticket",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.CASCADE,related_name="notifications",to="tickets.ticket")),("user",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="notifications",to=settings.AUTH_USER_MODEL))],options={"ordering":["-created_at"]}),
        migrations.CreateModel(name="AuditLog",fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("action",models.CharField(max_length=100)),("model_name",models.CharField(max_length=100)),("object_id",models.CharField(max_length=100)),("details",models.JSONField(blank=True,default=dict)),("ip_address",models.GenericIPAddressField(blank=True,null=True)),("created_at",models.DateTimeField(auto_now_add=True)),("organization",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.CASCADE,related_name="audit_logs",to="tickets.organization")),("user",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,to=settings.AUTH_USER_MODEL))],options={"ordering":["-created_at"]}),
        migrations.AddIndex(model_name="ticket",index=models.Index(fields=["organization","status","-created_at"],name="tickets_tic_organiza_idx")),
        migrations.AddConstraint(model_name="department",constraint=models.UniqueConstraint(fields=["organization","code"],name="uniq_department_code_org")),
        migrations.AlterUniqueTogether(name="category",unique_together=set()),
        migrations.AddConstraint(model_name="category",constraint=models.UniqueConstraint(fields=["department","name"],name="uniq_category_department_name")),
        migrations.AddConstraint(model_name="emailaccount",constraint=models.UniqueConstraint(fields=["organization","email"],name="uniq_mailbox_org_email")),
        migrations.AlterField(model_name="ticket",name="source",field=models.CharField(choices=[("EMAIL","Email"),("PORTAL","Portal"),("MANUAL","Manual"),("API","API")],default="MANUAL",max_length=20)),
        migrations.RemoveIndex(model_name="ticket",name="tickets_tic_status_15eec8_idx"),
        migrations.RunPython(seed_legacy_org, reverse_legacy_org),
    ]
