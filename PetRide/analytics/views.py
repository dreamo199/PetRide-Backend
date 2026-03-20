from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum, Count, Avg
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import logging
from orders.models import Order
from users.permissions import IsCustomer, IsDriver
from users.models import CustomerProfile, DriverProfile
from django.core.cache import cache

logger = logging.getLogger(__name__)

def get_date_range(days=30):
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    return start_date, end_date

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsCustomer])
def customer_analytics(request):
    try:
        customer = CustomerProfile.objects.get(user=request.user)
    except CustomerProfile.DoesNotExist:
        logger.error(f"Customer profile does not exist")
        return Response({'error': 'Customer not found'}, status=status.HTTP_404_NOT_FOUND)

    cache_key = f'customer_analytics_{customer.id}'
    cached_data = cache.get(cache_key)

    if cached_data:
        logger.debug(f"Found cached data for customer {customer.user.username}")
        return Response(cached_data)

    orders = Order.objects.filter(customer=customer)
    completed_orders = orders.filter(status='completed')

    total_orders = orders.count()
    completed_count = completed_orders.count()
    cancelled_count = orders.filter(status='cancelled').count()
    pending_count = orders.filter(status='pending').count()

    total_spent = completed_orders.aggregate(Sum('total_price'))['total_price__sum'] or Decimal('0.00')
    total_liters = completed_orders.aggregate(Sum('quantity_liters'))['quantity_liters__sum'] or Decimal('0.00')
    average_spent = completed_orders.aggregate(avg=Avg('total_price'))['avg'] or Decimal('0.00')
    result_fuel = completed_orders.values('fuel_type__name').annotate(usage_count=Count('fuel_type')).order_by('-usage_count').first()
    favourite_fuel = result_fuel['fuel_type__name'] if result_fuel else None

    week_ago = timezone.now() - timedelta(days=7)
    recent_orders = orders.filter(created_at__gte=week_ago).count()
    recent_spent = completed_orders.filter(created_at__gte=week_ago).aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')

    six_month_ago = timezone.now() - timedelta(days=180)
    monthly_data = completed_orders.filter(created_at__gte=six_month_ago).annotate(month=TruncMonth('created_at')).values('month').annotate(orders=Count('id'), spent=Sum('total_price'), liters=Sum('quantity_liters'))

    analytic_data = {
        'overview': {
            'total_orders': total_orders,
            'completed_order': completed_count,
            'cancelled_orders': cancelled_count,
            'pending_orders': pending_count
        },
        'financial': {
            'total_spent': float(total_spent),
            'currency': '₦',
            'average_spent': float(average_spent)
        },
        'fuel': {
            'total_liters_ordered': total_liters,
            'favourite_fuel': favourite_fuel,
        },
        'recent_activity': {
            'orders_last_7_days': recent_orders,
            'spent_last_7_days': float(recent_spent)
        },
        'monthly_breakdown': [
            {
                'month': item['month'].isoformat(),
                'orders': item['orders'],
                'spent': float(item['spent'] or 0),
                'liters': float(item['liters'] or 0),
            }
            for item in monthly_data
        ],
        'ratings': {
            'total_ratings': completed_orders.filter(customer_rating__isnull=False).count(),
        }
    }

    cache.set(cache_key, analytic_data, 300)

    logger.info(f"Generated analytics for customer: {customer.user.username}")
    return Response(analytic_data)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsDriver])
