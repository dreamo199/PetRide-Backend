from rest_framework import serializers
from .models import Order, FuelType, OrderStatusHistory, DriverRejection
from users.serializers import CustomerProfileSerializer, DriverProfileSerializer
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
import bleach
from math import radians, cos, sin, atan2, sqrt
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class FuelTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FuelType
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

class OrderStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_username = serializers.CharField(source='changed_by.username',read_only=True)
    old_status_display = serializers.CharField(source='get_old_status_display', read_only=True)
    new_status_display = serializers.CharField(source='get_new_status_display', read_only=True)
    
    class Meta:
        model = OrderStatusHistory
        fields = [
            'id', 'old_status', 'old_status_display', 
            'new_status', 'new_status_display',
            'changed_by_username', 'reason', 'created_at'
        ]


class OrderSerializer(serializers.ModelSerializer):
    customer = CustomerProfileSerializer(read_only=True)
    driver = DriverProfileSerializer(read_only=True)
    fuel_type = FuelTypeSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    cancellation_reason = serializers.CharField(source='get_cancellation_reason', read_only=True)
    can_be_cancelled = serializers.BooleanField(read_only=True)
    can_be_rated = serializers.BooleanField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Order
        fields = '__all__'
        read_only_fields = ['id', 'order_number', 'customer', 'total_price', 'created_at', 'updated_at', 'driver', 'quantity_liters', 'fuel_price', 'fuel_type',
                            'delivery_fee', 'service_charge', 'distance_km', 'assigned_at', 'in_transit_at', 'completed_at', 'cancelled_at', 'rated_at',
                            'driver_rejections_count']

class OrderCreateSerializer(serializers.ModelSerializer):
    depot_latitude = serializers.DecimalField(max_digits=16, decimal_places=15, write_only=True, required=False)
    depot_longitude = serializers.DecimalField(max_digits=16, decimal_places=15, write_only=True, required=False)
    fuel_type = serializers.PrimaryKeyRelatedField(queryset=FuelType.objects.filter(is_available=True))

    def validate(self, attrs):
        for field in ['delivery_latitude', 'delivery_longitude', 'depot_latitude', 'depot_longitude']:
            value = attrs.get(field)
            if value is not None:
                if field.endswith('latitude') and not (-90 <= value <= 90):
                    raise serializers.ValidationError({field: "Latitude must be between -90 and 90."})
                if field.endswith('longitude') and not (-180 <= value <= 180):
                    raise serializers.ValidationError({field: "Longitude must be between -180 and 180."})
        if 'notes' in attrs:
            attrs['notes'] = bleach.clean(attrs['notes'], tags=[], strip=True)
        return attrs

    def validate_quantity_liters(self, value):
        if value <= Decimal('0.00'):
            raise serializers.ValidationError("Quantity must be greater than zero.")
        if value > Decimal('50.00'):
            raise serializers.ValidationError('Maximum amount of liters is 50!')
        return value
    
    def validate_scheduled_time(self, value):
        if value < timezone.now():
            raise serializers.ValidationError("Scheduled time cannot be in the past!")
        return value
    
    class Meta:
        model = Order
        fields = ['fuel_type', 'quantity_liters', 'delivery_address',
                  'delivery_latitude', 'delivery_longitude', 'scheduled_time', 
                  'notes', 'depot_latitude', 'depot_longitude']
    
    @transaction.atomic
    def create(self, validated_data):

        depot_lat = validated_data.pop('depot_latitude', settings.DEPOT_LAT)
        depot_lng = validated_data.pop('depot_longitude', settings.DEPOT_LNG)

        fuel_type = validated_data['fuel_type']
        quantity_liters = validated_data['quantity_liters']

        fuel_price = fuel_type.price_per_liter * quantity_liters

        delivery_lat = validated_data['delivery_latitude']
        delivery_lng = validated_data['delivery_longitude']

        from geopy.distance import geodesic
        origin = (depot_lat, depot_lng)
        destination = (delivery_lat, delivery_lng)
        try:
            distance = geodesic(origin, destination).kilometers
        except Exception as e:
            logger.warning(f"Geopy distance calculation failed: {e}. Falling back to Haversine formula.")
            r = 6371.0
            lat1, lon1 = radians(float(depot_lat)), radians(float(depot_lng))
            lat2, lon2 = radians(float(delivery_lat)), radians(float(delivery_lng))
            d_lat = lat2 - lat1
            d_lon = lon2 - lon1
            a = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lon / 2) ** 2
            c = 2 * atan2(sqrt(a), sqrt(1 - a))
            distance = r * c
        distance_km = Decimal(str(round(distance, 2)))

        BASE_DELIVERY_FEE = Decimal('800.00')
        BASE_SERVICE_CHARGE = Decimal('0.05')
        PER_KM_RATE = Decimal('100.00')

        if distance_km:
            delivery_fee = BASE_DELIVERY_FEE + (distance_km * PER_KM_RATE)
        else:
            delivery_fee = BASE_DELIVERY_FEE

        if fuel_price > Decimal('29999.00'):
            service_charge = Decimal('0.1') * fuel_price
        else:
            service_charge = fuel_price * BASE_SERVICE_CHARGE

        total_price = fuel_price + delivery_fee + service_charge

        validated_data['fuel_price'] = fuel_price
        validated_data['delivery_fee'] = delivery_fee
        validated_data['service_charge'] = service_charge
        validated_data['total_price'] = total_price
        validated_data['distance_km'] = distance_km

        order = Order(**validated_data)
        order.save()

        OrderStatusHistory.objects.create(
            order=order,
            old_status='',
            new_status='pending',
            changed_by=order.customer.user,
            reason='Order Created'
        )
        return order

class OrderListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.user.get_full_name', read_only=True)
    customer_number = serializers.CharField(source='customer.user.get_phone', read_only=True)
    customer_id = serializers.CharField(source='customer.user.customer_profile.customer_id', read_only=True)
    driver_id = serializers.CharField(source='driver.user.driver_profile.driver_id', read_only=True)
    driver_name = serializers.CharField(source='driver.user.get_full_name', read_only=True)
    fuel_type_name = serializers.CharField(source='fuel_type.get_name_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    class Meta:
        model = Order
        fields = ['id', 'completed_at', 'customer_name', 'customer_number', 'customer_id', 'driver_id', 'driver_name', 'status_display', 'fuel_type_name', 'status', 'order_number', 'quantity_liters', 'total_price',
                  'delivery_address', 'created_at', 'scheduled_time', 'customer_rating', 'distance_km', 'delivery_fee']

    
class OrderUpdateSerializer(serializers.ModelSerializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)
    status = serializers.ChoiceField(choices=Order.STATUS_CHOICES, required=True)
    cancellation_reason = serializers.ChoiceField(choices=Order.CANCELLATION_REASONS, required=False, allow_null=True)
    cancellation_notes = serializers.CharField(max_length=500, required = False)

    def validate_reason(self, value):
        if value:
            return bleach.clean(value, tags=[], strip=True)
        return value

    class Meta:
        model = Order
        fields = ['reason', 'status', 'cancellation_reason', 'cancellation_notes']
    
class OrderRatingSerializer(serializers.ModelSerializer):
    customer_rating = serializers.IntegerField(min_value=1, max_value=5, required=True)
    customer_feedback = serializers.CharField(required=False, allow_blank=True, max_length=1000)

    def validate_customer_feedback(self, value):
        if value:
            return bleach.clean(value, tags=[], strip=True)
        return value

    class Meta:
        model = Order
        fields = ['customer_rating', 'customer_feedback']
    
class DriverRejectionSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(source='driver.user.get_full_name', read_only=True)

    class Meta:
        model = DriverRejection
        fields = ['id', 'driver_name', 'reason', 'rejected_at']
        read_only_fields = ['rejected_at']

