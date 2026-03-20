from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FuelTypeViewSet, OrderViewSet

router = DefaultRouter()
router.register(r'fuel-types', FuelTypeViewSet)
router.register(r'orders', OrderViewSet)

urlpatterns = [
    path('', include(router.urls)),
]