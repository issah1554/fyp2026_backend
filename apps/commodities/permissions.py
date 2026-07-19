from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.auth.models import Profile


class IsAdminOrAuthenticatedReadOnly(BasePermission):
    message = "You do not have permission to manage commodities."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        if user.is_staff or user.is_superuser:
            return True
        try:
            return user.profile.role == Profile.Role.ADMIN
        except Profile.DoesNotExist:
            return False


class IsMarketOfficerOrAdmin(BasePermission):
    message = "You do not have permission to manage market records."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True
        try:
            return user.profile.role in {Profile.Role.MARKET_OFFICER, Profile.Role.ADMIN}
        except Profile.DoesNotExist:
            return False
