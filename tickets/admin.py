from django.contrib import admin
from .models import *
for model in [Organization,Membership,Customer,Department,Category,EmailAccount,SLAPolicy,Ticket,TicketMessage,TicketComment,TicketAttachment,TicketHistory,Notification,AuditLog]:
    admin.site.register(model)
