# orders/tests.py (Updated)
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from decimal import Decimal
import requests_mock
from .models import FuelType, Order
from .serializers import OrderCreateSerializer
from users.models import User, CustomerProfile, DriverProfile
from django.conf import settings

class FuelTypeModelTest(TestCase):
    def setUp(self):
        self.fuel = FuelType.objects.create(name='petrol', price_per_liter=Decimal('650.00'), is_available=True)

    def test_fuel_str(self):
        self.assertEqual(str(self.fuel), 'petrol')

class OrderModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='orduser', email='ord@example.com', password='pass', role='customer', phone='+234555555555')
        self.customer = CustomerProfile.objects.create(user=self.user, address='Lagos Address')
        self.fuel = FuelType.objects.create(name='petrol', price_per_liter=Decimal('650.00'))
        self.order = Order(
            customer=self.customer, fuel_type=self.fuel, quantity_liters=Decimal('10.00'),
            delivery_latitude=Decimal('6.5244'), delivery_longitude=Decimal('3.3792'),
            delivery_address='Lagos Test'
        )
        self.order.calculate_distance(settings.DEPOT_LAT, settings.DEPOT_LNG)
        self.order.calculate_delivery_fee()
        self.order.calculate_total_price()
        self.order.save()

    def test_calculate_distance(self):
        distance = self.order.calculate_distance(Decimal('6.5244'), Decimal('3.3792'))
        self.assertEqual(distance, Decimal('0.00'))

    def test_calculate_total_price(self):
        expected_fuel = self.fuel.price_per_liter * self.order.quantity_liters
        expected_charge = expected_fuel * Decimal('0.05') if expected_fuel <= 29999 else expected_fuel * Decimal('0.1')
        expected_total = expected_fuel + self.order.delivery_fee + expected_charge
        self.assertEqual(self.order.total_price, expected_total)

# class OrderSerializerTest(TestCase):
#     def test_geocode_fallback(self):
#         with requests_mock.Mocker() as m:
#             m.get(requests_mock.ANY, json={
#                 'status': 'OK',
#                 'results': [{'geometry': {'location': {'lat': 6.5244, 'lng': 3.3792}}}]
#             })
#             serializer = OrderCreateSerializer()  # Instance is fine, method is on class
#             lat, lng = serializer._geocode_address('Test Lagos Address')
#             self.assertEqual(lat, Decimal('6.5244'))
#             self.assertEqual(lng, Decimal('3.3792'))

class OrderViewsTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='viewuser', email='view@example.com', password='viewpass', role='customer', phone='+234666666666')
        self.driver_user = User.objects.create_user(username='driver', email='driver@example.com', password='pass1234', role='driver', phone='+234777777777')
        self.driver = DriverProfile.objects.create(user=self.driver_user, vehicle_type='Car Model', vehicle_number='XYZ 1234', vehicle_capacity=Decimal('50.00'))
        self.customer = CustomerProfile.objects.create(user=self.user, address='View Address')
        self.fuel = FuelType.objects.create(name='petrol', price_per_liter=Decimal('650.00'))
        self.client.force_authenticate(user=self.user)

    def test_create_order(self):
        url = reverse('order-list')
        data = {
            'fuel_type': self.fuel.id, 'quantity_liters': 10.00, 'delivery_address': 'View Lagos',
            'delivery_latitude': 6.5244, 'delivery_longitude': 3.3792,
            'scheduled_time': '2026-01-25T10:00:00Z'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Order.objects.exists())

    def test_driver_update_status_flow(self):
        order = Order.objects.create(
            customer=self.customer,
            fuel_type=self.fuel,
            quantity_liters=20,
            status="assigned",
            driver=self.driver,
            fuel_price=self.fuel
    )

        self.client.logout()
        self.client.login(username="driver", password="pass1234")
        url = reverse("orders-update-status", args=[order.id])

        response = self.client.post(url, {"status": "in_transit"})
        self.assertEqual(response.status_code, 200)