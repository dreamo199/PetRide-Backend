from django.urls import path
from .views import customer_analytics, driver_analytics, business_analytics, real_time_dashboard

urlpatterns = [
    path('customer/', customer_analytics, name='customer_analytics'),
    path('driver/', driver_analytics, name='driver_analytics'),
    path('business/', business_analytics, name='business_analytics'),
    path('dashboard/', real_time_dashboard, name='real_time_dashboard'),
]