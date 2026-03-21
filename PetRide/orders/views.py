from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
from django.utils import timezone
import logging
from django.shortcuts import get_object_or_404
import bleach
from django.db.models import Avg, Q
from .permissions import IsOrderDriver, CanAcceptOrder, CanRateOrder, CanUpdateOrderStatus
from .models import FuelType, Order, DriverRejection, OrderStatusHistory
from .serializers import FuelTypeSerializer, OrderSerializer, OrderCreateSerializer, OrderRatingSerializer,OrderUpdateSerializer, OrderListSerializer
from users.models import CustomerProfile, DriverProfile
from notifications.tasks import send_order_confirmation_email, send_driver_assignment_notification, send_order_cancellation_email, send_order_completed_notification, send_driver_order_notification
logger = logging.getLogger(__name__)

class FuelTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FuelType.objects.filter(is_available=True).order_by('name')
    serializer_class = FuelTypeSerializer
    permission_classes = [AllowAny]


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch']

    ALLOWED_TRANSITIONS = {
        'pending': ['cancelled', 'assigned'],
        'assigned': ['in_transit', 'cancelled', 'pending'],
        'in_transit': ['completed', 'cancelled'],
        'completed': [],
        'cancelled': [],
    }

    def get_serializer_class(self):
        if self.action == 'list':
            return OrderListSerializer
        if self.action == 'create':
            return OrderCreateSerializer
        if self.action == 'update_status':
            return OrderUpdateSerializer
        if self.action == 'rate_order':
            return OrderRatingSerializer
        return OrderSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == 'customer':
            return Order.objects.filter(customer__user=user).select_related('customer__user', 'driver__user', 'fuel_type').order_by('-created_at')
        if user.role == 'driver':
            return Order.objects.filter(Q(status=['pending', 'assigned', 'in_transit'], driver__user=user) | Q(driver__user=user)).select_related('customer__user', 'driver__user', 'fuel_type').order_by('-created_at')
        if user.is_staff:
            return Order.objects.select_related('customer__user', 'driver__user', 'fuel_type')
        return Order.objects.none()

    def perform_create(self, serializer):
        try:
            customer = CustomerProfile.objects.get(user=self.request.user)
        except CustomerProfile.DoesNotExist:
            raise ValidationError("Customer profile not found")
        
        order = serializer.save(customer=customer)

        try:
            send_order_confirmation_email(order.id)
        except Exception as e:
            logger.error(f'Failed to queue confirmation email: {e}')

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsOrderDriver])
    def active_orders(self, request):
        try:
            order = Order.objects.filter(driver__user=request.user, status__in=['assigned', 'in_transit'])
            serializer = OrderListSerializer(order, many=True)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found for this driver'}, status=status.HTTP_404_NOT_FOUND)

        return Response({'Order': serializer.data}, status=status.HTTP_200_OK)


    @transaction.atomic
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, CanAcceptOrder])
    def accept_order(self, request, pk=None):

        try:
            order = Order.objects.select_for_update().get(pk=pk, status='pending', driver__isnull=True)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found or already assigned'}, status=404)

        try:
            driver = DriverProfile.objects.select_for_update().get(user=request.user, is_available=True, approval_status='approved')
        except DriverProfile.DoesNotExist:
            return Response({'error': 'Driver not available'}, status=400)
        
        active_orders = Order.objects.filter(driver=driver, status__in=['assigned', 'in_transit'])
        if active_orders:
            return Response({'error': 'You already have an active order. Complete it before accepting another one!'}, status=status.HTTP_400_BAD_REQUEST)
        
        if DriverRejection.objects.filter(driver=driver, order=order):
            return Response({'error': 'You cannot accept an order you just rejected'}, status=status.HTTP_400_BAD_REQUEST)
        
        if driver.vehicle_capacity < order.quantity_liters:
            return Response({'error': f'This quantity of this order {order.quantity_liters}L is greater than your vehicle capacity {driver.vehicle_capacity}L'})

        old_status = order.status
        order.driver = driver
        order.status = 'assigned'
        order.assigned_at = timezone.now()
        order.save()

        driver.is_available = False
        driver.save()

        OrderStatusHistory.objects.create(
            order = order,
            old_status = old_status,
            new_status = 'assigned',
            changed_by = request.user,
            reason= f'Order accepted by driver {driver.user.get_full_name()} - Vehicle number {driver.vehicle_number}'
        )
        try:
            send_driver_order_notification(order.id, driver.id)
        except Exception as e:
            logger.error(f"Failed to send confirmation email to driver {e}")
        try:
            send_driver_assignment_notification(order.id)
        except Exception as e:
            logger.error(f"Failed to send driver assignment email to user {e}")
        
        logger.info(f"Driver {driver.user.username} accepted order {order.id} at {timezone.now()}")
        return Response({'message': 'order accepted', 'order': OrderSerializer(order).data}, status=status.HTTP_200_OK)

    @transaction.atomic
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, CanUpdateOrderStatus])
    def update_status(self, request, pk=None):
        order = get_object_or_404(Order, pk=pk)

        self.check_object_permissions(request, order)

        serializer = OrderUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        old_status = order.status
        new_status = serializer.validated_data['status']
        reason = serializer.validated_data.get('reason')
        user = request.user

        allowed_transitions = self.ALLOWED_TRANSITIONS.get(old_status, [])

        if not request.user.is_staff and new_status not in allowed_transitions:
            return Response({'error': f'Cannot transition from {old_status} to {new_status}'}, status=400)

        if request.user.role == 'customer':
            if new_status != 'cancelled' or old_status != 'pending':
                raise PermissionDenied('Customers can only cancel pending orders')
        elif request.user.role == 'driver':
            if order.driver.user != request.user:
                raise PermissionDenied('Not your order')
            if new_status not in ['in_transit', 'completed', 'cancelled']:
                raise ValidationError('Invalid status transition for driver')
            
        if new_status == 'completed':
            order.status = 'completed'
            order.completed_at = timezone.now()
            if order.driver:
                order.driver.is_available = True
                order.driver.total_deliveries += 1
                order.driver.save()
            order.save()
            try:
                send_order_completed_notification(order.id)
            except Exception as e:
                logger.error(f"Error sending cancellation email: {e}")
            return Response({'status': 'Order completed'})
        elif new_status == 'cancelled':
            cancellation_reason = serializer.validated_data.get('cancellation_reason')
            if cancellation_reason not in ['customer_request', 'driver', 'driver_unavailable', 'payment', 'admin_action', 'other']:
                return Response({'error': 'Cancellation reason required'}, status=400)

            if cancellation_reason == 'driver':
                order.status = 'pending'
            order.status = 'cancelled'
            order.cancelled_at = timezone.now()
            order.cancellation_reason = cancellation_reason
            order.save()
            
            if order.driver:
                cancellation_reason = serializer.validated_data.get('cancellation_reason')

                DriverRejection.objects.create(order=order, driver=order.driver, reason=cancellation_reason)

                order.driver_rejections_count += 1
                order.driver.is_available = True
                order.driver.save()

                order.driver = None
                order.status = 'pending'
                order.assigned_at = None

                order.save()
                logger.info(f"Order {order.order_number} returned to pool by driver {user.username}")

                try:
                    send_order_cancellation_email(order.id)
                except Exception as e:
                    logger.error(f"Error sending cancellation email: {e}")
                return Response({'status': 'Order returned to pending pool'})
        elif new_status == 'in_transit':
            order.status = 'in_transit'
            order.in_transit_at = timezone.now()
            order.save()
        else:
            order.status = new_status
            order.save()

        OrderStatusHistory.objects.create(
            order=order,
            old_status=old_status,
            new_status=order.status,
            changed_by=request.user,
            reason=reason or f'Status updated by {request.user.get_full_name()}'
        )

        logger.info(
            f"Order {order.order_number} status updated to {order.status} by {user.username} at {timezone.now()}"
        )
        return Response({'status': f'Order status updated to {order.get_status_display()}'})


    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, CanRateOrder])
    def rate_order(self, request, pk=None):
        order = get_object_or_404(Order, pk=pk)
        user = request.user

        if user != order.customer.user:
            return Response({'error': 'Not authorized'}, status=403)

        self.check_object_permissions(request, order)

        serializer = OrderRatingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        customer_rating = serializer.validated_data['customer_rating']
        customer_feedback = serializer.validated_data.get('customer_feedback', '')


        order.customer_rating = customer_rating
        order.customer_feedback = bleach.clean(customer_feedback)
        order.rated_at = timezone.now()
        order.save()

        if order.driver:
            self._update_driver_rating(order.driver)

        logger.info(f"Order {order.order_number} rated {customer_rating} by {user.username} at {timezone.now()}")    
        return Response({'status': 'Rating submitted successfully'})

    def _update_driver_rating(self, driver):
        avg_rating = Order.objects.filter(driver=driver, customer_rating__isnull=False).aggregate(avg=Avg('customer_rating'))['avg']
        if avg_rating is not None:
            driver.rating = round(avg_rating, 2)
            driver.save()
            logger.info(f"Driver {driver.user.username} rating updated to {driver.rating}")

    @action(detail=False, methods=['get'])
    def available_orders(self, request):
        user = request.user

        if user.role != 'driver':
            raise PermissionDenied('Only drivers can view available orders')

        try:
            driver = DriverProfile.objects.get(user=request.user)
        except DriverProfile.DoesNotExist:
            return Response({'error': 'Driver profile does not exist'}, status=status.HTTP_404_NOT_FOUND)
        
        rejected_order_ids = DriverRejection.objects.filter(driver=driver).values_list('order_id', flat=True)

        orders = Order.objects.filter(status='pending', driver__isnull=True).exclude(id__in=rejected_order_ids).select_related('customer__user', 'driver__user', 'fuel_type').order_by('-created_at')

        serializer=OrderListSerializer(orders, many=True)

        return Response(serializer.data)
