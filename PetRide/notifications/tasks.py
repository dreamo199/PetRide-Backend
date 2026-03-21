from django.core.mail import send_mail
from django.conf import settings
import threading
import logging

logger = logging.getLogger(__name__)

CANCELLATION_REASON_MAP = {
    'customer_request': 'You cancelled the order',
    'driver_unavailable': 'Driver became unavailable',
    'payment_failed': 'Payment could not be processed',
    'out_of_stock': 'Fuel temporarily out of stock',
    'customer_unreachable': 'Unable to reach you for confirmation',
    'admin_action': 'Administrative action',
    'other': 'Other reasons',
}


def _send_async(func, *args):
    """Run an email function in a background thread."""
    def wrapper():
        try:
            func(*args)
        except Exception as e:
            logger.error(f"Async email failed [{func.__name__}]: {str(e)}", exc_info=True)

    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()


def _do_send(subject, message, recipient):
    """Core send helper."""
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient],
        fail_silently=False,
    )

def _build_order_confirmation(order_id):
    from orders.models import Order
    try:
        order = Order.objects.select_related(
            'customer__user', 'fuel_type'
        ).get(id=order_id)
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for confirmation email")
        return

    if not order.customer.user.email:
        logger.warning(f"No email for customer on order {order_id}")
        return

    customer_name = order.customer.user.get_full_name() or order.customer.user.username

    message = f'''
Hello {customer_name},

Thank you for your order! We've received your fuel delivery request.

ORDER DETAILS
═════════════════════════════════════════
Order Number:     {order.order_number}
Fuel Type:        {order.fuel_type.get_name_display()}
Quantity:         {order.quantity_liters} liters
Delivery Address: {order.delivery_address}

PRICING BREAKDOWN
═════════════════════════════════════════
Fuel Cost:        ₦{order.fuel_price:,.2f}
Delivery Fee:     ₦{order.delivery_fee:,.2f}
Service Charge:   ₦{order.service_charge:,.2f}
─────────────────────────────────────────
TOTAL:            ₦{order.total_price:,.2f}
═════════════════════════════════════════

WHAT'S NEXT?
We'll notify you as soon as a driver accepts your order.

Need help? Contact our support team.

Best regards,
The PetRide Team
    '''.strip()

    _do_send(
        subject=f'Order Confirmation - {order.order_number}',
        message=message,
        recipient=order.customer.user.email,
    )
    logger.info(f"Confirmation email sent for {order.order_number}")


def _build_driver_assignment(order_id):
    from orders.models import Order
    try:
        order = Order.objects.select_related(
            'customer__user', 'driver__user', 'fuel_type'
        ).get(id=order_id)
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for driver assignment email")
        return

    if not order.driver:
        logger.warning(f"Order {order_id} has no driver assigned")
        return

    if not order.customer.user.email:
        logger.warning(f"No email for customer on order {order_id}")
        return

    customer_name = order.customer.user.get_full_name() or order.customer.user.username
    driver_name = order.driver.user.get_full_name() or order.driver.user.first_name

    message = f'''
Hello {customer_name},

Great news! A driver has been assigned to your order.

DRIVER DETAILS
═════════════════════════════════════════
Driver Name:      {driver_name}
Vehicle Type:     {order.driver.vehicle_type}
Vehicle Number:   {order.driver.vehicle_number}

ORDER INFORMATION
═════════════════════════════════════════
Order Number:     {order.order_number}
Fuel Type:        {order.fuel_type.get_name_display()}
Quantity:         {order.quantity_liters} liters

Your driver will contact you shortly to confirm delivery details.
Track your order status in real-time through our app.

Best regards,
The PetRide Team
    '''.strip()

    _do_send(
        subject=f'Driver Assigned - {order.order_number}',
        message=message,
        recipient=order.customer.user.email,
    )
    logger.info(f"Driver assignment email sent for {order.order_number}")


