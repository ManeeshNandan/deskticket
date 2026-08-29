from django.urls import path
from . import views
app_name="tickets"
urlpatterns=[
 path("",views.landing,name="landing"), path("signup/",views.signup,name="signup"), path("dashboard/",views.dashboard,name="dashboard"),
 path("tickets/",views.ticket_list,name="list"), path("tickets/create/",views.ticket_create,name="create"), path("tickets/<int:pk>/",views.ticket_detail,name="detail"), path("tickets/<int:pk>/update/",views.ticket_update,name="update"), path("tickets/<int:pk>/comment/",views.add_comment,name="comment"), path("tickets/<int:pk>/attachment/",views.add_attachment,name="attachment"), path("tickets/<int:pk>/reply/",views.ticket_reply,name="reply"),
 path("my-tickets/",views.customer_portal,name="customer_portal"), path("my-tickets/create/",views.customer_create_ticket,name="customer_create"), path("my-tickets/<int:pk>/",views.customer_ticket_detail,name="customer_detail"), path("my-tickets/<int:pk>/reply/",views.customer_reply,name="customer_reply"),
 path("notifications/",views.notifications,name="notifications"), path("notifications/<int:pk>/read/",views.notification_read,name="notification_read"),
 path("mailboxes/",views.mailbox_list,name="mailboxes"), path("mailboxes/create/",views.mailbox_create,name="mailbox_create"), path("mailboxes/<int:pk>/edit/",views.mailbox_edit,name="mailbox_edit"), path("mailboxes/<int:pk>/test/",views.mailbox_test,name="mailbox_test"), path("mailboxes/<int:pk>/sync/",views.mailbox_sync,name="mailbox_sync"),
 path("reports/",views.reports,name="reports"), path("reports/export/",views.report_csv,name="report_csv"), path("settings/",views.settings_home,name="settings"), path("settings/team/",views.members,name="members"), path("settings/customers/",views.customers,name="customers"), path("settings/departments/",views.departments,name="departments"), path("settings/sla/",views.sla_policies,name="sla"),
 
path(
    "settings/categories/",
    views.category_list,
    name="categories",
),

path(
    "settings/categories/create/",
    views.category_create,
    name="category_create",
),

path(
    "settings/categories/<int:pk>/edit/",
    views.category_edit,
    name="category_edit",
),

path(
    "settings/categories/<int:pk>/delete/",
    views.category_delete,
    name="category_delete",
),
]
