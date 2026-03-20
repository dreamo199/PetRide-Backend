# analytics/tests.py (Updated)
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from orders.models import Order, FuelType
from users.models import User, CustomerProfile, DriverProfile
from decimal import Decimal
from datetime import datetime, timedelta  # Fixed import

class AnalyticsViewsTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.cust_user = User.objects.create_user(username='anacust', email='anacust@example.com', password='anapass', role='customer', phone='+234777777777')
        self.customer = CustomerProfile.objects.create(user=self.cust_user, address='Ana Address')
        self.driver_user = User.objects.create_user(username='anadriver', email='anadriver@example.com', password='anapass', role='driver', phone='+234888888888')
        self.driver = DriverProfile.objects.create(user=self.driver_user, license_number='ANALIC', vehicle_number='ANAVEH', vehicle_type='Truck', vehicle_capacity=1000)
        self.fuel = FuelType.objects.create(name='petrol', price_per_liter=Decimal('650.00'))
        self.order = Order(
            customer=self.customer, driver=self.driver, fuel_type=self.fuel, quantity_liters=Decimal('10.00'),
            delivery_latitude=Decimal('6.5244'), delivery_longitude=Decimal('3.3792'), delivery_address='Test'
        )
        self.order.calculate_distance(Decimal('6.5244'), Decimal('3.3792'))  # Required for price calcs
        self.order.calculate_delivery_fee()
        self.order.calculate_total_price()
        self.order.status = 'completed'
        self.order.created_at = datetime.now() - timedelta(days=1)
        self.order.save()

    def test_customer_analytics(self):
        self.client.force_authenticate(user=self.cust_user)
        url = reverse('customer_analytics')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_orders'], 1)
        self.assertEqual(response.data['total_spent'], float(self.order.total_price))

    def test_driver_analytics(self):
        self.client.force_authenticate(user=self.driver_user)
        url = reverse('driver_analytics')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_deliveries'], 1)

    def test_business_analytics(self):
        admin_user = User.objects.create_superuser(username='admin', email='admin@example.com', password='adminpass')
        self.client.force_authenticate(user=admin_user)
        url = reverse('business_analytics')
        response = self.client.get(url + '?days=7')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_revenue'], float(self.order.total_price))