def _build_order_completed(order_id):
    from orders.models import Order
    try:
        order = Order.objects.select_related(
            'customer__user', 'driver__user', 'fuel_type'
        ).get(id=order_id)
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for completion email")
        return

    if not order.customer.user.email:
        logger.warning(f"No email for customer on order {order_id}")
        return

    customer_name = order.customer.user.get_full_name() or order.customer.user.username

    message = f'''
Hello {customer_name},

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
        message += f'''Driver:           {driver_name}
Vehicle:          {order.driver.vehicle_type} ({order.driver.vehicle_number})
'''

    message += '''
RATE YOUR EXPERIENCE
═════════════════════════════════════════
Log in to rate this order. Your feedback helps us improve.

Thank you for choosing PetRide!

Best regards,
The PetRide Team
    '''.strip()

    _do_send(
        subject=f'Order Completed - {order.order_number}',
        message=message,
        recipient=order.customer.user.email,
    )
    logger.info(f"Completion email sent for {order.order_number}")


def _build_order_cancellation(order_id):
    from orders.models import Order
    try:
        order = Order.objects.select_related(
            'customer__user', 'fuel_type'
        ).get(id=order_id)
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for cancellation email")
        return

    if not order.customer.user.email:
        logger.warning(f"No email for customer on order {order_id}")
        return

    customer_name = order.customer.user.get_full_name() or order.customer.user.username
    reason_text = CANCELLATION_REASON_MAP.get(
        order.cancellation_reason, 'Order was cancelled'
    )

    message = f'''
Hello {customer_name},

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
        message += f'\nAdditional Information:\n{order.cancellation_notes}\n'

    if order.cancellation_reason != 'customer_request':
        message += '''
REFUND INFORMATION
═════════════════════════════════════════
If you were charged, a full refund will be processed within 3-5 business days.
'''

    message += '''
We apologize for any inconvenience. You can place a new order anytime.

Best regards,
The PetRide Team
    '''.strip()

    _do_send(
        subject=f'Order Cancelled - {order.order_number}',
        message=message,
        recipient=order.customer.user.email,
    )
    logger.info(f"Cancellation email sent for {order.order_number}")


def _build_driver_order_notification(order_id, driver_id):
    from orders.models import Order
    from users.models import DriverProfile
    try:
        order = Order.objects.select_related('customer__user', 'fuel_type').get(id=order_id)
        driver = DriverProfile.objects.select_related('user').get(id=driver_id)
    except (Order.DoesNotExist, DriverProfile.DoesNotExist) as e:
        logger.error(f"Order or driver not found: {str(e)}")
        return

    if not driver.user.email:
        logger.warning(f"No email for driver {driver_id}")
        return

    driver_name = driver.user.get_full_name() or driver.user.first_name
    customer_name = order.customer.user.get_full_name() or order.customer.user.username

    message = f'''
Hello {driver_name},

You have been assigned a new delivery order!

ORDER DETAILS
═════════════════════════════════════════
Order Number:     {order.order_number}
Fuel Type:        {order.fuel_type.get_name_display()}
Quantity:         {order.quantity_liters} liters

CUSTOMER INFORMATION
═════════════════════════════════════════
Customer:         {customer_name}
Phone:            {order.customer.user.phone}
Delivery Address: {order.delivery_address}
Distance:         {order.distance_km} km
{f"Customer Notes:   {order.notes}" if order.notes else ""}

Please contact the customer to confirm delivery details.
Update the order status as you progress.

Drive safely!

Best regards,
The PetRide Team
    '''.strip()

    _do_send(
        subject=f'New Delivery Assignment - {order.order_number}',
        message=message,
        recipient=driver.user.email,
    )
    logger.info(f"Driver notification sent for {order.order_number}")

def send_order_confirmation_email(order_id):
    _send_async(_build_order_confirmation, order_id)

def send_driver_assignment_notification(order_id):
    _send_async(_build_driver_assignment, order_id)

def send_order_completed_notification(order_id):
    _send_async(_build_order_completed, order_id)

def send_order_cancellation_email(order_id):
    _send_async(_build_order_cancellation, order_id)

def send_driver_order_notification(order_id, driver_id):
    _send_async(_build_driver_order_notification, order_id, driver_id)