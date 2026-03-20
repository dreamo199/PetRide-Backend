from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone

from .models import FuelType, Order, OrderStatusHistory, DriverRejection


@admin.register(FuelType)
class FuelTypeAdmin(admin.ModelAdmin):
    """Admin interface for fuel types"""
    list_display = [
        'name_display', 'price_per_liter', 'is_available', 
        'orders_count', 'created_at'
    ]
    list_filter = ['is_available', 'name', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Fuel Information', {
            'fields': ('name', 'price_per_liter', 'description')
        }),
        ('Availability', {
            'fields': ('is_available',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def name_display(self, obj):
        """Display fuel name with availability indicator"""
        color = 'green' if obj.is_available else 'red'
        icon = '✓' if obj.is_available else '✗'
        return format_html(
            '<span style="color: {};">{}</span> {}',
            color, icon, obj.get_name_display()
        )
    name_display.short_description = 'Fuel Type'
    name_display.admin_order_field = 'name'
    
    def orders_count(self, obj):
        """Display total number of orders for this fuel type"""
        count = obj.order_set.count()
        return format_html('<strong>{}</strong>', count)
    orders_count.short_description = 'Total Orders'
    
    actions = ['mark_available', 'mark_unavailable']
    
    def mark_available(self, request, queryset):
        """Mark selected fuel types as available"""
        updated = queryset.update(is_available=True)
        self.message_user(request, f'{updated} fuel type(s) marked as available.')
    mark_available.short_description = "Mark as available"
    
    def mark_unavailable(self, request, queryset):
        """Mark selected fuel types as unavailable"""
        updated = queryset.update(is_available=False)
        self.message_user(request, f'{updated} fuel type(s) marked as unavailable.')
    mark_unavailable.short_description = "Mark as unavailable"


class OrderStatusHistoryInline(admin.TabularInline):
    """Inline admin for order status history"""
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ['old_status', 'new_status', 'changed_by', 'reason', 'created_at']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


class DriverRejectionInline(admin.TabularInline):
    """Inline admin for driver rejections"""
    model = DriverRejection
    extra = 0
    readonly_fields = ['driver', 'reason', 'rejected_at']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Enhanced admin interface for orders"""
    list_display = [
        'order_number', 'customer_link', 'driver_link', 'fuel_type_display',
        'quantity_liters', 'total_price', 'status_badge', 'rating_display',
        'created_at'
    ]
    list_filter = [
        'status', 'fuel_type', 'created_at', 'completed_at',
        'customer_rating', 'cancellation_reason'
    ]
    search_fields = [
        'order_number', 'customer__user__username', 'customer__user__email',
        'driver__user__username', 'delivery_address'
    ]
    readonly_fields = [
        'order_number', 'customer', 'fuel_price',
        'delivery_fee', 'service_charge', 'total_price', 'distance_km',
        'assigned_at', 'in_transit_at', 'completed_at', 'cancelled_at',
        'created_at', 'updated_at', 'rated_at', 'driver_rejections_count',
        'get_map_link', 'get_pricing_breakdown'
    ]
    date_hierarchy = 'created_at'
    inlines = [OrderStatusHistoryInline, DriverRejectionInline]
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'customer', 'driver', 'status')
        }),
        ('Fuel Details', {
            'fields': (
                'fuel_type', 'quantity_liters',
                'fuel_price', 'get_pricing_breakdown'
            )
        }),
        ('Pricing', {
            'fields': ('delivery_fee', 'service_charge', 'total_price'),
            'classes': ('collapse',)
        }),
        ('Delivery Location', {
            'fields': (
                'delivery_address', 'delivery_latitude', 'delivery_longitude',
                'distance_km', 'get_map_link'
            )
        }),
        ('Scheduling & Status', {
            'fields': (
                'scheduled_time', 'assigned_at', 'in_transit_at',
                'completed_at', 'cancelled_at'
            ),
            'classes': ('collapse',)
        }),
        ('Cancellation', {
            'fields': ('cancellation_reason', 'cancellation_notes'),
            'classes': ('collapse',)
        }),
        ('Customer Feedback', {
            'fields': ('customer_rating', 'customer_feedback', 'rated_at'),
            'classes': ('collapse',)
        }),
        ('Additional Info', {
            'fields': ('notes', 'driver_rejections_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def customer_link(self, obj):
        """Create clickable link to customer"""
        url = reverse('admin:users_customerprofile_change', args=[obj.customer.id])
        return format_html('<a href="{}">{}</a>', url, obj.customer.user.get_full_name())
    customer_link.short_description = 'Customer'
    
    def driver_link(self, obj):
        """Create clickable link to driver"""
        if obj.driver:
            url = reverse('admin:users_driverprofile_change', args=[obj.driver.id])
            return format_html('<a href="{}">{}</a>', url, obj.driver.user.get_full_name())
        return format_html('<em style="color: gray;">Not assigned</em>')
    driver_link.short_description = 'Driver'
    
    def fuel_type_display(self, obj):
        """Display fuel type"""
        return obj.fuel_type.get_name_display()
    fuel_type_display.short_description = 'Fuel'
    fuel_type_display.admin_order_field = 'fuel_type__name'
    
    def status_badge(self, obj):
        """Display status with color coding"""
        colors = {
            'pending': 'orange',
            'assigned': 'blue',
            'in_transit': 'purple',
            'completed': 'green',
            'cancelled': 'red'
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def rating_display(self, obj):
        """Display rating with stars"""
        if obj.customer_rating:
            stars = '⭐' * obj.customer_rating
            return format_html('{} ({})', stars, obj.customer_rating)
        return format_html('<em style="color: gray;">Not rated</em>')
    rating_display.short_description = 'Rating'
    rating_display.admin_order_field = 'customer_rating'
    
    def get_map_link(self, obj):
        """Generate Google Maps link"""
        url = f"https://www.google.com/maps?q={obj.delivery_latitude},{obj.delivery_longitude}"
        return format_html(
            '<a href="{}" target="_blank">View on Google Maps</a>',
            url
        )
    get_map_link.short_description = 'Delivery Location Map'
    
    def get_pricing_breakdown(self, obj):
        """Display pricing breakdown"""
        return format_html(
            '<strong>Fuel:</strong> ₦{}<br>'
            '<strong>Delivery:</strong> ₦{}<br>'
            '<strong>Service Charge:</strong> ₦{}<br>'
            '<strong style="color: green;">Total:</strong> ₦{}',
            obj.fuel_price, obj.delivery_fee, obj.service_charge, obj.total_price
        )
    get_pricing_breakdown.short_description = 'Pricing Breakdown'
    
    actions = ['mark_as_completed', 'cancel_orders', 'export_orders']
    
    def mark_as_completed(self, request, queryset):
        """Mark selected orders as completed"""
        updated = 0
        for order in queryset:
            if order.status in ['assigned', 'in_transit']:
                order.status = 'completed'
                order.completed_at = timezone.now()
                if order.driver:
                    order.driver.is_available = True
                    order.driver.total_deliveries += 1
                    order.driver.save()
                order.save()
                
                OrderStatusHistory.objects.create(
                    order=order,
                    old_status=order.status,
                    new_status='completed',
                    changed_by=request.user,
                    reason='Marked as completed by admin'
                )
                updated += 1
        
        self.message_user(request, f'{updated} order(s) marked as completed.')
    mark_as_completed.short_description = "Mark as completed"
    
    def cancel_orders(self, request, queryset):
        """Cancel selected orders"""
        updated = 0
        for order in queryset:
            if order.status in ['pending', 'assigned', 'in_transit']:
                old_status = order.status
                order.status = 'cancelled'
                order.cancelled_at = timezone.now()
                order.cancellation_reason = 'admin_action'
                order.cancellation_notes = 'Cancelled by admin'
                
                if order.driver:
                    order.driver.is_available = True
                    order.driver.save()
                
                order.save()
                
                OrderStatusHistory.objects.create(
                    order=order,
                    old_status=old_status,
                    new_status='cancelled',
                    changed_by=request.user,
                    reason='Cancelled by admin'
                )
                updated += 1
        
        self.message_user(request, f'{updated} order(s) cancelled.')
    cancel_orders.short_description = "Cancel orders"
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related(
            'customer__user', 'driver__user', 'fuel_type'
        )


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    """Admin interface for order status history"""
    list_display = [
        'order_link', 'old_status_display', 'new_status_display',
        'changed_by_link', 'created_at'
    ]
    list_filter = ['old_status', 'new_status', 'created_at']
    search_fields = ['order__order_number', 'changed_by__username', 'reason']
    readonly_fields = ['order', 'old_status', 'new_status', 'changed_by', 'reason', 'created_at']
    date_hierarchy = 'created_at'
    
    def order_link(self, obj):
        """Create clickable link to order"""
        url = reverse('admin:orders_order_change', args=[obj.order.id])
        return format_html('<a href="{}">{}</a>', url, obj.order.order_number)
    order_link.short_description = 'Order'
    
    def old_status_display(self, obj):
        """Display old status"""
        return obj.get_old_status_display() if obj.old_status else '-'
    old_status_display.short_description = 'From'
    
    def new_status_display(self, obj):
        """Display new status"""
        return obj.get_new_status_display()
    new_status_display.short_description = 'To'
    
    def changed_by_link(self, obj):
        if obj.changed_by:
            url = reverse('admin:users_user_change', args=[obj.changed_by.id])
            return format_html('<a href="{}">{}</a>', url, obj.changed_by.username)
        return '-'
    changed_by_link.short_description = 'Changed By'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DriverRejection)
class DriverRejectionAdmin(admin.ModelAdmin):
    list_display = [
        'order_link', 'driver_link', 'reason_short', 'rejected_at'
    ]
    list_filter = ['rejected_at']
    search_fields = ['order__order_number', 'driver__user__username', 'reason']
    readonly_fields = ['order', 'driver', 'reason', 'rejected_at']
    date_hierarchy = 'rejected_at'
    
    def order_link(self, obj):
        url = reverse('admin:orders_order_change', args=[obj.order.id])
        return format_html('<a href="{}">{}</a>', url, obj.order.order_number)
    order_link.short_description = 'Order'
    
    def driver_link(self, obj):
        url = reverse('admin:users_driverprofile_change', args=[obj.driver.id])
        return format_html('<a href="{}">{}</a>', url, obj.driver.user.get_full_name())
    driver_link.short_description = 'Driver'
    
    def reason_short(self, obj):
        return obj.reason[:50] + '...' if len(obj.reason) > 50 else obj.reason
    reason_short.short_description = 'Reason'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False