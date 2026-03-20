from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from users.models import User, CustomerProfile, DriverProfile
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class FuelType(models.Model):
    FUEL_CHOICES = [
        ('petrol', 'Petrol'),
        ('diesel', 'Diesel'),
    ]
    name = models.CharField(max_length=20, unique=True, choices=FUEL_CHOICES)
    price_per_liter = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    description = models.TextField(blank=True)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'fuel_types'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.get_name_display()} - ₦{self.price_per_liter}/L"


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('assigned', 'Driver Assigned'),
        ('in_transit', 'In Transit'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    CANCELLATION_REASONS = [
        ('customer_request', 'Cancelled by Customer'),
        ('driver', 'Cancelled by Driver'),
        ('driver_unavailable', 'Driver Unavailable'),
        ('payment', 'Payment Failed'),
        ('admin_action', 'Cancelled by admin'),
        ('other', 'Other'),
    ]
    
    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name='orders')
    driver = models.ForeignKey(DriverProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='deliveries')
    fuel_type = models.ForeignKey(FuelType, on_delete=models.PROTECT)
    order_number = models.CharField(max_length=20, unique=True, db_index=True)
    quantity_liters = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(Decimal('1.00')), MaxValueValidator(Decimal('50.00'))])
    fuel_price = models.DecimalField(max_digits=12, decimal_places=2, help_text="Total fuel cost (quantity * price per liter)")
    delivery_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    service_charge = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Final total price")
    delivery_address = models.TextField()
    delivery_latitude = models.DecimalField(max_digits=16, decimal_places=15, validators=[MinValueValidator(Decimal('-90')), MaxValueValidator(Decimal('90'))])
    delivery_longitude = models.DecimalField(max_digits=16, decimal_places=15, validators=[MinValueValidator(Decimal('-180')), MaxValueValidator(Decimal('180'))])
    distance_km = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal('0.00'))])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    cancellation_reason = models.CharField(max_length=20, choices=CANCELLATION_REASONS, null=True, blank=True)
    scheduled_time = models.DateTimeField(null=True, blank=True)
    assigned_at = models.DateTimeField(blank=True, null=True)
    in_transit_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)
    cancellation_notes = models.TextField(blank=True)
    customer_rating = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    customer_feedback = models.TextField(blank=True)
    rated_at = models.DateTimeField(null=True, blank=True)
    driver_rejections_count = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'orders'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['driver', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['order_number']),
        ]

    def __str__(self):
        return f"Order {self.order_number} - {self.customer.user.username} ({self.get_status_display()})"
    
    def generate_order_number(self):
        import uuid
        return f'ORD-{uuid.uuid4().hex[:8].upper()}'
    
    def can_be_cancelled(self):
        return self.status in ['pending', 'assigned']

    def soft_delete(self):
        if self.cancellation_reason in ['customer', 'admin']:
            return self.status == 'cancelled'
        elif self.cancellation_reason in ['driver']:
            return  self.status == 'pending'
        return None

    def can_be_rated(self):
        return self.customer_rating is None and self.status == 'completed'
    
    def is_active(self):
        return self.status in ['pending', 'assigned', 'in_transit']
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)

class OrderStatusHistory(models.Model):
    order = models.ForeignKey( Order, on_delete=models.CASCADE, related_name='status_history')
    old_status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES)
    new_status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'order_status_history'
        ordering = ['-created_at']
        verbose_name_plural = 'Order status histories'
    
    def __str__(self):
        return f"{self.order.order_number}: {self.old_status} → {self.new_status}"

class DriverRejection(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='driver_rejections')
    driver = models.ForeignKey(DriverProfile, on_delete=models.CASCADE)
    reason = models.TextField(blank=True, max_length=500)
    rejected_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'driver_rejections'
        unique_together = [['order', 'driver']]
        ordering = ['-rejected_at']
    
    def __str__(self):
        return f"{self.driver.user.username} rejected {self.order.order_number}"