from rest_framework import permissions

class IsCustomer(permissions.BasePermission):
    message = "Access restricted to customers only."
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_active and 
            request.user.is_authenticated and
            request.user.role == 'customer'
        )


class IsDriver(permissions.BasePermission):
    message = "Access restricted to drivers only."
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_active and 
            request.user.is_authenticated and
            request.user.role == 'driver'
        )


class IsApprovedDriver(permissions.BasePermission):
    message = "Access restricted to approved drivers only."
    
    def has_permission(self, request, view):
        if not (request.user and request.user.is_active and request.user.is_authenticated):
            return False
        
        if request.user.role != 'driver':
            return False
        
        try:
            driver_profile = request.user.driver_profile
            return driver_profile.approval_status == 'approved'
        except:
            return False


class IsVerifiedUser(permissions.BasePermission):
    message = "Email verification required."
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_active and 
            request.user.is_verified
        )


class IsOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        return obj == request.user