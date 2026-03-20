from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from celery import shared_task
from celery.utils.log import get_task_logger
import logging

logger = get_task_logger(__name__)


class EmailTaskError(Exception):
    pass


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60},
             retry_backoff=True, retry_backoff_max=600, retry_jitter=True)
def send_order_confirmation_email(self, order_id):
    from orders.models import Order

    try:
        order = Order.objects.select_related(
            'customer__user', 'fuel_type', 'driver'
        ).get(id=order_id)
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for confirmation email")
        return f"Order {order_id} not found"

    if not order.customer.user.email:
        logger.warning(f"No email address for customer {order.customer.user.username}")
        return "No email address"

    try:
        subject = f'Order Confirmation - {order.order_number}'

        # Create context for email template
        context = {
            'customer_name': order.customer.user.get_full_name() or order.customer.user.username,
            'order_number': order.order_number,
            'fuel_type': order.fuel_type.get_name_display(),
            'quantity': order.quantity_liters,
            'fuel_price': order.fuel_price,
            'delivery_fee': order.delivery_fee,
            'service_charge': order.service_charge,
            'total_price': order.total_price,
            'delivery_address': order.delivery_address,
            'scheduled_time': order.scheduled_time,
            'currency': '₦',
        }

        # Plain text message (fallback)
        message = f'''
Hello {context['customer_name']},

Thank you for your order! We've received your fuel delivery request.

ORDER DETAILS
═════════════════════════════════════════
Order Number:     {order.order_number}
Fuel Type:        {context['fuel_type']}
Quantity:         {context['quantity']} liters
Delivery Address: {context['delivery_address']}

PRICING BREAKDOWN
═════════════════════════════════════════
Fuel Cost:        ₦{context['fuel_price']:,.2f}
Delivery Fee:     ₦{context['delivery_fee']:,.2f}
Service Charge:   ₦{context['service_charge']:,.2f}
─────────────────────────────────────────
TOTAL:            ₦{context['total_price']:,.2f}
═════════════════════════════════════════

WHAT'S NEXT?
We'll notify you as soon as a driver accepts your order and is on the way.

Need help? Contact our support team.

Thank you for choosing our service!

Best regards,
The PetRide Team
        '''.strip()
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[order.customer.user.email],
            fail_silently=False,
        )

        logger.info(f"Order confirmation email sent for order {order.order_number}")
        return f"Confirmation email sent for order {order.order_number}"

    except Exception as e:
        logger.error(
            f"Failed to send confirmation email for order {order.order_number}: {str(e)}",
            exc_info=True
        )
        raise self.retry(exc=e)


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60},
             retry_backoff=True, retry_backoff_max=600, retry_jitter=True)
def send_driver_assignment_notification(self, order_id):
    from orders.models import Order

    try:
        order = Order.objects.select_related(
            'customer__user', 'driver__user', 'fuel_type'
        ).get(id=order_id)
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for driver assignment notification")
        return f"Order {order_id} not found"

    if not order.driver:
        logger.warning(f"Order {order.order_number} has no driver assigned")
        return "No driver assigned"

    if not order.customer.user.email:
        logger.warning(f"No email address for customer {order.customer.user.username}")
        return "No email address"

    try:
        subject = f'Driver Assigned - Order {order.order_number}'

        driver_name = order.driver.user.get_full_name() or order.driver.user.first_name

        message = f'''
Hello {order.customer.user.get_full_name() or order.customer.user.username},

Great news! A driver has been assigned to your order.

ORDER INFORMATION
═════════════════════════════════════════
Order Number:     {order.order_number}
Status:           Driver Assigned
Fuel Type:        {order.fuel_type.get_name_display()}
Quantity:         {order.quantity_liters} liters

DRIVER DETAILS
═════════════════════════════════════════
Driver Name:      {driver_name}
Vehicle Type:     {order.driver.vehicle_type}
Vehicle Number:   {order.driver.vehicle_number}

Your driver will contact you shortly to confirm delivery details.

Track your order status in real-time through our app.

Thank you for your patience!

Best regards,
The PetRide Team
        '''.strip()

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[order.customer.user.email],
            fail_silently=False,
        )

        logger.info(f"Driver assignment notification sent for order {order.order_number}")
        return f"Driver assignment notification sent for order {order.order_number}"

    except Exception as e:
        logger.error(
            f"Failed to send driver assignment notification for order {order.order_number}: {str(e)}",
            exc_info=True
        )
        raise self.retry(exc=e)


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60},
             retry_backoff=True, retry_backoff_max=600, retry_jitter=True)
