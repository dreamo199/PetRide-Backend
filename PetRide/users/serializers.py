from rest_framework import serializers
from .models import User, CustomerProfile, DriverProfile, VerificationToken
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.contrib.auth.password_validation import validate_password
import logging

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone', 'first_name', 'last_name', 
                  'role', 'is_verified', 'created_at']
        read_only_fields = ['id', 'created_at', 'role']


class CustomerProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    first_name = serializers.CharField(source='user.first_name', required=False)
    last_name = serializers.CharField(source='user.last_name', required=False)
    email = serializers.EmailField(source='user.email', required=False)
    phone = serializers.CharField(source='user.phone', required=False)
    
    class Meta:
        model = CustomerProfile
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'customer_id']
 
    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", None)

        if user_data: 
            for attr, value in user_data.items():
                setattr(instance.user, attr, value)
            instance.user.save()

        return super().update(instance, validated_data)


class DriverProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    first_name = serializers.CharField(source='user.first_name', required=False)
    last_name = serializers.CharField(source='user.last_name', required=False)
    email = serializers.EmailField(source='user.email', required=False)
    phone = serializers.CharField(source='user.phone', required=False)
    
    class Meta:
        model = DriverProfile
        fields = '__all__'
        read_only_fields = ['id', 'rating', 'is_available', 'approval_status', 'created_at', 'updated_at', 'driver_id']

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", None)

        if user_data:
            for attr, value in user_data.items():
                setattr(instance.user, attr, value)
            instance.user.save()

        return super().update(instance, validated_data)

logger = logging.getLogger(__name__)

class CustomerRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password], required=True)
    password2 = serializers.CharField(write_only=True, validators=[validate_password])
    address = serializers.CharField(write_only=True)
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password2', 'phone', 
                  'first_name', 'last_name', 'address', 'latitude', 'longitude']
        
    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Passwords don't match"})
        
        has_lat = attrs.get('latitude') is not None
        has_lng = attrs.get('longitude') is not None
        if has_lat != has_lng:
            raise serializers.ValidationError(
                "Both latitude and longitude must be provided together"
            )
        
        return attrs
    
    @transaction.atomic
    def create(self, validated_data):
        address = validated_data.pop('address')
        latitude = validated_data.pop('latitude', None)
        longitude = validated_data.pop('longitude', None)
        validated_data.pop('password2')
        
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            phone=validated_data['phone'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role='customer'
        )
        
        # token = VerificationToken.objects.create(user=user)
        
        # try:
        #     verification_url = f"{settings.FRONTEND_URL}/verify/{token.token}"
        #     send_mail(
        #         'Verify Your PetRide Account',
        #         f'Click to verify: {verification_url}',
        #         settings.EMAIL_HOST_USER,
        #         [user.email],
        #         fail_silently=True,
        #     )
        # except Exception as e:
        #     logger.error(f"Failed to send verification email to {user.email}: {e}")

        from notifications.tasks import send_welcome_email
        send_welcome_email(user.email, user.first_name)

        CustomerProfile.objects.create(
            user=user,
            address=address,
            latitude=latitude,
            longitude=longitude
        )
        
        return user


class DriverRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password], required=True)
    password2 = serializers.CharField(write_only=True, validators=[validate_password])
    license_number = serializers.CharField(write_only=True, required=True)
    vehicle_number = serializers.CharField(write_only=True, required=True)
    vehicle_type = serializers.CharField(write_only=True)
    vehicle_capacity = serializers.DecimalField(max_digits=8, decimal_places=2, write_only=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password2', 'phone', 'first_name', 
                  'last_name', 'license_number', 'vehicle_number', 
                  'vehicle_type', 'vehicle_capacity']
        
    def validate_license_number(self, value):
        if DriverProfile.objects.filter(license_number=value).exists():
            raise serializers.ValidationError("This license number already exists.")
        return value
    def validate_vehicle_number(self, value):
        if DriverProfile.objects.filter(vehicle_number=value).exists():
            raise serializers.ValidationError("This vehicle number already exists.")
        return value
    
    @transaction.atomic
    def create(self, validated_data):
        license_number = validated_data.pop('license_number')
        vehicle_number = validated_data.pop('vehicle_number')
        vehicle_type = validated_data.pop('vehicle_type')
        vehicle_capacity = validated_data.pop('vehicle_capacity')
        validated_data.pop('password2', None)
        
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            phone=validated_data['phone'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role='driver'
        )
        # token = VerificationToken.objects.create(user=user)
        
        # try:
        #     verification_url = f"{settings.FRONTEND_URL}/verify/{token.token}"
        #     send_mail(
        #         'Verify Your PetRide Account',
        #         f'Click to verify: {verification_url}',
        #         settings.EMAIL_HOST_USER,
        #         [user.email],
        #         fail_silently=True,
        #     )
        # except Exception as e:
        #     logger.error(f"Failed to send verification email to {user.email}: {e}")

        from notifications.tasks import send_welcome_email
        send_welcome_email(user.email, user.first_name)
        
        DriverProfile.objects.create(
            user=user,
            license_number=license_number,
            vehicle_number=vehicle_number,
            vehicle_type=vehicle_type,
            vehicle_capacity=vehicle_capacity,
            approval_status='pending'
        )
        
        return user