from rest_framework.permissions import BasePermission

from apps.auth.models import Profile


class IsUserAdmin(BasePermission):
    message = "You do not have permission to manage users."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True
        try:
            return user.profile.role.code == Profile.Role.ADMIN
        except Profile.DoesNotExist:
            return False
