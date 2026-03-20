# notifications/tests.py (Updated)
from django.test import TestCase
from django.core import mail
from celery.result import AsyncResult
from .views import send_order_confirmation_email
from orders.models import Order, FuelType
from users.models import User, CustomerProfile
from decimal import Decimal

class NotificationsTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='notifuser', email='notif@example.com', password='pass', role='customer', phone='+234999999999')
        customer = CustomerProfile.objects.create(user=user, address='Notif Address')
        fuel = FuelType.objects.create(name='petrol', price_per_liter=Decimal('650.00'))
        self.order = Order(
            customer=customer, fuel_type=fuel, quantity_liters=Decimal('10.00'),
            delivery_latitude=Decimal('6.5244'), delivery_longitude=Decimal('3.3792'), delivery_address='Test'
        )
        self.order.calculate_distance(Decimal('6.5244'), Decimal('3.3792'))  # Required
        self.order.calculate_delivery_fee()
        self.order.calculate_total_price()
        self.order.order_number = 'ORD-TEST123'
        self.order.save()

    # def test_send_order_confirmation_email(self):
    #     with self.settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):  # Mock for tests
    #         task = send_order_confirmation_email.delay(self.order.id)
    #         self.assertIsInstance(task, AsyncResult)
    #         self.assertEqual(len(mail.outbox), 1)
    #         self.assertIn('Order Confirmation #ORD-TEST123', mail.outbox[0].subject)
    #         self.assertIn(f'₦{self.order.total_price:.2f}', mail.outbox[0].body)  # NGN for Lagos