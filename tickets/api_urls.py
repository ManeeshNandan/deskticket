from django.urls import include,path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .api import TicketViewSet,DepartmentViewSet,CategoryViewSet,CustomerViewSet,NotificationViewSet
router=DefaultRouter(); router.register("tickets",TicketViewSet,basename="ticket"); router.register("departments",DepartmentViewSet); router.register("categories",CategoryViewSet); router.register("customers",CustomerViewSet); router.register("notifications",NotificationViewSet)
urlpatterns=[path("",include(router.urls)),path("token/",TokenObtainPairView.as_view(),name="token"),path("token/refresh/",TokenRefreshView.as_view(),name="token_refresh")]
