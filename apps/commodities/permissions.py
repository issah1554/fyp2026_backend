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
            return user.profile.role.code == Profile.Role.ADMIN
        except Profile.DoesNotExist:
            return False
