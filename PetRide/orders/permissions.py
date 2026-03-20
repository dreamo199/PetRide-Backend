from rest_framework import permissions


class IsOrderCustomer(permissions.BasePermission):
    message = "You can only access your own orders."
    
    def has_object_permission(self, request, view, obj):
        # Staff can access all orders
        if request.user.is_staff:
            return True
        
        # Customer can only access their own orders
        return obj.customer.user == request.user


class IsOrderDriver(permissions.BasePermission):
    message = "You can only access orders assigned to you."
    
    def has_object_permission(self, request, view, obj):
        # Staff can access all orders
        if request.user.is_staff:
            return True
        
        # Driver can only access orders assigned to them
        if obj.driver:
            return obj.driver.user == request.user
        
        return False


class CanAcceptOrder(permissions.BasePermission):
    message = "You must be an approved and available driver to accept orders."
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if request.user.role != 'driver':
            return False
        
        try:
            driver = request.user.driver_profile
            return (
                driver.approval_status == 'approved' and 
                driver.is_available
            )
        except:
            return False


class CanCancelOrder(permissions.BasePermission):
    message = "You cannot cancel this order."
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        
        if not obj.can_be_cancelled():
            return False
        
        if request.user.role == 'customer' and obj.customer.user == request.user:
            return obj.status == 'pending'
        
        if request.user.role == 'driver' and obj.driver and obj.driver.user == request.user:
            return obj.status in ['assigned', 'in_transit']
        
        return False


class CanRateOrder(permissions.BasePermission):
    message = "You cannot rate this order."
    
    def has_object_permission(self, request, view, obj):
        if obj.customer.user != request.user:
            return False
        
        return obj.can_be_rated() 


class CanUpdateOrderStatus(permissions.BasePermission):
    message = "You cannot update this order's status."
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        
        if request.user.role == 'customer':
            return obj.customer.user == request.user and obj.status == 'pending'
        
        if request.user.role == 'driver':
            return obj.driver and obj.driver.user == request.user
        
        return False