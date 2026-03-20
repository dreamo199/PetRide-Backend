from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import User, CustomerProfile, DriverProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Enhanced admin interface for User model"""
    
    list_display = [
        'username', 'email', 'role', 'is_verified', 'is_active', 
        'is_deleted', 'created_at'
    ]
    list_filter = ['role', 'is_verified', 'is_active', 'is_deleted', 'created_at']
    search_fields = ['username', 'email', 'phone', 'first_name', 'last_name']
    readonly_fields = ['created_at', 'updated_at', 'deleted_at', 'last_login', 'date_joined']
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {
            'fields': ('first_name', 'last_name', 'email', 'phone')
        }),
        ('Role & Verification', {
            'fields': ('role', 'is_verified')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Deletion', {
            'fields': ('is_deleted', 'deleted_at'),
            'classes': ('collapse',)
        }),
        ('Important dates', {
            'fields': ('last_login', 'date_joined', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'phone', 'role', 'password1', 'password2'),
        }),
    )
    
    actions = ['verify_users', 'soft_delete_users', 'restore_users']
    
    def verify_users(self, request, queryset):
        """Bulk verify users"""
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} user(s) successfully verified.')
    verify_users.short_description = "Mark selected users as verified"
    
    def soft_delete_users(self, request, queryset):
        """Bulk soft delete users"""
        count = 0
        for user in queryset:
            user.soft_delete()
            count += 1
        self.message_user(request, f'{count} user(s) soft deleted.')
    soft_delete_users.short_description = "Soft delete selected users"
    
    def restore_users(self, request, queryset):
        """Restore soft deleted users"""
        updated = queryset.update(is_deleted=False, is_active=True, deleted_at=None)
        self.message_user(request, f'{updated} user(s) restored.')
    restore_users.short_description = "Restore soft deleted users"


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    
    list_display = [
        'user_link', 'get_email', 'get_phone', 'address_short', 
        'has_coordinates', 'preferred_payment_method', 'created_at'
    ]
    list_filter = ['preferred_payment_method', 'created_at']

    search_fields = [
        'user__username', 'user__email', 'user__phone', 
        'user__first_name', 'user__last_name', 'address'
    ]
    readonly_fields = ['user', 'created_at', 'updated_at', 'get_map_link', 'get_email', 'get_phone', 'customer_id']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'get_email', 'get_phone', 'customer_id')
        }),
        ('Address & Location', {
            'fields': ('address', 'latitude', 'longitude', 'get_map_link')
        }),
        ('Preferences', {
            'fields': ('preferred_payment_method',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_link(self, obj):
        """Create clickable link to user"""
        url = reverse('admin:users_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'Username'
    
    def get_email(self, obj):
        """Display user email"""
        return obj.user.email
    get_email.short_description = 'Email'
    get_email.admin_order_field = 'user__email'
    
    def get_phone(self, obj):
        """Display user phone"""
        return obj.user.phone
    get_phone.short_description = 'Phone'
    
    def address_short(self, obj):
        """Display shortened address"""
        return obj.address[:50] + '...' if len(obj.address) > 50 else obj.address
    address_short.short_description = 'Address'
    
    def has_coordinates(self, obj):
        """Display if coordinates are set"""
        if obj.latitude and obj.longitude:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    has_coordinates.short_description = 'GPS'
    
    def get_map_link(self, obj):
        """Generate Google Maps link"""
        if obj.latitude and obj.longitude:
            url = f"https://www.google.com/maps?q={obj.latitude},{obj.longitude}"
            return format_html('<a href="{}" target="_blank">View on Google Maps</a>', url)
        return "No coordinates"
    get_map_link.short_description = 'Map'


@admin.register(DriverProfile)
class DriverProfileAdmin(admin.ModelAdmin):
    
    list_display = [
        'user_link', 'get_email', 'vehicle_number', 'vehicle_type',
        'approval_status_badge', 'is_available_badge', 'rating_display',
        'total_deliveries', 'created_at', 'get_phone'
    ]
    list_filter = [
        'approval_status', 'is_available', 'vehicle_type', 
        'created_at', 'rating'
    ]
    search_fields = [
        'user__username', 'user__email', 'user__phone',
        'license_number', 'vehicle_number', 'vehicle_type'
    ]
    readonly_fields = [
        'user', 'created_at', 'updated_at', 'get_map_link',
        'rating', 'total_deliveries', 'get_phone', 'get_email', 'driver_id'
    ]
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'get_email', 'get_phone', 'driver_id')
        }),
        ('Vehicle Information', {
            'fields': (
                'license_number', 'vehicle_number', 
                'vehicle_type', 'vehicle_capacity'
            )
        }),
        ('Status', {
            'fields': ('approval_status', 'is_available')
        }),
        ('Performance', {
            'fields': ('rating', 'total_deliveries'),
            'classes': ('collapse',)
        }),
        ('Current Location', {
            'fields': ('current_latitude', 'current_longitude', 'get_map_link'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_drivers', 'reject_drivers', 'suspend_drivers']

    def user_link(self, obj):
        url = reverse('admin:users_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'Username'
    
    def get_email(self, obj):
        """Display user email"""
        return obj.user.email
    get_email.short_description = 'Email'
    
    def get_phone(self, obj):
        return obj.user.phone
    get_phone.short_description = 'Phone'
    
    def approval_status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'approved': 'green',
            'rejected': 'red',
            'suspended': 'gray'
        }
        color = colors.get(obj.approval_status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_approval_status_display()
        )
    approval_status_badge.short_description = 'Status'
    approval_status_badge.admin_order_field = 'approval_status'
    
    def is_available_badge(self, obj):
        """Display availability with icon"""
        if obj.is_available:
            return format_html('<span style="color: green; font-size: 18px;">●</span> Available')
        return format_html('<span style="color: red; font-size: 18px;">●</span> Unavailable')
    is_available_badge.short_description = 'Availability'
    is_available_badge.admin_order_field = 'is_available'
    
    def rating_display(self, obj):
        """Display rating with stars"""
        stars = '⭐' * int(obj.rating)
        return format_html('{} ({}/5.00)', stars, obj.rating)
    rating_display.short_description = 'Rating'
    rating_display.admin_order_field = 'rating'
    
    def get_map_link(self, obj):
        """Generate Google Maps link for current location"""
        if obj.current_latitude and obj.current_longitude:
            url = f"https://www.google.com/maps?q={obj.current_latitude},{obj.current_longitude}"
            return format_html('<a href="{}" target="_blank">View Current Location</a>', url)
        return "No location data"
    get_map_link.short_description = 'Current Location Map'
    
    def approve_drivers(self, request, queryset):
        updated = queryset.update(approval_status='approved')
        self.message_user(request, f'{updated} driver(s) approved.')
        
        # Optionally send email notifications
        # from .tasks import send_driver_approval_email_task
        # for driver in queryset:
        #     send_driver_approval_email_task.delay(driver.user.id, approved=True)
    approve_drivers.short_description = "Approve selected drivers"
    
    def reject_drivers(self, request, queryset):
        """Bulk reject drivers"""
        updated = queryset.update(approval_status='rejected', is_available=False)
        self.message_user(request, f'{updated} driver(s) rejected.')
    reject_drivers.short_description = "Reject selected drivers"
    
    def suspend_drivers(self, request, queryset):
        """Bulk suspend drivers"""
        updated = queryset.update(approval_status='suspended', is_available=False)
        self.message_user(request, f'{updated} driver(s) suspended.')
    suspend_drivers.short_description = "Suspend selected drivers"