def send_order_cancellation_email(self, order_id):
    from orders.models import Order

    CANCELLATION_REASON_MAP = {
        'customer_request': 'You cancelled the order',
        'driver_unavailable': 'Driver became unavailable',
        'payment_failed': 'Payment could not be processed',
        'out_of_stock': 'Fuel temporarily out of stock',
        'customer_unreachable': 'Unable to reach you for confirmation',
        'admin_action': 'Administrative action',
        'other': 'Other reasons',
    }

    try:
        order = Order.objects.select_related(
            'customer__user', 'fuel_type'
        ).get(id=order_id)
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for cancellation email")
        return f"Order {order_id} not found"

    if not order.customer.user.email:
        logger.warning(f"No email address for customer {order.customer.user.username}")
        return "No email address"

    try:
        subject = f'Order Cancelled - {order.order_number}'

        reason_text = CANCELLATION_REASON_MAP.get(
            order.cancellation_reason,
            'Order was cancelled'
        )

        message = f'''
Hello {order.customer.user.get_full_name() or order.customer.user.username},

Your order has been cancelled.

ORDER DETAILS
═════════════════════════════════════════
Order Number:     {order.order_number}
Fuel Type:        {order.fuel_type.get_name_display()}
Quantity:         {order.quantity_liters} liters
Original Total:   ₦{order.total_price:,.2f}

CANCELLATION REASON
═════════════════════════════════════════
{reason_text}
'''

        if order.cancellation_notes:
            message += f'''
Additional Information:
{order.cancellation_notes}
'''

        if order.cancellation_reason != 'customer_request':
            message += '''

REFUND INFORMATION
═════════════════════════════════════════
If you were charged for this order, a full refund will be 
processed within 3-5 business days.
'''

        message += '''

We apologize for any inconvenience. You can place a new order 
anytime through our app.

If you have questions, please contact our support team.

Thank you for your understanding.

Best regards,
The PetRide Team
        '''.strip()

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[order.customer.user.email],
            fail_silently=False,
        )

        logger.info(f"Cancellation email sent for order {order.order_number}")
        return f"Cancellation email sent for order {order.order_number}"

    except Exception as e:
        logger.error(
            f"Failed to send cancellation email for order {order.order_number}: {str(e)}",
            exc_info=True
        )
        raise self.retry(exc=e)


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60},
             retry_backoff=True, retry_backoff_max=600, retry_jitter=True)
def send_order_completed_notification(self, order_id):
    from orders.models import Order

    try:
        order = Order.objects.select_related(
            'customer__user', 'driver__user', 'fuel_type'
        ).get(id=order_id)
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for completion email")
        return f"Order {order_id} not found"

    if not order.customer.user.email:
        logger.warning(f"No email address for customer {order.customer.user.username}")
        return "No email address"

    try:
        subject = f'Order Completed - {order.order_number}'

        message = f'''
Hello {order.customer.user.get_full_name() or order.customer.user.username},

Your fuel delivery has been completed!

ORDER SUMMARY
═════════════════════════════════════════
Order Number:     {order.order_number}
Fuel Type:        {order.fuel_type.get_name_display()}
Quantity:         {order.quantity_liters} liters
Total Paid:       ₦{order.total_price:,.2f}
Delivery Address: {order.delivery_address}
'''

        if order.driver:
            driver_name = order.driver.user.get_full_name() or order.driver.user.first_name
            message += f'''
Driver:           {driver_name}
Vehicle:          {order.driver.vehicle_type} ({order.driver.vehicle_number})
'''

        message += f'''

RATE YOUR EXPERIENCE
═════════════════════════════════════════
How was your delivery experience? Your feedback helps us 
improve our service.

Log in to rate this order and provide feedback.

Thank you for choosing our service!

Best regards,
The PetRide Team
        '''.strip()

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[order.customer.user.email],
            fail_silently=False,
        )

        logger.info(f"Completion email sent for order {order.order_number}")
        return f"Completion email sent for order {order.order_number}"

    except Exception as e:
        logger.error(
            f"Failed to send completion email for order {order.order_number}: {str(e)}",
            exc_info=True
        )
        raise self.retry(exc=e)


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60},
             retry_backoff=True, retry_backoff_max=600, retry_jitter=True)
def send_driver_order_notification(self, order_id, driver_id):
    from orders.models import Order
    from users.models import DriverProfile

    try:
        order = Order.objects.select_related(
            'customer__user', 'fuel_type'
        ).get(id=order_id)
        driver = DriverProfile.objects.select_related('user').get(id=driver_id)
    except (Order.DoesNotExist, DriverProfile.DoesNotExist) as e:
        logger.error(f"Order or driver not found: {str(e)}")
        return "Order or driver not found"

    if not driver.user.email:
        logger.warning(f"No email address for driver {driver.user.username}")
        return "No email address"

    try:
        subject = f'New Delivery Assignment - Order {order.order_number}'

        message = f'''
Hello {driver.user.get_full_name() or driver.user.first_name},

You have been assigned a new delivery order!

ORDER DETAILS
═════════════════════════════════════════
Order Number:     {order.order_number}
Fuel Type:        {order.fuel_type.get_name_display()}
Quantity:         {order.quantity_liters} liters

CUSTOMER INFORMATION
═════════════════════════════════════════
Customer:         {order.customer.user.get_full_name() or order.customer.user.username}
Phone:            {order.customer.user.phone}
Delivery Address: {order.delivery_address}
Distance:         {order.distance_km} km

DELIVERY INSTRUCTIONS
═════════════════════════════════════════
'''

        if order.notes:
            message += f'''
Customer Notes: {order.notes}
'''

        message += '''

Please contact the customer to confirm delivery details.
Update the order status as you progress.

Drive safely!

Best regards,
The PetRide Team
        '''.strip()

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[driver.user.email],
            fail_silently=False,
        )

        logger.info(f"Driver notification sent for order {order.order_number}")
        return f"Driver notification sent for order {order.order_number}"

    except Exception as e:
        logger.error(
            f"Failed to send driver notification for order {order.order_number}: {str(e)}",
            exc_info=True
        )
        raise self.retry(exc=e)