from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (register_customer, register_driver, 
                    CustomerProfileViewSet, DriverProfileViewSet, verify_email)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

router = DefaultRouter()
router.register(r'customers', CustomerProfileViewSet)
router.register(r'drivers', DriverProfileViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('register/customer/', register_customer, name='register_customer'),
    path('register/driver/', register_driver, name='register_driver'),
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('verify/<uuid:token>/', verify_email, name='verify_email'),
]
