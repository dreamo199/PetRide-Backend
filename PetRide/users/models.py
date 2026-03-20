from django.contrib.auth.models import AbstractUser
from django.db import models
from decimal import Decimal
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid

PHONE_REGEX = RegexValidator(regex=r'^\+?1?\d{9,15}$',message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")

class User(AbstractUser):
    USER_TYPE_CHOICES = [
        ('customer', 'Customer'),
        ('driver', 'Driver'),
        ('admin', 'Admin'),
    ]
    
    role = models.CharField(max_length=20, choices=USER_TYPE_CHOICES)
    phone = models.CharField(validators=[PHONE_REGEX], max_length=15, unique=True)
    email = models.EmailField(unique=True, db_index=True)
    is_verified = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['role', 'is_active']),
            models.Index(fields=['email']),
            models.Index(fields=['username']),
            models.Index(fields=['is_deleted']),
        ]
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    def soft_delete(self):
        self.is_deleted = True
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save()

    def get_email(self):
        return self.email
    def get_phone(self):
        return self.phone


class CustomerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    customer_id = models.CharField(unique=True, db_index=True, max_length=20, null=True, blank=True)
    address = models.TextField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, validators=[MinValueValidator(Decimal('-90')), MaxValueValidator((Decimal('90')))])
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, validators=[MinValueValidator(Decimal('-180')), MaxValueValidator((Decimal('180')))])
    preferred_payment_method = models.CharField(max_length=20, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'customer_profiles'
    
    def __str__(self):
        return f"Customer: {self.user.username} - Customer ID: {self.customer_id}"

    def generate_customer_id(self):
        return f'PC-{uuid.uuid4().hex[:8].upper()}'

    def save(self, *args, **kwargs):
        if not self.customer_id:
            self.customer_id = self.generate_customer_id()
        super().save(*args, **kwargs)


class DriverProfile(models.Model):
    APPROVAL_STATUS_CHOICE = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('suspended', 'Suspended'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='driver_profile')
    driver_id = models.CharField(unique=True, db_index=True, max_length=20, null=True, blank=True)
    license_number = models.CharField(max_length=50, unique=True)
    vehicle_number = models.CharField(max_length=20)
    vehicle_type = models.CharField(max_length=50)
    vehicle_capacity = models.DecimalField(max_digits=8, decimal_places=2)
    approval_status = models.CharField(choices=APPROVAL_STATUS_CHOICE, max_length=20, default='pending')
    is_available = models.BooleanField(default=True)
    current_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, validators=[MinValueValidator(Decimal('-90')), MaxValueValidator((Decimal('90')))])
    current_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, validators=[MinValueValidator(Decimal('-180')), MaxValueValidator((Decimal('180')))])
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00, validators= [MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('5.00'))])
    total_deliveries = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'driver_profiles'
        indexes = [
            models.Index(fields=['is_available', 'approval_status']),
            models.Index(fields=['current_latitude', 'current_longitude']),
            models.Index(fields=['rating'])
        ]

    def __str__(self):
        return f"Driver: {self.user.first_name} - {self.vehicle_number}"
    
    @property
    def is_active_driver(self):
        return self.approval_status == 'approved' and self.is_available

    def generate_driver_id(self):
        return f'PD-{uuid.uuid4().hex[:8].upper()}'

    def save(self, *args, **kwargs):
        if not self.driver_id:
            self.driver_id = self.generate_driver_id()
        super().save(*args, **kwargs)

class VerificationToken(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)