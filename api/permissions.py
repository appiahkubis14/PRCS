# api/permissions.py

from rest_framework import permissions

class IsCollector(permissions.BasePermission):
    """Allow access only to collectors"""
    
    def has_permission(self, request, view):
        # Check if user is authenticated using the property
        if not request.user:
            return False
        
        # Use the property directly (no need to check if it exists)
        if not request.user.is_authenticated:
            return False
        
        # Check role
        return getattr(request.user, 'role', None) == 'collector'


class IsSupervisor(permissions.BasePermission):
    """Allow access only to supervisors"""
    
    def has_permission(self, request, view):
        if not request.user:
            return False
        
        if not request.user.is_authenticated:
            return False
        
        return getattr(request.user, 'role', None) == 'supervisor'


class IsAdmin(permissions.BasePermission):
    """Allow access only to admins"""
    
    def has_permission(self, request, view):
        if not request.user:
            return False
        
        if not request.user.is_authenticated:
            return False
        
        return getattr(request.user, 'role', None) == 'admin'


class CanAccessCollectorAssignments(permissions.BasePermission):
    """Allow collectors to access their own assignments, admins to access any"""
    
    def has_permission(self, request, view):
        if not request.user:
            return False
        
        if not request.user.is_authenticated:
            return False
        
        role = getattr(request.user, 'role', None)
        return role in ['collector', 'admin', 'supervisor']
    
    def has_object_permission(self, request, view, obj):
        if not request.user:
            return False
        
        if not request.user.is_authenticated:
            return False
        
        # Admin can access any
        if getattr(request.user, 'role', None) == 'admin':
            return True
        
        # Collector can only access their own
        if getattr(request.user, 'role', None) == 'collector':
            # Check if the object has collector attribute or user_id
            if hasattr(obj, 'collector'):
                return obj.collector.id == request.user.id
            elif hasattr(obj, 'user_id'):
                return obj.user_id == request.user.id
            elif hasattr(obj, 'id') and hasattr(request.user, 'id'):
                return obj.id == request.user.id
        
        return False