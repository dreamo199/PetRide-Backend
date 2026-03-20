from django.contrib import admin
from django.urls import path, include
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

schema_view = get_schema_view(
   openapi.Info(
      title="PetRide API",
      default_version='v1',
      description="API documentation for PetRide",
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0)),
    path('api/v1/', include('users.urls')),
    path('api/v1/orders/', include('orders.urls')),
    path('api/v1/analytics/', include('analytics.urls')),
]
