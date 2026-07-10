from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.auth.models import Profile


class IsAdminOrReadOnly(BasePermission):
    message = "You do not have permission to manage administrative areas."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True
        try:
            return user.profile.role == Profile.Role.ADMIN
        except Profile.DoesNotExist:
            return False


class IsSellerOrReadOnly(BasePermission):
    message = "You do not have permission to perform this action on this listing."

    def has_permission(self, request, view):
        # Safe methods (GET, HEAD, OPTIONS) are allowed for all users
        if request.method in SAFE_METHODS:
            return True
            
        user = request.user
        if not user or not user.is_authenticated:
            return False
            
        # Admin / Staff can do anything
        if user.is_staff or user.is_superuser:
            return True
        try:
            if user.profile.role == Profile.Role.ADMIN:
                return True
            # Create action: Only farmers and entrepreneurs (and admin)
            if request.method == "POST":
                return user.profile.role in [Profile.Role.FARMER, Profile.Role.ENTREPRENEUR]
        except Profile.DoesNotExist:
            return False
            
        return True

    def has_object_permission(self, request, view, obj):
        user = request.user
        if request.method in SAFE_METHODS:
            return True
        if user.is_staff or user.is_superuser:
            return True
        try:
            if user.profile.role == Profile.Role.ADMIN:
                return True
        except Profile.DoesNotExist:
            pass
            
        # For update/delete, must be the owner (seller) of the listing
        return obj.user == user