def driver_analytics(request):
    try:
        driver = DriverProfile.objects.get(user=request.user)
    except DriverProfile.DoesNotExist:
        return Response({'error': 'Driver Profile Not Found'}, status=status.HTTP_404_NOT_FOUND)

    cache_key = f'driver_analytics_{driver.id}'
    cached_data = cache.get(cache_key)

    if cached_data:
        logger.info(f"Generated analytics for driver: {driver.user.username}")
        return Response(cached_data)

    orders = Order.objects.filter(driver=driver)
    completed_orders = orders.filter(status='completed')

    total_deliveries = completed_orders.count()
    active_deliveries = orders.filter(status__in=['assigned', 'in_transit']).count()
    cancelled_by_driver = orders.filter(status='cancelled', cancellation_reason='driver_unavailable').count()

    total_distance = completed_orders.aggregate(total=Sum('distance_km'))['total'] or Decimal('0.00')
    total_liter_delivered = completed_orders.aggregate(total=Sum('quantity_liters'))['total'] or Decimal('0.00')

    total_earnings = completed_orders.aggregate(total=Sum('delivery_fee'))['total'] or Decimal('0.00')
    avg_delivery_fee = completed_orders.aggregate(avg=Avg('delivery_fee'))['avg'] or Decimal('0.00')

    total_ratings = completed_orders.filter(customer_rating__isnull=False).count()

    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_deliveries = completed_orders.filter(created_at__gte=thirty_days_ago).count()

    recent_earnings = completed_orders.filter(completed_at__gte=thirty_days_ago).aggregate(total=Sum('delivery_fee'))['total'] or Decimal('0.00')
    recent_distance = completed_orders.filter(completed_at__gte=thirty_days_ago).aggregate(total=Sum('distance_km'))['total'] or Decimal('0.00')

    eight_weeks_ago = timezone.now() - timedelta(weeks=8)
    weekly_data = completed_orders.filter(completed_at__gte=eight_weeks_ago).annotate(week=TruncWeek('completed_at')
    ).values('week').annotate(deliveries=Count('id'),earnings=Sum('delivery_fee'),distance=Sum('distance_km')).order_by('week')

    analytics_data = {
        'overview': {
            'total_deliveries': total_deliveries,
            'active_deliveries': active_deliveries,
            'cancelled_deliveries': cancelled_by_driver
        },
        'performance': {
            'total_distance_km': total_distance,
            'total_liters_delivered': total_liter_delivered,
        },
        'earnings': {
            'total_earnings': float(total_earnings),
            'average_per_delivery': float(avg_delivery_fee),
            'currency': '₦',
        },
        'ratings': {
            'current_rating': float(driver.rating),
            'total_ratings_received': total_ratings
        },
        'recent_performance': {
            'deliveries_last_30_days': recent_deliveries,
            'earnings_last_30_days': float(recent_earnings),
            'distance_last_30_days': float(recent_distance),
        },
        'weekly_breakdown': [
            {
                'week': item['week'].isoformat(),
                'deliveries': item['deliveries'],
                'earnings': float(item['earnings'] or 0),
                'distance': float(item['distance'] or 0),
            }
            for item in weekly_data
        ],
        'status': {
            'is_available': driver.is_available,
            'approval_status': driver.approval_status,
            'vehicle_type': driver.vehicle_type,
            'vehicle_capacity': float(driver.vehicle_capacity),
        }

    }

    # Cache for 5 minutes
    cache.set(cache_key, analytics_data, 300)

    logger.info(f"Generated analytics for driver: {driver.user.username}")
    return Response(analytics_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def business_analytics(request):
    days = int(request.GET.get('days', 30))
    group_by = request.GET.get('group_by', 'day')

    # Validate group_by parameter
    if group_by not in ['day', 'week', 'month']:
        return Response(
            {'error': 'Invalid group_by parameter. Must be: day, week, or month'},
            status=status.HTTP_400_BAD_REQUEST
        )

    cache_key = f'business_analytics_{days}_{group_by}'
    cached_data = cache.get(cache_key)

    if cached_data:
        logger.info("Returning cached business analytics")
        return Response(cached_data)

    start_date, end_date = get_date_range(days)

    orders = Order.objects.filter(created_at__gte=start_date)
    completed_orders = orders.filter(status='completed')

    total_revenue = completed_orders.aggregate(
        total=Sum('total_price')
    )['total'] or Decimal('0.00')

    total_fuel_revenue = completed_orders.aggregate(
        total=Sum('fuel_price')
    )['total'] or Decimal('0.00')

    total_delivery_fees = completed_orders.aggregate(
        total=Sum('delivery_fee')
    )['total'] or Decimal('0.00')

    total_service_charges = completed_orders.aggregate(
        total=Sum('service_charge')
    )['total'] or Decimal('0.00')

    avg_order_value = completed_orders.aggregate(
        avg=Avg('total_price')
    )['avg'] or Decimal('0.00')

    total_orders = orders.count()
    completed_count = completed_orders.count()
    cancelled_count = orders.filter(status='cancelled').count()
    pending_count = orders.filter(status='pending').count()
    in_progress_count = orders.filter(status__in=['assigned', 'in_transit']).count()

    # Completion rate
    completion_rate = (
        (completed_count / total_orders * 100) if total_orders > 0 else 0
    )

    # Cancellation rate
    cancellation_rate = (
        (cancelled_count / total_orders * 100) if total_orders > 0 else 0
    )
    total_customers = CustomerProfile.objects.count()
    active_customers = orders.values('customer').distinct().count()
    new_customers = CustomerProfile.objects.filter(
        created_at__gte=start_date
    ).count()

    # Customer lifetime value
    customer_ltv = completed_orders.values('customer').annotate(
        total_spent=Sum('total_price')
    ).aggregate(avg=Avg('total_spent'))['avg'] or Decimal('0.00')

    # === DRIVER METRICS ===
    total_drivers = DriverProfile.objects.count()
    approved_drivers = DriverProfile.objects.filter(approval_status='approved').count()
    active_drivers = completed_orders.values('driver').distinct().count()
    available_drivers = DriverProfile.objects.filter(is_available=True).count()

    # Top drivers by deliveries
    top_drivers = completed_orders.values(
        'driver__user__first_name',
        'driver__user__last_name'
    ).annotate(
        deliveries=Count('id'),
        earnings=Sum('delivery_fee')
    ).order_by('-deliveries')[:10]

    # === TEMPORAL BREAKDOWN ===
    if group_by == 'day':
        trunc_func = TruncDate
    elif group_by == 'week':
        trunc_func = TruncWeek
    else:  # month
        trunc_func = TruncMonth

    temporal_data = completed_orders.annotate(
        period=trunc_func('created_at')
    ).values('period').annotate(
        orders=Count('id'),
        revenue=Sum('total_price'),
        liters=Sum('quantity_liters'),
        avg_order_value=Avg('total_price')
    ).order_by('period')

    # === GROWTH METRICS ===
    previous_start = start_date - timedelta(days=days)
    previous_orders = Order.objects.filter(
        created_at__gte=previous_start,
        created_at__lt=start_date,
        status='completed'
    )

    previous_revenue = previous_orders.aggregate(
        total=Sum('total_price')
    )['total'] or Decimal('0.00')

    previous_count = previous_orders.count()

    # Growth calculations
    revenue_growth = (
        ((total_revenue - previous_revenue) / previous_revenue * 100)
        if previous_revenue > 0 else 0
    )

    order_growth = (
        ((completed_count - previous_count) / previous_count * 100)
        if previous_count > 0 else 0
    )

    # === CANCELLATION ANALYSIS ===
    cancellation_reasons = orders.filter(
        status='cancelled'
    ).values('cancellation_reason').annotate(
        count=Count('id')
    ).order_by('-count')

    # === DISTANCE AND EFFICIENCY ===
    total_distance = completed_orders.aggregate(
        total=Sum('distance_km')
    )['total'] or Decimal('0.00')

    avg_distance = completed_orders.aggregate(
        avg=Avg('distance_km')
    )['avg'] or Decimal('0.00')

    total_liters = completed_orders.aggregate(
        total=Sum('quantity_liters')
    )['total'] or Decimal('0.00')

    analytics_data = {
        'period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'days': days,
            'group_by': group_by,
        },
        'revenue': {
            'total_revenue': float(total_revenue),
            'fuel_revenue': float(total_fuel_revenue),
            'delivery_fees': float(total_delivery_fees),
            'service_charges': float(total_service_charges),
            'average_order_value': float(avg_order_value),
            'currency': '₦',
        },
        'orders': {
            'total_orders': total_orders,
            'completed_orders': completed_count,
            'cancelled_orders': cancelled_count,
            'pending_orders': pending_count,
            'in_progress_orders': in_progress_count,
            'completion_rate': round(completion_rate, 2),
            'cancellation_rate': round(cancellation_rate, 2),
        },
        'customers': {
            'total_customers': total_customers,
            'active_customers': active_customers,
            'new_customers': new_customers,
            'customer_lifetime_value': float(customer_ltv),
        },
        'drivers': {
            'total_drivers': total_drivers,
            'approved_drivers': approved_drivers,
            'active_drivers': active_drivers,
            'available_drivers': available_drivers,
        },
        'temporal_breakdown': [
            {
                'period': item['period'].isoformat(),
                'orders': item['orders'],
                'revenue': float(item['revenue'] or 0),
                'liters': float(item['liters'] or 0),
                'avg_order_value': float(item['avg_order_value'] or 0),
            }
            for item in temporal_data
        ],
        'growth': {
            'revenue_growth_percentage': round(float(revenue_growth), 2),
            'order_growth_percentage': round(float(order_growth), 2),
            'previous_period_revenue': float(previous_revenue),
            'previous_period_orders': previous_count,
        },
        'top_drivers': [
            {
                'name': f"{item['driver__user__first_name']} {item['driver__user__last_name']}",
                'deliveries': item['deliveries'],
                'earnings': float(item['earnings'] or 0),
            }
            for item in top_drivers
        ],
        'cancellation_analysis': [
            {
                'reason': item['cancellation_reason'],
                'count': item['count'],
            }
            for item in cancellation_reasons
        ],
        'operations': {
            'total_distance_km': float(total_distance),
            'average_distance_km': float(avg_distance),
            'total_liters_delivered': float(total_liters),
        }
    }

    cache.set(cache_key, analytics_data, 600)

    logger.info(f"Generated business analytics for {days} days grouped by {group_by}")
    return Response(analytics_data)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def real_time_dashboard(request):
    # Current orders by status
    pending_orders = Order.objects.filter(
        status='pending',
        driver__isnull=True
    ).count()

    assigned_orders = Order.objects.filter(status='assigned').count()
    in_transit_orders = Order.objects.filter(status='in_transit').count()

    # Available drivers
    available_drivers = DriverProfile.objects.filter(
        is_available=True,
        approval_status='approved'
    ).count()

    # Recent activity (last hour)
    one_hour_ago = timezone.now() - timedelta(hours=1)
    recent_orders = Order.objects.filter(created_at__gte=one_hour_ago).count()
    recent_completions = Order.objects.filter(
        status='completed',
        completed_at__gte=one_hour_ago
    ).count()

    # Today's summary
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_orders = Order.objects.filter(created_at__gte=today_start)
    today_completed = today_orders.filter(status='completed')

    today_revenue = today_completed.aggregate(
        total=Sum('total_price')
    )['total'] or Decimal('0.00')

    dashboard_data = {
        'current_state': {
            'pending_assignment': pending_orders,
            'assigned': assigned_orders,
            'in_transit': in_transit_orders,
            'available_drivers': available_drivers,
        },
        'recent_activity': {
            'orders_last_hour': recent_orders,
            'completions_last_hour': recent_completions,
        },
        'today': {
            'total_orders': today_orders.count(),
            'completed_orders': today_completed.count(),
            'revenue': float(today_revenue),
            'currency': '₦',
        },
        'timestamp': timezone.now().isoformat(),
    }

    logger.info("Generated real-time dashboard metrics")
    return Response(dashboard_data)
